from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


ROLAND_ID = 0x41
DEVICE_ID = 0x10
MODEL_ID = [0x00, 0x00, 0x00, 0x4F]
RQ1 = 0x11
DT1 = 0x12

TEMPORARY_PATCH_NAME = [0x10, 0x00, 0x00, 0x00]
TEMPORARY_PATCH_MASTER_BPM = [0x10, 0x00, 0x10, 0x61]
TEMPORARY_PATCH_EFFECT = [0x10, 0x00, 0x10, 0x00]
TEMPORARY_PATCH_COMMON = [0x10, 0x00, 0x00, 0x00]
TEMPORARY_PATCH_STOMPBOX = [0x10, 0x00, 0x01, 0x00]
TEMPORARY_PATCH2_STOMPBOX = [0x10, 0x01, 0x00, 0x00]
TEMPORARY_PATCH3_STOMPBOX = [0x10, 0x02, 0x00, 0x00]
SYSTEM_COMMON = [0x00, 0x00, 0x00, 0x00]
SYSTEM_CONTROL = [0x00, 0x00, 0x10, 0x00]
SYSTEM_MIDI = [0x00, 0x00, 0x30, 0x00]
SYSTEM_IN_OUT = [0x00, 0x00, 0x40, 0x00]
SYSTEM_EFFECTS = [0x00, 0x00, 0x50, 0x00]
SYSTEM_PITCH = [0x00, 0x00, 0x60, 0x00]
SYSTEM_CONTROL2 = [0x00, 0x00, 0x70, 0x00]
SYSTEM_INPUT_SETTING_BASE = [0x00, 0x01, 0x00, 0x00]
SYSTEM_INPUT_SETTING_STRIDE = 0x80
PC_MAP_BASE = [0x00, 0x10, 0x00, 0x00]
PC_MAP_BANK_STRIDE = 0x200
ASSIGN_BASE = [0x10, 0x00, 0x03, 0x00]
ASSIGN_STRIDE = 0x40
USER_PATCH_1 = [0x20, 0x00, 0x00, 0x00]
USER_PATCH2_1 = [0x21, 0x7A, 0x00, 0x00]
USER_PATCH3_1 = [0x23, 0x74, 0x00, 0x00]
USER_PATCH_STRIDE = 0x4000
USER_BANK_COUNT = 50
USER_PATCHES_PER_BANK = 5


class LiveMIDIError(Exception):
    pass


@dataclass(frozen=True)
class PatchReadRequest:
    label: str
    address: list[int]
    size: list[int]

    @property
    def message(self) -> list[int]:
        return build_request_data(self.address, self.size)


@dataclass(frozen=True)
class Parameter:
    id: str
    display_name: str
    offset: int
    kind: str
    values: tuple[str, ...] = ()
    byte_count: int = 1


@dataclass(frozen=True)
class BlockDefinition:
    id: str
    display_name: str
    chain_element_value: int
    address: list[int]
    size: int
    parameters: tuple[Parameter, ...]


@dataclass(frozen=True)
class ResidentBlockDefinition:
    id: str
    display_name: str
    chain_element_value: int
    offset: int
    size: int
    parameters: tuple[Parameter, ...]


def byte(id_: str, display_name: str, offset: int) -> Parameter:
    return Parameter(id_, display_name, offset, "byte")


def switch(id_: str, display_name: str, offset: int) -> Parameter:
    return Parameter(id_, display_name, offset, "bool")


def type_param(id_: str, display_name: str, offset: int, values: list[str]) -> Parameter:
    return Parameter(id_, display_name, offset, "type", tuple(values))


def nibble_param(id_: str, display_name: str, offset: int, byte_count: int) -> Parameter:
    return Parameter(id_, display_name, offset, "nibbles", byte_count=byte_count)


DISTORTION_TYPES = [
    "MID BOOST", "CLEAN BOOST", "TREBLE BOOST", "CRUNCH", "NATURAL OD", "WARM OD",
    "FAT DS", "LEAD DS", "METAL DS", "OCT FUZZ", "A-DIST", "X-OD", "X-DIST",
    "BLUES OD", "OD-1", "T-SCREAM", "TURBO OD", "DIST", "RAT", "GUV DS",
    "DIST+", "METAL ZONE", "'60S FUZZ", "MUFF FUZZ",
]
PREAMP_TYPES = [
    "TRANSPARENT", "NATURAL", "BOUTIQUE", "SUPREME", "MAXIMUM", "JUGGERNAUT",
    "X-CRUNCH", "X-HI GAIN", "X-MODDED", "JC-120", "TWIN COMBO", "DELUXE COMBO",
    "TWEED COMBO", "DIAMOND AMP", "BRIT STACK", "RECTI STACK",
]
MASTER_DELAY_TYPES = [
    "MONO", "PAN", "STEREO1", "STEREO2", "ANALOG", "ANALOG ST", "TAPE",
    "REVERSE", "SHIMMER", "DUAL", "WARP", "TWIST",
]
CHORUS_TYPES = ["MONO", "STEREO 1", "STEREO 2", "DUAL"]

