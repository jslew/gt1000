import Foundation

public struct GT1000PatchSnapshot: Sendable, Equatable {
    public var patchName: String?
    public var masterBPM: Double?
    public var masterPatchLevel: Int?
    public var masterKey: String?
    public var ampControl1Enabled: Bool?
    public var ampControl2Enabled: Bool?
    public var chainElements: [ChainElement]
    public var blockSummaries: [BlockSummary]
    public var rawSections: [RawSection]

    public init(
        patchName: String? = nil,
        masterBPM: Double? = nil,
        masterPatchLevel: Int? = nil,
        masterKey: String? = nil,
        ampControl1Enabled: Bool? = nil,
        ampControl2Enabled: Bool? = nil,
        chainElements: [ChainElement] = [],
        blockSummaries: [BlockSummary] = [],
        rawSections: [RawSection] = []
    ) {
        self.patchName = patchName
        self.masterBPM = masterBPM
        self.masterPatchLevel = masterPatchLevel
        self.masterKey = masterKey
        self.ampControl1Enabled = ampControl1Enabled
        self.ampControl2Enabled = ampControl2Enabled
        self.chainElements = chainElements
        self.blockSummaries = blockSummaries
        self.rawSections = rawSections
    }

    public var isEmpty: Bool {
        patchName == nil && masterBPM == nil && chainElements.isEmpty && blockSummaries.isEmpty
    }

    public var summaryLines: [String] {
        var lines: [String] = []

        if let patchName {
            lines.append("Patch: \(patchName)")
        }

        if let masterBPM {
            lines.append(String(format: "Master BPM: %.1f", masterBPM))
        }

        if let masterPatchLevel {
            lines.append("Patch Level: \(masterPatchLevel)")
        }

        if chainElements.isEmpty {
            lines.append("Signal chain: not decoded yet")
        } else {
            lines.append("Signal chain: \(chainElements.map(\.displayName).joined(separator: " -> "))")
        }

        return lines
    }

    public var signalChainSummary: String {
        summaryLines.joined(separator: "\n")
    }

    public struct ChainElement: Sendable, Equatable, Identifiable {
        public let id: String
        public let position: Int
        public let address: [UInt8]
        public let rawValue: UInt8
        public let displayName: String
        public let isReserved: Bool
        public let isOutput: Bool

        public init(
            position: Int,
            address: [UInt8],
            rawValue: UInt8,
            displayName: String,
            isReserved: Bool = false,
            isOutput: Bool = false
        ) {
            self.id = "chain-\(position)"
            self.position = position
            self.address = address
            self.rawValue = rawValue
            self.displayName = displayName
            self.isReserved = isReserved
            self.isOutput = isOutput
        }
    }

    public struct BlockSummary: Sendable, Equatable, Identifiable {
        public let id: String
        public let displayName: String
        public let chainElementValue: UInt8
        public let address: [UInt8]
        public let isInSignalChain: Bool
        public let isEnabled: Bool?
        public let typeName: String?
        public let parameters: [ParameterValue]
        public let rawDataHex: String

        public init(
            id: String,
            displayName: String,
            chainElementValue: UInt8,
            address: [UInt8],
            isInSignalChain: Bool,
            isEnabled: Bool?,
            typeName: String?,
            parameters: [ParameterValue],
            rawDataHex: String
        ) {
            self.id = id
            self.displayName = displayName
            self.chainElementValue = chainElementValue
            self.address = address
            self.isInSignalChain = isInSignalChain
            self.isEnabled = isEnabled
            self.typeName = typeName
            self.parameters = parameters
            self.rawDataHex = rawDataHex
        }
    }

    public struct ParameterValue: Sendable, Equatable, Identifiable {
        public let id: String
        public let displayName: String
        public let rawValue: Int
        public let displayValue: String?

        public init(id: String, displayName: String, rawValue: Int, displayValue: String? = nil) {
            self.id = id
            self.displayName = displayName
            self.rawValue = rawValue
            self.displayValue = displayValue
        }
    }

    public struct RawSection: Sendable, Equatable, Identifiable {
        public let id: String
        public let label: String
        public let address: [UInt8]
        public let dataHex: String

