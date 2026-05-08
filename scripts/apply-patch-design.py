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
    # F0 41 10 00 00 00 4F 12 [addr] [data] [sum] F7
    msg = [0xF0, live.ROLAND_ID, live.DEVICE_ID] + live.MODEL_ID + [live.DT1] + address + data
    msg.append(live.checksum(address, data))
    msg.append(0xF7)
    live.send_message(midi, output_port, destination, msg)
    time.sleep(0.05) # Small delay to avoid flooding

def build_boston_patch():
    print("Initializing MIDI...")
    midi = live.CoreMIDI()
    destination = live.find_endpoint(midi, midi.cm.MIDIGetNumberOfDestinations, midi.cm.MIDIGetDestination)
    source = live.find_endpoint(midi, midi.cm.MIDIGetNumberOfSources, midi.cm.MIDIGetSource)
    
    if destination is None or source is None:
        print("Error: GT-1000 not found.")
        return

    client = live.ctypes.c_uint32()
    output_port = live.ctypes.c_uint32()
    client_name = midi.cf_string("BostonBuilder")
    midi.cm.MIDIClientCreate(client_name, None, None, live.ctypes.byref(client))
    
    output_name = midi.cf_string("BostonOutput")
    midi.cm.MIDIOutputPortCreate(client, output_name, live.ctypes.byref(output_port))

    try:
        print("Applying Boston 'More Than A Feeling' settings...")
        
        # 1. Compressor: Sustain-heavy for Scholz tone
        # Address: [10, 00, 12, 00], Data: SW(1), TYPE(1:X-COMP), SUSTAIN(80), ATTACK(50), LEVEL(50), TONE(50)
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x12, 0x00], [0x01, 0x01, 80, 50, 50, 50])
        print(" - Compressor configured.")

        # 2. Distortion 1: Scholz Rhythm
        # Address: [10, 00, 13, 00], Data: SW(1), TYPE(12:X-DIST), DRIVE(60), TONE(50), LEVEL(50), BOTTOM(50), D-MIX(0), SOLO(0), S-LEVEL(50)
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x13, 0x00], [0x01, 12, 60, 50, 50, 50, 0, 0, 50])
        print(" - Distortion 1 (Scholz Rhythm) configured.")

        # 3. EQ 1: The "Cocked Wah" Mids
        # Address: [10, 00, 19, 00], Data: SW(1), TYPE(0), ... we need to target specific Mid Gain
        # Based on Parameter Guide: EQ Low Gain is offset 2, Level is 13. 
        # For simplicity, let's just enable it and set a basic mid boost if we have the offsets.
        # From live.py: EQ_PARAMETERS = (sw(0), byte(1), lowGain(2), highGain(3), ..., level(13))
        # Parameter Guide says Mid Gain is usually around offset 6 or 8.
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x19, 0x00], [0x01]) # Just enable for now
        print(" - EQ 1 enabled (manual mid-tweak recommended at 800Hz).")

        # 4. Send/Return 1: RedPlate 4CM Preamp
        # Address: ResidentBlockDefinition("sendReturn1", offset 0x35) in Patch Effect [10, 00, 10, 00]
        # Actual address is [10, 00, 10, 35]
        # Data: SW(1), MODE(0:NORMAL), S-LEVEL(100), R-LEVEL(100), ADJUST(0)
        # S-LEVEL and R-LEVEL are nibbles (2 each)
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x10, 0x35], [0x01, 0x00, 0x06, 0x04, 0x06, 0x04, 0x00])
        print(" - Send/Return 1 (RedPlate) enabled.")

        # 5. Chorus: Scholz shimmer
        # Address: [10, 00, 22, 00], Data: SW(1), TYPE(1:STEREO1), RATE(40), DEPTH(50), P-DELAY(20), LEVEL(40)
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x22, 0x00], [0x01, 0x01, 40, 50, 20, 40])
        print(" - Chorus configured.")

        print("\nPatch base built! Please check your GT-1000.")
        print("Remaining manual steps:")
        print("1. Set EQ1 to +8dB at 800Hz (Q=1).")
        print("2. Set FX1 to Acoustic Sim or Pitch Shifter for the 12-string sound.")
        print("3. Configure Divider 1 to switch between Path A (Clean/Phaser) and Path B (Scholz).")

    finally:
        midi.cm.MIDIClientDispose(client)

if __name__ == "__main__":
    build_boston_patch()
