# Hawaiʻi Business Express

Independent business-information website for `hawaiibusinessexpress.com`.

## Deployment

The production site is deployed through cPanel Git Version Control.

- GitHub default branch: `main`
- cPanel repository: `/home/vrbaandc/repositories/hbe-site`
- Production document root: `/home/vrbaandc/public_html/hawaiibusinessexpress.com`
- Deployable website files: `site/`
- cPanel deployment configuration: `.cpanel.yml`

After changes are merged to `main`, use cPanel **Git Version Control → Manage → Pull or Deploy → Update from Remote → Deploy HEAD Commit**.

## Search integration

Business searches are handed off to the official Hawaiʻi Department of Commerce and Consumer Affairs (DCCA) search at `https://hbe.dcca.hawaii.gov/search-and-buy`. Search results open in a new tab; this repository does not maintain a copy of the state registry.

## Analytics

Google Analytics tag: `G-MRNR6J06RW`.