        public init(id: String, label: String, address: [UInt8], dataHex: String) {
            self.id = id
            self.label = label
            self.address = address
            self.dataHex = dataHex
        }
    }
}

public struct GT1000PatchSnapshotReport: Codable, Sendable, Equatable {
    public let patchName: String?
    public let masterBPM: Double?
    public let masterPatchLevel: Int?
    public let masterKey: String?
    public let ampControl1Enabled: Bool?
    public let ampControl2Enabled: Bool?
    public let signalChainSummary: String
    public let signalChainElements: [SignalChainElement]
    public let blocks: [Block]
    public let rawSections: [RawSection]

    public init(snapshot: GT1000PatchSnapshot) {
        self.patchName = snapshot.patchName
        self.masterBPM = snapshot.masterBPM
        self.masterPatchLevel = snapshot.masterPatchLevel
        self.masterKey = snapshot.masterKey
        self.ampControl1Enabled = snapshot.ampControl1Enabled
        self.ampControl2Enabled = snapshot.ampControl2Enabled
        self.signalChainSummary = snapshot.signalChainSummary
        self.signalChainElements = snapshot.chainElements.map(SignalChainElement.init)
        self.blocks = snapshot.blockSummaries.map(Block.init)
        self.rawSections = snapshot.rawSections.map(RawSection.init)
    }

    public struct SignalChainElement: Codable, Sendable, Equatable {
        public let id: String
        public let position: Int
        public let address: [String]
        public let rawValue: UInt8
        public let displayName: String
        public let isReserved: Bool
        public let isOutput: Bool

        public init(_ element: GT1000PatchSnapshot.ChainElement) {
            self.id = element.id
            self.position = element.position
            self.address = element.address.map { String(format: "%02X", $0) }
            self.rawValue = element.rawValue
            self.displayName = element.displayName
            self.isReserved = element.isReserved
            self.isOutput = element.isOutput
        }
    }

    public struct Block: Codable, Sendable, Equatable {
        public let id: String
        public let displayName: String
        public let chainElementValue: UInt8
        public let address: [String]
        public let isInSignalChain: Bool
        public let isEnabled: Bool?
        public let typeName: String?
        public let parameters: [Parameter]
        public let rawDataHex: String

        public init(_ block: GT1000PatchSnapshot.BlockSummary) {
            self.id = block.id
            self.displayName = block.displayName
            self.chainElementValue = block.chainElementValue
            self.address = block.address.map { String(format: "%02X", $0) }
            self.isInSignalChain = block.isInSignalChain
            self.isEnabled = block.isEnabled
            self.typeName = block.typeName
            self.parameters = block.parameters.map(Parameter.init)
            self.rawDataHex = block.rawDataHex
        }
    }

    public struct Parameter: Codable, Sendable, Equatable {
        public let id: String
        public let displayName: String
        public let rawValue: Int
        public let displayValue: String?

        public init(_ parameter: GT1000PatchSnapshot.ParameterValue) {
            self.id = parameter.id
            self.displayName = parameter.displayName
            self.rawValue = parameter.rawValue
            self.displayValue = parameter.displayValue
        }
    }

    public struct RawSection: Codable, Sendable, Equatable {
        public let id: String
        public let label: String
        public let address: [String]
        public let dataHex: String

        public init(_ section: GT1000PatchSnapshot.RawSection) {
            self.id = section.id
            self.label = section.label
            self.address = section.address.map { String(format: "%02X", $0) }
            self.dataHex = section.dataHex
        }
    }
}

public struct GT1000PatchOverviewReport: Codable, Sendable, Equatable {
    public let patchName: String?
    public let masterBPM: Double?
    public let masterPatchLevel: Int?
    public let masterKey: String?
    public let ampControl1Enabled: Bool?
    public let ampControl2Enabled: Bool?
    public let signalChainElementCount: Int
    public let detailBlockCount: Int

    public init(snapshot: GT1000PatchSnapshot) {
        self.patchName = snapshot.patchName
        self.masterBPM = snapshot.masterBPM
        self.masterPatchLevel = snapshot.masterPatchLevel
        self.masterKey = snapshot.masterKey
        self.ampControl1Enabled = snapshot.ampControl1Enabled
        self.ampControl2Enabled = snapshot.ampControl2Enabled
        self.signalChainElementCount = snapshot.chainElements.count
        self.detailBlockCount = snapshot.blockSummaries.count
    }