DISTORTION_PARAMETERS = (
    switch("sw", "SW", 0), type_param("type", "TYPE", 1, DISTORTION_TYPES),
    byte("drive", "DRIVE", 2), byte("tone", "TONE", 3), byte("level", "LEVEL", 4),
    byte("bottom", "BOTTOM", 5), byte("directMix", "DIRECT MIX", 6),
    switch("soloSw", "SOLO SW", 7), byte("soloLevel", "SOLO LEVEL", 8),
)
PREAMP_PARAMETERS = (
    switch("sw", "SW", 0), type_param("type", "TYPE", 1, PREAMP_TYPES),
    byte("gain", "GAIN", 2), byte("sag", "SAG", 3), byte("resonance", "RESONANCE", 4),
    byte("level", "LEVEL", 5), byte("bass", "BASS", 6), byte("middle", "MIDDLE", 7),
    byte("treble", "TREBLE", 8), byte("presence", "PRESENCE", 9), switch("bright", "BRIGHT", 10),
    byte("gainSw", "GAIN SW", 11), switch("soloSw", "SOLO SW", 12), byte("soloLevel", "SOLO LEVEL", 13),
)
EQ_PARAMETERS = (
    switch("sw", "SW", 0), byte("type", "TYPE", 1), byte("lowGain", "LOW GAIN", 2),
    byte("highGain", "HIGH GAIN", 3), byte("level", "LEVEL", 13),
)
DELAY_PARAMETERS = (
    switch("sw", "SW", 0), nibble_param("time", "TIME", 1, 4),
    byte("feedback", "FEEDBACK", 5), byte("highCut", "HIGH CUT", 6),
    byte("effectLevel", "EFFECT LEVEL", 7), byte("directLevel", "DIRECT LEVEL", 8),
)
MASTER_DELAY_PARAMETERS = (
    switch("sw", "SW", 0), type_param("type", "TYPE", 1, MASTER_DELAY_TYPES),
    nibble_param("time", "TIME", 2, 4), byte("feedback", "FEEDBACK", 6),
    byte("highCut", "HIGH CUT", 7), byte("effectLevel", "EFFECT LEVEL", 8),
    byte("modRate", "MOD RATE", 9), byte("modDepth", "MOD DEPTH", 10),
    byte("directLevel", "DIRECT LEVEL", 14),
)
CHORUS_PARAMETERS = (
    switch("sw", "SW", 0), type_param("type", "TYPE", 1, CHORUS_TYPES),
    byte("rate", "RATE", 2), byte("depth", "DEPTH", 3), byte("preDelay", "PRE-DELAY", 4),
    byte("effectLevel", "EFFECT LEVEL", 5), byte("waveform", "WAVEFORM", 6),
    byte("lowCut", "LOW CUT", 7), byte("highCut", "HIGH CUT", 8),
)
FX_PARAMETERS = (switch("sw", "SW", 0), byte("type", "TYPE", 1))
REVERB_PARAMETERS = (
    switch("sw", "SW", 0), byte("type", "TYPE", 1), byte("time", "TIME", 2),
    byte("tone", "TONE", 3), byte("density", "DENSITY", 4), byte("effectLevel", "EFFECT LEVEL", 5),
    byte("preDelay", "PRE-DELAY", 6), byte("lowCut", "LOW CUT", 7), byte("highCut", "HIGH CUT", 8),
    byte("directLevel", "DIRECT LEVEL", 16),
)

SUMMARY_BLOCKS = [
    BlockDefinition("comp", "COMPRESSOR", 0, [0x10, 0x00, 0x12, 0x00], 8, (
        switch("sw", "SW", 0), type_param("type", "TYPE", 1, ["BOSS COMP", "X-COMP", "D-COMP", "ORANGE", "STEREO COMP"]),
        byte("sustain", "SUSTAIN", 2), byte("attack", "ATTACK", 3), byte("level", "LEVEL", 4), byte("tone", "TONE", 5),
    )),
    BlockDefinition("dist1", "DISTORTION 1", 1, [0x10, 0x00, 0x13, 0x00], 9, DISTORTION_PARAMETERS),
    BlockDefinition("dist2", "DISTORTION 2", 2, [0x10, 0x00, 0x14, 0x00], 9, DISTORTION_PARAMETERS),
    BlockDefinition("preamp1", "AIRD PREAMP 1", 3, [0x10, 0x00, 0x15, 0x00], 14, PREAMP_PARAMETERS),
    BlockDefinition("preamp2", "AIRD PREAMP 2", 4, [0x10, 0x00, 0x16, 0x00], 14, PREAMP_PARAMETERS),
    BlockDefinition("ns1", "NOISE SUPPRESSOR 1", 5, [0x10, 0x00, 0x17, 0x00], 4, (switch("sw", "SW", 0), byte("threshold", "THRESHOLD", 1), byte("release", "RELEASE", 2), byte("detect", "DETECT", 3))),
    BlockDefinition("ns2", "NOISE SUPPRESSOR 2", 6, [0x10, 0x00, 0x18, 0x00], 4, (switch("sw", "SW", 0), byte("threshold", "THRESHOLD", 1), byte("release", "RELEASE", 2), byte("detect", "DETECT", 3))),
    BlockDefinition("eq1", "EQUALIZER 1", 10, [0x10, 0x00, 0x19, 0x00], 24, EQ_PARAMETERS),
    BlockDefinition("eq2", "EQUALIZER 2", 11, [0x10, 0x00, 0x1A, 0x00], 24, EQ_PARAMETERS),
    BlockDefinition("eq3", "EQUALIZER 3", 12, [0x10, 0x00, 0x1B, 0x00], 24, EQ_PARAMETERS),
    BlockDefinition("eq4", "EQUALIZER 4", 13, [0x10, 0x00, 0x1C, 0x00], 24, EQ_PARAMETERS),
    BlockDefinition("delay1", "DELAY 1", 15, [0x10, 0x00, 0x1D, 0x00], 9, DELAY_PARAMETERS),
    BlockDefinition("delay2", "DELAY 2", 16, [0x10, 0x00, 0x1E, 0x00], 9, DELAY_PARAMETERS),
    BlockDefinition("delay3", "DELAY 3", 17, [0x10, 0x00, 0x1F, 0x00], 9, DELAY_PARAMETERS),
    BlockDefinition("delay4", "DELAY 4", 18, [0x10, 0x00, 0x20, 0x00], 9, DELAY_PARAMETERS),
    BlockDefinition("masterDelay", "MASTER DELAY", 19, [0x10, 0x00, 0x21, 0x00], 31, MASTER_DELAY_PARAMETERS),
    BlockDefinition("chorus", "CHORUS", 14, [0x10, 0x00, 0x22, 0x00], 24, CHORUS_PARAMETERS),
    BlockDefinition("fx1", "FX 1", 7, [0x10, 0x00, 0x23, 0x00], 2, FX_PARAMETERS),
    BlockDefinition("fx2", "FX 2", 8, [0x10, 0x00, 0x3E, 0x00], 2, FX_PARAMETERS),
    BlockDefinition("fx3", "FX 3", 9, [0x10, 0x00, 0x59, 0x00], 2, FX_PARAMETERS),
    BlockDefinition("reverb", "REVERB", 21, [0x10, 0x00, 0x74, 0x00], 42, REVERB_PARAMETERS),
    BlockDefinition("pedalFx", "PEDAL FX", 23, [0x10, 0x00, 0x75, 0x00], 5, (
        switch("sw", "SW", 0), byte("type", "TYPE", 1), byte("effectLevel", "EFFECT LEVEL", 3), byte("directMix", "DIRECT MIX", 4),
    )),
]


