import Testing
@testable import GT1000AppFeature

@Suite("GT-1000 Patch Snapshot Tests")
struct GT1000PatchSnapshotTests {
    @Test("Decode Patch Name And BPM Replies Into Snapshot")
    func testDecodePatchNameAndBPM() throws {
        let decoder = GT1000PatchSnapshotDecoder()
        let nameData = Array("CLEAN ROOM      ".utf8)
        let nameReply = GT1000SysEx.buildDataSet(
            address: GT1000SysEx.Address.temporaryPatchName,
            data: nameData
        )
        let bpmReply = GT1000SysEx.buildDataSet(
            address: GT1000SysEx.Address.temporaryPatchMasterBPM,
            data: GT1000SysEx.bpmData(for: 123.4)
        )

        let namedSnapshot = try decoder.applying(message: nameReply)
        let fullSnapshot = try decoder.applying(message: bpmReply, to: namedSnapshot)

        #expect(fullSnapshot.patchName == "CLEAN ROOM")
        #expect(fullSnapshot.masterBPM == 123.4)
        #expect(fullSnapshot.summaryLines == [
            "Patch: CLEAN ROOM",
            "Master BPM: 123.4",
            "Signal chain: not decoded yet"
        ])
    }

    @Test("Ignore Unknown DataSet Addresses")
    func testIgnoreUnknownAddress() {
        let decoder = GT1000PatchSnapshotDecoder()
        let snapshot = GT1000PatchSnapshot(patchName: "BASE")
        let dataSet = GT1000SysEx.DataSetMessage(
            deviceID: 0x10,
            address: [0x10, 0x00, 0x7E, 0x00],
            data: [0x01]
        )

        #expect(decoder.applying(dataSet, to: snapshot) == snapshot)
    }
}
