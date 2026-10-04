"""validate articles and record their first publication date."""

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import re

import yaml


def prepare_posts(directory: Path, now: datetime | None = None) -> list[Path]:
    timestamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    updates = []
    for path in sorted(directory.glob("*.md")):
        if path.name == "_index.md":
            continue
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.md", path.name):
            raise ValueError(f"{path}: use a lowercase, hyphen-separated filename")
        text = path.read_text(encoding="utf-8")
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
        if not match:
            raise ValueError(f"{path}: yaml front matter is required")
        metadata = yaml.safe_load(match[1])
        if not isinstance(metadata, dict):
            raise ValueError(f"{path}: front matter must be a mapping")
        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip() or title != title.lower():
            raise ValueError(f"{path}: a lowercase title is required")
        if type(metadata.get("draft")) is not bool:
            raise ValueError(f"{path}: set draft explicitly to true or false")
        if "slug" in metadata and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(metadata["slug"])):
            raise ValueError(f"{path}: the slug must be lowercase and hyphen-separated")
        published = metadata.get("date")
        if "date" in metadata and published is None:
            raise ValueError(f"{path}: remove the empty date field to use an automatic date")
        if published is not None:
            if isinstance(published, str):
                try:
                    published = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except ValueError as error:
                    raise ValueError(f"{path}: date must be an iso 8601 date or timestamp") from error
            if not isinstance(published, (date, datetime)):
                raise ValueError(f"{path}: date must be an iso 8601 date or timestamp")
        elif not metadata["draft"]:
            # insert only this field; leave the author's formatting and body intact.
            frontmatter = match[1]
            replacement = f"---\n{frontmatter}\ndate: {timestamp}\n---\n"
            updates.append((path, replacement + text[match.end():]))
    # validate the full batch before changing any files.
    for path, text in updates:
        path.write_text(text, encoding="utf-8")
    return [path for path, _ in updates]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("content/posts"))
    args = parser.parse_args()
    for updated in prepare_posts(args.directory):
        print(f"recorded publication date: {updated}")
