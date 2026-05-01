import Foundation

/// A utility to construct Roland/BOSS System Exclusive (SysEx) messages for the GT-1000.
public struct GT1000SysEx {
    /// The Roland Manufacturer ID.
    public static let rolandID: UInt8 = 0x41
    
    /// The default Device ID (Unit ID). Default is 16 (0x10).
    public static let defaultDeviceID: UInt8 = 0x10
    
    /// Possible Model IDs for the GT-1000. 
    /// GT-1000/GT-1000CORE use a 4-byte Model ID.
    public enum ModelID {
        public static let gt1000: [UInt8] = [0x00, 0x00, 0x00, 0x4F]
    }

    /// Command IDs for Roland SysEx.
    public enum Command {
        public static let rq1: UInt8 = 0x11 // Request Data
        public static let dt1: UInt8 = 0x12 // Data Set
    }

    /// Builds a "Data Set 1" (DT1) SysEx message.
    /// - Parameters:
    ///   - deviceID: The unit ID of the device (default 0x10).
    ///   - modelID: The 4-byte model ID.
    ///   - address: The 4-byte address to write to.
    ///   - data: The data bytes to write.
    /// - Returns: A complete SysEx message byte array.
    public static func buildDataSet(
        deviceID: UInt8 = defaultDeviceID,
        modelID: [UInt8] = ModelID.gt1000,
        address: [UInt8],
        data: [UInt8]
    ) -> [UInt8] {
        var message: [UInt8] = [0xF0, rolandID, deviceID]
        message.append(contentsOf: modelID)
        message.append(Command.dt1)
        message.append(contentsOf: address)
        message.append(contentsOf: data)

        // Calculate checksum over address and data
        let checksum = calculateChecksum(address: address, data: data)
        message.append(checksum)

        message.append(0xF7)
        return message
    }
    
    /// Builds a "Request Data 1" (RQ1) SysEx message.
    /// - Parameters:
    ///   - deviceID: The unit ID of the device (default 0x10).
    ///   - modelID: The 4-byte model ID.
    ///   - address: The 4-byte address to read from.
    ///   - size: The number of bytes to request.
    /// - Returns: A complete SysEx message byte array.
    public static func buildRequestData(
        deviceID: UInt8 = defaultDeviceID,
        modelID: [UInt8] = ModelID.gt1000,
        address: [UInt8],
        size: [UInt8]
    ) -> [UInt8] {
        var message: [UInt8] = [0xF0, rolandID, deviceID]
        message.append(contentsOf: modelID)
        message.append(Command.rq1)
        message.append(contentsOf: address)
        message.append(contentsOf: size)
        
        // Checksum is calculated over address and size
        let checksum = calculateChecksum(address: address, data: size)
        message.append(checksum)
        
        message.append(0xF7)
        return message
    }
    
    /// Calculates the Roland checksum.
    /// The checksum is (128 - (sum % 128)) % 128.
    public static func calculateChecksum(address: [UInt8], data: [UInt8]) -> UInt8 {
        let totalSum = (address + data).reduce(0) { $0 + Int($1) }
        let remainder = totalSum % 128
        let checksum = (128 - remainder) % 128
        return UInt8(checksum)
    }

    public static func identityRequest(deviceID: UInt8 = 0x7F) -> [UInt8] {
        [0xF0, 0x7E, deviceID, 0x06, 0x01, 0xF7]
    }

    public static func nibbles(for value: Int, byteCount: Int = 4) -> [UInt8] {
        precondition(byteCount > 0)
        precondition(value >= 0)

        return stride(from: (byteCount - 1) * 4, through: 0, by: -4).map {
            UInt8((value >> $0) & 0x0F)
        }
    }

    public static func bpmData(for bpm: Double) -> [UInt8] {
        let value = min(max(Int((bpm * 10).rounded()), 400), 2500)
        return nibbles(for: value)
    }
}

// MARK: - Common Addresses (Firmware 4.x)
extension GT1000SysEx {
    public enum Address {
        /// Temporary patch common starts at 10 00 00 00.
        public static let temporaryPatchName: [UInt8] = [0x10, 0x00, 0x00, 0x00]

        /// System common metronome BPM starts at 00 00 00 09.
        public static let systemMetronomeBPM: [UInt8] = [0x00, 0x00, 0x00, 0x09]