def divider_parameters(offset: int) -> tuple[Parameter, ...]:
    return (
        byte("mode", "MODE", offset), byte("channelSelect", "CHANNEL SELECT", offset + 1),
        byte("dynamicSensitivity", "DYNAMIC SENS", offset + 2), byte("dynamicFilter", "DYNAMIC FILTER", offset + 3),
        byte("frequency", "FREQUENCY", offset + 4), byte("curve", "CURVE", offset + 5),
        byte("levelA", "LEVEL A", offset + 6), byte("levelB", "LEVEL B", offset + 7),
        byte("directLevelA", "DIRECT LEVEL A", offset + 8), byte("directLevelB", "DIRECT LEVEL B", offset + 9),
    )


def mixer_parameters(offset: int) -> tuple[Parameter, ...]:
    return (byte("mode", "MODE", offset), byte("balanceA", "BALANCE A", offset + 1), byte("balanceB", "BALANCE B", offset + 2))


def send_return_parameters(offset: int) -> tuple[Parameter, ...]:
    return (
        switch("sw", "SW", offset), byte("mode", "MODE", offset + 1),
        nibble_param("sendLevel", "SEND LEVEL", offset + 2, 2),
        nibble_param("returnLevel", "RETURN LEVEL", offset + 4, 2),
        byte("adjust", "ADJUST", offset + 6),
    )


def speaker_simulator_parameters(offset: int, stereo_link_offset: int | None = None) -> tuple[Parameter, ...]:
    params: list[Parameter] = []
    if stereo_link_offset is not None:
        params.append(switch("stereoLink", "STEREO LINK", stereo_link_offset))
    params.extend([
        byte("speakerType", "SP TYPE", offset), byte("micType", "MIC TYPE", offset + 1),
        byte("micDistance", "MIC DISTANCE", offset + 2), byte("micPosition", "MIC POSITION", offset + 3),
        byte("micLevel", "MIC LEVEL", offset + 4), byte("directMix", "DIRECT MIX", offset + 5),
    ])
    return tuple(params)


RESIDENT_BLOCKS = [
    ResidentBlockDefinition("footVolume", "FOOT VOLUME", 22, 0x00, 13, (
        nibble_param("volumeMin", "VOLUME MIN", 0x00, 4), nibble_param("volumeMax", "VOLUME MAX", 0x04, 4),
        nibble_param("pedalPosition", "PEDAL POSITION", 0x08, 4), byte("curve", "CURVE", 0x0C),
    )),
    ResidentBlockDefinition("divider1", "DIVIDER 1", 35, 0x0D, 10, divider_parameters(0x0D)),
    ResidentBlockDefinition("branchSplit1", "BRANCH SPLIT 1", 36, 0x0D, 10, ()),
    ResidentBlockDefinition("mixer1", "MIXER 1", 37, 0x17, 3, mixer_parameters(0x17)),
    ResidentBlockDefinition("divider2", "DIVIDER 2", 38, 0x1A, 10, divider_parameters(0x1A)),
    ResidentBlockDefinition("branchSplit2", "BRANCH SPLIT 2", 39, 0x1A, 10, ()),
    ResidentBlockDefinition("mixer2", "MIXER 2", 40, 0x24, 3, mixer_parameters(0x24)),
    ResidentBlockDefinition("divider3", "DIVIDER 3", 41, 0x27, 10, divider_parameters(0x27)),
    ResidentBlockDefinition("branchSplit3", "BRANCH SPLIT 3", 42, 0x27, 10, ()),
    ResidentBlockDefinition("mixer3", "MIXER 3", 43, 0x31, 3, mixer_parameters(0x31)),
    ResidentBlockDefinition("sendReturn1", "SEND/RETURN 1", 24, 0x35, 7, send_return_parameters(0x35)),
    ResidentBlockDefinition("sendReturn2", "SEND/RETURN 2", 25, 0x3C, 7, send_return_parameters(0x3C)),
    ResidentBlockDefinition("looper", "LOOPER", 26, 0x44, 1, (byte("playLevel", "PLAY LEVEL", 0x44),)),
    ResidentBlockDefinition("subSpeakerSimulatorL", "SUB SP.SIMULATOR L", 27, 0x52, 7, speaker_simulator_parameters(0x53, 0x52)),
    ResidentBlockDefinition("subSpeakerSimulatorR", "SUB SP.SIMULATOR R", 28, 0x59, 6, speaker_simulator_parameters(0x59)),
    ResidentBlockDefinition("mainSpeakerSimulatorL", "MAIN SP.SIMULATOR L", 29, 0x45, 7, speaker_simulator_parameters(0x46, 0x45)),
    ResidentBlockDefinition("mainSpeakerSimulatorR", "MAIN SP.SIMULATOR R", 30, 0x4C, 6, speaker_simulator_parameters(0x4C)),
]


def seven_bit_address(value: int) -> list[int]:
    return [(value >> shift) & 0x7F for shift in (21, 14, 7, 0)]


INITIAL_READS = [
    PatchReadRequest("Patch Name", TEMPORARY_PATCH_NAME, [0x00, 0x00, 0x00, 0x10]),
    PatchReadRequest("Master BPM", TEMPORARY_PATCH_MASTER_BPM, [0x00, 0x00, 0x00, 0x04]),
    PatchReadRequest("Patch Effect", TEMPORARY_PATCH_EFFECT, [0x00, 0x00, 0x01, 0x1C]),
    PatchReadRequest("Patch Common", TEMPORARY_PATCH_COMMON, [0x00, 0x00, 0x00, 0x7E]),
    PatchReadRequest("System Control", SYSTEM_CONTROL, [0x00, 0x00, 0x00, 0x36]),
]

BLOCK_READS = [
    PatchReadRequest(block.display_name, block.address, seven_bit_address(block.size))
    for block in SUMMARY_BLOCKS
]

READ_PLAN = INITIAL_READS + BLOCK_READS


class MIDIPacket(ctypes.Structure):
    _fields_ = [
        ("timeStamp", ctypes.c_uint64),
        ("length", ctypes.c_uint16),
        ("data", ctypes.c_ubyte * 256),
    ]


class MIDIPacketList(ctypes.Structure):
    _fields_ = [("numPackets", ctypes.c_uint32), ("packet", MIDIPacket)]


