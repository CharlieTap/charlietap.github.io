"""check generated internal links, the feed, and draft exclusion."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as xml
import re

import yaml


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.ids.add(attributes.get("id"))
        for key in ("href", "src"):
            if key in attributes:
                self.links.append(attributes[key])


root = Path("public").resolve()
pages = {}
for path in root.rglob("*.html"):
    parser = Links()
    parser.feed(path.read_text())
    pages[path] = parser

errors = []
for page, parser in pages.items():
    for link in parser.links:
        url = urlsplit(link)
        if url.scheme and url.scheme not in ("http", "https"):
            continue
        if url.netloc and url.netloc != "charlietap.github.io":
            continue
        rawpath = unquote(url.path)
        target = ((root / rawpath.lstrip("/")) if rawpath.startswith("/") else (page.parent / rawpath)).resolve() if rawpath else page
        if target.is_dir():
            target /= "index.html"
        if not target.is_file():
            errors.append(f"{page.relative_to(root)}: broken link {link}")
        elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
            errors.append(f"{page.relative_to(root)}: missing anchor {link}")

feed = xml.parse(root / "index.xml")
sitemap = xml.parse(root / "sitemap.xml")
feed_links = {item.text for item in feed.findall("./channel/item/link")}
sitemap_links = {item.text for item in sitemap.findall("./{*}url/{*}loc")}
for path in Path("content/posts").glob("*.md"):
    if path.name == "_index.md":
        continue
    metadata = yaml.safe_load(re.match(r"\A---\n(.*?)\n---", path.read_text(), re.DOTALL)[1])
    slug = metadata.get("slug", path.stem)
    url = f"https://charlietap.github.io/writing/{slug}/"
    exists = (root / "writing" / slug / "index.html").is_file()
    if metadata["draft"]:
        if exists or url in feed_links or url in sitemap_links:
            errors.append(f"draft is exposed in the generated site: {path}")
    elif not exists or url not in feed_links or url not in sitemap_links:
        errors.append(f"published article missing from site, rss or sitemap: {path}")

if errors:
    raise SystemExit("\n".join(errors))
print(f"checked {len(pages)} pages, internal links, rss, sitemap and draft exclusion")
