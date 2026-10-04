# Agent instructions

This is the Hugo source for https://charlietap.github.io, deployed with GitHub Pages. Keep operational documentation here rather than adding a README to the repository landing page.

## Content and design

- Preserve the existing Quiet layout: one column, system fonts, generous spacing and a muted green accent. Templates are in `layouts`; styling is in `assets/style.css`.
- The repository name and URLs are lowercase. Article titles and prose use normal capitalisation.
- When the user requests wording for review, keep it as a draft until they agree to publish. Do not publish invented sample articles.
- The introduction is `content/_index.md`; the About page is `content/about.md`; articles are in `content/posts`.
- Article filenames use lowercase words separated by hyphens. Keep filenames and any explicit slugs stable after publication, even when titles change.

## Publishing

- Pages CMS is configured by `.pages.yml`. Authors write in its visual editor and save with `draft: true` while working; switching to `draft: false` and saving publishes through CI.
- Drafts are excluded from the site, feed and sitemap, but their source is public in this repository.
- The publish workflow adds `date` on first publication and commits it. Preserve that date on later edits or republication. Keep `settings.content.merge: true` in the CMS configuration so it preserves this metadata.
- Images uploaded through the editor belong in `static/uploads` and are served from `/uploads`.
- Pull requests run checks. Pushes to `main` build and deploy automatically using the repository token. The CMS requires its own GitHub App connection.

## Local development

Use the Hugo version in `.hugo-version` and Python 3.10 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r scripts/requirements.txt
hugo server --buildDrafts
```

The local preview is at http://localhost:1313. For validation:

```sh
python -m unittest discover -s scripts -p 'test_*.py'
hugo --gc --minify --cleanDestinationDir --panicOnWarning
python scripts/check_site.py
```

The workflow runs `python scripts/prepare_posts.py` before building. This writes dates into undated articles with `draft: false`; running it locally chooses their publication date early. Use a temporary copy when testing first publication, as the integration test does.

GitHub Actions are pinned to commit hashes. When updating Hugo, update both `.hugo-version` and the Linux archive checksum in `.github/actions/setup/action.yml`.
