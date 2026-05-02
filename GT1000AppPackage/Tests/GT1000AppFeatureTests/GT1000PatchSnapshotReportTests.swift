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

    @Test("Encode Progressive Disclosure Reports")
    func testEncodeProgressiveDisclosureReports() throws {
        let snapshot = GT1000PatchSnapshot(
            patchName: "MULTIBAND CRUNCH",
            masterBPM: 120,
            masterPatchLevel: 4,
            masterKey: "C(Am)",
            ampControl1Enabled: false,
            ampControl2Enabled: false,
            chainElements: [
                .init(position: 1, address: [0x10, 0x00, 0x10, 0x68], rawValue: 0x03, displayName: "AIRD PREAMP 1")
            ],
            blockSummaries: [
                .init(
                    id: "preamp1",
                    displayName: "AIRD PREAMP 1",
                    chainElementValue: 0x03,
                    address: [0x10, 0x00, 0x15, 0x00],
                    isInSignalChain: true,
                    isEnabled: true,
                    typeName: "DIAMOND AMP",
                    parameters: [
                        .init(id: "sw", displayName: "SW", rawValue: 1, displayValue: "ON"),
                        .init(id: "gain", displayName: "GAIN", rawValue: 50)
                    ],
                    rawDataHex: "01 0D 32"
                )
            ]
        )

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]

        let overviewData = try encoder.encode(GT1000PatchOverviewReport(snapshot: snapshot))
        let overviewJSON = try #require(String(data: overviewData, encoding: .utf8))
        #expect(overviewJSON == #"{"ampControl1Enabled":false,"ampControl2Enabled":false,"detailBlockCount":1,"masterBPM":120,"masterKey":"C(Am)","masterPatchLevel":4,"patchName":"MULTIBAND CRUNCH","signalChainElementCount":1}"#)

        let chainData = try encoder.encode(GT1000PatchChainReport(snapshot: snapshot))
        let chainJSON = try #require(String(data: chainData, encoding: .utf8))
        #expect(chainJSON == #"{"elements":[{"detailBlockID":"preamp1","displayName":"AIRD PREAMP 1","id":"chain-1","isOutput":false,"isReserved":false,"position":1}],"overview":{"ampControl1Enabled":false,"ampControl2Enabled":false,"detailBlockCount":1,"masterBPM":120,"masterKey":"C(Am)","masterPatchLevel":4,"patchName":"MULTIBAND CRUNCH","signalChainElementCount":1},"signalChainSummary":"AIRD PREAMP 1"}"#)

        let block = try #require(snapshot.blockSummaries.first)
        let blockData = try encoder.encode(GT1000PatchBlockDetailReport(snapshot: snapshot, block: block))
        let blockJSON = try #require(String(data: blockData, encoding: .utf8))
        #expect(blockJSON == #"{"block":{"address":["10","00","15","00"],"chainElementValue":3,"displayName":"AIRD PREAMP 1","id":"preamp1","isEnabled":true,"isInSignalChain":true,"parameters":[{"displayName":"SW","displayValue":"ON","id":"sw","rawValue":1},{"displayName":"GAIN","id":"gain","rawValue":50}],"rawDataHex":"01 0D 32","typeName":"DIAMOND AMP"},"chainPositions":[1],"overview":{"ampControl1Enabled":false,"ampControl2Enabled":false,"detailBlockCount":1,"masterBPM":120,"masterKey":"C(Am)","masterPatchLevel":4,"patchName":"MULTIBAND CRUNCH","signalChainElementCount":1}}"#)
    }
}
