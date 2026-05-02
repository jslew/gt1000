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

            switch options.command {
            case .listPorts:
                try print(PatchDumpTool.listPorts(), format: options.format, pretty: options.pretty)
            case .readCurrentPatch:
                let tool = PatchDumpTool(timeout: options.timeout)
                let snapshot = try tool.readCurrentPatch()
                try print(snapshot, options: options)
            }
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
        options: Options
    ) throws {
        switch options.view {
        case .overview:
            let report = GT1000PatchOverviewReport(snapshot: snapshot)
            switch options.format {
            case .text:
                Swift.print(report.textSummary)
            case .json:
                try printJSON(report, pretty: options.pretty)
            }
        case .chain:
            let report = GT1000PatchChainReport(snapshot: snapshot)
            switch options.format {
            case .text:
                Swift.print(report.textSummary)
            case .json:
                try printJSON(report, pretty: options.pretty)
            }
        case .block:
            let block = try resolveBlock(in: snapshot, options: options)
            let report = GT1000PatchBlockDetailReport(snapshot: snapshot, block: block)
            switch options.format {
            case .text:
                Swift.print(report.textSummary)
            case .json:
                try printJSON(report, pretty: options.pretty)
            }
        case .full:
            switch options.format {
            case .text:
                Swift.print(snapshot.signalChainSummary)
            case .json:
                try printJSON(GT1000PatchSnapshotReport(snapshot: snapshot), pretty: options.pretty)
            }
        }
    }

    private static func resolveBlock(
        in snapshot: GT1000PatchSnapshot,
        options: Options
    ) throws -> GT1000PatchSnapshot.BlockSummary {
        if let blockID = options.blockID {
            guard let block = snapshot.blockSummaries.first(where: { $0.id == blockID }) else {
                throw CLIError.unknownBlock(blockID, availableBlockIDs: snapshot.blockSummaries.map(\.id))
            }
            return block
        }

        if let position = options.chainPosition {
            guard let element = snapshot.chainElements.first(where: { $0.position == position }) else {
                throw CLIError.unknownChainPosition(position, validRange: snapshot.chainElements.indices.map { $0 + 1 })
            }
            guard let block = snapshot.blockSummaries.first(where: { $0.chainElementValue == element.rawValue }) else {
                throw CLIError.missingDetailBlockForChainPosition(position, element.displayName)
            }
            return block
        }

        throw CLIError.missingBlockSelector
    }

    private static func print(
        _ inventory: MIDIPortInventoryReport,
        format: Options.OutputFormat,
        pretty: Bool
    ) throws {
        switch format {
        case .text:
            Swift.print(inventory.textSummary)
        case .json:
            try printJSON(inventory, pretty: pretty)
        }
    }

    private static func printJSON<T: Encodable>(_ value: T, pretty: Bool) throws {
        let encoder = JSONEncoder()
        if pretty {
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        } else {
            encoder.outputFormatting = [.sortedKeys]
        }

        let data = try encoder.encode(value)
        guard let json = String(data: data, encoding: .utf8) else {
            throw CLIError.outputEncodingFailed
        }

        Swift.print(json)
    }
}

private struct Options: Sendable, Equatable {
    enum Command: Sendable, Equatable {
        case listPorts
        case readCurrentPatch
    }

    enum OutputFormat: String, Sendable {
        case text
        case json
    }

    enum PatchView: String, Sendable {
        case overview
        case chain
        case block
        case full
    }

    var command: Command = .readCurrentPatch
    var timeout: TimeInterval = 5.0
    var format: OutputFormat = .text
    var view: PatchView = .overview
    var blockID: String?
    var chainPosition: Int?
    var pretty = false
    var showsHelp = false

