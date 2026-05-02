import Foundation
import Testing
@testable import GT1000AppFeature

@Suite("GT-1000 Patch Snapshot Report Tests")
struct GT1000PatchSnapshotReportTests {
    @Test("Encode Snapshot Report As Stable JSON")
    func testEncodeSnapshotReport() throws {
        let snapshot = GT1000PatchSnapshot(
            patchName: "MULTIBAND CRUNCH",
            masterBPM: 120,
            chainElements: [
                .init(position: 1, address: [0x10, 0x00, 0x10, 0x68], rawValue: 0x01, displayName: "COMP"),
                .init(position: 2, address: [0x10, 0x00, 0x10, 0x69], rawValue: 0x02, displayName: "OD/DS")
            ]
        )
        let report = GT1000PatchSnapshotReport(snapshot: snapshot)

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let data = try encoder.encode(report)
        let json = try #require(String(data: data, encoding: .utf8))

        #expect(json == #"{"blocks":[],"masterBPM":120,"patchName":"MULTIBAND CRUNCH","rawSections":[],"signalChainElements":[{"address":["10","00","10","68"],"displayName":"COMP","id":"chain-1","isOutput":false,"isReserved":false,"position":1,"rawValue":1},{"address":["10","00","10","69"],"displayName":"OD\/DS","id":"chain-2","isOutput":false,"isReserved":false,"position":2,"rawValue":2}],"signalChainSummary":"Patch: MULTIBAND CRUNCH\nMaster BPM: 120.0\nSignal chain: COMP -> OD\/DS"}"#)
    }
}
