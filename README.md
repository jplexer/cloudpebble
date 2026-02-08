# CloudPebble

A web-based IDE for developing Pebble smartwatch applications. Write C or JavaScript, compile, and test on an in-browser emulator — all from the browser.

**Live demo:** https://cloudpebble-og-dev.exe.xyz (test with `testuser`/`testpass123`)

## Quick Start

```bash
git clone https://github.com/coredevices/cloudpebble.git
cd cloudpebble
export PUBLIC_URL=http://localhost:8080
docker compose build
docker compose up
# Open http://localhost:8080 and register an account
```

For HTTPS behind a reverse proxy:

```bash
export PUBLIC_URL=https://your-domain.com
export EXPECT_SSL=yes
docker compose build
docker compose up -d
```

Optional services (emulator, code completion):

```bash
docker compose --profile emulator --profile codecomplete up -d
```

## Architecture

```
Browser → nginx:8080 → web:80       (Django app)
                     → qemu:80      (emulator, WebSocket/VNC)
                     → ycmd:80      (code completion, WebSocket)
                     → s3:4569      (build artifacts via /s3builds/)

web ←→ postgres      (database)
    ←→ redis         (Celery broker)
    ←→ s3            (source files, builds)

celery ←→ same backends (background build tasks)
```

### Services

| Service | Image | Purpose |
|---------|-------|---------|
| **nginx** | nginx:alpine | Reverse proxy, WebSocket routing, S3 proxy |
| **web** | Python 3.11 + Django 4.2 | IDE frontend and REST API |
| **celery** | Same as web | Background build tasks |
| **qemu** | Python 3.11 + QEMU | Pebble emulator with VNC (profile: `emulator`) |
| **ycmd** | Python 3.11 + ycmd/clang | C code completion (profile: `codecomplete`) |
| **redis** | redis | Celery task broker |
| **postgres** | postgres:16 | Database |
| **s3** | kuracloud/fake-s3 | S3-compatible object storage |

### Three Codebases

| Directory | Service | Framework |
|-----------|---------|-----------|
| `cloudpebble/` | web + celery | Django 4.2 + Celery 5.x |
| `cloudpebble-qemu-controller/` | qemu | Flask + gevent |
| `cloudpebble-ycmd-proxy/` | ycmd | Flask + gevent |

The web and celery containers share the same Docker image. `RUN_WEB=yes` starts Django; `RUN_CELERY=yes` starts the Celery worker.

## How It Works

### Building Apps

1. User clicks "Run" in the browser
2. Django creates a `BuildResult` and queues a Celery task
3. Celery assembles source files from S3, runs `pebble build`
4. Compiled `.pbw` is uploaded to S3
5. Browser polls for build status and shows results

### Emulator

1. Browser POSTs to `/qemu/launch` via nginx
2. QEMU controller spawns a QEMU ARM emulator + pypkjs (JS runtime)
3. Browser connects via WebSocket for VNC display
4. Emulators auto-kill after 5 minutes without a ping

Platforms: aplite (Pebble), basalt (Time), chalk (Time Round), diorite (Pebble 2), emery (Time 2)

### Code Completion

1. Browser POSTs to `/ycmd/spinup` to initialize a session
2. Proxy spawns a ycmd instance per target platform with Pebble SDK headers
3. Browser connects via WebSocket for real-time completions, errors, and go-to-definition

## Development

```bash
# Run tests
docker compose exec web python manage.py test

# Run a single test module
docker compose exec web python manage.py test ide.tests.test_compile

# Django shell
docker compose exec web python manage.py shell

# Database migrations
docker compose exec web python manage.py migrate

# Create a user via CLI
docker compose exec web python manage.py shell -c "
from django.contrib.auth.models import User
User.objects.create_user('username', 'email@example.com', 'password')
"
```

### Django App Structure

