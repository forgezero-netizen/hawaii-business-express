# Hawaiʻi Business Express Article Publishing

Articles are authored as Markdown files in this folder and are converted to live HTML during the GitHub Actions deployment.

## Create an article

1. Copy `ARTICLE-TEMPLATE.md` to a new file, such as `hawaii-annual-report-guide.md`.
2. Fill in every required front-matter field.
3. Write the article in Markdown.
4. Keep `draft: true` while the article is being reviewed.
5. Change to `draft: false` when it is approved for publication.
6. Commit or upload the Markdown file to `content/articles/`.

A push affecting `content/**` triggers the deployment workflow. The build validates the article, generates the public page, updates article search, and adds published articles to the sitemap.

## Required metadata

- `title`
- `slug`
- `description`
- `category`
- `published`

The build also validates `updated`, `featured`, `draft`, `keywords`, and the slug format.

Approved categories:

- Starting a Business
- Managing a Business
- Compliance
- Taxes
- Financing
- Marketing
- Business Strategy

Only one published article may have `featured: true`.

## Images

Article images are optional. If an image is used, place it under:

`site/assets/articles/<article-slug>/`

Then set `image` to the file name, such as:

`image: "annual-report.jpg"`

You may also use a root-relative path (starting with `/`) or a full HTTPS URL.

## Public URLs

A published article with:

`slug: "hawaii-annual-report-guide"`

is published at:

`https://hawaiibusinessexpress.com/articles/hawaii-annual-report-guide/`

Do not change a published slug unless you intentionally want to change its public URL.

## Safety controls

- `draft: true` excludes the article from the live page, search index, and sitemap.
- Missing required metadata fails the deployment.
- Invalid categories fail the deployment.
- Duplicate slugs fail the deployment.
- More than one featured published article fails the deployment.