    public var textSummary: String {
        var lines: [String] = []
        if let patchName {
            lines.append("Patch: \(patchName)")
        }
        if let masterBPM {
            lines.append(String(format: "Master BPM: %.1f", masterBPM))
        }
        if let masterPatchLevel {
            lines.append("Patch Level: \(masterPatchLevel)")
        }
        if let masterKey {
            lines.append("Master Key: \(masterKey)")
        }
        if let ampControl1Enabled {
            lines.append("Amp CTL1: \(ampControl1Enabled ? "ON" : "OFF")")
        }
        if let ampControl2Enabled {
            lines.append("Amp CTL2: \(ampControl2Enabled ? "ON" : "OFF")")
        }
        lines.append("Signal Chain Elements: \(signalChainElementCount)")
        lines.append("Detail Blocks: \(detailBlockCount)")
        return lines.joined(separator: "\n")
    }
}

public struct GT1000PatchChainReport: Codable, Sendable, Equatable {
    public let overview: GT1000PatchOverviewReport
    public let signalChainSummary: String
    public let elements: [Element]

    public init(snapshot: GT1000PatchSnapshot) {
        self.overview = GT1000PatchOverviewReport(snapshot: snapshot)
        self.signalChainSummary = snapshot.chainElements.map(\.displayName).joined(separator: " -> ")
        self.elements = snapshot.chainElements.map { element in
            Element(
                element: element,
                detailBlockID: snapshot.blockSummaries.first { $0.chainElementValue == element.rawValue }?.id
            )
        }
    }

    public struct Element: Codable, Sendable, Equatable {
        public let id: String
        public let position: Int
        public let displayName: String
        public let detailBlockID: String?
        public let isReserved: Bool
        public let isOutput: Bool

        public init(element: GT1000PatchSnapshot.ChainElement, detailBlockID: String?) {
            self.id = element.id
            self.position = element.position
            self.displayName = element.displayName
            self.detailBlockID = detailBlockID
            self.isReserved = element.isReserved
            self.isOutput = element.isOutput
        }
    }

    public var textSummary: String {
        var lines = [overview.textSummary, "Signal chain: \(signalChainSummary)"]
        lines.append(contentsOf: elements.map { element in
            let detail = element.detailBlockID.map { " detail=\($0)" } ?? ""
            return "\(element.position). \(element.displayName)\(detail)"
        })
        return lines.joined(separator: "\n")
    }
}

public struct GT1000PatchBlockDetailReport: Codable, Sendable, Equatable {
    public let overview: GT1000PatchOverviewReport
    public let chainPositions: [Int]
    public let block: GT1000PatchSnapshotReport.Block

    public init(snapshot: GT1000PatchSnapshot, block: GT1000PatchSnapshot.BlockSummary) {
        self.overview = GT1000PatchOverviewReport(snapshot: snapshot)
        self.chainPositions = snapshot.chainElements
            .filter { $0.rawValue == block.chainElementValue }
            .map(\.position)
        self.block = GT1000PatchSnapshotReport.Block(block)
    }

    public var textSummary: String {
        var lines = [overview.textSummary]
        lines.append("Block: \(block.displayName) (\(block.id))")
        if !chainPositions.isEmpty {
            lines.append("Chain Positions: \(chainPositions.map(String.init).joined(separator: ", "))")
        }
        if let isEnabled = block.isEnabled {
            lines.append("Enabled: \(isEnabled ? "ON" : "OFF")")
        }
        if let typeName = block.typeName {
            lines.append("Type: \(typeName)")
        }
        lines.append(contentsOf: block.parameters.map { parameter in
            if let displayValue = parameter.displayValue {
                return "\(parameter.displayName): \(displayValue) (\(parameter.rawValue))"
            }
            return "\(parameter.displayName): \(parameter.rawValue)"
        })
        return lines.joined(separator: "\n")
    }
}

public struct GT1000PatchSnapshotDecoder: Sendable {
    public init() {}

