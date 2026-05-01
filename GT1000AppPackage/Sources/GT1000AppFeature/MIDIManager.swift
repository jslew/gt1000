import Foundation
import CoreMIDI
import Observation

@Observable
@MainActor
public class MIDIManager: NSObject {
    public var client = MIDIClientRef()
    public var outputPort = MIDIPortRef()
    public var inputPort = MIDIPortRef()
    public var isConnected = false
    public var connectedDeviceName: String? = nil
    public private(set) var lastReceivedMessage: [UInt8] = []
    
    public override init() {
        super.init()
        setupMIDI()
    }
    
    private func setupMIDI() {
        var clientRef = MIDIClientRef()
        let clientStatus = MIDIClientCreateWithBlock(
            "GT1000AppClient" as CFString,
            &clientRef,
            Self.makeNotificationHandler(for: self)
        )
        
        guard clientStatus == noErr else { return }
        self.client = clientRef
        
        var outPort = MIDIPortRef()
        MIDIOutputPortCreate(clientRef, "GT1000OutputPort" as CFString, &outPort)
        self.outputPort = outPort
        
        var inPort = MIDIPortRef()
        let inStatus = MIDIInputPortCreateWithBlock(
            clientRef,
            "GT1000InputPort" as CFString,
            &inPort,
            Self.makeReadHandler(for: self)
        )
        if inStatus == noErr {
            self.inputPort = inPort
        }
        
        updateConnectionStatus()
    }
    
    private func handleMIDINotification(_ notification: MIDINotification) {
        updateConnectionStatus()
    }

    private func handleIncomingMessages(_ messages: [[UInt8]]) {
        for message in messages {
            lastReceivedMessage = message
            print("MIDI: Received \(Self.hexString(message))")
        }
    }
    
    public func updateConnectionStatus() {
        let destinationCount = MIDIGetNumberOfDestinations()
        var foundDevice = false
        var foundName: String? = nil

        for i in 0..<destinationCount {
            let destination = MIDIGetDestination(i)
            var name: Unmanaged<CFString>?
            MIDIObjectGetStringProperty(destination, kMIDIPropertyName, &name)
            
            if let deviceName = name?.takeRetainedValue() as String?, 
               deviceName.localizedCaseInsensitiveContains("GT-1000"),
               !deviceName.localizedCaseInsensitiveContains("DAW"),
               !deviceName.localizedCaseInsensitiveContains("CTRL") {
                foundDevice = true
                foundName = deviceName
                connectSource(named: deviceName)
                break
            }
        }
        
        self.isConnected = foundDevice
        self.connectedDeviceName = foundName
    }
    
    private func connectSource(named deviceName: String) {
        let sourceCount = MIDIGetNumberOfSources()
        for i in 0..<sourceCount {
            let source = MIDIGetSource(i)
            var name: Unmanaged<CFString>?
            MIDIObjectGetStringProperty(source, kMIDIPropertyName, &name)
            if let sourceName = name?.takeRetainedValue() as String?, sourceName == deviceName {
                MIDIPortConnectSource(inputPort, source, nil)
            }
        }
    }
    
    public func sendSysEx(_ message: [UInt8]) {
        sendMIDIMessage(message, logLabel: "SysEx")
    }

    public func sendProgramChange(patch: UInt8) {
        sendMIDIMessage([0xC0, patch], logLabel: "Program Change")
    }

    public func sendControlChange(controller: UInt8, value: UInt8, channel: UInt8 = 0) {
        sendMIDIMessage([0xB0 | (channel & 0x0F), controller & 0x7F, value & 0x7F], logLabel: "Control Change")
    }

    public func sendControlChangeOnAllChannels(controller: UInt8, value: UInt8) {
        for channel in UInt8(0)..<UInt8(16) {
            sendControlChange(controller: controller, value: value, channel: channel)
        }
    }

