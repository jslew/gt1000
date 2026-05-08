#!/usr/bin/env python3
import sys
import time
from pathlib import Path

# Add project root to path so we can import tools
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from tools.gt1000 import live

def send_dt1(midi, output_port, destination, address, data):
    """Build and send a DT1 message."""
    msg = [0xF0, live.ROLAND_ID, live.DEVICE_ID] + live.MODEL_ID + [live.DT1] + address + data
    msg.append(live.checksum(address, data))
    msg.append(0xF7)
    live.send_message(midi, output_port, destination, msg)
    time.sleep(0.05)

def fix_boston_dist():
    print("Initializing MIDI...")
    midi = live.CoreMIDI()
    destination = live.find_endpoint(midi, midi.cm.MIDIGetNumberOfDestinations, midi.cm.MIDIGetDestination)
    
    if destination is None:
        print("Error: GT-1000 not found.")
        return

    client = live.ctypes.c_uint32()
    output_port = live.ctypes.c_uint32()
    client_name = midi.cf_string("BostonDistFixer")
    midi.cm.MIDIClientCreate(client_name, None, None, live.ctypes.byref(client))
    
    output_name = midi.cf_string("BostonOutput")
    midi.cm.MIDIOutputPortCreate(client, output_name, live.ctypes.byref(output_port))

    try:
        print("Moving Distortion 1 into Path B...")
        
        # Position 6 was Distortion 1 (1). 
        # Position 12 was Distortion 2 (2).
        
        # Let's move DIST 1 (1) to Pos 12 (Path B)
        # And move DIST 2 (2) to Pos 6 (Path A, but we'll turn it OFF).
        
        # Address for Pos 6: 10 00 10 6D (10 68 + 5)
        # Address for Pos 12: 10 00 10 73 (10 68 + 11)
        
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x10, 0x6D], [2]) # DIST 2 to Pos 6
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x10, 0x73], [1]) # DIST 1 to Pos 12
        
        print(" - Distortion 1 moved to Position 12 (Path B).")
        print(" - Distortion 2 moved to Position 6 (Path A).")

    finally:
        midi.cm.MIDIClientDispose(client)

if __name__ == "__main__":
    fix_boston_dist()
