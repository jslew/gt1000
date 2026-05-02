import CoreMIDI
import Foundation
import GT1000AppFeature

@main
struct GT1000PatchDump {
    static func main() {
        do {
            let options = try Options.parse(CommandLine.arguments)

            if options.showsHelp {
                Swift.print(Options.usage)
                return
            }

            let tool = PatchDumpTool(timeout: options.timeout)
            let snapshot = try tool.readCurrentPatch()
            try print(snapshot, format: options.format, pretty: options.pretty)
        } catch let error as CLIError {
            fputs("error: \(error.description)\n", stderr)
            exit(Int32(error.exitCode))
        } catch {
            fputs("error: \(error)\n", stderr)
            exit(1)
        }
    }

    private static func print(
        _ snapshot: GT1000PatchSnapshot,
        format: Options.OutputFormat,
        pretty: Bool
    ) throws {
        switch format {
        case .text:
            Swift.print(snapshot.signalChainSummary)
        case .json:
            let encoder = JSONEncoder()
            if pretty {
                encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            } else {
                encoder.outputFormatting = [.sortedKeys]
            }

            let data = try encoder.encode(GT1000PatchSnapshotReport(snapshot: snapshot))
            guard let json = String(data: data, encoding: .utf8) else {
                throw CLIError.outputEncodingFailed
            }

            Swift.print(json)
        }
    }
}

private struct Options: Sendable, Equatable {
    enum OutputFormat: String, Sendable {
        case text
        case json
    }

    var timeout: TimeInterval = 5.0
    var format: OutputFormat = .text
    var pretty = false
    var showsHelp = false

    static let usage = """
    Usage: GT1000PatchDump [options]

    Reads the connected GT-1000 temporary patch and prints a decoded snapshot.

    Options:
      --format text|json   Output format. Defaults to text.
      --pretty             Pretty-print JSON output.
      --timeout seconds    Seconds to wait for patch replies. Defaults to 5.
      --help               Show this help.
    """

    static func parse(_ arguments: [String]) throws -> Self {
        var options = Self()
        var index = arguments.index(after: arguments.startIndex)

        while index < arguments.endIndex {
            let argument = arguments[index]

            switch argument {
            case "--help", "-h":
                options.showsHelp = true
                index = arguments.index(after: index)
            case "--pretty":
                options.pretty = true
                index = arguments.index(after: index)
            case "--format":
                let value = try value(after: index, in: arguments, option: argument)
                guard let format = OutputFormat(rawValue: value) else {
                    throw CLIError.invalidOptionValue(argument, value)
                }

                options.format = format
                index = arguments.index(index, offsetBy: 2)
            case "--timeout":
                let value = try value(after: index, in: arguments, option: argument)
                guard let timeout = TimeInterval(value), timeout > 0 else {
                    throw CLIError.invalidOptionValue(argument, value)
                }

                options.timeout = timeout
                index = arguments.index(index, offsetBy: 2)
            default:
                throw CLIError.unknownOption(argument)
            }
        }

        return options
    }

    private static func value(after index: Array<String>.Index, in arguments: [String], option: String) throws -> String {
        let valueIndex = arguments.index(after: index)
        guard arguments.indices.contains(valueIndex) else {
            throw CLIError.missingOptionValue(option)
        }

        return arguments[valueIndex]
    }
}

private enum CLIError: Swift.Error, CustomStringConvertible {
    case unknownOption(String)
    case missingOptionValue(String)
    case invalidOptionValue(String, String)
    case outputEncodingFailed

    var exitCode: Int {
        switch self {
        case .unknownOption, .missingOptionValue, .invalidOptionValue:
            64
        case .outputEncodingFailed:
            1
        }
    }

    var description: String {
        switch self {
        case let .unknownOption(option):
            "unknown option \(option)\n\n\(Options.usage)"
        case let .missingOptionValue(option):
            "missing value for \(option)\n\n\(Options.usage)"
        case let .invalidOptionValue(option, value):
            "invalid value \(value) for \(option)\n\n\(Options.usage)"
        case .outputEncodingFailed:
            "failed to encode output"
        }
    }
}

private final class PatchDumpTool {
    private enum Error: Swift.Error, CustomStringConvertible {
        case coreMIDI(String, OSStatus)
        case missingGT1000Destination
        case missingGT1000Source
        case timedOut(GT1000PatchSnapshot)

        var description: String {
            switch self {
            case let .coreMIDI(operation, status):
                "\(operation) failed with OSStatus \(status)"
            case .missingGT1000Destination:
                "No GT-1000 MIDI destination found"
            case .missingGT1000Source:
                "No GT-1000 MIDI source found"
            case let .timedOut(snapshot):
                "Timed out waiting for GT-1000 patch replies. Partial snapshot:\n\(snapshot.signalChainSummary)"
            }
        }
    }

    private let timeout: TimeInterval
    private let state = PatchDumpState()
    private var client = MIDIClientRef()
    private var outputPort = MIDIPortRef()
    private var inputPort = MIDIPortRef()

    init(timeout: TimeInterval) {
        self.timeout = timeout
    }