- `ide/api/` — REST endpoints returning JSON (project CRUD, source files, resources, builds, git, emulator, autocomplete)
- `ide/models/` — Database models: Project, SourceFile, ResourceFile, BuildResult, UserSettings
- `ide/tasks/` — Celery tasks: `build.py` (compile), `git.py` (GitHub sync), `archive.py` (import/export)
- `ide/static/ide/js/` — Frontend JavaScript (jQuery + Backbone + CodeMirror SPA)
- `auth/` — Authentication (local accounts + Pebble/Rebble OAuth2)

### Environment Variables

Key variables set in `docker-compose.yml`:

| Variable | Purpose |
|----------|---------|
| `PUBLIC_URL` | Public-facing URL (e.g. `http://localhost:8080`) |
| `EXPECT_SSL` | Set to `yes` for HTTPS deployments |
| `AWS_S3_FAKE_S3` | fake-s3 endpoint (default: `s3:4569`) |
| `QEMU_URLS` | Emulator controller URL |
| `YCM_URLS` | Code completion proxy URL |
| `GITHUB_ID` / `GITHUB_SECRET` | GitHub OAuth (optional) |

## Production Deployment

### Simple (Single Server)

The nginx container listens on port 8080. Point your reverse proxy (Caddy, Traefik, etc.) at it for TLS termination.

### Scaled (Hybrid Architecture)

For production at scale, split stateless services onto a PaaS and run the emulator on dedicated hardware:

```
Browser ──→ Railway
              ├── Web (Django) ──→ Supabase (Postgres + Auth)
              │                ──→ Upstash (Redis)
              │                ──→ Cloudflare R2 (object storage)
              ├── Celery worker ──→ same backends
              └── ycmd proxy

Browser ──→ Hetzner (direct WebSocket for VNC)
              └── QEMU controller (Docker + nginx + TLS)
```

QEMU runs on dedicated hardware because ARM emulation needs ~400MB RAM per instance and long-lived WebSocket connections — making it 3-10x cheaper on a dedicated server vs PaaS.

| Service | Provider | Spec | ~Monthly Cost |
|---------|----------|------|---------------|
| Web (Django) | Railway | ~1 vCPU, 1GB | $30 |
| Celery worker | Railway | ~2 vCPU, 2GB | $60 |
| ycmd proxy | Railway | ~0.5 vCPU, 512MB | $15 |
| QEMU controller | Hetzner AX42 | 8C/16T, 64GB DDR5 | $50 |
| PostgreSQL + Auth | Supabase Pro | 8GB DB, 100K MAU | $25 |
| Redis | Upstash | Pay-as-you-go | $3 |
| Object storage | Cloudflare R2 | 500GB, zero egress | $10 |
| **Total** | | | **~$200/mo** |

**Capacity:** ~1,000 developers doing 20 builds/month + 5 hrs emulator/month. The Hetzner server handles 150+ concurrent emulators.

Set `QEMU_URLS` to the Hetzner server's public HTTPS endpoint. The browser connects directly to Hetzner for VNC — no traffic proxied through Railway.

## Tech Stack

- **Backend:** Python 3.11, Django 4.2 LTS, Celery 5.x, PostgreSQL 16, Redis
- **Frontend:** jQuery 2.1, Backbone, CodeMirror 4.2, noVNC (Bower-managed)
- **Build:** pebble-tool 5.0 + SDK 4.9, ARM GCC cross-compiler
- **Emulator:** coredevices/qemu (ARM Cortex-M3/M4), pypkjs (JS runtime)
- **Code Completion:** ycm-core/ycmd with Clang completer

## Known Limitations

| Limitation | Notes |
|------------|-------|
| No Pebble SSO | Pebble's auth servers are gone; use local accounts |
| No phone installs | Requires SSO token; use emulator instead |
| Code completion | WIP — container builds but not yet functional end-to-end |

## Credits

- Originally written by Katharine Berry, supported by [Pebble Technology](https://github.com/pebble)
- Community revival at [Rebble](https://rebble.io)
- Docker Compose setup by [iSevenDays](https://github.com/iSevenDays/cloudpebble-composed)
- 2026 modernization by Eric Migicovsky

## License

MIT — see [LICENSE](LICENSE).
