import Testing
@testable import GT1000AppFeature

@Suite("MIDI SysEx Message Assembler Tests")
struct MIDISysExMessageAssemblerTests {
    @Test("Pass Through Complete SysEx And Channel Voice Messages")
    func testPassThroughCompleteMessages() {
        var assembler = MIDISysExMessageAssembler()
        let identityReply: [UInt8] = [0xF0, 0x7E, 0x10, 0x06, 0x02, 0xF7]
        let controlChange: [UInt8] = [0xB0, 0x50, 0x7F]

        let messages = assembler.assemble(from: [identityReply, controlChange])

        #expect(messages == [identityReply, controlChange])
        #expect(assembler.hasPendingSysExMessage == false)
    }

    @Test("Reassemble Fragmented GT-1000 DataSet Reply")
    func testReassembleFragmentedDataSetReply() {
        var assembler = MIDISysExMessageAssembler()
        let completeReply = GT1000SysEx.buildDataSet(
            address: GT1000SysEx.Address.temporaryPatchMasterBPM,
            data: GT1000SysEx.bpmData(for: 120)
        )

        let firstResult = assembler.assemble(from: [
            Array(completeReply[0..<8]),
            Array(completeReply[8..<15])
        ])
        let secondResult = assembler.assemble(from: [
            Array(completeReply[15..<completeReply.count])
        ])

        #expect(firstResult.isEmpty)
        #expect(secondResult == [completeReply])
        #expect(assembler.hasPendingSysExMessage == false)
    }

    @Test("Replace Incomplete SysEx When New SysEx Starts")
    func testReplaceIncompleteSysExOnNewStart() {
        var assembler = MIDISysExMessageAssembler()
        let completeReply = GT1000SysEx.buildDataSet(
            address: GT1000SysEx.Address.temporaryPatchMasterBPM,
            data: GT1000SysEx.bpmData(for: 121)
        )

        let messages = assembler.assemble(from: [
            [0xF0, 0x41, 0x10],
            completeReply
        ])

        #expect(messages == [completeReply])
        #expect(assembler.hasPendingSysExMessage == false)
    }
}
