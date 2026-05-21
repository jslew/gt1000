import sys
import unittest

sys.dont_write_bytecode = True

from tools.gt1000 import live, patch_edit


class PatchEditTests(unittest.TestCase):
    def test_default_plan_builds_minimal_no_branch_chain_and_off_writes(self):
        plan = patch_edit.build_default_patch_plan("PY DEFAULT")
        chain = next(write for write in plan.writes if write.label == "Minimal no-branch chain")

        self.assertEqual(chain.address, [0x10, 0x00, 0x10, 0x68])
        self.assertEqual(chain.data[:5], [0, 34, 33, 47, 48])
        self.assertEqual(len(chain.data), 49)
        self.assertEqual(len(set(chain.data)), 49)
        self.assertEqual(chain.data[-1], 44)
        self.assertIn(
            live.PatchWrite("CTL1 direct function off", [0x10, 0x00, 0x00, 0x31], [0, 0]),
            plan.writes,
        )
        self.assertIn(live.PatchWrite("dist1 switch off", [0x10, 0x00, 0x13, 0x00], [0]), plan.writes)
        self.assertIn(live.PatchWrite("Assign 16 disabled", [0x10, 0x00, 0x0A, 0x40], patch_edit.DISABLED_ASSIGN_DATA), plan.writes)

    def test_4cm_template_chain_and_ctl1_direct_mapping(self):
        plan = patch_edit.build_4cm_template_plan("PY 4CM CTL1")
        chain = next(write for write in plan.writes if write.label == "4CM CTL1 divider template chain")

        self.assertEqual(chain.data[:12], [0, 35, 14, 36, 1, 15, 37, 24, 34, 33, 47, 48])
        self.assertEqual(len(set(chain.data)), 49)
        self.assertEqual(chain.data[-1], 44)
        self.assertIn(
            live.PatchWrite(
                "CTL1 direct function: DIVIDER 1 channel select",
                [0x10, 0x00, 0x00, 0x31],
                [47, 0],
            ),
            plan.writes,
        )
        self.assertIn(
            live.PatchWrite("Distortion 1 T-SCREAM path on", [0x10, 0x00, 0x13, 0x00], [1, 15, 45, 50, 55, 50, 0, 0, 50]),
            plan.writes,
        )
        self.assertIn(
            live.PatchWrite("Send/Return 1 4CM loop on", [0x10, 0x00, 0x10, 0x35], [1, 0, 6, 4, 6, 4, 0]),
            plan.writes,
        )

    def test_assign_builder_matches_known_tuner_bytes(self):
        data = patch_edit.tuner_assign_data()

        self.assertEqual(len(data), 44)
        self.assertEqual(data[:5], [0x01, 0x00, 0x03, 0x0D, 0x0B])
        self.assertEqual(data[5:9], [0x08, 0x00, 0x00, 0x00])
        self.assertEqual(data[9:13], [0x08, 0x00, 0x00, 0x01])
        self.assertEqual(data[13], 0x45)
        self.assertEqual(data[14], 0x01)
        self.assertEqual(data[20:24], [0x00, 0x00, 0x00, 0x00])
        self.assertEqual(data[24:28], [0x00, 0x00, 0x07, 0x0F])
        self.assertEqual(data[29], 0x50)

    def test_divider_channel_select_assign_uses_tested_target_table(self):
        data = patch_edit.divider1_channel_select_assign_data()

        self.assertEqual(data[1:5], [0x00, 0x03, 0x0A, 0x04])
        self.assertEqual(data[5:13], [0x08, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x01])
        self.assertEqual(data[13], 0x08)
        self.assertEqual(data[14], 0x00)

    def test_user_slot_remap_accepts_any_valid_user_slot(self):
        plan = patch_edit.build_default_patch_plan("PY DEFAULT")
        remapped = patch_edit.plan_for_user_slot(plan, "U03-1")

        self.assertEqual(remapped.writes[0].address, [0x20, 0x0A, 0x00, 0x00])
        self.assertEqual(remapped.writes[1].address, [0x20, 0x0A, 0x10, 0x68])

        u10 = patch_edit.plan_for_user_slot(plan, "U10-1")
        self.assertEqual(u10.writes[0].address, [0x20, 0x2D, 0x00, 0x00])

        u50 = patch_edit.plan_for_user_slot(plan, "U50-5")
        self.assertEqual(u50.writes[0].address, [0x21, 0x79, 0x00, 0x00])

        with self.assertRaises(ValueError):
            patch_edit.plan_for_user_slot(plan, "U51-1")

    def test_clone_read_requests_and_plan_copy_known_patch_records(self):
        requests = patch_edit.clone_core_read_requests("U03-2")

        self.assertEqual(requests[0].label, "Patch Common")
        self.assertEqual(requests[0].address, [0x20, 0x0B, 0x00, 0x00])
        self.assertEqual(requests[1].label, "Patch Stompbox")
        self.assertEqual(requests[1].address, [0x20, 0x0B, 0x01, 0x00])
        self.assertEqual(requests[2].label, "Patch Led")
        self.assertEqual(requests[2].address, [0x20, 0x0B, 0x02, 0x00])
        stompbox2 = next(request for request in requests if request.label == "Patch Stompbox 2")
        stompbox3 = next(request for request in requests if request.label == "Patch Stompbox 3")
        self.assertEqual(stompbox2.address, [0x22, 0x05, 0x00, 0x00])
        self.assertEqual(stompbox3.address, [0x23, 0x7F, 0x00, 0x00])

        source_data = {
            live.address_key(request.address): [index % 0x80] * live.seven_bit_address_value(request.size)
            for index, request in enumerate(requests)
        }
        plan = patch_edit.build_clone_plan("U03-2", "U10-1", source_data)

        self.assertEqual(plan.id, "clone:U03-2:U10-1")
        self.assertEqual(len(plan.writes), len(requests))
        self.assertEqual(plan.writes[0].address, [0x20, 0x2D, 0x00, 0x00])
        self.assertEqual(plan.writes[1].address, [0x20, 0x2D, 0x01, 0x00])
        self.assertEqual(plan.writes[2].address, [0x20, 0x2D, 0x02, 0x00])
        self.assertIn(live.PatchWrite("Clone Patch Stompbox 2", [0x22, 0x27, 0x00, 0x00], source_data[live.address_key(stompbox2.address)]), plan.writes)
        self.assertIn(live.PatchWrite("Clone Patch Stompbox 3", [0x24, 0x21, 0x00, 0x00], source_data[live.address_key(stompbox3.address)]), plan.writes)
        self.assertEqual(plan.writes[0].data, source_data[live.address_key(requests[0].address)])

        with self.assertRaises(ValueError):
            patch_edit.build_clone_plan("U03-2", "U03-2", source_data)

        incomplete_data = dict(source_data)
        incomplete_data.pop(live.address_key(requests[0].address))
        with self.assertRaises(ValueError):
            patch_edit.build_clone_plan("U03-2", "U10-1", incomplete_data)

    def test_clone_plan_includes_only_active_fx_algorithm_records(self):
        core_requests = patch_edit.clone_core_read_requests("U03-2")
        source_data = {
            live.address_key(request.address): [0] * live.seven_bit_address_value(request.size)
            for request in core_requests
        }
        fx1_summary = next(request for request in core_requests if request.label == "FX 1")
        source_data[live.address_key(fx1_summary.address)] = [1, live.FX_TYPES.index("CHORUS")]
        active_requests = patch_edit.active_fx_algorithm_read_requests("U03-2", source_data)
        self.assertEqual(
            [request.label for request in active_requests],
            ["FX 1 CHORUS", "FX 2 AC GUITAR SIM", "FX 3 AC GUITAR SIM", "FX 4 AC GUITAR SIM"],
        )
        for request in active_requests:
            source_data[live.address_key(request.address)] = [64] * live.seven_bit_address_value(request.size)

        plan = patch_edit.build_clone_plan("U03-2", "U10-1", source_data)

        self.assertEqual(len(plan.writes), len(core_requests) + 4)
        self.assertEqual(plan.writes[-4].label, "Clone FX 1 CHORUS")
        self.assertEqual(plan.writes[-4].address, [0x20, 0x2D, 0x27, 0x00])

    def test_verify_plan_reads_large_plans_in_one_session(self):
        writes = [
            live.PatchWrite(f"Write {index}", [0x20, 0x00, index, 0x00], [index])
            for index in range(patch_edit.VERIFY_READ_BATCH_SIZE + 1)
        ]
        plan = patch_edit.PatchPlan("large", "Large verified plan", writes)
        calls = []
        original_read_data_sets = patch_edit.live.read_data_sets

        def fake_read_data_sets(*, timeout, requests):
            calls.append([request.address for request in requests])
            return {live.address_key(request.address): [request.address[2]] for request in requests}

        try:
            patch_edit.live.read_data_sets = fake_read_data_sets
            result = patch_edit.verify_plan(plan, timeout=20)
        finally:
            patch_edit.live.read_data_sets = original_read_data_sets

        self.assertTrue(result["ok"])
        self.assertEqual(calls, [[write.address for write in writes]])

    def test_batched_reads_split_failed_multi_request_batches(self):
        requests = [
            live.PatchReadRequest(f"Read {index}", [0x20, 0x00, index, 0x00], [0, 0, 0, 1])
            for index in range(4)
        ]
        calls = []
        original_read_data_sets = patch_edit.live.read_data_sets

        def fake_read_data_sets(*, timeout, requests):
            calls.append([request.address for request in requests])
            if len(requests) > 1:
                raise live.LiveMIDIError("missing replies")
            return {live.address_key(requests[0].address): [requests[0].address[2]]}

        try:
            patch_edit.live.read_data_sets = fake_read_data_sets
            result = patch_edit.read_data_sets_batched(timeout=20, requests=requests)
        finally:
            patch_edit.live.read_data_sets = original_read_data_sets

        self.assertEqual(sorted(result), [live.address_key(request.address) for request in requests])
        self.assertIn([request.address for request in requests], calls)
        self.assertIn([requests[0].address], calls)

    def test_single_batched_read_retries_transient_failure(self):
        request = live.PatchReadRequest("Read", [0x20, 0x00, 0x00, 0x00], [0, 0, 0, 1])
        calls = 0
        original_read_data_sets = patch_edit.live.read_data_sets
        original_sleep = patch_edit.time.sleep

        def fake_read_data_sets(*, timeout, requests):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise live.LiveMIDIError("No GT-1000 MIDI destination found")
            return {live.address_key(requests[0].address): [1]}

        try:
            patch_edit.live.read_data_sets = fake_read_data_sets
            patch_edit.time.sleep = lambda seconds: None
            result = patch_edit.read_data_set_batch_resilient(timeout=20, requests=[request])
        finally:
            patch_edit.time.sleep = original_sleep
            patch_edit.live.read_data_sets = original_read_data_sets

        self.assertEqual(calls, 2)
        self.assertEqual(result, {"20 00 00 00": [1]})

    def test_apply_plan_retries_transient_write_failure(self):
        plan = patch_edit.PatchPlan("retry", "Retry write", [live.PatchWrite("Write", [0x10, 0, 0, 0], [1])])
        calls = 0
        original_write_data_sets = patch_edit.live.write_data_sets
        original_sleep = patch_edit.time.sleep

        def fake_write_data_sets(writes):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise live.LiveMIDIError("No GT-1000 MIDI destination found")

        try:
            patch_edit.live.write_data_sets = fake_write_data_sets
            patch_edit.time.sleep = lambda seconds: None
            result = patch_edit.apply_plan(plan, timeout=20, verify=False)
        finally:
            patch_edit.time.sleep = original_sleep
            patch_edit.live.write_data_sets = original_write_data_sets

        self.assertEqual(calls, 2)
        self.assertEqual(result["plan"], "retry")

    def test_liveset_export_and_import_validate_known_patch_records(self):
        requests = patch_edit.clone_core_read_requests("U03-2")
        source_data = {
            live.address_key(request.address): [index % 0x7F] * live.seven_bit_address_value(request.size)
            for index, request in enumerate(requests)
        }

        exported_patch = patch_edit.export_liveset_patch("U03-2", source_data)
        liveset = patch_edit.build_liveset_export([exported_patch])
        plan = patch_edit.build_liveset_import_plan(liveset, "U10-1")

        self.assertEqual(liveset["format"], patch_edit.LIVESET_FORMAT)
        self.assertEqual(liveset["patchCount"], 1)
        self.assertEqual(exported_patch["records"][0]["label"], "Patch Common")
        self.assertEqual(exported_patch["records"][0]["sourceAddress"], ["20", "0B", "00", "00"])
        self.assertEqual(plan.id, "liveset-import:U10-1:1")
        self.assertEqual(len(plan.writes), len(requests))
        self.assertEqual(plan.writes[0].address, [0x20, 0x2D, 0x00, 0x00])
        self.assertEqual(plan.writes[-1].address, [0x24, 0x21, 0x22, 0x00])

        with self.assertRaises(ValueError):
            patch_edit.build_liveset_export([])

        broken = {
            "format": patch_edit.LIVESET_FORMAT,
            "patches": [{"records": [dict(exported_patch["records"][0], dataHex="80")]}],
        }
        with self.assertRaises(ValueError):
            patch_edit.build_liveset_import_plan(broken, "U10-1")

    def test_liveset_summary_move_copy_rename_and_remove(self):
        def patch_for(slot: str, name: bytes) -> dict:
            requests = patch_edit.clone_read_requests(slot)
            source_data = {
                live.address_key(request.address): [index % 0x7F] * live.seven_bit_address_value(request.size)
                for index, request in enumerate(requests)
            }
            source_data[live.address_key(requests[0].address)] = list(name.ljust(live.seven_bit_address_value(requests[0].size), b" "))
            return patch_edit.export_liveset_patch(slot, source_data)

        liveset = patch_edit.build_liveset_export([
            patch_for("U03-2", b"PATCH ONE"),
            patch_for("U03-3", b"PATCH TWO"),
        ])

        summary = patch_edit.liveset_summary(liveset)
        self.assertEqual(summary["patchCount"], 2)
        self.assertEqual(summary["patches"][0]["patchName"], "PATCH ONE")
        self.assertEqual(summary["patches"][1]["patchName"], "PATCH TWO")

        moved = patch_edit.move_liveset_patch(liveset, 2, 1)
        self.assertEqual(patch_edit.liveset_summary(moved)["patches"][0]["patchName"], "PATCH TWO")

        copied = patch_edit.copy_liveset_patch(moved, 1, 3)
        copied_summary = patch_edit.liveset_summary(copied)
        self.assertEqual(copied_summary["patchCount"], 3)
        self.assertEqual(copied_summary["patches"][2]["patchName"], "PATCH TWO")

        renamed = patch_edit.rename_liveset_patch(copied, 2, "RENAMED PATCH")
        renamed_summary = patch_edit.liveset_summary(renamed)
        self.assertEqual(renamed_summary["patches"][1]["patchName"], "RENAMED PATCH")

        removed = patch_edit.remove_liveset_patch(moved, 2)
        self.assertEqual(removed["patchCount"], 1)
        self.assertEqual(patch_edit.liveset_summary(removed)["patches"][0]["patchName"], "PATCH TWO")

    def test_tsl_export_summary_and_import_round_trip_native_records(self):
        requests = patch_edit.clone_core_read_requests("U03-2")
        source_data = {
            live.address_key(request.address): [index % 0x7F] * live.seven_bit_address_value(request.size)
            for index, request in enumerate(requests)
        }
        source_data[live.address_key(requests[0].address)] = list(b"TSL PATCH".ljust(live.seven_bit_address_value(requests[0].size), b" "))
        liveset = patch_edit.build_liveset_export([patch_edit.export_liveset_patch("U03-2", source_data)])

        tsl = patch_edit.build_tsl_export(liveset, name="CLI Set", memo="round trip")
        summary = patch_edit.tsl_summary(tsl)
        imported = patch_edit.liveset_from_tsl(tsl)
        plan = patch_edit.build_liveset_import_plan(imported, "U10-1")

        self.assertEqual(tsl["format"], patch_edit.TSL_FORMAT)
        self.assertEqual(tsl["liveSetData"]["name"], "CLI Set")
        self.assertEqual(summary["patchCount"], 1)
        self.assertTrue(summary["canImportRecords"])
        self.assertEqual(summary["patches"][0]["name"], "TSL PATCH")
        self.assertEqual(imported["format"], patch_edit.LIVESET_FORMAT)
        self.assertEqual(imported["patchCount"], 1)
        self.assertEqual(plan.id, "liveset-import:U10-1:1")
        self.assertEqual(len(plan.writes), len(requests))

    def test_tsl_summary_lists_metadata_only_json_but_import_rejects_it(self):
        tsl = {
            "formatRev": 1,
            "device": "GT-1000",
            "liveSetData": {
                "name": "Tone Studio Export",
                "patchList": [
                    {"orderNumber": 1, "name": "PATCH ONE", "data": {"paramSet": []}},
                    {"orderNumber": 2, "patchName": "PATCH TWO"},
                ],
            },
        }

        summary = patch_edit.tsl_summary(tsl)

        self.assertEqual(summary["name"], "Tone Studio Export")
        self.assertEqual(summary["patchCount"], 2)
        self.assertFalse(summary["canImportRecords"])
        self.assertEqual(summary["patches"][0]["name"], "PATCH ONE")
        self.assertFalse(summary["patches"][0]["hasImportableRecords"])
        self.assertEqual(summary["patches"][1]["name"], "PATCH TWO")
        with self.assertRaises(ValueError):
            patch_edit.liveset_from_tsl(tsl)

    def test_tsl_summary_lists_tone_studio_data_param_set_shape(self):
        tsl = {
            "name": "Tone Studio Set",
            "formatRev": "0002",
            "device": "GT-1000",
            "data": [[
                {
                    "memo": "",
                    "paramSet": {
                        "UserPatch%PatchName": [
                            "54", "53", "4c", "20", "44", "41", "54", "41",
                            "20", "20", "20", "20", "20", "20", "20", "20",
                        ],
                        "UserPatch%Patch_0": ["00"],
                    },
                }
            ]],
        }

        summary = patch_edit.tsl_summary(tsl)

        self.assertEqual(summary["formatRev"], "0002")
        self.assertEqual(summary["device"], "GT-1000")
        self.assertEqual(summary["patchCount"], 1)
        self.assertFalse(summary["canImportRecords"])
        self.assertEqual(summary["patches"][0]["orderNumber"], 1)
        self.assertEqual(summary["patches"][0]["name"], "TSL DATA")
        with self.assertRaises(ValueError):
            patch_edit.liveset_from_tsl(tsl)

    def test_tsl_import_plan_accepts_gt1000_tone_studio_param_set_records(self):
        common = list(b"GT1000 TSL".ljust(126, b" "))
        stompbox = [0] * 104
        led = [0] * 32
        assign = [0] * 44
        efct_a = [0] * 104
        efct_b = [0] * 57
        stompbox2 = [3] * 17
        efct2 = [5] * 7
        master_delay2 = [0, 1, 2, 3]
        fx1_chorus_bass = [4] * 6
        fx1_flanger_bass = [5] * 16
        stompbox3 = [4] * 37
        comp = [1] * 9
        fx_chorus = [2] * 37
        fx4 = [0, 15]
        fx4_chorus = [6] * 37
        fx4_chorus_bass = [7] * 6
        fx4_flanger_bass = [8] * 16
        fx_master = [0, 32, 32, 64]
        tsl = {
            "name": "GT-1000 Tone Studio Set",
            "formatRev": "0000",
            "device": "GT-1000",
            "data": [[{
                "memo": "",
                "paramSet": {
                    "User_patch%common": [f"{byte:02X}" for byte in common],
                    "User_patch%stompBox": [f"{byte:02X}" for byte in stompbox],
                    "User_patch%led": [f"{byte:02X}" for byte in led],
                    "User_patch%assign(1)": [f"{byte:02X}" for byte in assign],
                    "User_patch%efct": [f"{byte:02X}" for byte in efct_a],
                    "User_patch%efctB": [f"{byte:02X}" for byte in efct_b],
                    "User_patch2%stompBox": [f"{byte:02X}" for byte in stompbox2],
                    "User_patch2%efct": [f"{byte:02X}" for byte in efct2],
                    "User_patch2%mstDelay": [f"{byte:02X}" for byte in master_delay2],
                    "User_patch2%fx1ChorusBass": [f"{byte:02X}" for byte in fx1_chorus_bass],
                    "User_patch2%fx1FlangerBass": [f"{byte:02X}" for byte in fx1_flanger_bass],
                    "User_patch3%stompBox": [f"{byte:02X}" for byte in stompbox3],
                    "User_patch3%fx(4)%fx": [f"{byte:02X}" for byte in fx4],
                    "User_patch%comp": [f"{byte:02X}" for byte in comp],
                    "User_patch%fx(1)%fxChorus": [f"{byte:02X}" for byte in fx_chorus],
                    "User_patch3%fx4Chorus": [f"{byte:02X}" for byte in fx4_chorus],
                    "User_patch3%fx4ChorusBass": [f"{byte:02X}" for byte in fx4_chorus_bass],
                    "User_patch3%fx4FlangerBass": [f"{byte:02X}" for byte in fx4_flanger_bass],
                    "User_patch3%fx1MasterFx": [f"{byte:02X}" for byte in fx_master],
                    "User_patch3%fx2MasterFx": [f"{byte:02X}" for byte in fx_master],
                    "User_patch3%fx3MasterFx": [f"{byte:02X}" for byte in fx_master],
                    "User_patch3%fx4MasterFx": [f"{byte:02X}" for byte in fx_master],
                },
            }]],
        }

        summary = patch_edit.tsl_summary(tsl)
        plan = patch_edit.build_tsl_import_plan(tsl, "U10-1")

        self.assertTrue(summary["canImportRecords"])
        self.assertTrue(summary["patches"][0]["hasImportableRecords"])
        self.assertEqual(summary["patches"][0]["name"], "GT1000 TSL")
        self.assertEqual(plan.id, "tsl-import:U10-1:1")
        self.assertEqual(plan.writes[0].address, [0x20, 0x2D, 0x00, 0x00])
        self.assertEqual(plan.writes[0].data, common)
        self.assertIn(live.PatchWrite("Import U10-1 TSL Patch Effect B", [0x20, 0x2D, 0x10, 0x68], efct_b), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL COMPRESSOR", [0x20, 0x2D, 0x12, 0x00], comp), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL FX 1 CHORUS", [0x20, 0x2D, 0x27, 0x00], fx_chorus), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL Patch Stompbox 2", [0x22, 0x27, 0x00, 0x00], stompbox2), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL Patch Stompbox 3", [0x24, 0x21, 0x00, 0x00], stompbox3), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL Patch Effect 2", [0x22, 0x27, 0x0A, 0x00], efct2), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL Master Delay 2", [0x22, 0x27, 0x07, 0x00], master_delay2), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL FX 1 Chorus Bass", [0x22, 0x27, 0x01, 0x00], fx1_chorus_bass), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL FX 1 Flanger Bass", [0x22, 0x27, 0x02, 0x00], fx1_flanger_bass), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL FX 4", [0x24, 0x21, 0x01, 0x00], fx4), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL FX 4 CHORUS", [0x24, 0x21, 0x05, 0x00], fx4_chorus), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL FX 4 Chorus Bass", [0x24, 0x21, 0x1C, 0x00], fx4_chorus_bass), plan.writes)
        self.assertIn(live.PatchWrite("Import U10-1 TSL FX 4 Flanger Bass", [0x24, 0x21, 0x1D, 0x00], fx4_flanger_bass), plan.writes)
        self.assertFalse(any("MASTER FX" in write.label for write in plan.writes))

    def test_tsl_import_rejects_oversized_bass_extension_records(self):
        tsl = {
            "name": "GT-1000 Tone Studio Set",
            "formatRev": "0000",
            "device": "GT-1000",
            "data": [[{
                "memo": "",
                "paramSet": {
                    "User_patch%common": ["20"] * 126,
                    "User_patch2%fx1ChorusBass": ["00"] * 7,
                },
            }]],
        }

        with self.assertRaisesRegex(ValueError, "User_patch2%fx1ChorusBass has 7 bytes"):
            patch_edit.build_tsl_import_plan(tsl, "U10-1")

    def test_tsl_import_plan_rejects_unsupported_gt1000_param_set_keys(self):
        tsl = {
            "name": "GT-1000 Tone Studio Set",
            "formatRev": "0000",
            "device": "GT-1000",
            "data": [[{
                "memo": "",
                "paramSet": {
                    "User_patch%common": ["20"] * 126,
                    "User_patch3%unknownFutureRecord": ["00", "0F"],
                },
            }]],
        }

        summary = patch_edit.tsl_summary(tsl)

        self.assertFalse(summary["canImportRecords"])
        self.assertEqual(summary["patches"][0]["unsupportedParamSetKeys"], ["User_patch3%unknownFutureRecord"])
        with self.assertRaisesRegex(ValueError, "unsupported GT-1000 paramSet keys"):
            patch_edit.build_tsl_import_plan(tsl, "U10-1")

    def test_preset_restore_uses_documented_primary_patch_records_only(self):
        requests = patch_edit.preset_restore_read_requests("P03-2")

        self.assertEqual(requests[0].label, "Patch Common")
        self.assertEqual(requests[0].address, [0x30, 0x0B, 0x00, 0x00])
        self.assertEqual(requests[1].label, "Patch Stompbox")
        self.assertEqual(requests[1].address, [0x30, 0x0B, 0x01, 0x00])
        self.assertNotIn("Patch Stompbox 2", [request.label for request in requests])
        self.assertIn("FX 4", [request.label for request in requests])
        self.assertNotIn("FX 4 AC RESONANCE", [request.label for request in requests])
        self.assertNotIn("FX 4 HARMONIST", [request.label for request in requests])
        self.assertNotIn("FX 4 PAN", [request.label for request in requests])

        source_data = {
            live.address_key(request.address): [index % 0x7F] * live.seven_bit_address_value(request.size)
            for index, request in enumerate(requests)
        }
        plan = patch_edit.build_preset_restore_plan("P03-2", "U10-1", source_data)

        self.assertEqual(plan.id, "restore-preset:P03-2:U10-1")
        self.assertEqual(len(plan.writes), len(requests))
        self.assertEqual(plan.writes[0].address, [0x20, 0x2D, 0x00, 0x00])
        self.assertEqual(plan.writes[1].address, [0x20, 0x2D, 0x01, 0x00])
        self.assertNotIn("Patch Stompbox 2", [write.label for write in plan.writes])

    def test_parameter_set_plan_encodes_nibbles_and_user_slot(self):
        plan = patch_edit.build_parameter_set_plan("delay1", "time", "420", slot="U03-2")

        self.assertEqual(plan.writes[0].address, [0x20, 0x0B, 0x1D, 0x01])
        self.assertEqual(plan.writes[0].data, [0x00, 0x01, 0x0A, 0x04])

    def test_parameter_set_plan_accepts_type_names(self):
        plan = patch_edit.build_parameter_set_plan("dist1", "type", "T-SCREAM")

        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x13, 0x01])
        self.assertEqual(plan.writes[0].data, [15])

        eq_plan = patch_edit.build_parameter_set_plan("eq1", "type", "GRAPHIC")
        self.assertEqual(eq_plan.writes[0].address, [0x10, 0x00, 0x19, 0x01])
        self.assertEqual(eq_plan.writes[0].data, [1])

        with self.assertRaises(ValueError):
            patch_edit.build_parameter_set_plan("eq1", "type", "2")

    def test_parameter_set_plan_covers_named_eq_fields(self):
        plan = patch_edit.build_parameter_set_plan("eq1", "lowMidGain", "32")

        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x19, 0x07])
        self.assertEqual(plan.writes[0].data, [32])

        geq_plan = patch_edit.build_parameter_set_plan("eq1", "geq16kHz", "24")
        self.assertEqual(geq_plan.writes[0].address, [0x10, 0x00, 0x19, 0x17])
        self.assertEqual(geq_plan.writes[0].data, [24])

        geq_level_plan = patch_edit.build_parameter_set_plan("eq1", "geqLevel", "30")
        self.assertEqual(geq_level_plan.writes[0].address, [0x10, 0x00, 0x19, 0x0D])
        self.assertEqual(geq_level_plan.writes[0].data, [30])

    def test_parameter_set_plan_covers_named_master_delay_reverb_and_pedal_fx_fields(self):
        master_delay = patch_edit.build_parameter_set_plan("masterDelay", "d2EffectLevel", "90")

        self.assertEqual(master_delay.writes[0].address, [0x10, 0x00, 0x21, 0x22])
        self.assertEqual(master_delay.writes[0].data, [90])

        reverb = patch_edit.build_parameter_set_plan("reverb", "preDelay", "120")
        self.assertEqual(reverb.writes[0].address, [0x10, 0x00, 0x74, 0x0E])
        self.assertEqual(reverb.writes[0].data, [0x07, 0x08])

        pedal = patch_edit.build_parameter_set_plan("pedalFx", "pedalMax", "1000")
        self.assertEqual(pedal.writes[0].address, [0x10, 0x00, 0x75, 0x0A])
        self.assertEqual(pedal.writes[0].data, [0x00, 0x03, 0x0E, 0x08])

    def test_parameter_set_plan_covers_fx_algorithm_blocks(self):
        chorus = patch_edit.build_parameter_set_plan("fx1Chorus", "effectLevel2", "75")

        self.assertEqual(chorus.writes[0].address, [0x10, 0x00, 0x27, 0x19])
        self.assertEqual(chorus.writes[0].data, [75])

        pitch_shift = patch_edit.build_parameter_set_plan("fx2PitchShift", "ps1PreDelay", "120")
        self.assertEqual(pitch_shift.writes[0].address, [0x10, 0x00, 0x4E, 0x06])
        self.assertEqual(pitch_shift.writes[0].data, [0x00, 0x00, 0x07, 0x08])

        fx4 = patch_edit.build_parameter_set_plan("fx4", "type", "CHORUS")
        self.assertEqual(fx4.writes[0].address, [0x10, 0x02, 0x01, 0x01])
        self.assertEqual(fx4.writes[0].data, [3])

        fx4_chorus = patch_edit.build_parameter_set_plan("fx4Chorus", "effectLevel2", "75")
        self.assertEqual(fx4_chorus.writes[0].address, [0x10, 0x02, 0x05, 0x19])
        self.assertEqual(fx4_chorus.writes[0].data, [75])

        persistent_fx4_chorus = patch_edit.build_parameter_set_plan("fx4Chorus", "effectLevel2", "75", slot="U10-3")
        self.assertEqual(persistent_fx4_chorus.writes[0].address, [0x24, 0x23, 0x05, 0x19])

    def test_clone_read_requests_include_fx_algorithm_records(self):
        requests = patch_edit.clone_read_requests("U03-2")
        labels = [request.label for request in requests]

        self.assertIn("FX 1 CHORUS", labels)
        self.assertIn("FX 2 PITCH SHIFTER", labels)
        self.assertIn("FX 3 VIBRATO", labels)
        fx1_chorus = requests[labels.index("FX 1 CHORUS")]
        self.assertEqual(fx1_chorus.address, [0x20, 0x0B, 0x27, 0x00])
        self.assertEqual(fx1_chorus.size, [0x00, 0x00, 0x00, 0x1D])

    def test_clone_core_read_requests_include_validated_extended_records(self):
        requests = patch_edit.clone_core_read_requests("U10-1")
        by_label = {request.label: request for request in requests}

        self.assertEqual(by_label["FX 1 Chorus Bass"].address, [0x22, 0x27, 0x01, 0x00])
        self.assertEqual(by_label["FX 1 Chorus Bass"].size, [0x00, 0x00, 0x00, 0x06])
        self.assertEqual(by_label["FX 1 Flanger Bass"].address, [0x22, 0x27, 0x02, 0x00])
        self.assertEqual(by_label["Master Delay 2"].address, [0x22, 0x27, 0x07, 0x00])
        self.assertEqual(by_label["Patch Effect 2"].address, [0x22, 0x27, 0x0A, 0x00])
        self.assertEqual(by_label["FX 4"].address, [0x24, 0x21, 0x01, 0x00])
        self.assertEqual(by_label["FX 4 Chorus Bass"].address, [0x24, 0x21, 0x1C, 0x00])
        self.assertEqual(by_label["FX 4 Flanger Bass"].address, [0x24, 0x21, 0x1D, 0x00])
        self.assertEqual(by_label["FX 1 DIST"].address, [0x24, 0x21, 0x1F, 0x00])
        self.assertEqual(by_label["FX 2 DIST"].address, [0x24, 0x21, 0x20, 0x00])
        self.assertEqual(by_label["FX 3 DIST"].address, [0x24, 0x21, 0x21, 0x00])
        self.assertEqual(by_label["FX 4 Dist"].address, [0x24, 0x21, 0x22, 0x00])

    def test_parameter_set_plan_supports_resident_blocks(self):
        plan = patch_edit.build_parameter_set_plan("sendReturn1", "sendLevel", "100")

        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x10, 0x37])
        self.assertEqual(plan.writes[0].data, [0x06, 0x04])

    def test_raw_parameter_set_plan_covers_unknown_offsets(self):
        plan = patch_edit.build_raw_parameter_set_plan("fx1", 12, "64")

        self.assertEqual(plan.id, "raw-set:fx1:12:byte")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x23, 0x0C])
        self.assertEqual(plan.writes[0].data, [64])

        fx_boundary = patch_edit.build_raw_parameter_set_plan("fx1", 0x0D7F, "1")
        self.assertEqual(fx_boundary.writes[0].address, [0x10, 0x00, 0x3D, 0x7F])
        with self.assertRaises(ValueError):
            patch_edit.build_raw_parameter_set_plan("fx1", 0x0D80, "1")

        resident = patch_edit.build_raw_parameter_set_plan("divider1", 1, "1", slot="U03-2")
        self.assertEqual(resident.writes[0].address, [0x20, 0x0B, 0x10, 0x0E])
        self.assertEqual(resident.writes[0].data, [1])

        nibbles = patch_edit.build_raw_parameter_set_plan("sendReturn1", 2, "100", width="nibbles2")
        self.assertEqual(nibbles.writes[0].address, [0x10, 0x00, 0x10, 0x37])
        self.assertEqual(nibbles.writes[0].data, [0x06, 0x04])

    def test_chain_move_plan_reorders_full_validated_chain(self):
        chain = list(patch_edit.CANONICAL_FULL_CHAIN)
        plan = patch_edit.build_chain_move_plan(chain, 15, before=14)

        self.assertEqual(plan.id, "move:chain:15:before:14")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x10, 0x68])
        data = plan.writes[0].data
        self.assertEqual(len(data), 49)
        self.assertEqual(set(data), set(patch_edit.CANONICAL_FULL_CHAIN))
        self.assertLess(data.index(15), data.index(14))

    def test_chain_move_plan_validates_reference_and_user_slot(self):
        chain = list(patch_edit.CANONICAL_FULL_CHAIN)
        plan = patch_edit.build_chain_move_plan(chain, 15, after=14, slot="U03-2")

        self.assertEqual(plan.id, "move:chain:15:after:14:U03-2")
        self.assertEqual(plan.writes[0].address, [0x20, 0x0B, 0x10, 0x68])
        self.assertGreater(plan.writes[0].data.index(15), plan.writes[0].data.index(14))

        with self.assertRaises(ValueError):
            patch_edit.build_chain_move_plan(chain[:-1], 15, before=14)
        with self.assertRaises(ValueError):
            patch_edit.build_chain_move_plan(chain, 15, before=15)

    def test_bpm_set_plan_encodes_tenths_and_user_slot(self):
        plan = patch_edit.build_bpm_set_plan("120.0")

        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x10, 0x61])
        self.assertEqual(plan.writes[0].data, [0x00, 0x04, 0x0B, 0x00])

        remapped = patch_edit.build_bpm_set_plan("99.5", slot="U03-2")
        self.assertEqual(remapped.writes[0].address, [0x20, 0x0B, 0x10, 0x61])
        self.assertEqual(remapped.writes[0].data, [0x00, 0x03, 0x0E, 0x03])

    def test_bpm_set_plan_validates_documented_range(self):
        self.assertEqual(patch_edit.parse_bpm_tenths("40"), 400)
        self.assertEqual(patch_edit.parse_bpm_tenths("250.0"), 2500)

        for value in ["39.9", "250.1", "120.01", "fast"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    patch_edit.build_bpm_set_plan(value)

    def test_master_set_plan_encodes_named_patch_master_fields(self):
        level = patch_edit.build_master_set_plan("level", "95", slot="U03-2")
        self.assertEqual(level.id, "master-set:level:U03-2")
        self.assertEqual(level.writes[0].address, [0x20, 0x0B, 0x10, 0x60])
        self.assertEqual(level.writes[0].data, [95])

        record = [0] * live.seven_bit_address_value([0x00, 0x00, 0x01, 0x1C])
        record_level = patch_edit.build_master_set_record_plan("level", "95", record, slot="U03-2")
        self.assertEqual(record_level.id, "master-set:level:U03-2")
        self.assertEqual(record_level.writes[0].address, [0x20, 0x0B, 0x10, 0x00])
        self.assertEqual(len(record_level.writes[0].data), len(record))
        self.assertEqual(record_level.writes[0].data[0x60], 95)

        key = patch_edit.build_master_set_plan("key", "Db(Bbm)")
        self.assertEqual(key.writes[0].address, [0x10, 0x00, 0x10, 0x65])
        self.assertEqual(key.writes[0].data, [1])

        carryover = patch_edit.build_master_set_plan("carryover", "on")
        self.assertEqual(carryover.writes[0].address, [0x10, 0x00, 0x11, 0x19])
        self.assertEqual(carryover.writes[0].data, [1])

        with self.assertRaises(ValueError):
            patch_edit.build_master_set_plan("level", "201")
        with self.assertRaises(ValueError):
            patch_edit.build_master_set_plan("key", "H")

    def test_tuner_assign_plan_targets_assign_16_and_user_slot(self):
        plan = patch_edit.build_tuner_assign_plan()

        self.assertEqual(plan.id, "set:tunerAssign")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x0A, 0x40])
        self.assertEqual(plan.writes[0].data, patch_edit.tuner_assign_data())

        remapped = patch_edit.build_tuner_assign_plan(slot="U03-2")
        self.assertEqual(remapped.writes[0].address, [0x20, 0x0B, 0x0A, 0x40])
        self.assertEqual(remapped.writes[0].data, patch_edit.tuner_assign_data())

    def test_assign_cc_plan_encodes_source_and_offset_target_range(self):
        plan = patch_edit.build_assign_cc_plan(
            3,
            target=158,
            target_min=0,
            target_max=1,
            source_cc=80,
            mode="moment",
        )

        data = plan.writes[0].data
        self.assertEqual(plan.id, "set:assign3:cc80:target158")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x04, 0x00])
        self.assertEqual(data[0], 1)
        self.assertEqual(data[1:5], live.nibbles_for(158))
        self.assertEqual(data[5:9], live.nibbles_for(32768))
        self.assertEqual(data[9:13], live.nibbles_for(32769))
        self.assertEqual(data[13], 69)
        self.assertEqual(data[14], 1)
        self.assertEqual(data[20:28], live.nibbles_for(0) + live.nibbles_for(127))
        self.assertEqual(data[29], 80)

    def test_assign_cc_plan_validates_supported_cc_sources(self):
        self.assertEqual(patch_edit.assign_source_for_cc(1), 22)
        self.assertEqual(patch_edit.assign_source_for_cc(31), 52)
        self.assertEqual(patch_edit.assign_source_for_cc(64), 53)
        self.assertEqual(patch_edit.assign_source_for_cc(95), 84)

        with self.assertRaises(ValueError):
            patch_edit.build_assign_cc_plan(1, target=158, target_min=0, target_max=1, source_cc=32, mode="moment")

    def test_assign_set_plan_encodes_general_assign_and_patch_midi_fields(self):
        plan = patch_edit.build_assign_set_plan(
            2,
            enabled=True,
            target=987,
            target_min=0,
            target_max=1,
            source=19,
            mode="toggle",
            active_min=0,
            active_max=127,
            midi_channel=1,
            midi_cc=80,
            midi_cc_min=12,
            midi_cc_max=64,
            midi_pc=10,
            midi_bank_msb=2,
            midi_bank_lsb=3,
        )

        data = plan.writes[0].data
        self.assertEqual(plan.id, "set:assign2:target987:source19")
        self.assertEqual(plan.writes[0].address, [0x10, 0x00, 0x03, 0x40])
        self.assertEqual(data[0], 1)
        self.assertEqual(data[1:5], live.nibbles_for(987))
        self.assertEqual(data[5:13], live.nibbles_for(32768) + live.nibbles_for(32769))
        self.assertEqual(data[13:15], [19, 0])
        self.assertEqual(data[28:30], [1, 80])
        self.assertEqual(data[30:38], live.nibbles_for(12) + live.nibbles_for(64))
        self.assertEqual(data[39], 10)
        self.assertEqual(data[40:44], live.nibbles_for(2, byte_count=2) + live.nibbles_for(3, byte_count=2))

    def test_control_set_and_rename_plans(self):
        ctl = patch_edit.build_control_set_plan("ctl1", "dist1", mode="toggle", slot="U03-2")
        self.assertEqual(ctl.id, "control:ctl1:dist1:U03-2")
        self.assertEqual(ctl.writes[0].address, [0x20, 0x0B, 0x00, 0x31])
        self.assertEqual(ctl.writes[0].data, [19, 0])

        exp = patch_edit.build_control_set_plan("exp1", "foot-volume-pedal-fx")
        self.assertEqual(exp.writes[0].address, [0x10, 0x00, 0x00, 0x43])
        self.assertEqual(exp.writes[0].data, [3])

        system_ctl = patch_edit.build_system_control_set_plan("ctl1", "dist1", mode="toggle")
        self.assertEqual(system_ctl.id, "system-control:ctl1:dist1")
        self.assertEqual(system_ctl.writes[0].address, [0x00, 0x00, 0x10, 0x0E])
        self.assertEqual(system_ctl.writes[0].data, [19, 0])

        preference = patch_edit.build_control_preference_plan("ctl1", "patch")
        self.assertEqual(preference.id, "control-preference:ctl1:patch")
        self.assertEqual(preference.writes[0].address, [0x00, 0x00, 0x10, 0x2A])
        self.assertEqual(preference.writes[0].data, [0])

        rename = patch_edit.build_rename_plan("ABCDEFGHIJKLMNOPQ", slot="U03-2")
        self.assertEqual(rename.writes[0].address, [0x20, 0x0B, 0x00, 0x00])
        self.assertEqual(rename.writes[0].data, list(b"ABCDEFGHIJKLMNOP"))

        led = patch_edit.build_led_set_plan("ctl1", "on", "auto-cyan", slot="U03-2")
        self.assertEqual(led.id, "led:ctl1:on:auto-cyan:U03-2")
        self.assertEqual(led.writes[0].address, [0x20, 0x0B, 0x02, 0x0F])
        self.assertEqual(led.writes[0].data, [21])

        with self.assertRaises(ValueError):
            patch_edit.build_led_set_plan("ctl1", "off", "auto-cyan")

    def test_exchange_plan_swaps_known_patch_records(self):
        requests_a = patch_edit.clone_core_read_requests("U03-2")
        requests_b = patch_edit.clone_core_read_requests("U03-3")
        data_a = {
            live.address_key(request.address): [index % 0x80] * live.seven_bit_address_value(request.size)
            for index, request in enumerate(requests_a)
        }
        data_b = {
            live.address_key(request.address): [(index + 10) % 0x80] * live.seven_bit_address_value(request.size)
            for index, request in enumerate(requests_b)
        }

        plan = patch_edit.build_exchange_plan("U03-2", "U03-3", data_a, data_b)

        self.assertEqual(plan.id, "exchange:U03-2:U03-3")
        self.assertEqual(len(plan.writes), len(requests_a) * 2)
        self.assertEqual(plan.writes[0].address, requests_b[0].address)
        self.assertEqual(plan.writes[0].data, data_a[live.address_key(requests_a[0].address)])
        self.assertEqual(plan.writes[len(requests_a)].address, requests_a[0].address)
        self.assertEqual(plan.writes[len(requests_a)].data, data_b[live.address_key(requests_b[0].address)])


if __name__ == "__main__":
    unittest.main()
