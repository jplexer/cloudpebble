# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

CloudPebble is a web-based IDE for developing Pebble smartwatch applications. It runs as a Docker Compose stack of 7 services: nginx (reverse proxy), web (Django), celery (background tasks), qemu (Pebble emulator), ycmd (code completion), redis, postgres, and fake-s3.

## Build and Run Commands

```bash
# Build and start all services
export PUBLIC_URL=http://localhost:8080
docker compose build
docker compose up

# For HTTPS deployments
export PUBLIC_URL=https://your-domain.com
export EXPECT_SSL=yes
docker compose build
docker compose up -d

# Initial setup (installs bower components for mounted volumes)
./dev_setup.sh

# Run tests (inside web container)
docker compose exec web python manage.py test

# Run a single test module
docker compose exec web python manage.py test ide.tests.test_compile

# Run Django shell
docker compose exec web python manage.py shell

# Database migrations
docker compose exec web python manage.py syncdb --noinput
docker compose exec web python manage.py migrate
```

## Tech Stack

- **Python 2.7** with **Django 1.6.2** (legacy, EOL)
- **Celery 3.1** with Redis broker for async build tasks
- **South** for database migrations (predecessor to Django's built-in migrations)
- **Frontend**: jQuery 2.1 + Backbone + CodeMirror 4.2 + noVNC (managed via Bower)
- **Node.js 16.x** (used by Pebble SDK build system and JSHint)
- **Pebble SDK 4.3** with ARM GCC cross-compiler

## Architecture

### Service Topology

```
Browser → nginx:8080 → web:80      (Django app, REST API)
                     → qemu:8001   (emulator WebSocket/VNC)
                     → ycmd:8002   (code completion WebSocket)
                     → s3:4569     (build artifacts via /s3builds/)
```

nginx routes `/qemu/*` to the emulator controller, `/ycmd/*` to the completion proxy, `/s3builds/*` to fake-s3, and everything else to the Django web app.

### Three Separate Codebases

| Directory | Service | Framework | Purpose |
|-----------|---------|-----------|---------|
| `cloudpebble/` | web + celery | Django 1.6 | Main IDE app, REST API, build tasks |
| `cloudpebble-qemu-controller/` | qemu | Flask + gevent | Manages QEMU emulator instances with VNC |
| `cloudpebble-ycmd-proxy/` | ycmd | Flask + gevent | Proxies to ycmd for C autocomplete/errors |

The web and celery containers share the same Docker image. `RUN_WEB=yes` starts Django; `RUN_CELERY=yes` starts the Celery worker.

### Django App Structure (`cloudpebble/`)

- `ide/api/` — REST endpoints returning JSON (project CRUD, source files, resources, builds, git, emulator launch)
- `ide/models/` — Django models: Project, SourceFile, ResourceFile, BuildResult, UserSettings, etc.
- `ide/tasks/` — Celery tasks: `build.py` (compile projects), `git.py` (GitHub sync), `archive.py` (import/export)
- `ide/static/js/` — 57 JavaScript files (jQuery/Backbone SPA, CodeMirror editor, noVNC emulator display)
- `ide/templates/` — Django HTML templates
- `ide/utils/` — SDK project assembly, validation helpers
- `ide/migrations/` — 51 South database migrations
- `auth/` — Authentication (local accounts + Pebble OAuth2)

### Key Data Flow: Build Process

1. Browser POSTs to `/ide/project/<id>/build/run`
2. Django creates a `BuildResult` record and queues a Celery task
3. Celery worker fetches source from S3, generates `appinfo.json`, runs `pebble/waf configure build`
4. Compiled `.pbw` uploaded to S3, `BuildResult` updated
5. Browser polls `/ide/project/<id>/build/last` for status

### Key Data Flow: Emulator

1. Browser POSTs to `/qemu/launch` via nginx
2. QEMU controller spawns a QEMU process (ARM emulator) + pypkjs (JS runtime)
3. Browser connects via WebSocket for VNC display and app installation
4. Emulators auto-kill after 5 minutes without a ping

### Storage

- **PostgreSQL**: Users, projects, source file metadata, build results
- **fake-s3**: Source file contents (bucket: `source.cloudpebble.net`), build artifacts (`builds.cloudpebble.net`), exports (`export.cloudpebble.net`)
- **Redis**: Celery task broker and results

## Important Conventions

- All Django REST endpoints are in `ide/api/` and return JSON responses
- URL routing: `cloudpebble/urls.py` delegates `/ide/` to `ide/urls.py`, `/accounts/` to `auth/urls.py`
- Source file contents are stored in S3, not the database — models store metadata only
- The frontend is a single-page app loaded from `ide/templates/ide/project.html` with 57 JS files included via script tags (no module bundler for most files)
- Pebble platforms: aplite, basalt, chalk, diorite, emery — each has different QEMU machine configs
- Build resource limits enforced via `resource.setrlimit` in Celery tasks (120s CPU, 30MB RAM, 500 open files)

## Environment Variables

Key variables set in `docker-compose.yml`:
- `PUBLIC_URL` — The public-facing URL (e.g., `http://localhost:8080`)
- `EXPECT_SSL` — Set to `yes` for HTTPS deployments
- `AWS_S3_FAKE_S3` — fake-s3 endpoint (`s3:4569`)
- `QEMU_URLS` / `YCM_URLS` — Internal service endpoints
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` — GitHub OAuth (via `GITHUB_ID`/`GITHUB_SECRET` env vars)

## Deployment (exe.dev)

**Live dev instance**: https://cloudpebble-og-dev.exe.xyz/ (public, working)
- Test account: `testuser` / `testpass123`
- Hosted on exe.dev VM `cloudpebble-og-dev`
- exe.dev handles TLS termination, proxying HTTPS to Docker's nginx on port 8080

### Deploying changes

```bash
# 1. Sync local code to remote
rsync -avz --delete --exclude='.git' --exclude='.env' -e "ssh -i ~/.ssh/id_exe" /Users/eric/dev/cloudpebble/ cloudpebble-og-dev.exe.xyz:~/cloudpebble/

# 2. Rebuild and restart on remote
ssh -i ~/.ssh/id_exe cloudpebble-og-dev.exe.xyz "cd ~/cloudpebble && docker compose build && docker compose down && docker compose up -d"
```

### Remote access

```bash
# SSH into the VM
ssh -i ~/.ssh/id_exe cloudpebble-og-dev.exe.xyz

# View logs
ssh -i ~/.ssh/id_exe cloudpebble-og-dev.exe.xyz "cd ~/cloudpebble && docker compose logs web --tail 30"

# Create a user account
ssh -i ~/.ssh/id_exe cloudpebble-og-dev.exe.xyz 'cd ~/cloudpebble && docker compose exec -T web python manage.py shell <<EOF
from django.contrib.auth.models import User
User.objects.create_user("username", "email@example.com", "password")
EOF'
```

### Remote server setup

The `.env` file on the remote sets `PUBLIC_URL=https://cloudpebble-og-dev.exe.xyz` and `EXPECT_SSL=yes`. Docker Compose reads it automatically.

Host nginx is disabled — not needed since exe.dev handles TLS.

### exe.dev platform commands

exe.dev handles TLS termination and proxies HTTPS traffic to the VM. All commands run from the local machine via SSH:

```bash
# Set which port gets proxied to https://vmname.exe.xyz/
ssh -i ~/.ssh/id_exe exe.dev share port <vmname> <port>

# Make publicly accessible (no auth required)
ssh -i ~/.ssh/id_exe exe.dev share set-public <vmname>

# Restrict to authenticated users
ssh -i ~/.ssh/id_exe exe.dev share set-private <vmname>

# Share with specific user or generate a link
ssh -i ~/.ssh/id_exe exe.dev share add <vmname> <email>
ssh -i ~/.ssh/id_exe exe.dev share add-link <vmname>
```

Ports 3000-9999 are also transparently forwarded (e.g., `https://vmname.exe.xyz:3456/`) but only for authenticated users. The main HTTP proxy port is configured via `share port`.

## Changes from Original

- `cloudpebble/requirements.txt`: `psycopg2` upgraded from 2.4.5 to 2.8.6 (old version couldn't parse PostgreSQL 11.x version string)
- Dockerfiles: Debian archive repos, Node.js 16.x, GPG keyserver fixes
- `docker-compose.yml`: Docker Compose v2 format, nginx reverse proxy added
- `EXPECT_SSL` / `PUBLIC_URL` env vars for HTTPS support

## Known Limitations

- No Pebble SSO (Pebble's auth servers are offline) — use local account registration
- No phone installs (requires SSO token) — emulator only
- Python 2.7 / Django 1.6 — print statements, old-style string formatting, `unicode` type throughout
- Bower for frontend dependencies (no npm/webpack for most frontend code)
