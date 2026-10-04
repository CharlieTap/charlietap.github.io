# charlietap

a quiet home for writing: [charlietap.github.io](https://charlietap.github.io).

the site uses hugo, a small custom layout, and github pages. it has no browser javascript, external fonts, analytics, or paid hosting services.

## write and publish

1. open [pages cms](https://app.pagescms.org), sign in with github, and install its github app for this repository only.
2. select `charlietap.github.io`, the `main` branch, and `posts`.
3. create an article, give it a lowercase title, and write in the visual editor. new articles start as drafts.
4. save with `draft` switched on while you work. to publish, switch `draft` off and save.
5. the [publish workflow](https://github.com/charlietap/charlietap.github.io/actions/workflows/publish.yml) builds and deploys the site. allow a minute or two for the change to appear.

the first time an article is published, the workflow adds its publication date to the markdown file and commits it. later edits keep that date. you do not need to enter it yourself. reopen the article after its first publication so the editor has the latest version.

edit an article and save to update it. turn `draft` back on to remove it from the live site; publishing it again keeps its original date. deleting a post removes it from the live site on the next deployment.

drafts are excluded from the website and feed, but their source is visible in this public repository. use a private writing app for anything you want to keep private.

`my-first-post.md` is an unpublished example to replace or delete. edit the introduction and about page in the same editor. uploaded images go in `static/uploads`.

## use markdown directly

you can also edit files on github or locally. save each article in `content/posts`, with a lowercase, hyphen-separated filename:

```yaml
---
title: an article title
draft: true
---
```

write the body below the closing separator. change `draft` to `false` to publish. omit `date` for automatic dating, or set a past date such as `date: 2026-10-04` when importing an older article. preserve an existing date when editing.

article addresses use the filename, for example `/writing/an-article-title/`. keep the filename after publishing so links stay stable; changing the title alone is fine. the cms merges fields with the saved markdown so the automatic date is preserved.

## local preview

install the hugo version in `.hugo-version` and python 3.10 or newer. then:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements.txt
hugo server --buildDrafts
```

the preview is available at `http://localhost:1313`. draft preview is local only.

to check a production build:

```sh
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/prepare_posts.py
hugo --gc --minify --cleanDestinationDir --panicOnWarning
python scripts/check_site.py
```

the prepare step writes a date into any undated article with `draft: false`. running it locally counts as choosing that article's publication date; leave dating to the workflow if you want to record the first publishing run instead.

## automation

pull requests run validation without deploying. changes to `main` run the checks, preserve first publication dates, build the site, and deploy through github pages. workflows use the repository's automatic token; no personal access token is needed. the cms has its own github app connection.

the hugo download is version-pinned and checksum-verified; github actions are pinned to commit hashes. when updating hugo, update both `.hugo-version` and the linux archive checksum in `.github/actions/setup/action.yml`.

site layout lives in `layouts`, styling in `assets/style.css`, and the cms configuration in `.pages.yml`. the design intentionally keeps the content central: one column, system fonts, generous spacing and a muted green accent.