        /// Temporary patch PatchEfct MASTER:BPM starts at 10 00 10 61.
        public static let temporaryPatchMasterBPM: [UInt8] = [0x10, 0x00, 0x10, 0x61]

        /// Temporary patch assign 16 starts at 10 00 0A 40.
        public static let temporaryAssign16: [UInt8] = [0x10, 0x00, 0x0A, 0x40]

    }

    public enum Assign {
        public enum Switch: UInt8 {
            case off = 0x00
            case on = 0x01
        }

        public enum Target: Int {
            /// TUNER:ON/OFF target accepted by GT-1000 firmware 4.01.
            case tunerOnOff = 987
        }

        public enum Source: UInt8 {
            case cc80 = 0x45
        }

        public enum Mode: UInt8 {
            case toggle = 0x00
            case momentary = 0x01
        }

        public enum Waveform: UInt8 {
            case saw = 0x00
        }

        public enum InternalPedalTrigger: UInt8 {
            case patchChange = 0x00
        }

        public enum InternalPedalCurve: UInt8 {
            case linear = 0x00
        }

        public enum MIDIChannel: UInt8 {
            case system = 0x00
        }

        public enum BankSelect: Int {
            case off = 128
        }

        public struct NibbleValueRange: Sendable {
            let lowerBound: Int
            let upperBound: Int

            public static let offOn = Self(lowerBound: 32768, upperBound: 32769)
            public static let controlChange = Self(lowerBound: 0, upperBound: 127)
            public static let fixedZero = Self(lowerBound: 0, upperBound: 0)
        }

        public struct Builder {
            private static let reservedParameter: UInt8 = 0x00

            var enabled: Switch = .on
            var target: Target
            var targetRange: NibbleValueRange
            var source: Source
            var mode: Mode = .momentary
            var waveRate = 0
            var waveform: Waveform = .saw
            var internalPedalTrigger: InternalPedalTrigger = .patchChange
            var internalPedalTime = 0
            var internalPedalCurve: InternalPedalCurve = .linear
            var activeRange: NibbleValueRange = .controlChange
            var midiChannel: MIDIChannel = .system
            var midiControlChange: UInt8
            var midiControlChangeValueRange: NibbleValueRange = .fixedZero
            var midiProgramChange: UInt8 = 0
            var midiBankMSB: BankSelect = .off
            var midiBankLSB: BankSelect = .off

            public init(
                target: Target,
                targetRange: NibbleValueRange,
                source: Source,
                midiControlChange: UInt8
            ) {
                self.target = target
                self.targetRange = targetRange
                self.source = source
                self.midiControlChange = midiControlChange
            }

            public func build() -> [UInt8] {
                let fields: [EncodedField] = [
                    .byte(enabled.rawValue),
                    .nibbles(target.rawValue),
                    .range(targetRange),
                    .byte(source.rawValue),
                    .byte(mode.rawValue),
                    .byte(UInt8(waveRate)),
                    .byte(waveform.rawValue),
                    .byte(internalPedalTrigger.rawValue),
                    .byte(UInt8(internalPedalTime)),
                    .byte(internalPedalCurve.rawValue),
                    .range(activeRange),
                    .byte(midiChannel.rawValue),
                    .byte(midiControlChange),
                    .range(midiControlChangeValueRange),
                    .byte(Self.reservedParameter),
                    .byte(midiProgramChange),
                    .nibbles(midiBankMSB.rawValue, byteCount: 2),
                    .nibbles(midiBankLSB.rawValue, byteCount: 2)
                ]

                return fields.flatMap(\.bytes)
            }
        }

        public static let tunerControlChange: UInt8 = 80

        public static var tunerControlChangeData: [UInt8] {
            Builder(
                target: .tunerOnOff,
                targetRange: .offOn,
                source: .cc80,
                midiControlChange: tunerControlChange
            ).build()
        }

        private enum EncodedField {
            case byte(UInt8)
            case nibbles(Int, byteCount: Int = 4)
            case range(NibbleValueRange)

            var bytes: [UInt8] {
                switch self {
                case let .byte(value):
                    [value]
                case let .nibbles(value, byteCount):
                    GT1000SysEx.nibbles(for: value, byteCount: byteCount)
                case let .range(range):
                    GT1000SysEx.nibbles(for: range.lowerBound) + GT1000SysEx.nibbles(for: range.upperBound)
                }
            }
        }
    }
}
