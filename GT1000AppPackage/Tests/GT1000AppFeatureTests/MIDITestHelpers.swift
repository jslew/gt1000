import CoreMIDI
import Foundation

/// A helper class to create a virtual MIDI destination for intercepting outgoing MIDI data.
class VirtualMIDIDestination {
    private var client = MIDIClientRef()
    private var destination = MIDIEndpointRef()
    
    var receivedMessages: [[UInt8]] = []
    
    init(name: String) {
        MIDIClientCreate("TestMIDIClient" as CFString, nil, nil, &client)
        
        MIDIDestinationCreateWithBlock(client, name as CFString, &destination) { [weak self] eventList, context in
            let packets = eventList.pointee
            // For standard packets (legacy)
            // Note: This is simplified for testing
            self?.receivedMessages.append([0xDE, 0xAD]) // Placeholder for actual packet parsing
        }
    }
}
