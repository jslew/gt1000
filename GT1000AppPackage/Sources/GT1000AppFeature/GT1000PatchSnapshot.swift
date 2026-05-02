import Foundation

public struct GT1000PatchSnapshot: Sendable, Equatable {
    public var patchName: String?
    public var masterBPM: Double?
    public var chainElements: [ChainElement]

    public init(
        patchName: String? = nil,
        masterBPM: Double? = nil,
        chainElements: [ChainElement] = []
    ) {
        self.patchName = patchName
        self.masterBPM = masterBPM
        self.chainElements = chainElements
    }

    public var isEmpty: Bool {
        patchName == nil && masterBPM == nil && chainElements.isEmpty
    }

    public var summaryLines: [String] {
        var lines: [String] = []

        if let patchName {
            lines.append("Patch: \(patchName)")
        }

        if let masterBPM {
            lines.append(String(format: "Master BPM: %.1f", masterBPM))
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
        public let id: Int
        public let rawValue: UInt8
        public let displayName: String

        public init(id: Int, rawValue: UInt8, displayName: String) {
            self.id = id
            self.rawValue = rawValue
            self.displayName = displayName
        }
    }
}

public struct GT1000PatchSnapshotReport: Codable, Sendable, Equatable {
    public let patchName: String?
    public let masterBPM: Double?
    public let signalChainSummary: String
    public let signalChainElements: [SignalChainElement]

    public init(snapshot: GT1000PatchSnapshot) {
        self.patchName = snapshot.patchName
        self.masterBPM = snapshot.masterBPM
        self.signalChainSummary = snapshot.signalChainSummary
        self.signalChainElements = snapshot.chainElements.map(SignalChainElement.init)
    }

    public struct SignalChainElement: Codable, Sendable, Equatable {
        public let id: Int
        public let rawValue: UInt8
        public let displayName: String

        public init(_ element: GT1000PatchSnapshot.ChainElement) {
            self.id = element.id
            self.rawValue = element.rawValue
            self.displayName = element.displayName
        }
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
        default:
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
}
