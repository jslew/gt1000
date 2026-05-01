import Testing
import Foundation
@testable import GT1000AppFeature

@Suite("GT-1000 SysEx Protocol Tests")
struct GT1000SysExTests {
    
    @Test("Verify Checksum Calculation")
    func testChecksum() {
        let address = GT1000SysEx.Address.temporaryPatchMasterBPM
        let data = GT1000SysEx.bpmData(for: 120)
        let checksum = GT1000SysEx.calculateChecksum(address: address, data: data)
        #expect(checksum == 0x70)
    }
    
    @Test("Verify GT-1000 Model ID in SysEx Message")
    func testModelIDLength() {
        let address = GT1000SysEx.Address.temporaryPatchMasterBPM
        let data: [UInt8] = [0x00]
        let message = GT1000SysEx.buildDataSet(address: address, data: data)
        
        // F0 (0)
        // 41 (1)
        // 10 (2) - Device ID
        // 00 00 00 4F (3, 4, 5, 6) - Model ID
        // 12 (7) - Command
        // ...
        #expect(message[1] == 0x41) // Roland
        #expect(message[3] == 0x00)
        #expect(message[6] == 0x4F)
        #expect(message[7] == 0x12) // DT1
    }
    
    @Test("Verify BPM Formatting")
    func testBPMFormatting() {
        #expect(GT1000SysEx.bpmData(for: 120.0) == [0x00, 0x04, 0x0B, 0x00])
        #expect(GT1000SysEx.bpmData(for: 250.0) == [0x00, 0x09, 0x0C, 0x04])
        #expect(GT1000SysEx.bpmData(for: 20.0) == [0x00, 0x01, 0x09, 0x00])
    }
    
    @Test("Verify Master BPM Message Structure")
    func testMasterBPMMessage() {
        let message = GT1000SysEx.buildDataSet(
            deviceID: 0x10,
            address: GT1000SysEx.Address.temporaryPatchMasterBPM,
            data: GT1000SysEx.bpmData(for: 120)
        )
        
        let expectedHeader: [UInt8] = [0xF0, 0x41, 0x10, 0x00, 0x00, 0x00, 0x4F, 0x12]
        for i in 0..<expectedHeader.count {
            #expect(message[i] == expectedHeader[i])
        }
        
        #expect(Array(message[8..<16]) == [0x10, 0x00, 0x10, 0x61, 0x00, 0x04, 0x0B, 0x00])
        #expect(message[16] == 0x70)
        #expect(message.last == 0xF7)
    }
    
    @Test("Verify Identity Request Sequence")
    func testIdentityRequest() {
        let identityRequest = GT1000SysEx.identityRequest()
        #expect(identityRequest.count == 6)
        #expect(identityRequest[0] == 0xF0)
        #expect(identityRequest[5] == 0xF7)
    }
    
    @Test("Verify Tuner Assign Data")
    func testTunerAssignData() {
        let data = GT1000SysEx.Assign.tunerControlChangeData

        #expect(data.count == 44)
        #expect(Array(data[0..<5]) == [0x01, 0x00, 0x03, 0x0D, 0x0B])
        #expect(Array(data[5..<9]) == [0x08, 0x00, 0x00, 0x00])
        #expect(Array(data[9..<13]) == [0x08, 0x00, 0x00, 0x01])
        #expect(data[13] == 0x45)
        #expect(data[14] == 0x01)
        #expect(Array(data[20..<24]) == [0x00, 0x00, 0x00, 0x00])
        #expect(Array(data[24..<28]) == [0x00, 0x00, 0x07, 0x0F])
        #expect(data[29] == 0x50)
    }
}
