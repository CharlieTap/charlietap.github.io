"""check publication semantics without editing real articles."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from prepare_posts import prepare_posts


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.now = datetime(2026, 10, 4, 12, 30, tzinfo=timezone.utc)

    def article(self, filename="article.md", frontmatter="draft: false"):
        path = self.directory / filename
        path.write_text(f"---\ntitle: 'an article'\n{frontmatter}\n---\n\nbody with `Code`.\n")
        return path

    def test_first_publication_is_stamped_once_and_body_is_preserved(self):
        path = self.article()
        original = path.read_text()
        self.assertEqual(prepare_posts(self.directory, self.now), [path])
        first = path.read_text()
        self.assertIn("date: 2026-10-04T12:30:00+00:00", first)
        self.assertEqual(first.split("---\n", 2)[2], original.split("---\n", 2)[2])
        path.write_text(first.replace("body with", "edited body with"))
        edited = path.read_text()
        self.assertEqual(prepare_posts(self.directory), [])
        self.assertEqual(path.read_text(), edited)

    def test_drafts_have_no_publication_date(self):
        path = self.article(frontmatter="draft: true")
        original = path.read_text()
        self.assertEqual(prepare_posts(self.directory, self.now), [])
        self.assertEqual(path.read_text(), original)

    def test_manual_date_is_preserved(self):
        path = self.article(frontmatter="draft: false\ndate: 2025-01-02")
        original = path.read_text()
        self.assertEqual(prepare_posts(self.directory, self.now), [])
        self.assertEqual(path.read_text(), original)

    def test_missing_draft_is_rejected(self):
        self.article(frontmatter="description: a note")
        with self.assertRaisesRegex(ValueError, "draft explicitly"):
            prepare_posts(self.directory, self.now)

    def test_invalid_date_does_not_partially_stamp_other_posts(self):
        first = self.article("a-first.md")
        original = first.read_text()
        self.article("z-last.md", "draft: false\ndate: yesterday")
        with self.assertRaisesRegex(ValueError, "iso 8601"):
            prepare_posts(self.directory, self.now)
        self.assertEqual(first.read_text(), original)

    def test_invalid_title_and_filename_are_rejected(self):
        path = self.article("Upper.md")
        with self.assertRaisesRegex(ValueError, "filename"):
            prepare_posts(self.directory, self.now)
        path.unlink()
        path = self.article()
        path.write_text(path.read_text().replace("an article", "   "))
        with self.assertRaisesRegex(ValueError, "non-empty title"):
            prepare_posts(self.directory, self.now)


if __name__ == "__main__":
    unittest.main()