ReadProc = ctypes.CFUNCTYPE(None, ctypes.POINTER(MIDIPacketList), ctypes.c_void_p, ctypes.c_void_p)
BlockInvoke = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(MIDIPacketList), ctypes.c_void_p)


class BlockDescriptor(ctypes.Structure):
    _fields_ = [("reserved", ctypes.c_ulong), ("size", ctypes.c_ulong)]


class BlockLiteral(ctypes.Structure):
    _fields_ = [
        ("isa", ctypes.c_void_p),
        ("flags", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("invoke", ctypes.c_void_p),
        ("descriptor", ctypes.POINTER(BlockDescriptor)),
    ]


class MIDIReadBlock:
    def __init__(self, callback: Callable[[ctypes.POINTER(MIDIPacketList)], None]) -> None:
        libsystem = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        self.descriptor = BlockDescriptor(0, ctypes.sizeof(BlockLiteral))
        self.invoke = BlockInvoke(lambda _block, packet_list, _refcon: callback(packet_list))
        self.literal = BlockLiteral(
            ctypes.c_void_p.in_dll(libsystem, "_NSConcreteGlobalBlock").value,
            1 << 28,  # BLOCK_IS_GLOBAL
            0,
            ctypes.cast(self.invoke, ctypes.c_void_p).value,
            ctypes.pointer(self.descriptor),
        )

    @property
    def pointer(self) -> ctypes.c_void_p:
        return ctypes.cast(ctypes.pointer(self.literal), ctypes.c_void_p)


class CoreMIDI:
    def __init__(self) -> None:
        self.cm = ctypes.CDLL("/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
        self.cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        self._configure()
        self.k_midi_property_name = ctypes.c_void_p.in_dll(self.cm, "kMIDIPropertyName")

    def _configure(self) -> None:
        self.cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        self.cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        self.cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        self.cf.CFStringGetCString.restype = ctypes.c_bool
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]

        self.cm.MIDIGetNumberOfDestinations.restype = ctypes.c_ulong
        self.cm.MIDIGetNumberOfSources.restype = ctypes.c_ulong
        self.cm.MIDIGetDestination.argtypes = [ctypes.c_ulong]
        self.cm.MIDIGetDestination.restype = ctypes.c_uint32
        self.cm.MIDIGetSource.argtypes = [ctypes.c_ulong]
        self.cm.MIDIGetSource.restype = ctypes.c_uint32
        self.cm.MIDIObjectGetStringProperty.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self.cm.MIDIObjectGetStringProperty.restype = ctypes.c_int32
        self.cm.MIDIClientCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        self.cm.MIDIClientCreate.restype = ctypes.c_int32
        self.cm.MIDIOutputPortCreate.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        self.cm.MIDIOutputPortCreate.restype = ctypes.c_int32
        self.cm.MIDIInputPortCreateWithBlock.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
        self.cm.MIDIInputPortCreateWithBlock.restype = ctypes.c_int32
        self.cm.MIDIPortConnectSource.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        self.cm.MIDIPortConnectSource.restype = ctypes.c_int32
        self.cm.MIDISend.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        self.cm.MIDISend.restype = ctypes.c_int32
        self.cm.MIDIClientDispose.argtypes = [ctypes.c_uint32]
        self.cm.MIDIPacketListInit.argtypes = [ctypes.c_void_p]
        self.cm.MIDIPacketListInit.restype = ctypes.c_void_p
        self.cm.MIDIPacketListAdd.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_ulong, ctypes.c_void_p]
        self.cm.MIDIPacketListAdd.restype = ctypes.c_void_p

    def cf_string(self, text: str) -> ctypes.c_void_p:
        return self.cf.CFStringCreateWithCString(None, text.encode("utf-8"), 0x08000100)

    def endpoint_name(self, endpoint: int) -> str:
        value = ctypes.c_void_p()
        status = self.cm.MIDIObjectGetStringProperty(endpoint, self.k_midi_property_name, ctypes.byref(value))
        if status != 0 or not value.value:
            return ""
        buffer = ctypes.create_string_buffer(512)
        ok = self.cf.CFStringGetCString(value, buffer, len(buffer), 0x08000100)
        self.cf.CFRelease(value)
        return buffer.value.decode("utf-8") if ok else ""

    def destinations(self) -> list[dict[str, Any]]:
        return self._endpoints(self.cm.MIDIGetNumberOfDestinations, self.cm.MIDIGetDestination)

    def sources(self) -> list[dict[str, Any]]:
        return self._endpoints(self.cm.MIDIGetNumberOfSources, self.cm.MIDIGetSource)

    def _endpoints(self, count_fn: Callable[[], int], endpoint_fn: Callable[[int], int]) -> list[dict[str, Any]]:
        endpoints = []
        for index in range(count_fn()):
            name = self.endpoint_name(endpoint_fn(index)) or "Unnamed MIDI Endpoint"
            endpoints.append({
                "index": index,
                "name": name,
                "isGT1000": "gt-1000" in name.lower(),
                "isDefaultGT1000Endpoint": is_default_gt1000_endpoint(name),
            })
        return endpoints


def list_ports() -> dict[str, Any]:
    midi = CoreMIDI()
    return {"destinations": midi.destinations(), "sources": midi.sources()}


def read_current_patch(timeout: float, requests: list[PatchReadRequest] | None = None) -> dict[str, Any]:
    state = transact_requests(timeout=timeout, requests=requests or READ_PLAN)
    return state.snapshot


def read_user_patch(slot: str, timeout: float, requests: list[PatchReadRequest] | None = None) -> dict[str, Any]:
    patch_base = user_patch_base(slot)
    source_requests = requests or READ_PLAN
    remapped_requests = [
        PatchReadRequest(request.label, remap_temporary_patch_address(request.address, patch_base), request.size)
        for request in source_requests
    ]
    raw = read_data_sets(timeout=timeout, requests=remapped_requests)
    snapshot = empty_snapshot()
    for source_request, remapped_request in zip(source_requests, remapped_requests):
        data = raw.get(address_key(remapped_request.address))
        if data is not None:
            apply_data_set(snapshot, source_request.address, data)
    snapshot["sourceSlot"] = normalize_user_slot(slot)
    snapshot["sourceAddress"] = hex_bytes(patch_base)
    return snapshot


