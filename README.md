# CloudPebble Composed

CloudPebble is a web-based IDE for developing Pebble smartwatch applications. This repository assembles all CloudPebble components via Docker Compose into a fully functional development environment.

**Updated February 2026** to work with modern Docker, fix EOL Debian repos, and support HTTPS deployments.

## Quick Start

### Local Development

```bash
# 1. Clone this repo
git clone https://github.com/coredevices/cloudpebble.git
cd cloudpebble

# 2. Set your public URL
export PUBLIC_URL=http://localhost:8080

# 3. Build and run
docker compose build
docker compose up

# 4. Open http://localhost:8080 and register an account
```

### HTTPS Deployment (Production)

For HTTPS deployments behind a reverse proxy:

```bash
export PUBLIC_URL=https://your-domain.com
export EXPECT_SSL=yes
docker compose build
docker compose up -d
```

The nginx container listens on port 8080. Configure your reverse proxy to forward HTTPS traffic to it.

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Emulator won't start | Check that QEMU_URLS points to your PUBLIC_URL |
| App install fails | Verify `/s3builds/` proxy: `curl -I ${PUBLIC_URL}/s3builds/test` |
| SSL errors | Set `EXPECT_SSL=yes` for HTTPS deployments |

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [System Components](#system-components)
  - [Web Container](#1-web-container)
  - [Celery Container](#2-celery-container)
  - [QEMU Controller](#3-qemu-controller)
  - [YCMD Proxy](#4-ycmd-proxy)
  - [Redis](#5-redis)
  - [PostgreSQL](#6-postgresql)
  - [S3 Storage](#7-s3-storage)
- [Data Models](#data-models)
- [API Reference](#api-reference)
- [Frontend Architecture](#frontend-architecture)
- [Build System](#build-system)
- [Data Flows](#data-flows)
- [Configuration Reference](#configuration-reference)
- [2026 Updates](#2026-updates)
- [Limitations](#limitations)
- [Modernization Proposal](#modernization-proposal)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    BROWSER                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐│
│  │  Frontend (jQuery + Backbone + CodeMirror)                                      ││
│  │  ├── Project management UI                                                       ││
│  │  ├── Code editor (CodeMirror with C/JS syntax highlighting)                     ││
│  │  ├── Resource manager (images, fonts, raw data)                                 ││
│  │  ├── Build output console                                                        ││
│  │  ├── Emulator display (noVNC canvas)                                            ││
│  │  └── Real-time autocomplete (WebSocket to YCMD)                                 ││
│  └─────────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      │ HTTP/WebSocket
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              NGINX CONTAINER (Port 8080)                             │
│  ├── Reverse proxy for web app                                                      │
│  ├── WebSocket routing (/qemu/*, /ycm/*)                                            │
│  └── S3 builds proxy (/s3builds/*)                                                  │
└─────────────────────────────────────┬───────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              WEB CONTAINER (Port 80)                                 │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  Django 1.6.2 Application                                                      │  │
│  │  ├── cloudpebble/        Django project config, URLs, WSGI                     │  │
│  │  ├── ide/                Core IDE functionality                                 │  │
│  │  │   ├── api/            REST endpoints (JSON responses)                       │  │
│  │  │   │   ├── project.py  CRUD for projects, builds, imports                    │  │
│  │  │   │   ├── source.py   Source file operations                                │  │
│  │  │   │   ├── resource.py Resource file operations                              │  │
│  │  │   │   ├── git.py      GitHub push/pull/repo management                      │  │
│  │  │   │   ├── ycm.py      Autocomplete initialization                           │  │
│  │  │   │   ├── qemu.py     Emulator launch API                                   │  │
│  │  │   │   └── npm.py      NPM package search                                    │  │
│  │  │   ├── models/         Database models (SQLAlchemy-style)                    │  │
│  │  │   │   ├── project.py  Project, TemplateProject                              │  │
│  │  │   │   ├── files.py    SourceFile, ResourceFile, ResourceVariant             │  │
│  │  │   │   ├── build.py    BuildResult, BuildSize                                │  │
│  │  │   │   ├── user.py     UserSettings, UserGithub                              │  │
│  │  │   │   └── dependency.py  NPM dependencies                                   │  │
│  │  │   ├── tasks/          Celery async tasks                                    │  │
│  │  │   │   ├── build.py    Compile projects using Pebble SDK                     │  │
│  │  │   │   ├── git.py      GitHub sync operations                                │  │
│  │  │   │   ├── archive.py  Project import/export (zip)                           │  │
│  │  │   │   └── gist.py     GitHub Gist imports                                   │  │
│  │  │   ├── views/          HTML template views                                   │  │
│  │  │   ├── static/         57 JS files, 8 CSS files                              │  │
│  │  │   ├── templates/      Django HTML templates                                 │  │
│  │  │   ├── utils/          SDK assembly, regex validation                        │  │
│  │  │   └── migrations/     51 South database migrations                          │  │
│  │  ├── auth/               Authentication (local + Pebble OAuth2)                │  │
│  │  ├── root/               Landing page                                          │  │
│  │  └── qr/                 QR code generation for phone pairing                  │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
└─────────┬─────────────────────────┬─────────────────────────┬───────────────────────┘
          │                         │                         │
          ▼                         ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│       REDIS         │   │     POSTGRESQL      │   │    S3 (fake-s3)     │
│    (Port 6379)      │   │    (Port 5432)      │   │    (Port 8003)      │
│                     │   │                     │   │                     │
│ • Celery broker     │   │ • User accounts     │   │ • Source code       │
│ • Task results      │   │ • Projects          │   │ • Build artifacts   │
│ • Session cache     │   │ • Source files      │   │ • Exports           │
│                     │   │ • Resources         │   │                     │
│                     │   │ • Build history     │   │ Buckets:            │
│                     │   │ • GitHub links      │   │ • source.*          │
│                     │   │ • Dependencies      │   │ • builds.*          │
│                     │   │                     │   │ • export.*          │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
          │
          │ Celery Task Queue
          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           CELERY CONTAINER (Background Worker)                       │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  Same codebase as web, runs with RUN_CELERY=yes                               │  │
│  │                                                                                │  │
│  │  Build Process:                                                                │  │
│  │  1. Create temp directory                                                      │  │
│  │  2. Assemble project files from S3/database                                   │  │
│  │  3. Generate appinfo.json / package.json                                      │  │
│  │  4. Run `npm install` if dependencies exist                                   │  │
│  │  5. Execute `pebble/waf configure build`                                      │  │
│  │  6. Extract .pbw file and debug symbols (.elf)                                │  │
│  │  7. Parse addr2line info for crash debugging                                  │  │
│  │  8. Upload artifacts to S3                                                    │  │
│  │  9. Update BuildResult in database                                            │  │
│  │                                                                                │  │
│  │  Resource Limits (per build):                                                 │  │
│  │  • CPU: 120 seconds                                                           │  │
│  │  • Memory: 30 MB                                                              │  │
│  │  • Open files: 500                                                            │  │
│  │  • Output size: 20 MB                                                         │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  Toolchain:                                                                          │
│  ├── /arm-cs-tools/         ARM GCC cross-compiler (arm-none-eabi-gcc)              │
│  ├── /sdk3/                 Pebble SDK 4.3                                          │
│  │   ├── pebble/waf         Build system (Python-based)                             │
│  │   ├── include/           Pebble API headers                                      │
│  │   └── lib/               Prebuilt libraries                                      │
│  └── npm                    Node.js package manager for dependencies                │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         QEMU CONTROLLER (Port 8001)                                  │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  Flask + gevent + WebSocket                                                    │  │
│  │                                                                                │  │
│  │  controller.py:                                                               │  │
│  │  ├── POST /qemu/launch     Create new emulator instance                       │  │
│  │  ├── POST /qemu/<id>/ping  Keep-alive (kills after 5min idle)                │  │
│  │  ├── POST /qemu/<id>/kill  Terminate emulator                                 │  │
│  │  ├── WS   /qemu/<id>/ws/phone  Bluetooth/app communication                    │  │
│  │  └── WS   /qemu/<id>/ws/vnc    VNC display stream (binary)                    │  │
│  │                                                                                │  │
│  │  emulator.py (per instance):                                                  │  │
│  │  ├── Allocates 5 random ports (console, bluetooth, ws, vnc, vnc_ws)          │  │
│  │  ├── Creates SPI flash image from firmware                                   │  │
│  │  ├── Spawns QEMU with platform-specific machine config                       │  │
│  │  ├── Waits for firmware boot (looks for "<SDK Home>" in console)             │  │
│  │  └── Spawns pypkjs for PebbleKit JS runtime                                  │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  QEMU (Pebble fork v2.5.2-pebble4):                                                 │
│  ├── ARM Cortex-M3/M4 emulation                                                     │
│  ├── Pebble-specific peripherals (display, buttons, vibration)                     │
│  └── VNC server for display output                                                  │
│                                                                                      │
│  pypkjs (PebbleKit JS runtime):                                                     │
│  ├── Runs JavaScript companion app code                                             │
│  ├── Simulates phone-side PebbleKit JS environment                                 │
│  ├── Handles AppMessage, localStorage, etc.                                        │
│  └── Connects to QEMU via simulated Bluetooth                                      │
│                                                                                      │
│  Platform Configurations:                                                            │
│  ┌──────────┬──────────────────┬────────────┬──────────────────────────────────┐    │
│  │ Platform │ Machine          │ CPU        │ Watch Models                     │    │
│  ├──────────┼──────────────────┼────────────┼──────────────────────────────────┤    │
│  │ aplite   │ pebble-bb2       │ cortex-m3  │ Original Pebble, Pebble Steel   │    │
│  │ basalt   │ pebble-snowy-bb  │ cortex-m4  │ Pebble Time, Time Steel         │    │
│  │ chalk    │ pebble-s4-bb     │ cortex-m4  │ Pebble Time Round               │    │
│  │ diorite  │ pebble-silk-bb   │ cortex-m4  │ Pebble 2                         │    │
│  │ emery    │ pebble-robert-bb │ cortex-m4  │ Pebble Time 2 (unreleased)      │    │
│  └──────────┴──────────────────┴────────────┴──────────────────────────────────┘    │
│                                                                                      │
│  Firmware Images (/qemu-tintin-images/):                                            │
│  ├── <platform>/<version>/qemu_micro_flash.bin   Main firmware                      │
│  └── <platform>/<version>/qemu_spi_flash.bin     SPI flash template                 │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          YCMD PROXY (Port 8002)                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  Flask + gevent + WebSocket                                                    │  │
│  │                                                                                │  │
│  │  proxy.py:                                                                    │  │
│  │  ├── POST /spinup              Initialize completion session                  │  │
│  │  └── WS   /ycm/<uuid>/ws       Bidirectional completion channel              │  │
│  │                                                                                │  │
│  │  WebSocket Commands:                                                          │  │
│  │  ├── completions    Get autocomplete suggestions at cursor                   │  │
│  │  ├── errors         Get syntax/semantic errors for file                      │  │
│  │  ├── goto           Go to definition of symbol                               │  │
│  │  ├── create         Notify new file created                                  │  │
│  │  ├── delete         Notify file deleted                                      │  │
│  │  ├── rename         Notify file renamed                                      │  │
│  │  ├── resources      Update resource ID definitions                           │  │
│  │  ├── messagekeys    Update AppMessage key definitions                        │  │
│  │  ├── dependencies   Update NPM dependencies (regenerates headers)            │  │
│  │  └── ping           Keep session alive                                       │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ycm_helpers.py:                                                                    │
│  ├── Manages temp directories per session                                          │
│  ├── Syncs file changes via FileSync class                                         │
│  ├── Generates pebble.h / messagekeys.h headers                                    │
│  ├── Spawns separate ycmd instance per platform (aplite, basalt, chalk, diorite)   │
│  └── Handles NPM dependency resolution for type info                               │
│                                                                                      │
│  ycmd (YouCompleteMe daemon):                                                       │
│  ├── Clang-based C/C++ semantic completion                                         │
│  ├── Uses .ycm_extra_conf.py for compiler flags                                   │
│  ├── Includes: ARM toolchain headers, Pebble SDK headers                          │
│  └── Returns: completions, diagnostics, goto locations                            │
│                                                                                      │
│  Generated Headers:                                                                  │
│  ├── __pebble_resource_ids__.h   #define RESOURCE_ID_* for each resource           │
│  └── __pebble_messagekeys__.h    #define MESSAGE_KEY_* for AppMessage keys         │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## System Components

### 1. Web Container

**Image:** Custom (Python 2.7.11 + Node.js 16.x)  
**Port:** 80  
**Build Context:** `cloudpebble/`

The main Django application serving the IDE interface and REST API.

#### Startup Sequence
```bash
# docker_start.sh
python manage.py syncdb --noinput  # Create tables
python manage.py migrate           # Run South migrations
python manage.py runserver 0.0.0.0:$PORT
```

#### Django Apps

| App | Purpose | Key Files |
|-----|---------|-----------|
| `ide` | Core IDE functionality | models/, api/, tasks/, views/, static/ |
| `auth` | Authentication | pebble.py (OAuth2), views.py (login/logout) |
| `root` | Landing page | templates/root/index.html |
| `qr` | QR code generation | views.py (phone pairing codes) |

#### Key Dependencies (requirements.txt)

| Package | Version | Purpose |
|---------|---------|---------|
| Django | 1.6.2 | Web framework |
| celery | 3.1.23 | Async task queue |
| python-social-auth | 0.1.23 | OAuth2 (Pebble SSO) |
| boto | 2.39.0 | S3 client |
| pygithub | 1.14.2 | GitHub API |
| South | 1.0.2 | Database migrations |
| redis | 2.10.5 | Celery broker client |
| gevent | 1.1 | Async I/O |
| Pillow | 2.9.0 | Image processing |
| psycopg2 | 2.4.5 | PostgreSQL client |

#### Environment Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `DEBUG` | `yes` | Enable debug mode |
| `RUN_WEB` | `yes` | Run web server (not celery) |
| `PUBLIC_URL` | `https://cloudpebble.example.com` | Public-facing URL |
| `EXPECT_SSL` | `yes` | Enable HTTPS mode |
| `AWS_S3_FAKE_S3` | `s3:4569` | fake-s3 endpoint |
| `MEDIA_URL` | `${PUBLIC_URL}/s3builds/` | Build artifact URL |
| `QEMU_URLS` | `http://qemu/` | QEMU controller endpoint |
| `YCM_URLS` | `http://ycmd/` | YCMD proxy endpoint |
| `LIBPEBBLE_PROXY` | `wss://cloudpebble-ws.herokuapp.com/tool` | Phone install proxy |
| `PEBBLE_AUTH_URL` | `https://auth.rebble.io` | OAuth endpoint |
| `GITHUB_CLIENT_ID` | `Iv1.0729...` | GitHub OAuth app ID |
| `GITHUB_CLIENT_SECRET` | `8baac2f3...` | GitHub OAuth secret |
| `SECRET_KEY` | `y_!-!-i!_txo...` | Django secret key |

---

### 2. Celery Container

**Image:** Same as web  
**Build Context:** `cloudpebble/`

Background task worker sharing the same codebase as web.

#### Task Definitions

**ide/tasks/build.py** - `run_compile(build_result_id)`
```python
# Simplified flow:
1. Fetch BuildResult from database
2. Create temp directory (optionally in chroot)
3. assemble_project() - write all files
4. npm install (if dependencies)
5. pebble/waf configure build
6. Extract .pbw, debug info, sizes
7. Upload to S3
8. Update BuildResult state
9. Cleanup temp directory
```

**ide/tasks/git.py** - GitHub operations
- `do_import_github(project_id, user, repo, branch)` - Clone and import
- `github_push(project_id, commit_message)` - Push changes
- `github_pull(project_id)` - Pull latest
- `hooked_commit(project_id, commit_sha)` - Handle webhook

**ide/tasks/archive.py** - Import/Export
- `create_archive(project_id)` - Export as .zip
- `do_import_archive(project_id, zip_data)` - Import from .zip

#### Resource Limits

```python
resource.setrlimit(resource.RLIMIT_CPU, (120, 120))      # 2 min CPU
resource.setrlimit(resource.RLIMIT_NOFILE, (500, 500))   # 500 files
resource.setrlimit(resource.RLIMIT_RSS, (30*1024*1024, ...))  # 30 MB RAM
resource.setrlimit(resource.RLIMIT_FSIZE, (20*1024*1024, ...)) # 20 MB output
```

#### Celery Configuration

```python
BROKER_URL = 'redis://redis:6379/1'
CELERY_RESULT_BACKEND = BROKER_URL
CELERYD_TASK_TIME_LIMIT = 620      # Hard kill after 10m20s
CELERYD_TASK_SOFT_TIME_LIMIT = 600 # Soft limit 10m
BROKER_POOL_LIMIT = 10
```

---

### 3. QEMU Controller

**Image:** Custom (Python 2.7 + QEMU + pypkjs)  
**Port:** 8001  
**Build Context:** `cloudpebble-qemu-controller/`

Manages Pebble emulator instances with VNC display streaming.

#### API Endpoints

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/qemu/launch` | POST | Header token | `platform`, `version`, `token`, `tz_offset`, `oauth` | `{uuid, ws_port, vnc_display, vnc_ws_port}` |
| `/qemu/<uuid>/ping` | POST | None | - | `{alive: bool}` |
| `/qemu/<uuid>/kill` | POST | None | - | `{status: "ok"}` |
| `/qemu/<uuid>/ws/phone` | WebSocket | None | Binary frames | Proxied to pypkjs |
| `/qemu/<uuid>/ws/vnc` | WebSocket | None | Binary frames | Proxied to QEMU VNC |

#### Emulator Lifecycle

```python
class Emulator:
    def run(self):
        self._choose_ports()      # Allocate 5 random ports
        self._make_spi_image()    # Copy firmware SPI flash
        self._spawn_qemu()        # Start QEMU process
        gevent.sleep(4)           # Wait for boot
        self._spawn_pkjs()        # Start pypkjs
```

#### Idle Killer

Emulators are automatically killed after 5 minutes without a ping.

---

### 4. YCMD Proxy

**Image:** Custom (Python 2.7 + ycmd + Clang)  
**Port:** 8002  
**Build Context:** `cloudpebble-ycmd-proxy/`

Code intelligence service providing autocomplete, errors, and go-to-definition.

#### Session Lifecycle

```
POST /spinup
├── Create temp directory
├── Write all source files
├── Generate __pebble_resource_ids__.h
├── Generate __pebble_messagekeys__.h
├── Create .ycm_extra_conf.py with SDK paths
├── Spawn ycmd instance per platform (aplite, basalt, chalk, diorite)
└── Return {uuid, ws_port, secure}

WebSocket /ycm/<uuid>/ws
├── Receive JSON commands
├── Route to appropriate ycmd instance
└── Return JSON responses
```

---

### 5. Redis

**Image:** `redis:latest`  
**Port:** 6379

Message broker for Celery and optional session/cache storage.

---

### 6. PostgreSQL

**Image:** `postgres:latest`  
**Port:** 5432

Primary relational database storing all application data.

---

### 7. S3 Storage

**Image:** `kuracloud/fake-s3`  
**Port:** 8003 (mapped to internal 4569)

S3-compatible object storage.

**Buckets:**

| Bucket | Purpose |
|--------|---------|
| `source.cloudpebble.net` | Source code |
| `builds.cloudpebble.net` | Build artifacts (.pbw) |
| `export.cloudpebble.net` | Project exports |

---

## Data Models

### Project

```python
class Project(models.Model):
    owner = models.ForeignKey(User)
    name = models.CharField(max_length=50)
    
    project_type = models.CharField(choices=[
        ('native', 'Pebble C SDK'),
        ('simplyjs', 'Simply.js'),
        ('pebblejs', 'Pebble.js'),
        ('package', 'Pebble Package'),
        ('rocky', 'Rocky.js'),
    ])
    sdk_version = models.CharField(choices=[('2', 'SDK 2'), ('3', 'SDK 4')])
    
    app_uuid = models.CharField(max_length=36)
    app_company_name = models.CharField(max_length=100)
    app_short_name = models.CharField(max_length=100)
    app_long_name = models.CharField(max_length=100)
    app_version_label = models.CharField(max_length=40)
    app_is_watchface = models.BooleanField()
    app_platforms = models.TextField()  # comma-separated
    
    github_repo = models.CharField(max_length=100, null=True)
    github_branch = models.CharField(max_length=100, null=True)
```

### SourceFile / ResourceFile

```python
class SourceFile(models.Model):
    project = models.ForeignKey(Project)
    file_name = models.CharField(max_length=100)
    target = models.CharField(max_length=10, default='app')  # pkjs, app, worker
    # Content stored in S3

class ResourceFile(models.Model):
    project = models.ForeignKey(Project)
    file_name = models.CharField(max_length=100)
    kind = models.CharField(choices=['png', 'font', 'raw', 'pbi'])
```

### BuildResult

```python
class BuildResult(models.Model):
    project = models.ForeignKey(Project)
    state = models.IntegerField(choices=[
        (0, 'Waiting'), (1, 'Running'),
        (2, 'Succeeded'), (3, 'Failed')
    ])
    started = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True)
```

---

## API Reference

### Projects

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /ide/projects` | GET | List user's projects |
| `POST /ide/project/create` | POST | Create new project |
| `GET /ide/project/<id>/info` | GET | Get project details |
| `POST /ide/project/<id>/save_settings` | POST | Update project settings |
| `POST /ide/project/<id>/delete` | POST | Delete project |

### Source Files

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /ide/project/<id>/create_source_file` | POST | Create file |
| `GET /ide/project/<id>/source/<file_id>/load` | GET | Load file content |
| `POST /ide/project/<id>/source/<file_id>/save` | POST | Save file content |

### Builds

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /ide/project/<id>/build/run` | POST | Start build |
| `GET /ide/project/<id>/build/last` | GET | Get last build |
| `GET /ide/project/<id>/build/<build_id>/log` | GET | Get build log |

---

## Frontend Architecture

### JavaScript (57 files)

**Core:** `ide.js`, `sidebar.js`, `editor.js`  
**Features:** `emulator.js`, `autocomplete.js`, `compilation.js`, `github.js`  
**Libraries:** `libpebble/`, `noVNC/`

### Bower Dependencies

- jQuery 2.1, Underscore, Backbone
- CodeMirror 4.2
- noVNC 0.5 (VNC client)
- Bluebird (Promises)
- JSHint

---

## Build System

### SDK Structure

```
/sdk3/
├── pebble/waf         # Build tool
├── include/           # Pebble API headers
└── lib/<platform>/    # Prebuilt libraries
```

### Output

```
build/
├── <platform>/
│   ├── pebble-app.bin
│   ├── pebble-app.elf      # Debug symbols
│   └── app_resources.pbpack
└── <project>.pbw           # Final package
```

---

## Data Flows

### Build Flow

```
Browser → POST /build/run → Web
Web → Create BuildResult → Queue Celery task
Celery → Fetch files from S3
       → npm install
       → waf build
       → Upload .pbw to S3
       → Update BuildResult
Browser → Poll /build/last → Get result
```

### Emulator Flow

```
Browser → POST /emulator/launch → QEMU Controller
QEMU Controller → Spawn QEMU + pypkjs → Return ports
Browser → WebSocket /ws/vnc → VNC display
Browser → WebSocket /ws/phone → App install
```

---

## 2026 Updates

Key changes from the original CloudPebble:

| Change | Details |
|--------|---------|
| **Debian EOL fixes** | All Dockerfiles use `archive.debian.org` |
| **Node.js updates** | Upgraded to Node 16.x, skip dead GPG keyservers |
| **Docker Compose v2** | Modern compose file format |
| **HTTPS support** | `EXPECT_SSL` env var, nginx for WebSocket proxying |
| **SSL verification** | Disabled for internal requests (self-signed/proxy setups) |
| **nginx reverse proxy** | Added for proper WebSocket and S3 routing |

---

## Limitations

| Limitation | Reason | Workaround |
|------------|--------|------------|
| No Pebble SSO | Pebble's auth servers are gone | Use local accounts |
| No phone installs | Requires SSO token | Use emulator only |
| No timeline sync | Pebble servers are down | N/A |
| Python 2.7 | Original codebase | Modernization needed |

---

## Modernization Proposal

### Current State Analysis

| Component | Current Version | Status | Risk Level |
|-----------|-----------------|--------|------------|
| Python | 2.7 | EOL Jan 2020 | 🔴 Critical |
| Django | 1.6 | EOL Oct 2015 | 🔴 Critical |
| Node.js | 16.x | EOL Sep 2023 | 🟡 High |
| Celery | 3.1 | EOL 2019 | 🟡 High |
| PostgreSQL | Latest | ✅ OK | 🟢 Low |
| Redis | Latest | ✅ OK | 🟢 Low |
| jQuery | 2.1 | Old but functional | 🟡 Medium |
| CodeMirror | 4.2 | Very old (current: 6.x) | 🟡 Medium |

### Recommended Approach: Phased Modernization

#### Phase 1: Infrastructure (1-2 weeks)

1. **Python 2 → Python 3.11**
   - Use `2to3` for automatic conversion
   - Update requirements.txt

2. **Django 1.6 → Django 4.2 LTS**
   - Update URL patterns, middleware, settings
   - Migrate South → Django migrations

3. **Replace fake-s3 with MinIO**
   - Actively maintained, production-ready

4. **Update Celery 3.1 → 5.3**

#### Phase 2: Production Setup (2-3 days)

Single Hetzner server setup with:
- Traefik for HTTPS/Let's Encrypt
- Docker Compose with resource limits
- **Recommended:** CX31 (4 vCPU, 8GB RAM) - €8.98/month

#### Phase 3: Frontend (Optional, 2-4 weeks)

**Option A:** Update CodeMirror only (3-5 days)  
**Option B:** Replace Backbone with Alpine.js (1-2 weeks)  
**Option C:** Full rewrite with Svelte (4-6 weeks)

### Questions for Feedback

1. **Python/Django upgrade** - In-place or fresh start?
2. **Frontend strategy** - Minimal, moderate, or full rewrite?
3. **Authentication** - Local only, or add OAuth (GitHub/Google)?
4. **Emulator** - Keep QEMU as-is, or explore WebAssembly?
5. **Hosting** - Single server, or split web/workers?

---

## Directory Structure

```
cloudpebble-composed/
├── docker-compose.yml          # Development orchestration
├── nginx/                      # Reverse proxy config
├── cloudpebble/                # Main Django app (submodule)
│   ├── ide/                    # Core IDE
│   ├── auth/                   # Authentication
│   └── ...
├── cloudpebble-qemu-controller/  # Emulator service (submodule)
└── cloudpebble-ycmd-proxy/       # Code completion (submodule)
```

---

## Credits

- Original CloudPebble by [Pebble Technology](https://github.com/pebble) / Katharine Berry
- Community revival at [Rebble](https://rebble.io)
- 2026 updates by Eric Migicovsky
- Docker compose setup by [iSevenDays](https://github.com/iSevenDays/cloudpebble-composed)

---

## License

See individual submodule licenses (MIT).
