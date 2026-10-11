"""Tests for validation logic (checks.scan)."""

import os
import unittest
from unittest import mock

import _support
from _support import TempTreeTestCase

from linklattice.checks import scan
from linklattice.scanner import Config


class RelativeLinkTests(TempTreeTestCase):
    def test_valid_relative_link_resolves(self):
        self.write("README.md", "See [the guide](guide.md) for details.\n")
        self.write("guide.md", "# Guide\n")
        result = scan(self.root)
        self.assertEqual([], result.findings)
        self.assertEqual(2, result.files_scanned)
        self.assertEqual(1, result.links_checked)
        self.assertTrue(result.ok)

    def test_broken_file_link_is_error_with_line_number(self):
        self.write("README.md", "intro\n\nline two\n[broken](missing.md)\n")
        result = scan(self.root)
        self.assertEqual(1, len(result.findings))
        finding = result.findings[0]
        self.assertEqual("error", finding.severity)
        self.assertEqual(4, finding.line)
        self.assertEqual("README.md", finding.file)
        self.assertEqual("missing.md", finding.target)
        self.assertIn("does not exist", finding.reason)
        self.assertEqual(1, result.errors)

    def test_nested_relative_path(self):
        self.write("docs/index.md", "[up](../README.md)\n")
        self.write("README.md", "# Root\n")
        self.assertEqual([], scan(self.root).findings)

    def test_percent_encoded_path(self):
        self.write("README.md", "[a](my%20file.md)\n")
        self.write("my file.md", "# hi\n")
        self.assertEqual([], scan(self.root).findings)

    def test_directory_target_without_anchor_is_ok(self):
        self.write("README.md", "[docs](docs/)\n")
        self.write("docs/index.md", "# hi\n")
        self.assertEqual([], scan(self.root).findings)

    def test_missing_image_path_is_error(self):
        self.write("README.md", "![logo](assets/logo.png)\n")
        result = scan(self.root)
        self.assertEqual(1, result.errors)
        self.assertEqual("assets/logo.png", result.findings[0].target)

    def test_existing_image_path_is_ok(self):
        self.write("README.md", "![logo](assets/logo.png)\n")
        self.write("assets/logo.png", "png-bytes")
        self.assertEqual([], scan(self.root).findings)

    def test_link_inside_code_fence_is_not_checked(self):
        self.write("README.md", "```\n[skip](missing.md)\n```\n")
        result = scan(self.root)
        self.assertEqual(0, result.links_checked)
        self.assertEqual([], result.findings)

    def test_case_mismatch_is_reported(self):
        self.write("README.md", "[me](readme.MD)\n")
        result = scan(self.root)
        self.assertEqual(1, result.errors)
        self.assertEqual("readme.MD", result.findings[0].target)
        self.assertEqual("error", result.findings[0].severity)

    def test_case_mismatch_helper(self):
        from linklattice.checks import _case_mismatch

        self.write("README.md", "# hi\n")
        self.assertTrue(_case_mismatch(os.path.join(self.root, "readme.md")))
        self.assertFalse(_case_mismatch(os.path.join(self.root, "README.md")))


class AnchorTests(TempTreeTestCase):
    def test_valid_anchor_passes(self):
        self.write("README.md", "# Title\n\n[jump](#usage-guide)\n## Usage Guide\n")
        self.assertEqual([], scan(self.root).findings)

    def test_missing_anchor_is_error(self):
        self.write("README.md", "# Title\n\n[jump](#missing-heading)\n")
        result = scan(self.root)
        self.assertEqual(1, result.errors)
        self.assertEqual(3, result.findings[0].line)
        self.assertIn("missing-heading", result.findings[0].reason)

    def test_duplicate_heading_second_slug(self):
        self.write("README.md", "# Same\n\n# Same\n\n[second](#same-1)\n")
        self.assertEqual([], scan(self.root).findings)

    def test_anchor_in_other_file(self):
        self.write("README.md", "[g](guide.md#install)\n")
        self.write("guide.md", "# Install\n")
        self.assertEqual([], scan(self.root).findings)

    def test_broken_anchor_in_other_file(self):
        self.write("README.md", "[g](guide.md#nope)\n")
        self.write("guide.md", "# Install\n")
        result = scan(self.root)
        self.assertEqual(1, result.errors)
        self.assertEqual("README.md", result.findings[0].file)

    def test_anchor_on_non_markdown_file_is_warning(self):
        self.write("README.md", "[spec](spec.pdf#section)\n")
        self.write("spec.pdf", "%PDF-1.4")
        result = scan(self.root)
        self.assertEqual(0, result.errors)
        self.assertEqual(1, result.warnings)
        self.assertEqual("warning", result.findings[0].severity)