def user_patch_base(slot: str) -> list[int]:
    normalized = normalize_user_slot(slot)
    bank_text, number_text = normalized[1:].split("-", 1)
    bank = int(bank_text)
    number = int(number_text)
    patch_index = (bank - 1) * USER_PATCHES_PER_BANK + number
    return seven_bit_address(seven_bit_address_value(USER_PATCH_1) + (patch_index - 1) * USER_PATCH_STRIDE)


def normalize_user_slot(slot: str) -> str:
    text = slot.strip().upper()
    if not text.startswith("U") or "-" not in text:
        raise ValueError("slot must look like U01-1")
    bank_text, number_text = text[1:].split("-", 1)
    try:
        bank = int(bank_text)
        number = int(number_text)
    except ValueError as error:
        raise ValueError("slot must look like U01-1") from error
    if not 1 <= bank <= USER_BANK_COUNT:
        raise ValueError(f"user bank must be U01...U{USER_BANK_COUNT:02d}")
    if not 1 <= number <= USER_PATCHES_PER_BANK:
        raise ValueError("user patch number must be 1...5")
    return f"U{bank:02d}-{number}"


def normalize_user_bank(bank: str) -> str:
    text = bank.strip().upper()
    if not text.startswith("U"):
        raise ValueError("bank must look like U01")
    try:
        bank_number = int(text[1:])
    except ValueError as error:
        raise ValueError("bank must look like U01") from error
    if not 1 <= bank_number <= USER_BANK_COUNT:
        raise ValueError(f"user bank must be U01...U{USER_BANK_COUNT:02d}")
    return f"U{bank_number:02d}"


def user_bank_slots(bank: str) -> list[str]:
    normalized = normalize_user_bank(bank)
    return [f"{normalized}-{number}" for number in range(1, USER_PATCHES_PER_BANK + 1)]


def remap_temporary_patch_address(address: list[int], patch_base: list[int]) -> list[int]:
    value = seven_bit_address_value(address)
    temporary_base = seven_bit_address_value(TEMPORARY_PATCH_COMMON)
    if value < temporary_base:
        return address
    return seven_bit_address(seven_bit_address_value(patch_base) + (value - temporary_base))


def read_data_sets(timeout: float, requests: list[PatchReadRequest]) -> dict[str, list[int]]:
    state = transact_requests(timeout=timeout, requests=requests)
    return dict(state.data_sets)


def read_system_section(address: list[int], size: list[int], timeout: float) -> dict[str, list[int]]:
    request = PatchReadRequest("System Section", address, size)
    return read_data_sets(timeout=timeout, requests=[request])


@dataclass(frozen=True)
class PatchWrite:
    label: str
    address: list[int]
    data: list[int]

    @property
    def message(self) -> list[int]:
        return build_data_set(self.address, self.data)

    @property
    def read_request(self) -> PatchReadRequest:
        return PatchReadRequest(self.label, self.address, seven_bit_address(len(self.data)))


def write_data_sets(writes: list[PatchWrite], delay: float = 0.05) -> None:
    midi = CoreMIDI()
    destination = find_endpoint(midi, midi.cm.MIDIGetNumberOfDestinations, midi.cm.MIDIGetDestination)
    if destination is None:
        raise LiveMIDIError("No GT-1000 MIDI destination found")

    client = ctypes.c_uint32()
    output_port = ctypes.c_uint32()
    client_name = midi.cf_string("GT1000PythonWriteClient")
    status = midi.cm.MIDIClientCreate(client_name, None, None, ctypes.byref(client))
    midi.cf.CFRelease(client_name)
    check_status("MIDIClientCreate", status)

    output_name = midi.cf_string("GT1000PythonWriteOutput")
    status = midi.cm.MIDIOutputPortCreate(client, output_name, ctypes.byref(output_port))
    midi.cf.CFRelease(output_name)
    check_status("MIDIOutputPortCreate", status)

    try:
        for write in writes:
            send_message(midi, output_port.value, destination, write.message)
            time.sleep(delay)
    finally:
        if client.value:
            midi.cm.MIDIClientDispose(client)


def send_channel_voice(message: list[int], delay: float = 0.1) -> None:
    if len(message) not in {2, 3}:
        raise ValueError("channel voice messages must be two or three bytes")
    midi = CoreMIDI()
    destination = find_endpoint(midi, midi.cm.MIDIGetNumberOfDestinations, midi.cm.MIDIGetDestination)
    if destination is None:
        raise LiveMIDIError("No GT-1000 MIDI destination found")

    client = ctypes.c_uint32()
    output_port = ctypes.c_uint32()
    client_name = midi.cf_string("GT1000PythonChannelVoiceClient")
    status = midi.cm.MIDIClientCreate(client_name, None, None, ctypes.byref(client))
    midi.cf.CFRelease(client_name)
    check_status("MIDIClientCreate", status)

    output_name = midi.cf_string("GT1000PythonChannelVoiceOutput")
    status = midi.cm.MIDIOutputPortCreate(client, output_name, ctypes.byref(output_port))
    midi.cf.CFRelease(output_name)
    check_status("MIDIOutputPortCreate", status)

    try:
        send_message(midi, output_port.value, destination, message)
        time.sleep(delay)
    finally:
        if client.value:
            midi.cm.MIDIClientDispose(client)


