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
                .init(id: 0, rawValue: 0x01, displayName: "COMP"),
                .init(id: 1, rawValue: 0x02, displayName: "OD/DS")
            ]
        )
        let report = GT1000PatchSnapshotReport(snapshot: snapshot)

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let data = try encoder.encode(report)
        let json = try #require(String(data: data, encoding: .utf8))

        #expect(json == #"{"masterBPM":120,"patchName":"MULTIBAND CRUNCH","signalChainElements":[{"displayName":"COMP","id":0,"rawValue":1},{"displayName":"OD\/DS","id":1,"rawValue":2}],"signalChainSummary":"Patch: MULTIBAND CRUNCH\nMaster BPM: 120.0\nSignal chain: COMP -> OD\/DS"}"#)
    }
}
