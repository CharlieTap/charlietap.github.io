"""build a temporary article to check publication and stable urls."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as xml

from prepare_posts import prepare_posts


@unittest.skipUnless(shutil.which("hugo"), "hugo must be available to run the integration test")
class SiteTests(unittest.TestCase):
    def test_publish_edit_and_unpublish(self):
        source = Path(__file__).resolve().parent.parent
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for directory in ("layouts", "assets", "static"):
                shutil.copytree(source / directory, root / directory)
            shutil.copy(source / "hugo.toml", root)
            posts = root / "content/posts"
            posts.mkdir(parents=True)
            post = posts / "stable-address.md"
            post.write_text("---\ntitle: Learning Kotlin and WebAssembly\ndraft: false\n---\n\nHello **world**.\n")
            prepare_posts(posts, datetime(2026, 1, 2, 12, tzinfo=timezone.utc))
            first = post.read_text()

            def build():
                result = subprocess.run(["hugo", "--source", str(root), "--cleanDestinationDir", "--panicOnWarning"], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return xml.parse(root / "public/index.xml")

            feed = build()
            page = root / "public/writing/stable-address/index.html"
            self.assertTrue(page.exists())
            self.assertIn("2026-01-02", page.read_text())
            self.assertIn("Learning Kotlin and WebAssembly", page.read_text())
            self.assertEqual(feed.findtext("./channel/item/title"), "Learning Kotlin and WebAssembly")
            self.assertIn("Hello <strong>world</strong>", feed.findtext("./channel/item/description"))
            self.assertEqual(feed.findtext("./channel/item/link"), "https://charlietap.github.io/writing/stable-address/")

            post.write_text(first.replace("Learning Kotlin and WebAssembly", "More lessons from WebAssembly"))
            self.assertEqual(prepare_posts(posts), [])
            build()
            self.assertTrue(page.exists(), "editing the title must not change the url")
            self.assertIn("More lessons from WebAssembly", page.read_text())
            self.assertIn("date: 2026-01-02T12:00:00+00:00", post.read_text())

            post.write_text(post.read_text().replace("draft: false", "draft: true"))
            feed = build()
            self.assertFalse(page.exists())
            self.assertEqual(feed.findall("./channel/item"), [])
            self.assertNotIn("stable-address", (root / "public/index.html").read_text())
            self.assertNotIn("stable-address", (root / "public/sitemap.xml").read_text())


if __name__ == "__main__":
    unittest.main()