    public func applying(
        _ dataSet: GT1000SysEx.DataSetMessage,
        to snapshot: GT1000PatchSnapshot = GT1000PatchSnapshot()
    ) -> GT1000PatchSnapshot {
        var nextSnapshot = snapshot

        switch dataSet.address {
        case GT1000SysEx.Address.temporaryPatchName:
            nextSnapshot.patchName = Self.decodePatchName(dataSet.data)
        case GT1000SysEx.Address.temporaryPatchMasterBPM:
            nextSnapshot.masterBPM = GT1000SysEx.bpm(fromData: dataSet.data)
        case GT1000SysEx.Address.temporaryPatchEffect:
            applyPatchEffect(dataSet.data, to: &nextSnapshot)
        default:
            if let definition = PatchBlockDefinition.definition(address: dataSet.address) {
                applyBlockSummary(definition: definition, data: dataSet.data, to: &nextSnapshot)
            }
            break
        }

        return nextSnapshot
    }

    public func applying(
        message: [UInt8],
        to snapshot: GT1000PatchSnapshot = GT1000PatchSnapshot()
    ) throws -> GT1000PatchSnapshot {
        let dataSet = try GT1000SysEx.parseDataSet(message)
        return applying(dataSet, to: snapshot)
    }

    private static func decodePatchName(_ data: [UInt8]) -> String {
        let characters = data
            .prefix(16)
            .filter { $0 >= 0x20 && $0 <= 0x7E }

        return String(bytes: characters, encoding: .ascii)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }

    private func applyPatchEffect(_ data: [UInt8], to snapshot: inout GT1000PatchSnapshot) {
        snapshot.rawSections.removeAll { $0.id == "patchEffect" }
        snapshot.rawSections.append(.init(
            id: "patchEffect",
            label: "Patch Effect",
            address: GT1000SysEx.Address.temporaryPatchEffect,
            dataHex: Self.hexString(data)
        ))

        snapshot.masterPatchLevel = data[safe: 0x60].map(Int.init)
        if let bpm = GT1000SysEx.bpm(fromData: Array(data[safe: 0x61..<0x65])) {
            snapshot.masterBPM = bpm
        }
        snapshot.masterKey = data[safe: 0x65].flatMap(Self.masterKeyName)
        snapshot.ampControl1Enabled = data[safe: 0x66].map { $0 == 1 }
        snapshot.ampControl2Enabled = data[safe: 0x67].map { $0 == 1 }

        let chainStartOffset = 0x68
        let chainCount = 49
        snapshot.chainElements = (0..<chainCount).compactMap { index in
            guard let rawValue = data[safe: chainStartOffset + index] else { return nil }
            let displayName = Self.chainElementName(rawValue)
            return GT1000PatchSnapshot.ChainElement(
                position: index + 1,
                address: GT1000SysEx.address(GT1000SysEx.Address.temporaryPatchEffect, adding: chainStartOffset + index),
                rawValue: rawValue,
                displayName: displayName,
                isReserved: displayName == "(RESERVED)",
                isOutput: ["SUB OUT L", "SUB OUT R", "MAIN OUT L", "MAIN OUT R"].contains(displayName)
            )
        }

        applyPatchEffectResidentBlocks(data, to: &snapshot)
        refreshBlockChainMembership(in: &snapshot)
    }

    private func applyPatchEffectResidentBlocks(_ data: [UInt8], to snapshot: inout GT1000PatchSnapshot) {
        for definition in Self.patchEffectResidentBlocks {
            let rawData = Array(data[safe: definition.offset..<(definition.offset + definition.size)])
            let parameterValues = definition.parameters.compactMap { parameter -> GT1000PatchSnapshot.ParameterValue? in
                guard let rawValue = rawValue(for: parameter, in: data) else { return nil }
                return .init(
                    id: parameter.id,
                    displayName: parameter.displayName,
                    rawValue: rawValue,
                    displayValue: displayValue(for: parameter, rawValue: rawValue)
                )
            }

            let block = GT1000PatchSnapshot.BlockSummary(
                id: definition.id,
                displayName: definition.displayName,
                chainElementValue: definition.chainElementValue,
                address: GT1000SysEx.address(GT1000SysEx.Address.temporaryPatchEffect, adding: definition.offset),
                isInSignalChain: snapshot.chainElements.contains { $0.rawValue == definition.chainElementValue },
                isEnabled: parameterValues.first { $0.id == "sw" }.map { $0.rawValue == 1 },
                typeName: parameterValues.first { $0.id == "type" }?.displayValue,
                parameters: parameterValues,
                rawDataHex: Self.hexString(rawData)
            )

            snapshot.blockSummaries.removeAll { $0.id == definition.id }
            snapshot.blockSummaries.append(block)
        }

        snapshot.blockSummaries.sort { lhs, rhs in
            if lhs.chainElementValue == rhs.chainElementValue {
                return lhs.id < rhs.id
            }
            return lhs.chainElementValue < rhs.chainElementValue
        }
    }