    private func sendMIDIMessage(_ message: [UInt8], logLabel: String) {
        guard client != 0, outputPort != 0, !message.isEmpty else { return }

        let destinationCount = MIDIGetNumberOfDestinations()
        for i in 0..<destinationCount {
            let destination = MIDIGetDestination(i)
            var name: Unmanaged<CFString>?
            MIDIObjectGetStringProperty(destination, kMIDIPropertyName, &name)
            
            if let deviceName = name?.takeRetainedValue() as String?,
               deviceName.localizedCaseInsensitiveContains("GT-1000"),
               !deviceName.localizedCaseInsensitiveContains("DAW"),
               !deviceName.localizedCaseInsensitiveContains("CTRL") {
                
                print("MIDI: Sending \(logLabel) \(Self.hexString(message)) to \(deviceName)")

                let packetListSize = max(1024, message.count + 256)
                var packetList = [UInt8](repeating: 0, count: packetListSize)
                packetList.withUnsafeMutableBytes { packetListBuffer in
                    message.withUnsafeBufferPointer { messageBuffer in
                        guard let packetListBaseAddress = packetListBuffer.baseAddress,
                              let messageBaseAddress = messageBuffer.baseAddress else {
                            return
                        }

                        let packetListPointer = packetListBaseAddress.assumingMemoryBound(to: MIDIPacketList.self)
                        let currentPacket = MIDIPacketListInit(packetListPointer)
                        _ = MIDIPacketListAdd(packetListPointer, packetListSize, currentPacket, 0, message.count, messageBaseAddress)
                        MIDISend(outputPort, destination, packetListPointer)
                    }
                }
            }
        }
    }
    
    public func listAllPorts() {
        let destinationCount = MIDIGetNumberOfDestinations()
        print("--- Available MIDI Destinations (\(destinationCount)) ---")
        for i in 0..<destinationCount {
            let destination = MIDIGetDestination(i)
            var name: Unmanaged<CFString>?
            MIDIObjectGetStringProperty(destination, kMIDIPropertyName, &name)
            if let deviceName = name?.takeRetainedValue() as String? {
                print("Port [\(i)]: \(deviceName)")
            }
        }
    }

    nonisolated private static func makeNotificationHandler(for manager: MIDIManager) -> (UnsafePointer<MIDINotification>) -> Void {
        let reference = MIDIManagerReference(manager)

        return { notification in
            let copiedNotification = notification.pointee

            Task { @MainActor [reference] in
                reference.manager.handleMIDINotification(copiedNotification)
            }
        }
    }

    nonisolated private static func makeReadHandler(for manager: MIDIManager) -> (UnsafePointer<MIDIPacketList>, UnsafeMutableRawPointer?) -> Void {
        let reference = MIDIManagerReference(manager)

        return { packetList, _ in
            let messages = messages(from: packetList)
            guard !messages.isEmpty else { return }

            Task { @MainActor [reference] in
                reference.manager.handleIncomingMessages(messages)
            }
        }
    }

    nonisolated private static func messages(from packetList: UnsafePointer<MIDIPacketList>) -> [[UInt8]] {
        var messages: [[UInt8]] = []
        let packetCount = Int(packetList.pointee.numPackets)
        let packetOffset = MemoryLayout<MIDIPacketList>.offset(of: \.packet) ?? MemoryLayout<UInt32>.size
        var packetPointer = UnsafeRawPointer(packetList)
            .advanced(by: packetOffset)
            .assumingMemoryBound(to: MIDIPacket.self)

        for _ in 0..<packetCount {
            let packet = packetPointer.pointee
            let bytes = withUnsafeBytes(of: packet.data) { dataBuffer in
                Array(dataBuffer.prefix(Int(packet.length)))
            }

            if !bytes.isEmpty {
                messages.append(bytes)
            }

            packetPointer = UnsafePointer(MIDIPacketNext(packetPointer))
        }

        return messages
    }

    nonisolated private static func hexString(_ message: [UInt8]) -> String {
        message.map { String(format: "%02X", $0) }.joined(separator: " ")
    }
}

extension MIDIManager: @unchecked Sendable {}

private final class MIDIManagerReference: @unchecked Sendable {
    let manager: MIDIManager

    init(_ manager: MIDIManager) {
        self.manager = manager
    }
}
