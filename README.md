# Threads → Obsidian Google Drive Collector (MVP)

Python MVP that collects Threads posts for target accounts, renders markdown for Obsidian, and uploads files to Google Drive by created-date (KST).

## Implemented MVP Scope

- `python app/main.py collect --accounts ...` CLI (`typer`)
- First-run validation CLI:
  - `python -m app.main check-drive`
  - `python -m app.main check-threads --account <username-or-user-id>`
- Incremental window with `state/collector_state.json`
  - fallback on first run: execution day KST `00:00:00`
- Markdown format from PRD (date/title/body only; no comments section)
- Google Drive upload with OAuth Installed App
- Date folder based on post `created_at` in KST (`YYYY-MM-DD`)
- Dedupe by `(author_id, post_id)` via filename existence check in date folder
- Summary logging + per-account failures
- `.env` + config defaults (`config/accounts.yaml`)
- Baseline tests for pure logic (title, filename/date derivation, window filtering)

## Project Structure

```text
app/main.py
threads_obsidian/
  collector.py
  config.py
  drive_client.py
  markdown.py
  models.py
  state_store.py
  threads_client.py
  time_utils.py
config/accounts.yaml
state/
logs/
tests/
```

## Quickstart

1) Create venv + install deps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Configure environment

```bash
cp .env.example .env
```

3) Put Google OAuth client secret JSON in:

```text
credentials/client_secret.json
```

4) Edit account defaults in `config/accounts.yaml` or pass `--accounts`.

5) First-run validation checklist (recommended)

```bash
# Google Drive OAuth + root folder capability check (non-destructive)
python -m app.main check-drive

# Threads token + account access check (fetch sample posts)
python -m app.main check-threads --account your_threads_username --limit 3
```

6) Run collection

```bash
python -m app.main collect
# or
python -m app.main collect --accounts gptaku_ai,unclejobs.ai,aicoffeechat
# (also supported)
python app/main.py collect
```

## Runtime Outputs

- State file: `state/collector_state.json`
- Log file: `logs/collect-YYYYMMDD-HHMMSS.log`
- Drive path: `<ROOT_FOLDER_ID>/<YYYY-MM-DD>/<YYYY-MM-DD_author_id_post_id.md>`

## Environment Variables

See `.env.example`.

Key variables:
- `THREADS_ACCESS_TOKEN`
- `THREADS_API_BASE_URL`
- `THREADS_PROFILE_LOOKUP_ENDPOINT` (default: `/v1.0/profile_lookup`)
- `THREADS_USER_THREADS_ENDPOINT_TEMPLATE` (default: `/v1.0/{threads_user_id}/threads`)
- `THREADS_POSTS_FIELDS`
- `THREADS_POSTS_LIMIT`
- `GOOGLE_DRIVE_ROOT_FOLDER_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET_FILE`
- `GOOGLE_OAUTH_TOKEN_FILE`

## Notes on Threads API

- This MVP intentionally avoids scraping and uses an HTTP adapter wired for official API usage.
- Threads endpoints can vary by app permissions/product rollout. Third-party account retrieval may be permission-gated by Meta policy/scopes and may fail for some accounts.
- Adapter behavior:
  - Username input is resolved via official `profile_lookup`, then posts are fetched via `/{threads_user_id}/threads`
  - Configurable base URL + endpoint templates + query options (`fields/since/until/limit`)
  - Retry/backoff for transient failures and 429
  - Clear structured errors per account, including permission-gated account hints

## Source Links

- Meta Threads API changelog entry: https://developers.facebook.com/blog/post/2024/06/18/introducing-threads-api-new-way-developers-create-integrations/
- Threads API Postman collection (official workspace): https://www.postman.com/meta/workspace/instagram/documentation/23987686-9386f468-7714-490f-991a-1577f2fcd2bc?entity=request-23987686-e7fc2e7c-fac0-4ee4-a7fd-f2023d0ad998
- Google Drive API Python quickstart: https://developers.google.com/workspace/drive/api/quickstart/python
- Google Drive files.create reference: https://developers.google.com/drive/api/reference/rest/v3/files/create