    private func applyBlockSummary(
        definition: PatchBlockDefinition,
        data: [UInt8],
        to snapshot: inout GT1000PatchSnapshot
    ) {
        let parameterValues = definition.parameters.compactMap { parameter -> GT1000PatchSnapshot.ParameterValue? in
            guard let rawValue = rawValue(for: parameter, in: data) else { return nil }
            return .init(
                id: parameter.id,
                displayName: parameter.displayName,
                rawValue: rawValue,
                displayValue: displayValue(for: parameter, rawValue: rawValue)
            )
        }

        let isEnabled = parameterValues.first { $0.id == "sw" }?.rawValue == 1
        let typeName = parameterValues.first { $0.id == "type" }?.displayValue
        let isInSignalChain = snapshot.chainElements.contains { $0.rawValue == definition.chainElementValue }

        let block = GT1000PatchSnapshot.BlockSummary(
            id: definition.id,
            displayName: definition.displayName,
            chainElementValue: definition.chainElementValue,
            address: definition.address,
            isInSignalChain: isInSignalChain,
            isEnabled: parameterValues.contains(where: { $0.id == "sw" }) ? isEnabled : nil,
            typeName: typeName,
            parameters: parameterValues,
            rawDataHex: Self.hexString(data)
        )

        snapshot.blockSummaries.removeAll { $0.id == definition.id }
        snapshot.blockSummaries.append(block)
        snapshot.blockSummaries.sort { $0.chainElementValue < $1.chainElementValue }
    }

    private func refreshBlockChainMembership(in snapshot: inout GT1000PatchSnapshot) {
        let chainValues = Set(snapshot.chainElements.map(\.rawValue))
        snapshot.blockSummaries = snapshot.blockSummaries.map { block in
            .init(
                id: block.id,
                displayName: block.displayName,
                chainElementValue: block.chainElementValue,
                address: block.address,
                isInSignalChain: chainValues.contains(block.chainElementValue),
                isEnabled: block.isEnabled,
                typeName: block.typeName,
                parameters: block.parameters,
                rawDataHex: block.rawDataHex
            )
        }
    }

    private func rawValue(for parameter: PatchParameterDefinition, in data: [UInt8]) -> Int? {
        switch parameter.kind {
        case .byte, .bool, .type:
            data[safe: parameter.offset].map(Int.init)
        case let .nibbles(byteCount):
            GT1000SysEx.integer(fromNibbles: Array(data[safe: parameter.offset..<(parameter.offset + byteCount)]))
        }
    }

    private func displayValue(for parameter: PatchParameterDefinition, rawValue: Int) -> String? {
        switch parameter.kind {
        case .byte, .nibbles:
            nil
        case .bool:
            rawValue == 0 ? "OFF" : "ON"
        case let .type(values):
            values.indices.contains(rawValue) ? values[rawValue] : nil
        }
    }

    private static func masterKeyName(_ rawValue: UInt8) -> String? {
        let names = ["C(Am)", "Db(Bbm)", "D(Bm)", "Eb(Cm)", "E(C#m)", "F(Dm)", "F#(D#m)", "G(Em)", "Ab(Fm)", "A(F#m)", "Bb(Gm)", "B(G#m)"]
        return names.indices.contains(Int(rawValue)) ? names[Int(rawValue)] : nil
    }

