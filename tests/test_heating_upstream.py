from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_heating_upstream", ROOT / "scripts/check_heating_upstream.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class UpstreamTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(checker.MANIFEST.read_text())
        self.before = deepcopy(self.manifest)
        self.blob = "b" * 40
        self.head = "a" * 40
        self.issues = []
        self.calls = []

    def request(self, path, data=None):
        self.calls.append((path, data))
        if "/commits/" in path:
            return {"sha": self.head}
        if "/contents/" in path:
            self.assertIn(self.head, path)
            return {"type": "file", "sha": self.blob}
        if data is not None:
            return {"html_url": "https://github.com/example/repo/issues/1"}
        page = int(path.split("page=")[-1])
        return self.issues[(page - 1) * 100:page * 100]

    def check(self, write=False):
        result = checker.check_upstream(self.manifest, "example/repo", write, self.request)
        self.assertEqual(self.manifest, self.before)
        return result

    def test_unrelated_commits_do_not_open_issues(self):
        self.blob = self.manifest["reviewed_blob"]
        self.assertEqual(self.check(True)["status"], "unchanged")
        self.assertEqual(len(self.calls), 2)

    def test_default_is_read_only(self):
        self.assertEqual(self.check()["status"], "changed")
        self.assertTrue(all(data is None for _, data in self.calls))

    def test_changed_file_creates_issue_with_compare_and_baseline(self):
        result = self.check(True)
        self.assertEqual(result["status"], "issue_created")
        self.assertIn("/compare/", self.calls[-1][1]["body"])
        self.assertIn(self.blob, self.calls[-1][1]["body"])

    def test_closed_issue_on_second_page_prevents_duplicates(self):
        body = self.check()["body"]
        self.issues = [{"body": "unrelated"} for _ in range(100)]
        self.issues.append({"body": body, "state": "closed", "html_url": "existing"})
        self.assertEqual(self.check(True)["status"], "already_reported")
        self.assertTrue(all(data is None for _, data in self.calls))

    def test_new_revision_after_closed_issue_creates_new_issue(self):
        body = self.check()["body"]
        self.issues = [{"body": body, "state": "closed", "html_url": "existing"}]
        self.blob = "c" * 40
        self.assertEqual(self.check(True)["status"], "issue_created")

    def test_api_failure_propagates_instead_of_reporting_no_changes(self):
        def broken(path, data=None):
            raise OSError("API unavailable")
        with self.assertRaises(OSError):
            checker.check_upstream(self.manifest, request=broken)


if __name__ == "__main__":
    unittest.main()