    func readCurrentPatch() throws -> GT1000PatchSnapshot {
        try setupMIDI()

        let destination = try findEndpoint(
            count: MIDIGetNumberOfDestinations,
            endpoint: MIDIGetDestination,
            missingError: Error.missingGT1000Destination
        )
        let source = try findEndpoint(
            count: MIDIGetNumberOfSources,
            endpoint: MIDIGetSource,
            missingError: Error.missingGT1000Source
        )

        let connectStatus = MIDIPortConnectSource(inputPort, source, nil)
        guard connectStatus == noErr else {
            throw Error.coreMIDI("MIDIPortConnectSource", connectStatus)
        }

        for request in GT1000SysEx.PatchReadPlan.initialSnapshotReads {
            try send(request.message, to: destination)
            Thread.sleep(forTimeInterval: 0.05)
        }

        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if state.snapshotHasInitialReadFields {
                return state.snapshot
            }

            RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }

        throw Error.timedOut(state.snapshot)
    }

    private func setupMIDI() throws {
        var clientRef = MIDIClientRef()
        let clientStatus = MIDIClientCreateWithBlock("GT1000PatchDumpClient" as CFString, &clientRef) { _ in }
        guard clientStatus == noErr else {
            throw Error.coreMIDI("MIDIClientCreateWithBlock", clientStatus)
        }
        client = clientRef

        var outputPortRef = MIDIPortRef()
        let outputStatus = MIDIOutputPortCreate(clientRef, "GT1000PatchDumpOutput" as CFString, &outputPortRef)
        guard outputStatus == noErr else {
            throw Error.coreMIDI("MIDIOutputPortCreate", outputStatus)
        }
        outputPort = outputPortRef

        let state = state
        var inputPortRef = MIDIPortRef()
        let inputStatus = MIDIInputPortCreateWithBlock(
            clientRef,
            "GT1000PatchDumpInput" as CFString,
            &inputPortRef
        ) { packetList, _ in
            let packets = Self.messages(from: packetList)
            state.handle(packets)
        }
        guard inputStatus == noErr else {
            throw Error.coreMIDI("MIDIInputPortCreateWithBlock", inputStatus)
        }
        inputPort = inputPortRef
    }

    private func findEndpoint(
        count: () -> Int,
        endpoint: (Int) -> MIDIEndpointRef,
        missingError: Error
    ) throws -> MIDIEndpointRef {
        for index in 0..<count() {
            let candidate = endpoint(index)
            guard let name = Self.name(of: candidate),
                  name.localizedCaseInsensitiveContains("GT-1000"),
                  !name.localizedCaseInsensitiveContains("DAW"),
                  !name.localizedCaseInsensitiveContains("CTRL") else {
                continue
            }

            return candidate
        }

        throw missingError
    }

    private func send(_ message: [UInt8], to destination: MIDIEndpointRef) throws {
        let packetListSize = max(1024, message.count + 256)
        var packetList = [UInt8](repeating: 0, count: packetListSize)
        var sendStatus: OSStatus = noErr

        packetList.withUnsafeMutableBytes { packetListBuffer in
            message.withUnsafeBufferPointer { messageBuffer in
                guard let packetListBaseAddress = packetListBuffer.baseAddress,
                      let messageBaseAddress = messageBuffer.baseAddress else {
                    sendStatus = kMIDIInvalidClient
                    return
                }

                let packetListPointer = packetListBaseAddress.assumingMemoryBound(to: MIDIPacketList.self)
                let currentPacket = MIDIPacketListInit(packetListPointer)
                _ = MIDIPacketListAdd(packetListPointer, packetListSize, currentPacket, 0, message.count, messageBaseAddress)
                sendStatus = MIDISend(outputPort, destination, packetListPointer)
            }
        }

        guard sendStatus == noErr else {
            throw Error.coreMIDI("MIDISend", sendStatus)
        }
    }

    private static func name(of endpoint: MIDIEndpointRef) -> String? {
        var name: Unmanaged<CFString>?
        MIDIObjectGetStringProperty(endpoint, kMIDIPropertyName, &name)
        return name?.takeRetainedValue() as String?
    }

    private static func messages(from packetList: UnsafePointer<MIDIPacketList>) -> [[UInt8]] {
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
}

private final class PatchDumpState: @unchecked Sendable {
    private let lock = NSLock()
    private var assembler = MIDISysExMessageAssembler()
    private var decoder = GT1000PatchSnapshotDecoder()
    private var mutableSnapshot = GT1000PatchSnapshot()

    var snapshot: GT1000PatchSnapshot {
        lock.withLock { mutableSnapshot }
    }

    var snapshotHasInitialReadFields: Bool {
        lock.withLock {
            mutableSnapshot.patchName != nil && mutableSnapshot.masterBPM != nil
        }
    }

    func handle(_ packets: [[UInt8]]) {
        lock.withLock {
            for message in assembler.assemble(from: packets) {
                guard let dataSet = try? GT1000SysEx.parseDataSet(message) else {
                    continue
                }

                mutableSnapshot = decoder.applying(dataSet, to: mutableSnapshot)
            }
        }
    }
}