    private static func chainElementName(_ rawValue: UInt8) -> String {
        let names: [UInt8: String] = [
            0: "COMPRESSOR", 1: "DISTORTION 1", 2: "DISTORTION 2", 3: "AIRD PREAMP 1", 4: "AIRD PREAMP 2",
            5: "NOISE SUPPRESSOR 1", 6: "NOISE SUPPRESSOR 2", 7: "FX 1", 8: "FX 2", 9: "FX 3",
            10: "EQUALIZER 1", 11: "EQUALIZER 2", 12: "EQUALIZER 3", 13: "EQUALIZER 4", 14: "CHORUS",
            15: "DELAY 1", 16: "DELAY 2", 17: "DELAY 3", 18: "DELAY 4", 19: "MASTER DELAY",
            20: "(RESERVED)", 21: "REVERB", 22: "FOOT VOLUME", 23: "PEDAL FX", 24: "SEND/RETURN 1",
            25: "SEND/RETURN 2", 26: "LOOPER", 27: "SUB SP.SIMULATOR L", 28: "SUB SP.SIMULATOR R",
            29: "MAIN SP.SIMULATOR L", 30: "MAIN SP.SIMULATOR R", 31: "(RESERVED)", 32: "(RESERVED)",
            33: "(RESERVED)", 34: "(RESERVED)", 35: "DIVIDER 1", 36: "BRANCH SPLIT1", 37: "MIXER 1",
            38: "DIVIDER 2", 39: "BRANCH SPLIT2", 40: "MIXER 2", 41: "DIVIDER 3", 42: "BRANCH SPLIT3",
            43: "MIXER 3", 44: "(RESERVED)", 45: "SUB OUT L", 46: "SUB OUT R", 47: "MAIN OUT L", 48: "MAIN OUT R"
        ]

        return names[rawValue] ?? "UNKNOWN \(rawValue)"
    }

    private static let patchEffectResidentBlocks: [PatchEffectResidentBlockDefinition] = [
        .init(id: "footVolume", displayName: "FOOT VOLUME", chainElementValue: 22, offset: 0x00, size: 13, parameters: [
            .nibbles("volumeMin", "VOLUME MIN", 0x00, byteCount: 4),
            .nibbles("volumeMax", "VOLUME MAX", 0x04, byteCount: 4),
            .nibbles("pedalPosition", "PEDAL POSITION", 0x08, byteCount: 4),
            .byte("curve", "CURVE", 0x0C)
        ]),
        .init(id: "divider1", displayName: "DIVIDER 1", chainElementValue: 35, offset: 0x0D, size: 10, parameters: dividerParameters(offset: 0x0D)),
        .init(id: "branchSplit1", displayName: "BRANCH SPLIT 1", chainElementValue: 36, offset: 0x0D, size: 10, parameters: []),
        .init(id: "mixer1", displayName: "MIXER 1", chainElementValue: 37, offset: 0x17, size: 3, parameters: mixerParameters(offset: 0x17)),
        .init(id: "divider2", displayName: "DIVIDER 2", chainElementValue: 38, offset: 0x1A, size: 10, parameters: dividerParameters(offset: 0x1A)),
        .init(id: "branchSplit2", displayName: "BRANCH SPLIT 2", chainElementValue: 39, offset: 0x1A, size: 10, parameters: []),
        .init(id: "mixer2", displayName: "MIXER 2", chainElementValue: 40, offset: 0x24, size: 3, parameters: mixerParameters(offset: 0x24)),
        .init(id: "divider3", displayName: "DIVIDER 3", chainElementValue: 41, offset: 0x27, size: 10, parameters: dividerParameters(offset: 0x27)),
        .init(id: "branchSplit3", displayName: "BRANCH SPLIT 3", chainElementValue: 42, offset: 0x27, size: 10, parameters: []),
        .init(id: "mixer3", displayName: "MIXER 3", chainElementValue: 43, offset: 0x31, size: 3, parameters: mixerParameters(offset: 0x31)),
        .init(id: "sendReturn1", displayName: "SEND/RETURN 1", chainElementValue: 24, offset: 0x35, size: 7, parameters: sendReturnParameters(offset: 0x35)),
        .init(id: "sendReturn2", displayName: "SEND/RETURN 2", chainElementValue: 25, offset: 0x3C, size: 7, parameters: sendReturnParameters(offset: 0x3C)),
        .init(id: "looper", displayName: "LOOPER", chainElementValue: 26, offset: 0x44, size: 1, parameters: [
            .byte("playLevel", "PLAY LEVEL", 0x44)
        ]),
        .init(id: "subSpeakerSimulatorL", displayName: "SUB SP.SIMULATOR L", chainElementValue: 27, offset: 0x52, size: 7, parameters: speakerSimulatorParameters(stereoLinkOffset: 0x52, offset: 0x53)),
        .init(id: "subSpeakerSimulatorR", displayName: "SUB SP.SIMULATOR R", chainElementValue: 28, offset: 0x59, size: 6, parameters: speakerSimulatorParameters(offset: 0x59)),
        .init(id: "mainSpeakerSimulatorL", displayName: "MAIN SP.SIMULATOR L", chainElementValue: 29, offset: 0x45, size: 7, parameters: speakerSimulatorParameters(stereoLinkOffset: 0x45, offset: 0x46)),
        .init(id: "mainSpeakerSimulatorR", displayName: "MAIN SP.SIMULATOR R", chainElementValue: 30, offset: 0x4C, size: 6, parameters: speakerSimulatorParameters(offset: 0x4C))
    ]

