#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-cirp-eoi-monitor}"
GITHUB_OWNER="${GITHUB_OWNER:-}"
RENDER_WORKSPACE="${RENDER_WORKSPACE:-tea-d77lneruibrs73c2s4bg}"
RENDER_REGION="${RENDER_REGION:-singapore}"
RENDER_WEB_PLAN="${RENDER_WEB_PLAN:-0.5c-512mb}"
RENDER_CRON_PLAN="${RENDER_CRON_PLAN:-0.5c-512mb}"
RENDER_DB_PLAN="${RENDER_DB_PLAN:-basic_256mb}"

command -v brew >/dev/null || { echo 'Homebrew is required: https://brew.sh'; exit 1; }
brew install gh jq render >/dev/null

gh auth status >/dev/null 2>&1 || gh auth login -w
render whoami -o json >/dev/null 2>&1 || render login
render workspace set "$RENDER_WORKSPACE"

if [ ! -d .git ]; then
  git init -b main
  git add .
  git -c user.name="${GIT_AUTHOR_NAME:-CIRP EOI Monitor}" -c user.email="${GIT_AUTHOR_EMAIL:-cirp-eoi@local}" commit -m "Initial CIRP EOI monitor"
else
  git branch -M main
fi

if [ -z "$GITHUB_OWNER" ]; then
  GITHUB_OWNER="$(gh api user -q .login)"
fi
REPO="$GITHUB_OWNER/$APP_NAME"

if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --private --source=. --remote=origin --push
else
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "git@github.com:$REPO.git"
  git push -u origin HEAD:main
fi
REPO_URL="https://github.com/$REPO"

APP_PASSWORD="${APP_PASSWORD:-$(openssl rand -base64 24 | tr -d '\n')}"

DB_JSON=$(render pg create --name "$APP_NAME-db" --database-name cirp_eoi --database-user cirp_eoi --plan "$RENDER_DB_PLAN" --region "$RENDER_REGION" --workspace "$RENDER_WORKSPACE" --confirm -o json)
DB_ID=$(printf '%s' "$DB_JSON" | jq -r '.id // .postgres.id // .database.id')
if [ -z "$DB_ID" ] || [ "$DB_ID" = "null" ]; then echo "$DB_JSON"; echo 'Could not determine DB id'; exit 1; fi
DB_INFO=$(render pg get "$DB_ID" --include-sensitive-connection-info -o json)
DATABASE_URL=$(printf '%s' "$DB_INFO" | jq -r '.. | .internalConnectionString? // empty' | head -1)
[ -n "$DATABASE_URL" ] || DATABASE_URL=$(printf '%s' "$DB_INFO" | jq -r '.. | .connectionString? // empty' | head -1)
[ -n "$DATABASE_URL" ] || { echo "$DB_INFO"; echo 'Could not determine DB connection string'; exit 1; }
# SQLAlchemy psycopg scheme
DATABASE_URL="${DATABASE_URL/postgresql:\/\//postgresql+psycopg:\/\/}"

WEB_JSON=$(render services create --name "$APP_NAME" --type web_service --repo "$REPO_URL" --branch main --runtime python --region "$RENDER_REGION" --plan "$RENDER_WEB_PLAN" --auto-deploy --build-command "pip install -r requirements.txt" --start-command "python -m app.cli init-db && uvicorn app.main:app --host 0.0.0.0 --port \$PORT" --health-check-path /healthz --env-var "DATABASE_URL=$DATABASE_URL" --env-var "APP_USERNAME=lawyer" --env-var "APP_PASSWORD=$APP_PASSWORD" --env-var "FETCH_PDFS=true" --output json --confirm)
WEB_ID=$(printf '%s' "$WEB_JSON" | jq -r '.id // .service.id')

CRON_JSON=$(render services create --name "$APP_NAME-ingest" --type cron_job --repo "$REPO_URL" --branch main --runtime python --region "$RENDER_REGION" --plan "$RENDER_CRON_PLAN" --auto-deploy --build-command "pip install -r requirements.txt" --cron-schedule "30 20 * * *" --cron-command "python -m app.cli init-db && python -m app.cli ingest" --env-var "DATABASE_URL=$DATABASE_URL" --env-var "FETCH_PDFS=true" --output json --confirm)
CRON_ID=$(printf '%s' "$CRON_JSON" | jq -r '.id // .service.id')

cat <<OUT

Deployment created.
Repository: $REPO_URL
Database:   $DB_ID
Web:        $WEB_ID
Cron:       $CRON_ID
Username:   lawyer
Password:   $APP_PASSWORD

Store that password in your password manager now.
Run a first ingestion with:
  render jobs create $CRON_ID --start-command "python -m app.cli ingest --pages 40" -o json --confirm

Then inspect:
  render services
  render logs -r $CRON_ID --tail
OUT