def transact_requests(timeout: float, requests: list[PatchReadRequest]) -> "PatchReadState":
    midi = CoreMIDI()
    state = PatchReadState()

    destination = find_endpoint(midi, midi.cm.MIDIGetNumberOfDestinations, midi.cm.MIDIGetDestination)
    source = find_endpoint(midi, midi.cm.MIDIGetNumberOfSources, midi.cm.MIDIGetSource)
    if destination is None:
        raise LiveMIDIError("No GT-1000 MIDI destination found")
    if source is None:
        raise LiveMIDIError("No GT-1000 MIDI source found")

    client = ctypes.c_uint32()
    output_port = ctypes.c_uint32()
    input_port = ctypes.c_uint32()
    client_name = midi.cf_string("GT1000PythonClient")
    status = midi.cm.MIDIClientCreate(client_name, None, None, ctypes.byref(client))
    midi.cf.CFRelease(client_name)
    check_status("MIDIClientCreate", status)

    output_name = midi.cf_string("GT1000PythonOutput")
    status = midi.cm.MIDIOutputPortCreate(client, output_name, ctypes.byref(output_port))
    midi.cf.CFRelease(output_name)
    check_status("MIDIOutputPortCreate", status)

    callback = MIDIReadBlock(lambda packet_list: state.handle(packets_from_packet_list(packet_list)))
    input_name = midi.cf_string("GT1000PythonInput")
    status = midi.cm.MIDIInputPortCreateWithBlock(client, input_name, ctypes.byref(input_port), callback.pointer)
    midi.cf.CFRelease(input_name)
    check_status("MIDIInputPortCreate", status)

    status = midi.cm.MIDIPortConnectSource(input_port, source, None)
    check_status("MIDIPortConnectSource", status)

    state.expect([request.address for request in requests])

    try:
        wait_for_quiet_input(state)
        deadline = time.monotonic() + timeout
        
        # Send all requests in a burst with small inter-message delays
        for request in requests:
            send_message(midi, output_port.value, destination, request.message)
            time.sleep(0.01) # Small delay to avoid clogging the buffer

        # Wait for the full set of replies
        while time.monotonic() < deadline:
            if state.has_expected_responses():
                return state
            time.sleep(0.05)

        if state.has_expected_responses():
            return state
        raise LiveMIDIError(f"Timed out waiting for GT-1000 patch replies. Missing: {list(state.expected - state.received)}\nPartial snapshot:\n{snapshot_text_summary(state.snapshot)}")
    finally:
        # Keep callback alive until after the read loop exits.
        _ = callback
        if client.value:
            midi.cm.MIDIClientDispose(client)


class PatchReadState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.assembler = SysExAssembler()
        self.snapshot = empty_snapshot()
        self.expected: set[str] = set()
        self.received: set[str] = set()
        self.data_sets: dict[str, list[int]] = {}
        self.last_packet_at: float | None = time.monotonic()

    def expect(self, addresses: list[list[int]]) -> None:
        with self.lock:
            self.assembler = SysExAssembler()
            self.expected = {address_key(address) for address in addresses}
            self.received.clear()

    def has_expected_responses(self) -> bool:
        with self.lock:
            return self.expected.issubset(self.received)

    def has_response(self, address: list[int]) -> bool:
        with self.lock:
            return address_key(address) in self.received

    def handle(self, packets: list[list[int]]) -> None:
        with self.lock:
            if packets:
                self.last_packet_at = time.monotonic()
            if os.environ.get("GT1000_DEBUG_MIDI"):
                for packet in packets:
                    print(
                        "packet",
                        len(packet),
                        " ".join(f"{byte:02X}" for byte in packet[:16]),
                        file=sys.stderr,
                    )
            for message in self.assembler.assemble(packets):
                if os.environ.get("GT1000_DEBUG_MIDI"):
                    print(
                        "message",
                        len(message),
                        " ".join(f"{byte:02X}" for byte in message[:16]),
                        file=sys.stderr,
                    )
                data_set = parse_data_set(message)
                if data_set is None:
                    continue
                address, data = data_set
                key = address_key(address)
                self.received.add(key)
                self.data_sets[key] = data
                apply_data_set(self.snapshot, address, data)

    def quiet_for(self) -> float:
        with self.lock:
            if self.last_packet_at is None:
                return float("inf")
            return time.monotonic() - self.last_packet_at


