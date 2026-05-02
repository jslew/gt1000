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

    public static func integer(fromNibbles nibbles: [UInt8]) -> Int? {
        guard !nibbles.isEmpty, nibbles.allSatisfy({ $0 <= 0x0F }) else { return nil }

        return nibbles.reduce(0) { result, nibble in
            (result << 4) | Int(nibble)
        }
    }

    public static func bpm(fromData data: [UInt8]) -> Double? {
        guard let value = integer(fromNibbles: data), value >= 400, value <= 2500 else {
            return nil
        }

        return Double(value) / 10.0
    }

    public static func sevenBitAddressValue(_ address: [UInt8]) -> Int? {
        guard address.count == 4, address.allSatisfy({ $0 <= 0x7F }) else { return nil }

        return address.reduce(0) { result, byte in
            (result << 7) | Int(byte)
        }
    }

    public static func sevenBitAddress(from value: Int) -> [UInt8] {
        precondition(value >= 0)

        return stride(from: 21, through: 0, by: -7).map {
            UInt8((value >> $0) & 0x7F)
        }
    }

    public static func address(_ address: [UInt8], adding offset: Int) -> [UInt8] {
        guard let value = sevenBitAddressValue(address) else {
            preconditionFailure("Invalid Roland address")
        }

        return sevenBitAddress(from: value + offset)
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

        /// Temporary patch PatchEfct starts at 10 00 10 00.
        public static let temporaryPatchEffect: [UInt8] = [0x10, 0x00, 0x10, 0x00]

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

// MARK: - Patch Inspection
extension GT1000SysEx {
    public struct PatchReadRequest: Sendable, Equatable {
        public let label: String
        public let address: [UInt8]
        public let size: [UInt8]

        public init(label: String, address: [UInt8], size: [UInt8]) {
            self.label = label
            self.address = address
            self.size = size
        }

        public var message: [UInt8] {
            GT1000SysEx.buildRequestData(address: address, size: size)
        }
    }

    public enum PatchReadPlan {
        public static let patchName = PatchReadRequest(
            label: "Patch Name",
            address: Address.temporaryPatchName,
            size: [0x00, 0x00, 0x00, 0x10]
        )

        public static let masterBPM = PatchReadRequest(
            label: "Master BPM",
            address: Address.temporaryPatchMasterBPM,
            size: [0x00, 0x00, 0x00, 0x04]
        )

        public static let patchEffect = PatchReadRequest(
            label: "Patch Effect",
            address: Address.temporaryPatchEffect,
            size: [0x00, 0x00, 0x01, 0x1C]
        )

        public static let blockSummaries: [PatchReadRequest] = PatchBlockDefinition.summaryBlocks.map {
            PatchReadRequest(
                label: $0.displayName,
                address: $0.address,
                size: GT1000SysEx.sevenBitAddress(from: $0.size)
            )
        }

        public static let initialSnapshotReads: [PatchReadRequest] = [
            patchName,
            masterBPM,
            patchEffect
        ] + blockSummaries
    }

    public struct DataSetMessage: Sendable, Equatable {
        public let deviceID: UInt8
        public let address: [UInt8]
        public let data: [UInt8]
    }

    public enum ParseError: Error, Equatable {
        case invalidEnvelope
        case unsupportedManufacturer(UInt8)
        case unsupportedModelID([UInt8])
        case unsupportedCommand(UInt8)
        case invalidChecksum(expected: UInt8, actual: UInt8)
    }

    public static func parseDataSet(_ message: [UInt8]) throws -> DataSetMessage {
        guard message.count >= 14, message.first == 0xF0, message.last == 0xF7 else {
            throw ParseError.invalidEnvelope
        }

        guard message[1] == rolandID else {
            throw ParseError.unsupportedManufacturer(message[1])
        }

        let modelID = Array(message[3..<7])
        guard modelID == ModelID.gt1000 else {
            throw ParseError.unsupportedModelID(modelID)
        }

        guard message[7] == Command.dt1 else {
            throw ParseError.unsupportedCommand(message[7])
        }

        let address = Array(message[8..<12])
        let data = Array(message[12..<(message.count - 2)])
        let expectedChecksum = calculateChecksum(address: address, data: data)
        let actualChecksum = message[message.count - 2]
        guard expectedChecksum == actualChecksum else {
            throw ParseError.invalidChecksum(expected: expectedChecksum, actual: actualChecksum)
        }

        return DataSetMessage(deviceID: message[2], address: address, data: data)
    }
}

public struct PatchBlockDefinition: Sendable, Equatable {
    public let id: String
    public let displayName: String
    public let chainElementValue: UInt8
    public let address: [UInt8]
    public let size: Int
    public let parameters: [PatchParameterDefinition]

    public init(
        id: String,
        displayName: String,
        chainElementValue: UInt8,
        address: [UInt8],
        size: Int,
        parameters: [PatchParameterDefinition]
    ) {
        self.id = id
        self.displayName = displayName
        self.chainElementValue = chainElementValue
        self.address = address
        self.size = size
        self.parameters = parameters
    }

    public static let summaryBlocks: [PatchBlockDefinition] = [
        .init(id: "comp", displayName: "COMPRESSOR", chainElementValue: 0, address: [0x10, 0x00, 0x12, 0x00], size: 8, parameters: [
            .switch("sw", "SW", 0), .type("type", "TYPE", 1, values: ["BOSS COMP", "X-COMP", "D-COMP", "ORANGE", "STEREO COMP"]),
            .byte("sustain", "SUSTAIN", 2), .byte("attack", "ATTACK", 3), .byte("level", "LEVEL", 4), .byte("tone", "TONE", 5)
        ]),
        .init(id: "dist1", displayName: "DISTORTION 1", chainElementValue: 1, address: [0x10, 0x00, 0x13, 0x00], size: 9, parameters: distortionParameters),
        .init(id: "dist2", displayName: "DISTORTION 2", chainElementValue: 2, address: [0x10, 0x00, 0x14, 0x00], size: 9, parameters: distortionParameters),
        .init(id: "preamp1", displayName: "AIRD PREAMP 1", chainElementValue: 3, address: [0x10, 0x00, 0x15, 0x00], size: 14, parameters: preampParameters),
        .init(id: "preamp2", displayName: "AIRD PREAMP 2", chainElementValue: 4, address: [0x10, 0x00, 0x16, 0x00], size: 14, parameters: preampParameters),
        .init(id: "ns1", displayName: "NOISE SUPPRESSOR 1", chainElementValue: 5, address: [0x10, 0x00, 0x17, 0x00], size: 4, parameters: [
            .switch("sw", "SW", 0), .byte("threshold", "THRESHOLD", 1), .byte("release", "RELEASE", 2), .byte("detect", "DETECT", 3)
        ]),
        .init(id: "ns2", displayName: "NOISE SUPPRESSOR 2", chainElementValue: 6, address: [0x10, 0x00, 0x18, 0x00], size: 4, parameters: [
            .switch("sw", "SW", 0), .byte("threshold", "THRESHOLD", 1), .byte("release", "RELEASE", 2), .byte("detect", "DETECT", 3)
        ]),
        .init(id: "eq1", displayName: "EQUALIZER 1", chainElementValue: 10, address: [0x10, 0x00, 0x19, 0x00], size: 24, parameters: eqParameters),
        .init(id: "eq2", displayName: "EQUALIZER 2", chainElementValue: 11, address: [0x10, 0x00, 0x1A, 0x00], size: 24, parameters: eqParameters),
        .init(id: "eq3", displayName: "EQUALIZER 3", chainElementValue: 12, address: [0x10, 0x00, 0x1B, 0x00], size: 24, parameters: eqParameters),
        .init(id: "eq4", displayName: "EQUALIZER 4", chainElementValue: 13, address: [0x10, 0x00, 0x1C, 0x00], size: 24, parameters: eqParameters),
        .init(id: "delay1", displayName: "DELAY 1", chainElementValue: 15, address: [0x10, 0x00, 0x1D, 0x00], size: 9, parameters: delayParameters),
        .init(id: "delay2", displayName: "DELAY 2", chainElementValue: 16, address: [0x10, 0x00, 0x1E, 0x00], size: 9, parameters: delayParameters),
        .init(id: "delay3", displayName: "DELAY 3", chainElementValue: 17, address: [0x10, 0x00, 0x1F, 0x00], size: 9, parameters: delayParameters),
        .init(id: "delay4", displayName: "DELAY 4", chainElementValue: 18, address: [0x10, 0x00, 0x20, 0x00], size: 9, parameters: delayParameters),
        .init(id: "masterDelay", displayName: "MASTER DELAY", chainElementValue: 19, address: [0x10, 0x00, 0x21, 0x00], size: 31, parameters: masterDelayParameters),
        .init(id: "chorus", displayName: "CHORUS", chainElementValue: 14, address: [0x10, 0x00, 0x22, 0x00], size: 24, parameters: chorusParameters),
        .init(id: "fx1", displayName: "FX 1", chainElementValue: 7, address: [0x10, 0x00, 0x23, 0x00], size: 2, parameters: fxParameters),
        .init(id: "fx2", displayName: "FX 2", chainElementValue: 8, address: [0x10, 0x00, 0x3E, 0x00], size: 2, parameters: fxParameters),
        .init(id: "fx3", displayName: "FX 3", chainElementValue: 9, address: [0x10, 0x00, 0x59, 0x00], size: 2, parameters: fxParameters),
        .init(id: "reverb", displayName: "REVERB", chainElementValue: 21, address: [0x10, 0x00, 0x74, 0x00], size: 42, parameters: reverbParameters),
        .init(id: "pedalFx", displayName: "PEDAL FX", chainElementValue: 23, address: [0x10, 0x00, 0x75, 0x00], size: 5, parameters: [
            .switch("sw", "SW", 0), .byte("type", "TYPE", 1), .byte("effectLevel", "EFFECT LEVEL", 3), .byte("directMix", "DIRECT MIX", 4)
        ])
    ]

    public static func definition(address: [UInt8]) -> PatchBlockDefinition? {
        summaryBlocks.first { $0.address == address }
    }

    public static func definition(chainElementValue: UInt8) -> PatchBlockDefinition? {
        summaryBlocks.first { $0.chainElementValue == chainElementValue }
    }

    private static let distortionTypeNames = [
        "MID BOOST", "CLEAN BOOST", "TREBLE BOOST", "CRUNCH", "NATURAL OD", "WARM OD",
        "FAT DS", "LEAD DS", "METAL DS", "OCT FUZZ", "A-DIST", "X-OD", "X-DIST",
        "BLUES OD", "OD-1", "T-SCREAM", "TURBO OD", "DIST", "RAT", "GUV DS",
        "DIST+", "METAL ZONE", "'60S FUZZ", "MUFF FUZZ"
    ]

    private static let preampTypeNames = [
        "TRANSPARENT", "NATURAL", "BOUTIQUE", "SUPREME", "MAXIMUM", "JUGGERNAUT",
        "X-CRUNCH", "X-HI GAIN", "X-MODDED", "JC-120", "TWIN COMBO", "DELUXE COMBO",
        "TWEED COMBO", "DIAMOND AMP", "BRIT STACK", "RECTI STACK"
    ]

    private static let masterDelayTypeNames = [
        "MONO", "PAN", "STEREO1", "STEREO2", "ANALOG", "ANALOG ST", "TAPE",
        "REVERSE", "SHIMMER", "DUAL", "WARP", "TWIST"
    ]

    private static let chorusTypeNames = ["MONO", "STEREO 1", "STEREO 2", "DUAL"]

    private static let distortionParameters: [PatchParameterDefinition] = [
        .switch("sw", "SW", 0), .type("type", "TYPE", 1, values: distortionTypeNames),
        .byte("drive", "DRIVE", 2), .byte("tone", "TONE", 3), .byte("level", "LEVEL", 4),
        .byte("bottom", "BOTTOM", 5), .byte("directMix", "DIRECT MIX", 6),
        .switch("soloSw", "SOLO SW", 7), .byte("soloLevel", "SOLO LEVEL", 8)
    ]

    private static let preampParameters: [PatchParameterDefinition] = [
        .switch("sw", "SW", 0), .type("type", "TYPE", 1, values: preampTypeNames),
        .byte("gain", "GAIN", 2), .byte("sag", "SAG", 3), .byte("resonance", "RESONANCE", 4),
        .byte("level", "LEVEL", 5), .byte("bass", "BASS", 6), .byte("middle", "MIDDLE", 7),
        .byte("treble", "TREBLE", 8), .byte("presence", "PRESENCE", 9), .switch("bright", "BRIGHT", 10),
        .byte("gainSw", "GAIN SW", 11), .switch("soloSw", "SOLO SW", 12), .byte("soloLevel", "SOLO LEVEL", 13)
    ]

    private static let eqParameters: [PatchParameterDefinition] = [
        .switch("sw", "SW", 0), .byte("type", "TYPE", 1), .byte("lowGain", "LOW GAIN", 2),
        .byte("highGain", "HIGH GAIN", 3), .byte("level", "LEVEL", 13)
    ]

    private static let delayParameters: [PatchParameterDefinition] = [
        .switch("sw", "SW", 0), .nibbles("time", "TIME", 1, byteCount: 4),
        .byte("feedback", "FEEDBACK", 5), .byte("highCut", "HIGH CUT", 6),
        .byte("effectLevel", "EFFECT LEVEL", 7), .byte("directLevel", "DIRECT LEVEL", 8)
    ]

    private static let masterDelayParameters: [PatchParameterDefinition] = [
        .switch("sw", "SW", 0), .type("type", "TYPE", 1, values: masterDelayTypeNames),
        .nibbles("time", "TIME", 2, byteCount: 4), .byte("feedback", "FEEDBACK", 6),
        .byte("highCut", "HIGH CUT", 7), .byte("effectLevel", "EFFECT LEVEL", 8),
        .byte("modRate", "MOD RATE", 9), .byte("modDepth", "MOD DEPTH", 10),
        .byte("directLevel", "DIRECT LEVEL", 14)
    ]

    private static let chorusParameters: [PatchParameterDefinition] = [
        .switch("sw", "SW", 0), .type("type", "TYPE", 1, values: chorusTypeNames),
        .byte("rate", "RATE", 2), .byte("depth", "DEPTH", 3), .byte("preDelay", "PRE-DELAY", 4),
        .byte("effectLevel", "EFFECT LEVEL", 5), .byte("waveform", "WAVEFORM", 6),
        .byte("lowCut", "LOW CUT", 7), .byte("highCut", "HIGH CUT", 8)
    ]

    private static let fxParameters: [PatchParameterDefinition] = [
        .switch("sw", "SW", 0), .byte("type", "TYPE", 1)
    ]

    private static let reverbParameters: [PatchParameterDefinition] = [
        .switch("sw", "SW", 0), .byte("type", "TYPE", 1), .byte("time", "TIME", 2),
        .byte("tone", "TONE", 3), .byte("density", "DENSITY", 4), .byte("effectLevel", "EFFECT LEVEL", 5),
        .byte("preDelay", "PRE-DELAY", 6), .byte("lowCut", "LOW CUT", 7), .byte("highCut", "HIGH CUT", 8),
        .byte("directLevel", "DIRECT LEVEL", 16)
    ]
}

public struct PatchParameterDefinition: Sendable, Equatable {
    public enum ValueKind: Sendable, Equatable {
        case byte
        case bool
        case type([String])
        case nibbles(Int)
    }

    public let id: String
    public let displayName: String
    public let offset: Int
    public let kind: ValueKind

    public static func byte(_ id: String, _ displayName: String, _ offset: Int) -> Self {
        Self(id: id, displayName: displayName, offset: offset, kind: .byte)
    }

    public static func `switch`(_ id: String, _ displayName: String, _ offset: Int) -> Self {
        Self(id: id, displayName: displayName, offset: offset, kind: .bool)
    }

    public static func type(_ id: String, _ displayName: String, _ offset: Int, values: [String]) -> Self {
        Self(id: id, displayName: displayName, offset: offset, kind: .type(values))
    }

    public static func nibbles(_ id: String, _ displayName: String, _ offset: Int, byteCount: Int) -> Self {
        Self(id: id, displayName: displayName, offset: offset, kind: .nibbles(byteCount))
    }
}
