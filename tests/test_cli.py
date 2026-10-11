"""Tests for the command line interface: exit codes, formats, flags, config."""

import json
import os
import unittest
from unittest import mock

import _support
from _support import TempTreeTestCase, run_cli


class ExitCodeTests(TempTreeTestCase):
    def test_exit_0_when_no_errors(self):
        self.write("README.md", "# Title\n\nSee [guide](guide.md).\n")
        self.write("guide.md", "# Guide\n")
        code, out, err = run_cli(self.root)
        self.assertEqual(0, code)
        self.assertIn("Summary:", out)
        self.assertEqual("", err)

    def test_exit_1_when_errors(self):
        self.write("README.md", "[broken](missing.md)\n")
        code, out, _ = run_cli(self.root)
        self.assertEqual(1, code)
        self.assertIn("missing.md", out)

    def test_exit_1_when_only_warnings(self):
        self.write("README.md", "[spec](spec.pdf#part)\n")
        self.write("spec.pdf", "%PDF")
        code, _, _ = run_cli(self.root)
        self.assertEqual(0, code, "warnings alone must not fail the run")

    def test_exit_2_when_path_missing_argument(self):
        code, _, err = run_cli()
        self.assertEqual(2, code)
        self.assertIn("path", err)

    def test_exit_2_when_path_does_not_exist(self):
        code, _, err = run_cli(os.path.join(self.root, "nope"))
        self.assertEqual(2, code)
        self.assertIn("does not exist", err)

    def test_exit_2_on_bad_format(self):
        code, _, _ = run_cli(self.root, "--format", "yaml")
        self.assertEqual(2, code)

    def test_exit_2_on_malformed_config(self):
        self.write(".linklattice.json", "{not json")
        code, _, err = run_cli(self.root)
        self.assertEqual(2, code)
        self.assertIn(".linklattice.json", err)

    def test_exit_2_on_bad_config_type(self):
        self.write(".linklattice.json", '{"exclude": "vendor"}')
        code, _, err = run_cli(self.root)
        self.assertEqual(2, code)
        self.assertIn("exclude", err)


class OutputFormatTests(TempTreeTestCase):
    def test_json_output_is_parseable_and_has_keys(self):
        self.write("README.md", "[broken](missing.md)\n")
        code, out, _ = run_cli(self.root, "--format", "json")
        self.assertEqual(1, code)
        payload = json.loads(out)
        self.assertIn("summary", payload)
        self.assertIn("findings", payload)
        self.assertIn("tool", payload)
        summary = payload["summary"]
        for key in (
            "files_scanned",
            "links_checked",
            "errors",
            "warnings",
            "skipped",
            "duration_seconds",
            "root",
        ):
            self.assertIn(key, summary)
        finding = payload["findings"][0]
        for key in ("file", "line", "target", "reason", "severity"):
            self.assertIn(key, finding)
        self.assertEqual(1, summary["errors"])

    def test_json_output_has_no_trailing_text(self):
        self.write("README.md", "# ok\n")
        code, out, _ = run_cli(self.root, "--format", "json")
        self.assertEqual(0, code)
        json.loads(out)  # whole stdout must be one JSON document

    def test_json_no_summary_flag_omits_summary_key(self):
        self.write("README.md", "# ok\n")
        _, out, _ = run_cli(self.root, "--format", "json", "--no-summary")
        self.assertNotIn("summary", json.loads(out))

    def test_quiet_prints_only_summary_line(self):
        self.write("README.md", "[broken](missing.md)\n")
        code, out, _ = run_cli(self.root, "--quiet")
        self.assertEqual(1, code)
        lines = out.strip().splitlines()
        self.assertEqual(1, len(lines))
        self.assertTrue(lines[0].startswith("Summary:"))
        self.assertIn("1 errors", lines[0])

    def test_no_summary_suppresses_summary_line(self):
        self.write("README.md", "[broken](missing.md)\n")
        _, out, _ = run_cli(self.root, "--no-summary")
        self.assertNotIn("Summary:", out)
        self.assertIn("missing.md", out)

    def test_text_report_groups_by_file(self):
        self.write("a.md", "[x](gone.md)\n")
        self.write("b.md", "[y](gone.md)\n")
        _, out, _ = run_cli(self.root)
        self.assertIn("a.md\n", out)
        self.assertIn("b.md\n", out)
        self.assertLess(out.index("a.md"), out.index("b.md"))

    def test_external_skipped_counted_in_summary(self):
        self.write("README.md", "[site](https://example.com/)\n")
        code, out, _ = run_cli(self.root)
        self.assertEqual(0, code)
        self.assertIn("1 skipped", out)
        self.assertIn("1 links checked", out)

    def test_default_run_makes_no_network_calls(self):
        self.write("README.md", "[site](https://example.com/)\n")
        with mock.patch(
            "linklattice.checks.http_status",
            side_effect=AssertionError("network must not be used"),
        ) as mocked:
            code, _, _ = run_cli(self.root)
        mocked.assert_not_called()
        self.assertEqual(0, code)


