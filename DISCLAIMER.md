# Disclaimer

This software is an independent open-source project and is **not** affiliated with, authorized, maintained, sponsored, or endorsed by Roland Corporation, BOSS, or any of their affiliates or subsidiaries.

"BOSS", "Roland", and "GT-1000" (including "GT-1000CORE") are registered trademarks of Roland Corporation.

## Hardware & MIDI Interaction Warning

**Use this software at your own risk.**

This software interacts directly with physical hardware (the BOSS GT-1000 and GT-1000CORE) by reading and writing parameters via MIDI System Exclusive (SysEx) messages. 

While this project is designed with safety limits and validators (such as read-back verification and restricted user slots for agent edits), there is always an inherent risk when transmitting low-level control messages to hardware. 

By using this software, you acknowledge and agree that:
- The authors and contributors of this software are not liable for any damage to your computer, MIDI interface, GT-1000 unit, amplifiers, speakers, or other connected equipment.
- The authors and contributors are not responsible for any loss of data, corrupted patches, corrupted system settings, or device malperformance.
- You are responsible for backing up your device settings and patches (e.g., using BOSS Tone Studio) before running any live write commands.