def wait_for_quiet_input(state: PatchReadState, quiet_seconds: float = 0.5, max_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        if state.quiet_for() >= quiet_seconds:
            return
        time.sleep(0.05)


class SysExAssembler:
    def __init__(self) -> None:
        self.buffer: list[int] = []

    def assemble(self, packets: list[list[int]]) -> list[list[int]]:
        messages = []
        for packet in packets:
            for byte_value in packet:
                if byte_value == 0xF0:
                    self.buffer = [byte_value]
                elif self.buffer:
                    self.buffer.append(byte_value)
                if byte_value == 0xF7 and self.buffer:
                    messages.append(self.buffer)
                    self.buffer = []
        return messages


def send_message(midi: CoreMIDI, output_port: int, destination: int, message: list[int]) -> None:
    packet_list_size = max(1024, len(message) + 256)
    packet_list = ctypes.create_string_buffer(packet_list_size)
    data = (ctypes.c_ubyte * len(message))(*message)
    packet = midi.cm.MIDIPacketListInit(ctypes.byref(packet_list))
    packet = midi.cm.MIDIPacketListAdd(ctypes.byref(packet_list), packet_list_size, packet, 0, len(message), data)
    if not packet:
        raise LiveMIDIError("MIDIPacketListAdd failed")
    check_status("MIDISend", midi.cm.MIDISend(output_port, destination, ctypes.byref(packet_list)))


def packets_from_packet_list(packet_list: ctypes.POINTER(MIDIPacketList)) -> list[list[int]]:
    packets = []
    count = int(packet_list.contents.numPackets)
    base = ctypes.addressof(packet_list.contents)
    if os.environ.get("GT1000_DEBUG_MIDI"):
        raw = list(ctypes.string_at(base, 64))
        print("packetlist", count, " ".join(f"{byte:02X}" for byte in raw), file=sys.stderr)
    offset = 4
    for _ in range(count):
        packet_address = base + offset
        packet = MIDIPacket.from_address(packet_address)
        length = int(packet.length)
        if length <= 0 or length > 4096:
            break
        data_address = packet_address + MIDIPacket.data.offset
        packets.append(list(ctypes.string_at(data_address, length)))
        next_offset = MIDIPacket.data.offset + length
        offset += (next_offset + 3) & ~3
    return packets


def find_endpoint(midi: CoreMIDI, count_fn: Callable[[], int], endpoint_fn: Callable[[int], int]) -> int | None:
    for index in range(count_fn()):
        endpoint = endpoint_fn(index)
        if is_default_gt1000_endpoint(midi.endpoint_name(endpoint)):
            return endpoint
    return None


def check_status(operation: str, status: int) -> None:
    if status != 0:
        raise LiveMIDIError(f"{operation} failed with OSStatus {status}")


def is_default_gt1000_endpoint(name: str) -> bool:
    lower = name.lower()
    return "gt-1000" in lower and "daw" not in lower and "ctrl" not in lower


def checksum(address: list[int], data: list[int]) -> int:
    return (128 - (sum(address + data) % 128)) % 128


def build_request_data(address: list[int], size: list[int]) -> list[int]:
    message = [0xF0, ROLAND_ID, DEVICE_ID] + MODEL_ID + [RQ1] + address + size
    message.append(checksum(address, size))
    message.append(0xF7)
    return message


def build_data_set(address: list[int], data: list[int]) -> list[int]:
    message = [0xF0, ROLAND_ID, DEVICE_ID] + MODEL_ID + [DT1] + address + data
    message.append(checksum(address, data))
    message.append(0xF7)
    return message


def parse_data_set(message: list[int]) -> tuple[list[int], list[int]] | None:
    if len(message) < 14 or message[0] != 0xF0 or message[-1] != 0xF7:
        return None
    if message[1] != ROLAND_ID or message[3:7] != MODEL_ID or message[7] != DT1:
        return None
    address = message[8:12]
    data = message[12:-2]
    if checksum(address, data) != message[-2]:
        return None
    return address, data


def seven_bit_address_value(address: list[int]) -> int:
    value = 0
    for byte_value in address:
        value = (value << 7) | byte_value
    return value


def address_adding(address: list[int], offset: int) -> list[int]:
    return seven_bit_address(seven_bit_address_value(address) + offset)


def integer_from_nibbles(values: list[int]) -> int | None:
    if not values or any(value > 0x0F for value in values):
        return None
    result = 0
    for value in values:
        result = (result << 4) | value
    return result


def nibbles_for(value: int, byte_count: int = 4) -> list[int]:
    if value < 0 or byte_count <= 0:
        raise ValueError("nibble values require a non-negative value and positive byte count")
    return [(value >> shift) & 0x0F for shift in range((byte_count - 1) * 4, -1, -4)]


def bpm_from_data(data: list[int]) -> float | None:
    value = integer_from_nibbles(data)
    if value is None or value < 400 or value > 2500:
        return None
    return value / 10.0


def empty_snapshot() -> dict[str, Any]:
    return {
        "patchName": None,
        "masterBPM": None,
        "masterPatchLevel": None,
        "masterKey": None,
        "ampControl1Enabled": None,
        "ampControl2Enabled": None,
        "masterCarryoverEnabled": None,
        "controlAssignTempoHoldEnabled": None,
        "controlAssignInputSensitivity": None,
        "signalChainSummary": "",
        "signalChainElements": [],
        "blocks": [],
        "rawSections": [],
    }


def apply_data_set(snapshot: dict[str, Any], address: list[int], data: list[int]) -> None:
    if address == TEMPORARY_PATCH_NAME:
        snapshot["patchName"] = decode_patch_name(data)
    
    # Check for specific section addresses
    if address == TEMPORARY_PATCH_COMMON:
        apply_raw_section(snapshot, "patchCommon", "Patch Common", address, data)
    elif address == SYSTEM_CONTROL:
        apply_raw_section(snapshot, "systemControl", "System Control", address, data)
    elif address == TEMPORARY_PATCH_MASTER_BPM:
        snapshot["masterBPM"] = bpm_from_data(data)
    elif address == TEMPORARY_PATCH_EFFECT:
        apply_patch_effect(snapshot, data)
    else:
        definition = next((block for block in SUMMARY_BLOCKS if block.address == address), None)
        if definition:
            apply_block_summary(snapshot, definition, data)
        elif is_assign_address(address):
            apply_assign_data(snapshot, address, data)
    snapshot["signalChainSummary"] = snapshot_text_summary(snapshot)


def is_assign_address(address: list[int]) -> bool:
    val = seven_bit_address_value(address)
    base = seven_bit_address_value(ASSIGN_BASE)
    if val < base: return False
    offset = val - base
    return offset % ASSIGN_STRIDE == 0 and 0 <= offset < (16 * ASSIGN_STRIDE)


def apply_assign_data(snapshot: dict[str, Any], address: list[int], data: list[int]) -> None:
    val = seven_bit_address_value(address)
    base = seven_bit_address_value(ASSIGN_BASE)
    index = (val - base) // ASSIGN_STRIDE + 1
    apply_raw_section(snapshot, f"Assign {index}", f"Assign {index}", address, data)


def apply_raw_section(snapshot: dict[str, Any], section_id: str, label: str, address: list[int], data: list[int]) -> None:
    snapshot["rawSections"] = [section for section in snapshot["rawSections"] if section["id"] != section_id]
    snapshot["rawSections"].append({
        "id": section_id,
        "label": label,
        "address": hex_bytes(address),
        "dataHex": hex_string(data),
    })


def decode_patch_name(data: list[int]) -> str:
    return bytes(byte for byte in data[:16] if 0x20 <= byte <= 0x7E).decode("ascii", errors="ignore").strip()


def apply_patch_effect(snapshot: dict[str, Any], data: list[int]) -> None:
    snapshot["rawSections"] = [section for section in snapshot["rawSections"] if section["id"] != "patchEffect"]
    snapshot["rawSections"].append({
        "id": "patchEffect",
        "label": "Patch Effect",
        "address": hex_bytes(TEMPORARY_PATCH_EFFECT),
        "dataHex": hex_string(data),
    })
    snapshot["masterPatchLevel"] = data[0x60] if len(data) > 0x60 else None
    bpm = bpm_from_data(data[0x61:0x65])
    if bpm is not None:
        snapshot["masterBPM"] = bpm
    snapshot["masterKey"] = master_key_name(data[0x65]) if len(data) > 0x65 else None
    snapshot["ampControl1Enabled"] = data[0x66] == 1 if len(data) > 0x66 else None
    snapshot["ampControl2Enabled"] = data[0x67] == 1 if len(data) > 0x67 else None
    snapshot["masterCarryoverEnabled"] = data[0x99] == 1 if len(data) > 0x99 else None
    snapshot["controlAssignTempoHoldEnabled"] = data[0x9A] == 1 if len(data) > 0x9A else None
    snapshot["controlAssignInputSensitivity"] = data[0x9B] if len(data) > 0x9B else None
    chain_start = 0x68
    elements = []
    for index, raw_value in enumerate(data[chain_start:chain_start + 49]):
        display_name = chain_element_name(raw_value)
        elements.append({
            "id": f"chain-{index + 1}",
            "position": index + 1,
            "address": hex_bytes(address_adding(TEMPORARY_PATCH_EFFECT, chain_start + index)),
            "rawValue": raw_value,
            "displayName": display_name,
            "isReserved": display_name == "(RESERVED)",
            "isOutput": display_name in {"SUB OUT L", "SUB OUT R", "MAIN OUT L", "MAIN OUT R"},
        })
    snapshot["signalChainElements"] = elements
    for definition in RESIDENT_BLOCKS:
        raw_data = data[definition.offset:definition.offset + definition.size]
        upsert_block(snapshot, block_from_definition(snapshot, definition, raw_data, base_data=data))
    refresh_block_membership(snapshot)


def apply_block_summary(snapshot: dict[str, Any], definition: BlockDefinition, data: list[int]) -> None:
    upsert_block(snapshot, block_from_definition(snapshot, definition, data))


def block_from_definition(
    snapshot: dict[str, Any],
    definition: BlockDefinition | ResidentBlockDefinition,
    data: list[int],
    *,
    base_data: list[int] | None = None,
) -> dict[str, Any]:
    raw_source = base_data if base_data is not None else data
    parameters = []
    for parameter in definition.parameters:
        raw_value = raw_parameter_value(parameter, raw_source if base_data is not None else data)
        if raw_value is None:
            continue
        parameters.append({
            "id": parameter.id,
            "displayName": parameter.display_name,
            "rawValue": raw_value,
            "displayValue": display_parameter_value(parameter, raw_value),
        })
    sw = next((param for param in parameters if param["id"] == "sw"), None)
    type_value = next((param for param in parameters if param["id"] == "type"), None)
    chain_values = {element["rawValue"] for element in snapshot["signalChainElements"]}
    address = definition.address if isinstance(definition, BlockDefinition) else address_adding(TEMPORARY_PATCH_EFFECT, definition.offset)
    return {
        "id": definition.id,
        "displayName": definition.display_name,
        "chainElementValue": definition.chain_element_value,
        "address": hex_bytes(address),
        "isInSignalChain": definition.chain_element_value in chain_values,
        "isEnabled": (sw["rawValue"] == 1) if sw else None,
        "typeName": type_value["displayValue"] if type_value else None,
        "parameters": parameters,
        "rawDataHex": hex_string(data),
    }


def raw_parameter_value(parameter: Parameter, data: list[int]) -> int | None:
    if parameter.kind in {"byte", "bool", "type"}:
        return data[parameter.offset] if len(data) > parameter.offset else None
    return integer_from_nibbles(data[parameter.offset:parameter.offset + parameter.byte_count])


def display_parameter_value(parameter: Parameter, raw_value: int) -> str | None:
    if parameter.kind == "bool":
        return "ON" if raw_value else "OFF"
    if parameter.kind == "type" and 0 <= raw_value < len(parameter.values):
        return parameter.values[raw_value]
    return None


def upsert_block(snapshot: dict[str, Any], block: dict[str, Any]) -> None:
    snapshot["blocks"] = [existing for existing in snapshot["blocks"] if existing["id"] != block["id"]]
    snapshot["blocks"].append(block)
    snapshot["blocks"].sort(key=lambda item: (item["chainElementValue"], item["id"]))


def refresh_block_membership(snapshot: dict[str, Any]) -> None:
    chain_values = {element["rawValue"] for element in snapshot["signalChainElements"]}
    for block in snapshot["blocks"]:
        block["isInSignalChain"] = block["chainElementValue"] in chain_values


def snapshot_text_summary(snapshot: dict[str, Any]) -> str:
    lines = []
    if snapshot.get("patchName"):
        lines.append(f"Patch: {snapshot['patchName']}")
    if snapshot.get("masterBPM") is not None:
        lines.append(f"Master BPM: {snapshot['masterBPM']:.1f}")
    if snapshot.get("masterPatchLevel") is not None:
        lines.append(f"Patch Level: {snapshot['masterPatchLevel']}")
    elements = snapshot.get("signalChainElements") or []
    if elements:
        lines.append("Signal chain: " + " -> ".join(element["displayName"] for element in elements))
    else:
        lines.append("Signal chain: not decoded yet")
    return "\n".join(lines)


def master_key_name(raw_value: int) -> str | None:
    names = ["C(Am)", "Db(Bbm)", "D(Bm)", "Eb(Cm)", "E(C#m)", "F(Dm)", "F#(D#m)", "G(Em)", "Ab(Fm)", "A(F#m)", "Bb(Gm)", "B(G#m)"]
    return names[raw_value] if 0 <= raw_value < len(names) else None


def chain_element_name(raw_value: int) -> str:
    names = {
        0: "COMPRESSOR", 1: "DISTORTION 1", 2: "DISTORTION 2", 3: "AIRD PREAMP 1", 4: "AIRD PREAMP 2",
        5: "NOISE SUPPRESSOR 1", 6: "NOISE SUPPRESSOR 2", 7: "FX 1", 8: "FX 2", 9: "FX 3",
        10: "EQUALIZER 1", 11: "EQUALIZER 2", 12: "EQUALIZER 3", 13: "EQUALIZER 4", 14: "CHORUS",
        15: "DELAY 1", 16: "DELAY 2", 17: "DELAY 3", 18: "DELAY 4", 19: "MASTER DELAY",
        20: "(RESERVED)", 21: "REVERB", 22: "FOOT VOLUME", 23: "PEDAL FX", 24: "SEND/RETURN 1",
        25: "SEND/RETURN 2", 26: "LOOPER", 27: "SUB SP.SIMULATOR L", 28: "SUB SP.SIMULATOR R",
        29: "MAIN SP.SIMULATOR L", 30: "MAIN SP.SIMULATOR R", 31: "BYPASS SUB L", 32: "BYPASS SUB R",
        33: "BYPASS MAIN L", 34: "BYPASS MAIN R", 35: "DIVIDER 1", 36: "BRANCH SPLIT1", 37: "MIXER 1",
        38: "DIVIDER 2", 39: "BRANCH SPLIT2", 40: "MIXER 2", 41: "DIVIDER 3", 42: "BRANCH SPLIT3",
        43: "MIXER 3", 44: "(RESERVED)", 45: "SUB OUT L", 46: "SUB OUT R", 47: "MAIN OUT L", 48: "MAIN OUT R",
    }
    return names.get(raw_value, f"UNKNOWN {raw_value}")


def address_key(address: list[int]) -> str:
    return " ".join(f"{byte:02X}" for byte in address)


def hex_bytes(values: list[int]) -> list[str]:
    return [f"{value:02X}" for value in values]


def hex_string(values: list[int]) -> str:
    return " ".join(f"{value:02X}" for value in values)
