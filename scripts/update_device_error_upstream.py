#!/usr/bin/env python3
"""Prepare a three-way update of the notification blueprint (dry-run by default)."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import quote

from check_heating_upstream import github_request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("upstream/device_error_notify.json")


def blob_sha(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def fetch_upstream(manifest, request=github_request):
    repository = manifest["repository"]
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("Invalid repository")
    prefix = f"/repos/{repository}"
    head = request(f"{prefix}/commits/{quote(manifest['branch'], safe='')}")["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("Invalid commit SHA")
    remote = request(f"{prefix}/contents/{quote(manifest['path'], safe='/')}?ref={head}")
    if remote.get("type") != "file" or remote.get("encoding") != "base64":
        raise ValueError("Expected a base64-encoded upstream file")
    content = base64.b64decode("".join(remote["content"].split()), validate=True)
    if blob_sha(content) != remote["sha"]:
        raise ValueError("Upstream content does not match its blob SHA")
    content.decode("utf-8")
    return head, remote["sha"], content


def merge(local, base, remote):
    with tempfile.TemporaryDirectory() as directory:
        paths = [Path(directory) / name for name in ("local", "base", "upstream")]
        for path, content in zip(paths, (local, base, remote)):
            path.write_bytes(content)
        result = subprocess.run(
            ["git", "merge-file", "-p", "--diff3", "-L", "local", "-L", "base",
             "-L", "upstream", *map(str, paths)], capture_output=True, check=False,
        )
        # git merge-file returns the number of conflicts (capped at 127).
        if result.returncode < 0 or result.returncode > 127:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
        return result.returncode != 0, result.stdout


def prepare_update(root=ROOT, apply=False, request=github_request):
    manifest_path = root / MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    baseline_path = root / manifest["baseline_path"]
    local_path = root / manifest["local_path"]
    baseline = baseline_path.read_bytes()
    if blob_sha(baseline) != manifest["reviewed_blob"]:
        raise ValueError("Stored upstream baseline does not match reviewed_blob")
    head, blob, remote = fetch_upstream(manifest, request)
    if blob == manifest["reviewed_blob"]:
        return {"status": "unchanged", "commit": head, "blob": blob}

    conflict, merged = merge(local_path.read_bytes(), baseline, remote)
    base_url = f"https://github.com/{manifest['repository']}"
    body = (
        "Änderungen am originalen Better-Thermostat-Benachrichtigungs-Blueprint.\n\n"
        f"- [Bisheriges Original]({base_url}/blob/{manifest['reviewed_commit']}/{manifest['path']})\n"
        f"- [Neues Original]({base_url}/blob/{head}/{manifest['path']})\n"
        f"- [Vergleich]({base_url}/compare/{manifest['reviewed_commit']}...{head})\n\n"
        "Drei-Wege-Merge mit unseren lokalen Anpassungen. Bitte insbesondere Raumangabe, "
        "source_url, Inputs und Benachrichtigungen prüfen. Kein automatischer Merge oder HA-Import.\n"
    )
    result = {"status": "conflict" if conflict else "available", "commit": head,
              "blob": blob, "body": body, "merged": merged.decode("utf-8")}
    if apply and not conflict:
        # Advance the baseline only together with a successfully merged blueprint.
        local_path.write_bytes(merged.rstrip(b"\n") + b"\n")
        baseline_path.write_bytes(remote)
        manifest.update(reviewed_commit=head, reviewed_blob=blob)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        result["status"] = "updated"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write a conflict-free update locally")
    parser.add_argument("--report-dir", type=Path, help="Write review report and merge candidate")
    args = parser.parse_args()
    result = prepare_update(apply=args.apply)
    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        (args.report_dir / "summary.json").write_text(
            json.dumps({k: v for k, v in result.items() if k != "merged"}, indent=2) + "\n",
            encoding="utf-8",
        )
        if "body" in result:
            (args.report_dir / "pull-request.md").write_text(result["body"], encoding="utf-8")
            (args.report_dir / "merge-candidate.yaml.txt").write_text(result["merged"], encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "merged"}, indent=2))
    return 2 if result["status"] == "conflict" else 0


if __name__ == "__main__":
    raise SystemExit(main())
