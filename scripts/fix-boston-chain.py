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

def fix_boston_chain():
    print("Initializing MIDI...")
    midi = live.CoreMIDI()
    destination = live.find_endpoint(midi, midi.cm.MIDIGetNumberOfDestinations, midi.cm.MIDIGetDestination)
    
    if destination is None:
        print("Error: GT-1000 not found.")
        return

    client = live.ctypes.c_uint32()
    output_port = live.ctypes.c_uint32()
    client_name = midi.cf_string("BostonChainFixer")
    midi.cm.MIDIClientCreate(client_name, None, None, live.ctypes.byref(client))
    
    output_name = midi.cf_string("BostonOutput")
    midi.cm.MIDIOutputPortCreate(client, output_name, live.ctypes.byref(output_port))

    try:
        print("Moving EQ1 into Path B for isolation...")
        
        # We need to rewrite the chain element list.
        # Base address for chain: 10 00 10 68
        # Current chain (partial):
        # 5: DIVIDER 1 (35)
        # 6: DISTORTION 1 (1)
        # 7: SEND/RETURN 1 (24)
        # 8: PREAMP 1 (3)
        # 9: NS 1 (5)
        # 10: EQ 1 (10) <--- MOVE THIS
        # 11: BRANCH SPLIT 1 (36)
        # 12: DISTORTION 2 (2)
        # 13: SEND/RETURN 2 (25)
        # 14: PREAMP 2 (4)
        # 15: NS 2 (6)
        # 16: EQ 2 (11)
        # 17: MIXER 1 (37)
        
        # Goal: Path A has nothing or only clean. Path B has Distortion 1 and EQ 1.
        # Let's rearrange:
        # 5: DIVIDER 1 (35)
        # 6: (A) SEND/RETURN 1 (24) - Real Amp Clean
        # 7: (A) ...
        # 10: (A) ...
        # 11: BRANCH SPLIT 1 (36)
        # 12: (B) DISTORTION 1 (1)
        # 13: (B) EQUALIZER 1 (10)
        # 14: (B) ...
        
        # Let's just swap EQ1 (pos 10) with some placeholder or move it to pos 13.
        # Current element at 13 is SEND/RETURN 2 (25).
        # Element at 10 is EQ 1 (10).
        
        # Address for Pos 10: 10 00 10 71 (10 68 + 9)
        # Address for Pos 13: 10 00 10 74 (10 68 + 12)
        
        # Move SR2 to Pos 10, EQ1 to Pos 13.
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x10, 0x71], [25])
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x10, 0x74], [10])
        
        print(" - EQ1 moved to Position 13 (Path B).")
        print(" - SEND/RETURN 2 moved to Position 10 (Path A).")
        print("\nChain isolation complete. EQ1 should now only affect the Dirty Path.")

    finally:
        midi.cm.MIDIClientDispose(client)

if __name__ == "__main__":
    fix_boston_chain()
