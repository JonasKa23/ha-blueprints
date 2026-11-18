import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "update_device_error_upstream", ROOT / "scripts/update_device_error_upstream.py"
)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class DeviceErrorUpstreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = json.loads((ROOT / updater.MANIFEST).read_text())
        self.files = [updater.MANIFEST, Path(self.manifest["baseline_path"]),
                      Path(self.manifest["local_path"])]
        for path in self.files:
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_bytes((ROOT / path).read_bytes())
        self.base = (self.root / self.manifest["baseline_path"]).read_bytes()
        # Stable fixtures: regression tests must still pass after real updates
        # change the upstream defaults or notification templates.
        self.base = (
            b"blueprint:\n  source_url: https://upstream.example/blueprint.yaml\n"
            b"  input:\n    delay:\n      default: 5\n"
            b"\nmode: parallel\n\nvariables:\n  enabled: true\n"
            b"\nmessage: \"{{ device_attr(thermostat_device, 'name') }}\"\n"
        )
        local = self.base.replace(
            b"https://upstream.example/blueprint.yaml",
            b"https://github.com/JonasKa23/ha-blueprints/blob/main/automations/device_error_notify.yaml",
        ).replace(
            b"message: ", b"room: \"{{ area_name(thermostat_device) }}\"\nmessage: "
        ).replace(
            b"device_attr(thermostat_device, 'name') }}",
            b"device_attr(thermostat_device, 'name') }} ({{ room }})",
        )
        (self.root / self.manifest["local_path"]).write_bytes(local)
        (self.root / self.manifest["baseline_path"]).write_bytes(self.base)
        self.manifest["reviewed_blob"] = updater.blob_sha(self.base)
        (self.root / updater.MANIFEST).write_text(json.dumps(self.manifest))
        self.remote = self.base
        self.head = "a" * 40
        self.calls = []

    def request(self, path):
        self.calls.append(path)
        if "/commits/" in path:
            return {"sha": self.head}
        self.assertTrue(path.endswith(f"?ref={self.head}"))
        return {"type": "file", "encoding": "base64", "sha": updater.blob_sha(self.remote),
                "content": base64.b64encode(self.remote).decode()}

    def snapshot(self):
        return [(self.root / path).read_bytes() for path in self.files]

    def update(self, apply=False):
        return updater.prepare_update(self.root, apply, self.request)

    def test_unrelated_commit_does_not_modify_files(self):
        before = self.snapshot()
        self.assertEqual(self.update(True)["status"], "unchanged")
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_keeps_all_files_unchanged(self):
        before = self.snapshot()
        self.remote = self.base.replace(b"      default: 5\n", b"      default: 7\n")
        self.assertNotEqual(self.remote, self.base)
        self.assertEqual(self.update()["status"], "available")
        self.assertEqual(self.snapshot(), before)

    def test_merge_preserves_room_and_local_source_and_advances_baseline(self):
        self.remote = self.base.replace(b"      default: 5\n", b"      default: 7\n")
        result = self.update(True)
        self.assertEqual(result["status"], "updated")
        local = (self.root / self.manifest["local_path"]).read_text()
        self.assertIn("default: 7", local)
        self.assertIn("area_name(thermostat_device)", local)
        self.assertIn("JonasKa23/ha-blueprints/blob/main/", local)
        self.assertTrue(local.endswith("\n"))
        updated = json.loads((self.root / updater.MANIFEST).read_text())
        self.assertEqual(updated["reviewed_commit"], self.head)
        self.assertEqual(updated["reviewed_blob"], updater.blob_sha(self.remote))
        self.assertEqual((self.root / updated["baseline_path"]).read_bytes(), self.remote)
        self.assertEqual(self.update(True)["status"], "unchanged")

    def test_conflicting_changes_preserve_all_files_and_return_candidate(self):
        before = self.snapshot()
        self.remote = self.base.replace(
            b"device_attr(thermostat_device, 'name')", b"device_attr(thermostat_device, 'name_by_user')"
        )
        result = self.update(True)
        self.assertEqual(result["status"], "conflict")
        self.assertIn("<<<<<<< local", result["merged"])
        self.assertEqual(self.snapshot(), before)

    def test_next_update_uses_the_advanced_baseline(self):
        self.remote = self.base.replace(b"      default: 5\n", b"      default: 7\n")
        self.update(True)
        self.remote = self.remote.replace(b"      default: 7\n", b"      default: 9\n")
        self.head = "b" * 40
        self.assertEqual(self.update(True)["status"], "updated")
        self.assertIn("default: 9", (self.root / self.manifest["local_path"]).read_text())

    def test_corrupt_baseline_is_rejected_before_fetching(self):
        (self.root / self.manifest["baseline_path"]).write_bytes(b"invalid")
        with self.assertRaisesRegex(ValueError, "baseline"):
            self.update(True)
        self.assertEqual(self.calls, [])

    def test_invalid_remote_hash_or_api_failure_does_not_write(self):
        before = self.snapshot()
        def bad_hash(path):
            result = self.request(path)
            if "content" in result:
                result["sha"] = "0" * 40
            return result
        with self.assertRaisesRegex(ValueError, "blob SHA"):
            updater.prepare_update(self.root, True, bad_hash)
        with self.assertRaises(OSError):
            updater.prepare_update(self.root, True, lambda path: (_ for _ in ()).throw(OSError("API failed")))
        self.assertEqual(self.snapshot(), before)

    def test_git_execution_failure_is_not_treated_as_a_conflict(self):
        with patch.object(updater.subprocess, "run") as run:
            run.return_value.returncode = 255
            run.return_value.stderr = b"merge failed"
            with self.assertRaisesRegex(RuntimeError, "merge failed"):
                updater.merge(b"local", b"base", b"remote")

    def test_real_baseline_matches_manifest(self):
        manifest = json.loads((ROOT / updater.MANIFEST).read_text())
        baseline = (ROOT / manifest["baseline_path"]).read_bytes()
        self.assertEqual(updater.blob_sha(baseline), manifest["reviewed_blob"])

    def test_real_blueprint_is_preserved_when_remote_equals_baseline(self):
        manifest = json.loads((ROOT / updater.MANIFEST).read_text())
        baseline = (ROOT / manifest["baseline_path"]).read_bytes()
        local = (ROOT / manifest["local_path"]).read_bytes()
        conflict, merged = updater.merge(local, baseline, baseline)
        self.assertFalse(conflict)
        self.assertEqual(merged, local)


if __name__ == "__main__":
    unittest.main()
