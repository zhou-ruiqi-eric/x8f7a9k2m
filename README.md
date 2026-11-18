# x8f7a9k2m

Automated public-event processing and static asset deployment.

Required Actions secrets: `GH_EVENTS_PAT`, `DATA_ENCRYPTION_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

Before enabling `a4`, initialize `state/index.json` once on the machine that holds the current 20,000-file `pages_assets` directory:

`python src/p4.py --init-manifest /path/to/pages_assets`

Commit the generated manifest as the repository's single initial commit. The Cloudflare token needs Cloudflare Pages Edit permission for project `fiatdock-data`.