    static let usage = """
    Usage:
      GT1000PatchDump list-ports [options]
      GT1000PatchDump read current-patch [--view overview|chain|block|full] [options]
      GT1000PatchDump [options]

    Agent-facing read-only CLI for connected GT-1000 devices.

    Commands:
      list-ports          List MIDI sources and destinations.
      read current-patch  Read the connected GT-1000 temporary patch. Default.

    Options:
      --view name         Patch view: overview, chain, block, or full. Defaults to overview.
      --block id          Block id for --view block, for example delay1 or preamp1.
      --position number   Signal-chain position for --view block.
      --format text|json  Output format. Defaults to text.
      --pretty            Pretty-print JSON output.
      --timeout seconds   Seconds to wait for patch replies. Defaults to 5.
      --help              Show this help.
    """

    static func parse(_ arguments: [String]) throws -> Self {
        var options = Self()
        var index = arguments.index(after: arguments.startIndex)

        if index < arguments.endIndex {
            switch arguments[index] {
            case "list-ports":
                options.command = .listPorts
                index = arguments.index(after: index)
            case "read":
                let targetIndex = arguments.index(after: index)
                guard arguments.indices.contains(targetIndex) else {
                    throw CLIError.missingCommandTarget("read")
                }
                guard arguments[targetIndex] == "current-patch" else {
                    throw CLIError.unknownCommand("read \(arguments[targetIndex])")
                }
                options.command = .readCurrentPatch
                index = arguments.index(after: targetIndex)
            case "current-patch":
                options.command = .readCurrentPatch
                index = arguments.index(after: index)
            default:
                break
            }
        }

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
            case "--view":
                let value = try value(after: index, in: arguments, option: argument)
                guard let view = PatchView(rawValue: value) else {
                    throw CLIError.invalidOptionValue(argument, value)
                }

                options.view = view
                index = arguments.index(index, offsetBy: 2)
            case "--block":
                options.blockID = try value(after: index, in: arguments, option: argument)
                index = arguments.index(index, offsetBy: 2)
            case "--position":
                let value = try value(after: index, in: arguments, option: argument)
                guard let position = Int(value), position > 0 else {
                    throw CLIError.invalidOptionValue(argument, value)
                }

                options.chainPosition = position
                index = arguments.index(index, offsetBy: 2)
            case "--timeout":
                let value = try value(after: index, in: arguments, option: argument)
                guard let timeout = TimeInterval(value), timeout > 0 else {
                    throw CLIError.invalidOptionValue(argument, value)
                }

                options.timeout = timeout
                index = arguments.index(index, offsetBy: 2)
            default:
                if argument.hasPrefix("-") {
                    throw CLIError.unknownOption(argument)
                } else {
                    throw CLIError.unknownCommand(argument)
                }
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
    case unknownCommand(String)
    case missingCommandTarget(String)
    case unknownOption(String)
    case missingOptionValue(String)
    case invalidOptionValue(String, String)
    case missingBlockSelector
    case unknownBlock(String, availableBlockIDs: [String])
    case unknownChainPosition(Int, validRange: [Int])
    case missingDetailBlockForChainPosition(Int, String)
    case outputEncodingFailed

    var exitCode: Int {
        switch self {
        case .unknownCommand, .missingCommandTarget, .unknownOption, .missingOptionValue, .invalidOptionValue,
             .missingBlockSelector, .unknownBlock, .unknownChainPosition, .missingDetailBlockForChainPosition:
            64
        case .outputEncodingFailed:
            1
        }
    }

    var description: String {
        switch self {
        case let .unknownCommand(command):
            "unknown command \(command)\n\n\(Options.usage)"
        case let .missingCommandTarget(command):
            "missing target for \(command)\n\n\(Options.usage)"
        case let .unknownOption(option):
            "unknown option \(option)\n\n\(Options.usage)"
        case let .missingOptionValue(option):
            "missing value for \(option)\n\n\(Options.usage)"
        case let .invalidOptionValue(option, value):
            "invalid value \(value) for \(option)\n\n\(Options.usage)"
        case .missingBlockSelector:
            "missing block selector for --view block; pass --block id or --position number\n\n\(Options.usage)"
        case let .unknownBlock(blockID, availableBlockIDs):
            "unknown block \(blockID). Available block ids: \(availableBlockIDs.joined(separator: ", "))"
        case let .unknownChainPosition(position, validRange):
            "unknown chain position \(position). Valid positions: \(validRange.map(String.init).joined(separator: ", "))"
        case let .missingDetailBlockForChainPosition(position, displayName):
            "chain position \(position) (\(displayName)) does not have a decoded detail block"
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

    static func listPorts() -> MIDIPortInventoryReport {
        MIDIPortInventoryReport(
            destinations: endpoints(count: MIDIGetNumberOfDestinations, endpoint: MIDIGetDestination),
            sources: endpoints(count: MIDIGetNumberOfSources, endpoint: MIDIGetSource)
        )
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

        let requests = GT1000SysEx.PatchReadPlan.initialSnapshotReads
        state.expectResponses(addresses: requests.map(\.address))

        for request in requests {
            try send(request.message, to: destination)
            Thread.sleep(forTimeInterval: 0.02)
        }

        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if state.hasReceivedExpectedResponses {
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
                  Self.isDefaultGT1000EndpointName(name) else {
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

    private static func endpoints(
        count: () -> Int,
        endpoint: (Int) -> MIDIEndpointRef
    ) -> [MIDIPortInventoryReport.Endpoint] {
        (0..<count()).map { index in
            let name = Self.name(of: endpoint(index)) ?? "Unnamed MIDI Endpoint"
            return MIDIPortInventoryReport.Endpoint(
                index: index,
                name: name,
                isGT1000: name.localizedCaseInsensitiveContains("GT-1000"),
                isDefaultGT1000Endpoint: Self.isDefaultGT1000EndpointName(name)
            )
        }
    }

    private static func isDefaultGT1000EndpointName(_ name: String) -> Bool {
        name.localizedCaseInsensitiveContains("GT-1000")
            && !name.localizedCaseInsensitiveContains("DAW")
            && !name.localizedCaseInsensitiveContains("CTRL")
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

private struct MIDIPortInventoryReport: Codable, Sendable, Equatable {
    let destinations: [Endpoint]
    let sources: [Endpoint]

    var textSummary: String {
        var lines: [String] = []
        lines.append("MIDI Destinations (\(destinations.count))")
        lines.append(contentsOf: destinations.map(\.textSummary))
        lines.append("MIDI Sources (\(sources.count))")
        lines.append(contentsOf: sources.map(\.textSummary))
        return lines.joined(separator: "\n")
    }

    struct Endpoint: Codable, Sendable, Equatable {
        let index: Int
        let name: String
        let isGT1000: Bool
        let isDefaultGT1000Endpoint: Bool

        var textSummary: String {
            let marker = isDefaultGT1000Endpoint ? " default-gt1000" : (isGT1000 ? " gt1000" : "")
            return "[\(index)] \(name)\(marker)"
        }
    }
}

private final class PatchDumpState: @unchecked Sendable {
    private let lock = NSLock()
    private var assembler = MIDISysExMessageAssembler()
    private var decoder = GT1000PatchSnapshotDecoder()
    private var mutableSnapshot = GT1000PatchSnapshot()
    private var expectedAddressKeys = Set<String>()
    private var receivedAddressKeys = Set<String>()

    var snapshot: GT1000PatchSnapshot {
        lock.withLock { mutableSnapshot }
    }

    var hasReceivedExpectedResponses: Bool {
        lock.withLock { expectedAddressKeys.isSubset(of: receivedAddressKeys) }
    }

    func expectResponses(addresses: [[UInt8]]) {
        lock.withLock {
            expectedAddressKeys = Set(addresses.map(Self.key))
            receivedAddressKeys.removeAll()
        }
    }

    func handle(_ packets: [[UInt8]]) {
        lock.withLock {
            for message in assembler.assemble(from: packets) {
                guard let dataSet = try? GT1000SysEx.parseDataSet(message) else {
                    continue
                }

                receivedAddressKeys.insert(Self.key(dataSet.address))
                mutableSnapshot = decoder.applying(dataSet, to: mutableSnapshot)
            }
        }
    }

    private static func key(_ address: [UInt8]) -> String {
        address.map { String(format: "%02X", $0) }.joined(separator: " ")
    }
}
