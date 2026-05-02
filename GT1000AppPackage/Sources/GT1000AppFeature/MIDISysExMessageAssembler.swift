import Foundation

public struct MIDISysExMessageAssembler: Sendable {
    private var pendingSysExMessage: [UInt8] = []

    public init() {}

    public mutating func assemble(from packets: [[UInt8]]) -> [[UInt8]] {
        var completeMessages: [[UInt8]] = []

        for packet in packets where !packet.isEmpty {
            let startsSysEx = packet.first == 0xF0
            let endsSysEx = packet.last == 0xF7

            if startsSysEx {
                pendingSysExMessage = packet

                if endsSysEx {
                    completeMessages.append(pendingSysExMessage)
                    pendingSysExMessage.removeAll()
                }

                continue
            }

            if !pendingSysExMessage.isEmpty {
                pendingSysExMessage.append(contentsOf: packet)

                if endsSysEx {
                    completeMessages.append(pendingSysExMessage)
                    pendingSysExMessage.removeAll()
                }

                continue
            }

            completeMessages.append(packet)
        }

        return completeMessages
    }

    public var hasPendingSysExMessage: Bool {
        !pendingSysExMessage.isEmpty
    }
}
