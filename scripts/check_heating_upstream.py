#!/usr/bin/env python3
"""Report upstream file changes. Never change the blueprint or its reviewed baseline."""

import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "upstream/better_thermostat.json"


def github_request(path, data=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ha-blueprints-upstream-check",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = None if data is None else json.dumps(data).encode()
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(f"https://api.github.com{path}", headers=headers, data=payload)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def check_upstream(manifest, destination=None, create_issue=False, request=github_request):
    upstream = manifest["repository"]
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", upstream):
        raise ValueError("Invalid upstream repository")
    if destination and not re.fullmatch(r"[\w.-]+/[\w.-]+", destination):
        raise ValueError("Invalid destination repository")
    # Resolve branch once, then read the file at that immutable revision.
    head = request(f"/repos/{upstream}/commits/{quote(manifest['branch'], safe='')}")["sha"]
    file_path = quote(manifest["path"], safe="/")
    remote = request(f"/repos/{upstream}/contents/{file_path}?{urlencode({'ref': head})}")
    if remote.get("type") != "file" or not re.fullmatch(r"[0-9a-f]{40}", remote.get("sha", "")):
        raise ValueError("Expected a regular upstream file with a Git blob SHA")
    blob = remote["sha"]
    if blob == manifest["reviewed_blob"]:
        return {"status": "unchanged", "commit": head, "blob": blob}

    marker = f"<!-- heating-upstream:{upstream}:{manifest['path']}:{blob} -->"
    base = f"https://github.com/{upstream}"
    body = (
        f"{marker}\n"
        "Der originale Better-Thermostat-Heizplan hat sich seit unserem geprüften Stand geändert.\n\n"
        f"- [Übernommener Stand]({base}/blob/{manifest['reviewed_commit']}/{file_path})\n"
        f"- [Aktueller Stand]({base}/blob/{head}/{file_path})\n"
        f"- [Commit-Vergleich]({base}/compare/{manifest['reviewed_commit']}...{head}) "
        "(enthält auch andere Dateien)\n"
        f"- [Dateihistorie]({base}/commits/{quote(manifest['branch'], safe='')}/{file_path})\n\n"
        f"Lokaler Blueprint: `{manifest['local_path']}`.\n\n"
        "Änderungen manuell prüfen und bei Bedarf übernehmen. Es wurde nichts automatisch eingespielt. "
        "Nach der Prüfung die folgenden Werte in `upstream/better_thermostat.json` gemeinsam aktualisieren "
        "(auch wenn die Änderung bewusst nicht übernommen wird):\n\n"
        f"```json\n{json.dumps({'reviewed_commit': head, 'reviewed_blob': blob}, indent=2)}\n```\n"
    )
    result = {"status": "changed", "commit": head, "blob": blob, "body": body}
    if not create_issue:
        return result
    if not destination:
        raise ValueError("GITHUB_REPOSITORY or --repository is required to create an issue")
    # Include closed issues: declining a particular revision should not cause weekly duplicates.
    page = 1
    while True:
        issues = request(f"/repos/{destination}/issues?state=all&per_page=100&page={page}")
        for issue in issues:
            if "pull_request" not in issue and marker in (issue.get("body") or ""):
                return {**result, "status": "already_reported", "issue": issue["html_url"]}
        if len(issues) < 100:
            break
        page += 1
    issue = request(f"/repos/{destination}/issues", {
        "title": f"Better Thermostat: Heizplan-Update prüfen ({blob[:8]})",
        "body": body,
    })
    return {**result, "status": "issue_created", "issue": issue["html_url"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-issue", action="store_true", help="Create an issue; otherwise read-only")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    print(json.dumps(check_upstream(manifest, args.repository, args.create_issue), indent=2))


if __name__ == "__main__":
    main()
