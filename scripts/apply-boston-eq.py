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

def apply_boston_eq():
    print("Initializing MIDI...")
    midi = live.CoreMIDI()
    destination = live.find_endpoint(midi, midi.cm.MIDIGetNumberOfDestinations, midi.cm.MIDIGetDestination)
    
    if destination is None:
        print("Error: GT-1000 not found.")
        return

    client = live.ctypes.c_uint32()
    output_port = live.ctypes.c_uint32()
    client_name = midi.cf_string("BostonEQSetter")
    midi.cm.MIDIClientCreate(client_name, None, None, live.ctypes.byref(client))
    
    output_name = midi.cf_string("BostonOutput")
    midi.cm.MIDIOutputPortCreate(client, output_name, live.ctypes.byref(output_port))

    try:
        print("Applying Scholz 'Cocked Wah' EQ settings to EQ1...")
        
        # EQ1 Base Address: [10, 00, 19, 00]
        # We'll send a block of data to set:
        # SW(1), TYPE(0), LOW GAIN(20), HIGH GAIN(20), ...
        # Based on BOSS 4-band EQ maps:
        # Offset 5: Mid 1 Freq (14 = 800Hz in many BOSS tables)
        # Offset 6: Mid 1 Q (1 = 0.5 or 2 = 1.0)
        # Offset 7: Mid 1 Gain (0x20 is 0dB, so +8dB is 0x28 or 0x2C depending on scale)
        # Let's try 0x2C for a significant boost (44 decimal).
        
        # Current raw read was: 01 00 20 20 20 0E 01 20 17 01 20 00 1F 20
        # Let's modify:
        # 01 (SW)
        # 00 (TYPE)
        # 20 (LOW GAIN)
        # 20 (HIGH GAIN)
        # 20 (LOW-MID FREQ? or placeholder)
        # 0E (MID 1 FREQ - 800Hz)
        # 01 (MID 1 Q)
        # 2C (MID 1 GAIN - +8dB approx)
        
        eq_data = [0x01, 0x00, 0x20, 0x20, 0x20, 0x0E, 0x01, 0x2C]
        send_dt1(midi, output_port.value, destination, [0x10, 0x00, 0x19, 0x00], eq_data)
        
        print(" - EQ1 updated with 800Hz boost.")
        print(" - Frequency: 800Hz")
        print(" - Gain: ~ +8dB")

    finally:
        midi.cm.MIDIClientDispose(client)

if __name__ == "__main__":
    apply_boston_eq()
