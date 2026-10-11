"""Tests for Markdown link extraction."""

import unittest

import _support  # noqa: F401  (puts src/ on sys.path)

from linklattice.markdown import extract_links, mask_fenced, normalize_label


class InlineLinkTests(unittest.TestCase):
    def test_inline_link_line_number(self):
        text = "line one\nline two\n\nsee [docs](docs.md)\n"
        links = extract_links(text).links
        self.assertEqual(1, len(links))
        self.assertEqual(4, links[0].line)
        self.assertEqual("docs.md", links[0].target)
        self.assertEqual("inline", links[0].kind)
        self.assertFalse(links[0].is_image)

    def test_image_link(self):
        links = extract_links("![logo](assets/logo.png)").links
        self.assertEqual(1, len(links))
        self.assertTrue(links[0].is_image)
        self.assertEqual("assets/logo.png", links[0].target)

    def test_angle_bracket_target_with_spaces(self):
        links = extract_links("[a](<my file.md>)").links
        self.assertEqual("my file.md", links[0].target)

    def test_link_with_title(self):
        links = extract_links('[a](file.md "the title")').links
        self.assertEqual("file.md", links[0].target)

    def test_anchor_only_link(self):
        links = extract_links("[top](#top)").links
        self.assertEqual("#top", links[0].target)


class CodeAwarenessTests(unittest.TestCase):
    def test_link_inside_fenced_block_is_ignored(self):
        text = "before\n\n```\n[nope](missing.md)\n```\n\nafter\n"
        self.assertEqual([], extract_links(text).links)

    def test_link_inside_tilde_fence_is_ignored(self):
        text = "~~~\n![nope](missing.png)\n~~~\n"
        self.assertEqual([], extract_links(text).links)

    def test_link_after_fence_is_still_found(self):
        text = "```\n[skip](a.md)\n```\n\n[keep](b.md)\n"
        links = extract_links(text).links
        self.assertEqual(["b.md"], [link.target for link in links])

    def test_inline_code_span_is_ignored(self):
        text = "use `[not a link](x.md)` inline\n"
        self.assertEqual([], extract_links(text).links)

    def test_unclosed_fence_masks_rest_of_file(self):
        text = "```\n[skip](a.md)\n[skip2](b.md)\n"
        self.assertEqual([], extract_links(text).links)

    def test_fence_with_info_string_masked(self):
        text = '```python\nprint("[skip](a.md)")\n```\n[keep](b.md)\n'
        targets = [link.target for link in extract_links(text).links]
        self.assertEqual(["b.md"], targets)

    def test_backticks_in_info_string_not_a_fence(self):
        text = "``inline`` [keep](a.md)\n"
        self.assertEqual(1, len(extract_links(text).links))

    def test_front_matter_is_masked(self):
        text = '---\nlink: "[skip](a.md)"\n---\n\n[keep](b.md)\n'
        targets = [link.target for link in extract_links(text).links]
        self.assertEqual(["b.md"], targets)


class ReferenceLinkTests(unittest.TestCase):
    def test_reference_definition_is_extracted(self):
        extraction = extract_links("[guide]: guide.md\n")
        self.assertEqual(1, len(extraction.links))
        self.assertEqual("reference_def", extraction.links[0].kind)
        self.assertEqual("guide.md", extraction.links[0].target)
        self.assertEqual({"guide": "guide.md"}, extraction.definitions)

    def test_reference_usage_is_extracted(self):
        extraction = extract_links("read the [guide][guide] page\n")
        kinds = [link.kind for link in extraction.links]
        self.assertEqual(["reference_use"], kinds)

    def test_label_normalization(self):
        extraction = extract_links("[My Guide]: guide.md\nsee [x][MY GUIDE]\n")
        self.assertEqual("guide.md", extraction.definitions["my guide"])
        self.assertEqual(normalize_label("  My   Guide "), "my guide")

    def test_undefined_reference_is_not_an_inline_link(self):
        extraction = extract_links("see [text][undefined-label] here\n")
        self.assertEqual(["reference_use"], [l.kind for l in extraction.links])
        self.assertEqual({}, extraction.definitions)


class HtmlLinkTests(unittest.TestCase):
    def test_html_anchor_and_image(self):
        text = '<a href="guide.md">g</a> and <img src="assets/logo.png" alt="x">'
        targets = [link.target for link in extract_links(text).links]
        self.assertEqual(["guide.md", "assets/logo.png"], targets)
        self.assertFalse(extract_links(text).links[0].is_image)
        self.assertTrue(extract_links(text).links[1].is_image)

    def test_single_quoted_html_attributes(self):
        links = extract_links("<a href='a.md'>x</a>").links
        self.assertEqual("a.md", links[0].target)


class MaskTests(unittest.TestCase):
    def test_mask_preserves_line_count(self):
        text = "a\n```\nb\n```\nc\n"
        masked = mask_fenced(text)
        self.assertEqual(len(text.splitlines()), len(masked.splitlines()))
        self.assertEqual(["a", "", "", "", "c"], masked.splitlines())


if __name__ == "__main__":
    unittest.main()