class FlagTests(TempTreeTestCase):
    def test_glob_flag(self):
        self.write("README.md", "[x](gone.md)\n")
        self.write("notes.rst", "[y](gone.rst)\n")
        _, out, _ = run_cli(self.root, "--glob", "*.rst")
        self.assertIn("notes.rst", out)
        self.assertNotIn("README.md", out)

    def test_exclude_flag(self):
        self.write("README.md", "# ok\n")
        self.write("vendor/notes.md", "[x](gone.md)\n")
        code, _, _ = run_cli(self.root, "--exclude", "vendor")
        self.assertEqual(0, code)

    def test_config_exclude_merges_with_cli(self):
        self.write(".linklattice.json", '{"exclude": ["vendor"]}')
        self.write("README.md", "# ok\n")
        self.write("vendor/notes.md", "[x](gone.md)\n")
        code, _, _ = run_cli(self.root)
        self.assertEqual(0, code)

    def test_config_allow_suppresses_finding(self):
        self.write(".linklattice.json", '{"allow": ["missing.md"]}')
        self.write("README.md", "[gone](missing.md)\n")
        code, _, _ = run_cli(self.root)
        self.assertEqual(0, code)

    def test_cli_allow_suppresses_finding(self):
        self.write("README.md", "[gone](missing.md)\n")
        code, _, _ = run_cli(self.root, "--allow", "missing.md")
        self.assertEqual(0, code)

    def test_config_check_external_true_is_used(self):
        self.write(".linklattice.json", '{"check_external": true}')
        self.write("README.md", "[site](https://example.com/)\n")
        with mock.patch("linklattice.checks.http_status", return_value=200) as mocked:
            code, _, _ = run_cli(self.root)
        mocked.assert_called_once()
        self.assertEqual(0, code)

    def test_cli_can_disable_config_check_external(self):
        self.write(".linklattice.json", '{"check_external": true}')
        self.write("README.md", "[site](https://example.com/)\n")
        with mock.patch(
            "linklattice.checks.http_status",
            side_effect=AssertionError("network must not be used"),
        ) as mocked:
            code, _, _ = run_cli(self.root, "--no-check-external")
        mocked.assert_not_called()
        self.assertEqual(0, code)


@unittest.skipUnless(
    os.environ.get("LINKLATTICE_NET_TESTS") == "1",
    "set LINKLATTICE_NET_TESTS=1 to run live network checks",
)
class LiveNetworkTests(TempTreeTestCase):
    def test_real_head_request(self):
        self.write("README.md", "[site](https://example.com/)\n")
        code, out, _ = run_cli(self.root, "--check-external")
        self.assertIn("0 errors", out)
        self.assertEqual(0, code)


if __name__ == "__main__":
    unittest.main()