    private static func dividerParameters(offset: Int) -> [PatchParameterDefinition] {
        [
            .byte("mode", "MODE", offset),
            .byte("channelSelect", "CHANNEL SELECT", offset + 1),
            .byte("dynamicSensitivity", "DYNAMIC SENS", offset + 2),
            .byte("dynamicFilter", "DYNAMIC FILTER", offset + 3),
            .byte("frequency", "FREQUENCY", offset + 4),
            .byte("curve", "CURVE", offset + 5),
            .byte("levelA", "LEVEL A", offset + 6),
            .byte("levelB", "LEVEL B", offset + 7),
            .byte("directLevelA", "DIRECT LEVEL A", offset + 8),
            .byte("directLevelB", "DIRECT LEVEL B", offset + 9)
        ]
    }

    private static func mixerParameters(offset: Int) -> [PatchParameterDefinition] {
        [
            .byte("mode", "MODE", offset),
            .byte("balanceA", "BALANCE A", offset + 1),
            .byte("balanceB", "BALANCE B", offset + 2)
        ]
    }

    private static func sendReturnParameters(offset: Int) -> [PatchParameterDefinition] {
        [
            .switch("sw", "SW", offset),
            .byte("mode", "MODE", offset + 1),
            .nibbles("sendLevel", "SEND LEVEL", offset + 2, byteCount: 2),
            .nibbles("returnLevel", "RETURN LEVEL", offset + 4, byteCount: 2),
            .byte("adjust", "ADJUST", offset + 6)
        ]
    }

    private static func speakerSimulatorParameters(stereoLinkOffset: Int? = nil, offset: Int) -> [PatchParameterDefinition] {
        var parameters: [PatchParameterDefinition] = []
        if let stereoLinkOffset {
            parameters.append(.switch("stereoLink", "STEREO LINK", stereoLinkOffset))
        }

        parameters.append(contentsOf: [
            .byte("speakerType", "SP TYPE", offset),
            .byte("micType", "MIC TYPE", offset + 1),
            .byte("micDistance", "MIC DISTANCE", offset + 2),
            .byte("micPosition", "MIC POSITION", offset + 3),
            .byte("micLevel", "MIC LEVEL", offset + 4),
            .byte("directMix", "DIRECT MIX", offset + 5)
        ])

        return parameters
    }

    private static func hexString(_ bytes: [UInt8]) -> String {
        bytes.map { String(format: "%02X", $0) }.joined(separator: " ")
    }
}

private struct PatchEffectResidentBlockDefinition: Sendable, Equatable {
    let id: String
    let displayName: String
    let chainElementValue: UInt8
    let offset: Int
    let size: Int
    let parameters: [PatchParameterDefinition]
}

private extension Array where Element == UInt8 {
    subscript(safe index: Int) -> UInt8? {
        indices.contains(index) ? self[index] : nil
    }

    subscript(safe bounds: Range<Int>) -> ArraySlice<UInt8> {
        let lower = Swift.max(bounds.lowerBound, startIndex)
        let upper = Swift.min(bounds.upperBound, endIndex)
        guard lower <= upper else { return [] }
        return self[lower..<upper]
    }
}
