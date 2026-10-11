"""Tests for the GitHub slug algorithm and anchor collection."""

import unittest

import _support  # noqa: F401  (puts src/ on sys.path)

from linklattice.anchors import collect_anchors, slugify


class SlugifyTests(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_strips_punctuation(self):
        self.assertEqual(slugify("Fix the bug! (v2.1)"), "fix-the-bug-v21")

    def test_strips_trailing_hash_style_punctuation(self):
        self.assertEqual(slugify("What's new?"), "whats-new")

    def test_keeps_underscores_and_hyphens(self):
        self.assertEqual(slugify("use_foo-bar"), "use_foo-bar")

    def test_uppercase_heading(self):
        self.assertEqual(slugify("API Reference"), "api-reference")

    def test_non_ascii_heading_is_kept(self):
        self.assertEqual(slugify("Ünïcode Höading"), "ünïcode-höading")

    def test_code_span_markers_are_removed_but_content_kept(self):
        self.assertEqual(slugify("Use `pip install` here"), "use-pip-install-here")

    def test_bold_markers_are_removed(self):
        self.assertEqual(slugify("**Bold** heading"), "bold-heading")

    def test_single_word(self):
        self.assertEqual(slugify("Intro"), "intro")


class CollectAnchorsTests(unittest.TestCase):
    def test_collects_atx_headings_casefolded(self):
        anchors = collect_anchors("# Install\n\n## Usage Guide\n")
        self.assertIn("install", anchors)
        self.assertIn("usage-guide", anchors)

    def test_duplicate_headings_get_numeric_suffixes(self):
        text = "# Same\n\n# Same\n\n# Same\n"
        anchors = collect_anchors(text)
        self.assertEqual({"same", "same-1", "same-2"}, anchors)

    def test_headings_inside_fenced_code_are_ignored(self):
        text = "# Real\n\n```bash\n# not a heading\n```\n"
        anchors = collect_anchors(text)
        self.assertIn("real", anchors)
        self.assertNotIn("not-a-heading", anchors)

    def test_tilde_fence_is_honored(self):
        text = "~~~\n# not a heading\n~~~\n# Real\n"
        self.assertEqual({"real"}, collect_anchors(text))

    def test_html_id_and_name_attributes_are_anchors(self):
        text = '<a name="legacy-anchor"></a>\n<div id="custom-id"></div>\n'
        anchors = collect_anchors(text)
        self.assertIn("legacy-anchor", anchors)
        self.assertIn("custom-id", anchors)

    def test_setext_heading(self):
        anchors = collect_anchors("Intro\n=====\n\nSecond\n------\n")
        self.assertIn("intro", anchors)
        self.assertIn("second", anchors)

    def test_yaml_front_matter_is_not_a_heading(self):
        text = "---\ntitle: My Doc\n---\n\n# Body\n"
        anchors = collect_anchors(text)
        self.assertEqual({"body"}, anchors)

    def test_punctuation_and_non_ascii_headings(self):
        anchors = collect_anchors("## What's new?\n\n## Ünïcode Höading\n")
        self.assertIn("whats-new", anchors)
        self.assertIn("ünïcode-höading", anchors)


if __name__ == "__main__":
    unittest.main()
