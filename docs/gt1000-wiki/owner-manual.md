# Owner Manual Extraction

Source: current official GT-1000 Owner's Manual `GT-1000_eng08_W.pdf`.

## What The Owner Manual Covers

The Owner's Manual is the user-facing operating guide. It explains physical setup, patch selection, basic editing, saving, menu navigation, MIDI/USB connections, Bluetooth/app connection, footswitch/expression setup, looper use, and specifications.

## Physical Connections

Key jacks and their roles:

| Jack/Port | Role |
|---|---|
| INPUT | Guitar input |
| MAIN OUTPUT L/MONO, R | Guitar amp or mixer output |
| SUB OUTPUT L, R | PA/system output |
| SEND 1/2 and RETURN 1/2 | External effects loop; can be mono or stereo depending settings |
| PHONES | Headphones |
| USB COMPUTER | USB audio/MIDI with a computer |
| MIDI IN/OUT | External MIDI devices |
| CTL4,5/EXP2 and CTL6,7/EXP3 | External footswitches or expression pedals |
| AMP CTL 1/2 | Amp channel switching/control |

Important safety/practical notes:

- Turn down volume and power devices in the correct order before connecting.
- Use only specified expression pedals such as Roland EV-5; incompatible pedals can cause malfunction or damage.
- Use the cord hook to avoid accidental power interruption.

## Basic Use Flow

1. Connect guitar, output, and power.
2. Select the connected output/amplifier type in `MENU > IN/OUT SETTING`.
3. Select a patch from the play screen.
4. Use the effect edit screen to inspect and rearrange the chain.
5. Save edited patches with WRITE when the change should persist.

## Play Screen And Patch Selection

The play screen is the performance surface. It shows patch identity and control assignments. Number switches and bank switches can select patches, depending control mode and system/patch settings.

Patch selection and bank behavior are governed by `CONTROL MODE` and `PLAY OPTION` settings in the Parameter Guide.

## Control Mode

Control mode changes how the built-in switches behave during performance. The manual calls out selecting control mode as a core playing operation. Decode exact switch behavior from:

- User-facing menu: `MENU > CONTROL ASSIGN > CONTROL FUNCTION`
- MIDI data: PatchCommon/SystemControl control function fields
- Existing wiki: [Patch Controls](../midi-reference/patch-controls.md)

## Effect Editing

The GT-1000 shows all effects, output, and send/return as a chain. Basic editing workflow:

1. Press `EFFECT`.
2. Select a block.
3. Toggle the selected effect on/off by pressing the select knob.
4. Edit visible parameters with knobs.
5. Use page buttons to access more parameter pages.
6. Move blocks by holding the selected knob and turning it.

Important for agent behavior:

- The visual chain is user-facing truth for routing.
- The CLI `--view chain` mirrors the chain concept without exposing every parameter.
- The CLI `--view block` mirrors selecting one block for detailed edit.

## STOMPBOX

STOMPBOX stores preferred settings for an effect type and lets multiple patches reuse the same effect setup. Edits to a shared STOMPBOX can affect all patches using that STOMPBOX.

Agent caution:

- Before changing a parameter, determine whether the block is using STOMPBOX data and whether the user expects local patch editing or global STOMPBOX editing.
- The current CLI does not yet decode STOMPBOX selections.

## Saving

Edited sounds must be written if the user wants persistence. Until write, changes affect the temporary/current patch.

Agent caution:

- Treat live SysEx writes as temporary unless implementing explicit patch write.
- Ask before persistent write operations.

## USB, MIDI, Bluetooth

The Owner's Manual describes:

- USB audio/MIDI via the USB COMPUTER port.
- External MIDI device operation.
- Bluetooth/app functionality where available. Bluetooth availability varies by region/unit.

For MIDI details, use [MIDI reference wiki](../midi-reference/README.md).

## Foot Switches And Expression Pedals

The manual covers assigning functions to built-in and external switches/pedals, quick assign from the effect edit screen, expression pedal calibration, and external pedal connection.

Agent mapping:

- Built-in NUM/BANK/CTL/EXP behavior: [Patch Controls](../midi-reference/patch-controls.md)
- Arbitrary parameter mapping: [Assigns](../midi-reference/assigns.md)

## Looper

The looper is a chain element and has assignable switch functions. The manual covers assigning looper functions to switches, playback level, and switch color.

Agent mapping:

- Chain element: `LOOPER`
- PatchEfct looper play level offset: see [Patch Effect](../midi-reference/patch-effect.md)
- Control functions include looper, looper stop, and looper clear.

