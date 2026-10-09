# Webex Token Keeper

Serverless (AWS Lambda + API Gateway + DynamoDB) FastAPI service that runs the
Webex Integration OAuth flow, stores the resulting token under a random user key,
and serves/refreshes it via `GET /api/token/{key}`.

## Layout

- `src/wtk.py` — the entire application (FastAPI app, Pydantic model, DynamoDB
  helpers, Mangum `handler` for Lambda). Keep it a single small module.
- `src/templates/` — Jinja2 pages (Bootstrap 5 via jsdelivr, with SRI hash).
- `src/requirements.txt` — **generated** from `poetry.lock`; SAM packages it.
  Never hand-edit; regenerate with `make update` or
  `poetry export -f requirements.txt --output src/requirements.txt`.
- `tests/` — pytest + moto (`mock_aws`); no AWS account or network needed.
- `template.yml` — SAM/CloudFormation template (all infra).
- `samconfig.toml` — the maintainer's deploy config, **git-crypt encrypted**.
  Never read, edit, or regenerate it (also don't touch `.git-crypt/`).

## Commands

```bash
make setup   # poetry install
make check   # ruff format --check, ruff check, pytest, requirements.txt sync — same as CI
make test    # pytest
make lint    # ruff format + ruff check (mutates files)
make update  # poetry update + regenerate src/requirements.txt
```

Run `make check` before committing. CI (`.github/workflows/ci.yml`) runs the same
checks on Python 3.12 and 3.13, plus `cfn-lint template.yml`.

## Conventions

- Python >= 3.12 (Lambda runtime `python3.13`); Poetry 2.x with PEP 621
  `[project]` metadata and `package-mode = false`.
- Ruff for formatting and linting (rules: default + B, I, Q, UP; line length 88).
- Prefer small, pure functions; keep the app simple.
- Datetimes are timezone-aware UTC (`datetime.now(UTC)`). Tokens stored by older
  versions have naive ISO timestamps; `AccessToken.ensure_utc` treats them as UTC
  — keep that backward compatibility.
- `wtk.py` creates the boto3 table and Webex client at import time, so tests must
  set environment variables and start `mock_aws` before importing `wtk` (see
  `tests/conftest.py`). Mock `wtk.webex_api.access_tokens.get/refresh`, not HTTP.
- Deployment (`make deploy` / `sam deploy`) needs the maintainer's AWS
  credentials and decrypted `samconfig.toml`; never run it from automation.
