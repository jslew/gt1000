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

    @Test("Decode Patch Effect Chain And Routing Blocks")
    func testDecodePatchEffectChainAndRoutingBlocks() {
        let decoder = GT1000PatchSnapshotDecoder()
        let data: [UInt8] = [
            0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x0E, 0x08, 0x00, 0x00, 0x00, 0x00, 0x02,
            0x01, 0x01, 0x00, 0x32, 0x01, 0x0A, 0x00, 0x32, 0x02, 0x0A, 0x00, 0x32, 0x00,
            0x00, 0x00, 0x00, 0x32, 0x00, 0x09, 0x00, 0x32, 0x00, 0x09, 0x00, 0x32, 0x00,
            0x00, 0x00, 0x00, 0x32, 0x00, 0x09, 0x00, 0x32, 0x00, 0x09, 0x00, 0x32, 0x00,
            0x00, 0x00, 0x00, 0x06, 0x04, 0x06, 0x04, 0x00, 0x00, 0x00, 0x06, 0x04, 0x06,
            0x04, 0x00, 0x01, 0x64, 0x01, 0x01, 0x01, 0x00, 0x05, 0x64, 0x00, 0x01, 0x01,
            0x00, 0x05, 0x64, 0x00, 0x01, 0x01, 0x01, 0x00, 0x05, 0x64, 0x00, 0x01, 0x01,
            0x00, 0x05, 0x64, 0x00, 0x06, 0x04, 0x00, 0x04, 0x0B, 0x00, 0x00, 0x00, 0x00,
            0x17, 0x0C, 0x07, 0x08, 0x23, 0x01, 0x18, 0x03, 0x05, 0x0A, 0x24, 0x02, 0x19,
            0x04, 0x06, 0x0B, 0x25, 0x00, 0x0D, 0x16, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x09,
            0x14, 0x0E, 0x1A, 0x15, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x22, 0x1D, 0x1E,
            0x21, 0x2F, 0x30, 0x20, 0x1B, 0x1C, 0x1F, 0x2D, 0x2E, 0x2C, 0x01, 0x00, 0x00
        ]
        let snapshot = decoder.applying(.init(
            deviceID: 0x10,
            address: GT1000SysEx.Address.temporaryPatchEffect,
            data: data
        ))

        #expect(snapshot.masterBPM == 120)
        #expect(snapshot.masterPatchLevel == 4)
        #expect(snapshot.masterKey == "C(Am)")
        #expect(snapshot.chainElements.count == 49)
        #expect(snapshot.chainElements[39].address == [0x10, 0x00, 0x11, 0x0F])

        let footVolume = snapshot.blockSummaries.first { $0.id == "footVolume" }
        #expect(footVolume?.parameters.first { $0.id == "volumeMax" }?.rawValue == 1000)
        #expect(footVolume?.parameters.first { $0.id == "curve" }?.rawValue == 2)

        let sendReturn1 = snapshot.blockSummaries.first { $0.id == "sendReturn1" }
        #expect(sendReturn1?.parameters.first { $0.id == "sendLevel" }?.rawValue == 100)
        #expect(sendReturn1?.parameters.first { $0.id == "returnLevel" }?.rawValue == 100)

        let mainSpeakerLeft = snapshot.blockSummaries.first { $0.id == "mainSpeakerSimulatorL" }
        #expect(mainSpeakerLeft?.parameters.map(\.id) == [
            "stereoLink",
            "speakerType",
            "micType",
            "micDistance",
            "micPosition",
            "micLevel",
            "directMix"
        ])
        #expect(mainSpeakerLeft?.parameters.first { $0.id == "micLevel" }?.rawValue == 100)
        #expect(mainSpeakerLeft?.parameters.first { $0.id == "directMix" }?.rawValue == 0)
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