class ExternalLinkTests(TempTreeTestCase):
    def test_external_link_skipped_without_network(self):
        self.write("README.md", "[site](https://example.com/page)\n")
        with mock.patch(
            "linklattice.checks.http_status",
            side_effect=AssertionError("network must not be used"),
        ) as mocked:
            result = scan(self.root)
        mocked.assert_not_called()
        self.assertEqual(0, result.errors)
        self.assertEqual(1, result.links_checked)
        self.assertEqual(1, result.skipped)

    def test_mailto_is_skipped(self):
        self.write("README.md", "[mail](mailto:a@example.com)\n")
        result = scan(self.root)
        self.assertEqual(1, result.skipped)
        self.assertEqual([], result.findings)

    def test_check_external_reports_http_error(self):
        self.write("README.md", "[site](https://example.com/missing)\n")
        with mock.patch("linklattice.checks.http_status", return_value=404):
            result = scan(self.root, config=Config(check_external=True))
        self.assertEqual(1, result.warnings)
        self.assertIn("404", result.findings[0].reason)

    def test_check_external_ok(self):
        self.write("README.md", "[site](https://example.com/)\n")
        with mock.patch("linklattice.checks.http_status", return_value=200):
            result = scan(self.root, config=Config(check_external=True))
        self.assertEqual([], result.findings)
        self.assertEqual(0, result.skipped)


class ReferenceLinkTests(TempTreeTestCase):
    def test_reference_definition_resolves(self):
        self.write("README.md", "See the [guide][g] page.\n\n[g]: guide.md\n")
        self.write("guide.md", "# Guide\n")
        result = scan(self.root)
        self.assertEqual([], result.findings)
        self.assertEqual(2, result.links_checked)  # usage + definition

    def test_broken_reference_definition_is_reported(self):
        self.write("README.md", "See [guide][g].\n\n[g]: missing.md\n")
        result = scan(self.root)
        self.assertEqual(1, result.errors)
        self.assertEqual("missing.md", result.findings[0].target)
        self.assertEqual(1, len(result.findings))  # definition + usage deduplicated

    def test_undefined_reference_is_not_falsely_flagged(self):
        self.write("README.md", "See [text][no-such-label] in prose.\n")
        result = scan(self.root)
        self.assertEqual([], result.findings)
        self.assertEqual(0, result.errors)

    def test_broken_reference_anchor(self):
        self.write("README.md", "[top][t]\n\n[t]: #nope\n")
        result = scan(self.root)
        self.assertEqual(1, result.errors)

    def test_quoted_reference_target(self):
        self.write("README.md", "[top][t]\n\n[t]: '#nope'\n")
        result = scan(self.root)
        self.assertEqual(1, result.errors)
        self.assertEqual("#nope", result.findings[0].target)


class FilterTests(TempTreeTestCase):
    def test_exclude_pattern_skips_file(self):
        self.write("README.md", "[ok](guide.md)\n")
        self.write("guide.md", "# Guide\n")
        self.write("vendor/notes.md", "[bad](gone.md)\n")
        result = scan(self.root, excludes=["vendor"])
        self.assertEqual(2, result.files_scanned)
        self.assertEqual([], result.findings)

    def test_exclude_glob(self):
        self.write("README.md", "[ok](guide.md)\n")
        self.write("guide.md", "# Guide\n")
        self.write("vendor/notes.md", "[bad](gone.md)\n")
        result = scan(self.root, excludes=["vendor/*"])
        self.assertEqual(2, result.files_scanned)
        self.assertEqual([], result.findings)

    def test_allow_suppresses_finding(self):
        self.write("README.md", "[gone](missing.md)\n")
        result = scan(self.root)
        self.assertEqual(1, result.errors)
        allowed = scan(self.root, allows=["missing.md"])
        self.assertEqual([], allowed.findings)
        self.assertEqual(1, allowed.skipped)

    def test_config_exclude_and_allow_from_file(self):
        self.write(
            ".linklattice.json",
            '{"exclude": ["vendor"], "allow": ["legacy/*"], "check_external": false}',
        )
        self.write("README.md", "[a](legacy/a.md)\n[b](missing.md)\n")
        self.write("vendor/notes.md", "[bad](gone.md)\n")
        result = scan(self.root, config=Config(exclude=["vendor"], allow=["legacy/*"]))
        self.assertEqual(1, result.files_scanned)
        self.assertEqual(1, result.errors)
        self.assertEqual(1, result.skipped)


class DiscoveryTests(TempTreeTestCase):
    def test_recursive_scan(self):
        self.write("README.md", "# ok\n")
        self.write("docs/deep/readme.md", "# ok\n")
        self.write("docs/deep/broken.md", "[x](gone.md)\n")
        result = scan(self.root)
        self.assertEqual(3, result.files_scanned)
        self.assertEqual(1, result.errors)
        self.assertEqual("docs/deep/broken.md", result.findings[0].file)

    def test_custom_glob(self):
        self.write("README.md", "[x](gone.md)\n")
        self.write("notes.rst", "[y](gone.rst)\n")
        result = scan(self.root, pattern="*.rst")
        self.assertEqual(1, result.files_scanned)
        self.assertEqual("notes.rst", result.findings[0].file)

    def test_single_file_scan(self):
        path = self.write("README.md", "[x](gone.md)\n")
        result = scan(path)
        self.assertEqual(1, result.files_scanned)
        self.assertEqual("README.md", result.findings[0].file)


if __name__ == "__main__":
    unittest.main()
