# CloudPebble Composed

CloudPebble is a web-based IDE for developing Pebble smartwatch applications. This repository assembles all CloudPebble components via Docker Compose into a fully functional local development environment.

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
- [Getting Started](#getting-started)
- [Configuration Reference](#configuration-reference)
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

**Image:** Custom (Python 2.7.11 + Node.js 10.15.3)  
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
| `AWS_S3_FAKE_S3` | `192.168.76.5:8003` | fake-s3 endpoint |
| `MEDIA_URL` | `http://192.168.76.5:8003/builds.cloudpebble.net/` | Build artifact URL |
| `QEMU_URLS` | `http://192.168.76.5:8001/` | QEMU controller endpoint |
| `YCM_URLS` | `http://192.168.76.5:8002/` | YCMD proxy endpoint |
| `PUBLIC_URL` | `http://192.168.76.5/` | Public-facing URL |
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

**ide/tasks/gist.py**
- `import_gist(user_id, gist_id)` - Import from GitHub Gist

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

#### Build Process (Dockerfile)

```dockerfile
# 1. Build QEMU (Pebble fork)
RUN curl -L https://github.com/iSevenDays/pebble_qemu/archive/v2.5.2-pebble4.tar.gz | tar xz
RUN ./configure --target-list="arm-softmmu" && make -j4

# 2. Install pypkjs (PebbleKit JS runtime)
RUN git clone https://github.com/pebble/pypkjs.git --branch master
RUN virtualenv /pypkjs/.env && pip install -r /pypkjs/requirements.txt

# 3. Download firmware images
RUN curl -L https://github.com/pebble/qemu-tintin-images/archive/v4.3.tar.gz | tar xz
```

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

    def _spawn_qemu(self):
        # Platform-specific args
        if platform == 'aplite':
            args = ["-machine", "pebble-bb2", "-cpu", "cortex-m3"]
        elif platform == 'basalt':
            args = ["-machine", "pebble-snowy-bb", "-cpu", "cortex-m4"]
        # ... chalk, diorite, emery
        
        subprocess.Popen([QEMU_BIN,
            "-rtc", "base=localtime",
            "-pflash", "qemu_micro_flash.bin",
            "-serial", "tcp:127.0.0.1:{bt_port},server,nowait",
            "-serial", "tcp:127.0.0.1:{console_port},server",
            "-vnc", ":{display},password,websocket={vnc_ws_port}"
        ] + args)
```

#### Idle Killer

Emulators are automatically killed after 5 minutes without a ping:

```python
def _kill_idle_emulators():
    while True:
        for key, emulator in emulators.items():
            if now() - emulator.last_ping > 300:
                emulator.kill()
                del emulators[key]
        gevent.sleep(60)
```

---

### 4. YCMD Proxy

**Image:** Custom (Python 2.7 + ycmd + Clang)  
**Port:** 8002  
**Build Context:** `cloudpebble-ycmd-proxy/`

Code intelligence service providing autocomplete, errors, and go-to-definition.

#### Build Process (Dockerfile)

```dockerfile
# 1. Build ycmd with Clang completer
RUN git clone https://github.com/Valloric/ycmd.git /ycmd
RUN cd /ycmd && git reset --hard 10c456c6e32487c2b75b9ee754a1f6cc6bf38a4f
RUN python build.py --clang-completer

# 2. Install ARM toolchain
RUN curl -o /tmp/arm-cs-tools.tar https://cloudpebble-vagrant.s3.amazonaws.com/arm-cs-tools-stripped.tar
RUN tar -xf /tmp/arm-cs-tools.tar -C /

# 3. Install Pebble SDK
RUN curl -L https://github.com/aveao/PebbleArchive/raw/master/SDKCores/sdk-core-4.3.tar.bz2 | tar xj -C /sdk3
```

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

#### .ycm_extra_conf.py Template

```python
def FlagsForFile(filename, **kwargs):
    return {
        'flags': [
            '-x', 'c',
            '-std=c11',
            '-I', '{sdk}/include',
            '-I', '{here}/include',
            '-I', '{here}/build/aplite/applib',
            '-I', '{stdlib}',
            '-target', 'arm-none-eabi',
            '-mcpu=cortex-m3',
            '-mthumb',
            '-DPBL_PLATFORM_APLITE',
            '-DPBL_SDK_3',
        ]
    }
```

#### Generated Headers

**__pebble_resource_ids__.h:**
```c
#pragma once
#define RESOURCE_ID_FONT_GOTHIC_28 1
#define RESOURCE_ID_IMAGE_LOGO 2
// ...
```

**__pebble_messagekeys__.h:**
```c
#pragma once
#define MESSAGE_KEY_temperature 0
#define MESSAGE_KEY_conditions 1
// ...
```

---

### 5. Redis

**Image:** `redis:latest`  
**Port:** 6379

Message broker for Celery and optional session/cache storage.

**Usage:**
- Database 1: Celery task queue and results
- Database 0: (available for caching)

---

### 6. PostgreSQL

**Image:** `postgres:latest`  
**Port:** 5432

Primary relational database storing all application data.

**Default Connection:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'postgres',
        'USER': 'postgres',
        'HOST': 'postgres',
        'PORT': 5432,
    }
}
```

---

### 7. S3 Storage

**Image:** `kuracloud/fake-s3`  
**Port:** 8003 (mapped to internal 4569)

S3-compatible object storage using fake-s3.

**Buckets:**

| Bucket | Purpose | Example Content |
|--------|---------|-----------------|
| `source.cloudpebble.net` | Source code | `user_123/project_456/src/main.c` |
| `builds.cloudpebble.net` | Build artifacts | `build_789/watchapp.pbw` |
| `export.cloudpebble.net` | Project exports | `export_abc123.zip` |

---

## Data Models

### Project

```python
class Project(models.Model):
    owner = models.ForeignKey(User)
    name = models.CharField(max_length=50)
    last_modified = models.DateTimeField(auto_now_add=True)
    
    # Project type
    project_type = models.CharField(choices=[
        ('native', 'Pebble C SDK'),
        ('simplyjs', 'Simply.js'),
        ('pebblejs', 'Pebble.js'),
        ('package', 'Pebble Package'),
        ('rocky', 'Rocky.js'),
    ])
    sdk_version = models.CharField(choices=[('2', 'SDK 2'), ('3', 'SDK 4')])
    
    # App metadata
    app_uuid = models.CharField(max_length=36)
    app_company_name = models.CharField(max_length=100)
    app_short_name = models.CharField(max_length=100)
    app_long_name = models.CharField(max_length=100)
    app_version_label = models.CharField(max_length=40)
    app_is_watchface = models.BooleanField()
    app_capabilities = models.CharField(max_length=255)  # comma-separated
    app_platforms = models.TextField()  # comma-separated
    app_keys = models.TextField()  # JSON: {} or []
    
    # Compilation
    optimisation = models.CharField(choices=[
        ('0', 'None'), ('1', 'Limited'), ('s', 'Size'),
        ('2', 'Speed'), ('3', 'Aggressive')
    ])
    
    # GitHub integration
    github_repo = models.CharField(max_length=100, null=True)
    github_branch = models.CharField(max_length=100, null=True)
    github_last_sync = models.DateTimeField(null=True)
    github_last_commit = models.CharField(max_length=40, null=True)
    github_hook_uuid = models.CharField(max_length=36, null=True)
    github_hook_build = models.BooleanField()
```

### SourceFile

```python
class SourceFile(models.Model):
    project = models.ForeignKey(Project, related_name='source_files')
    file_name = models.CharField(max_length=100)
    last_modified = models.DateTimeField(auto_now=True)
    folded_lines = models.TextField(null=True)  # JSON array
    
    # Target (pkjs, app, worker, common)
    target = models.CharField(max_length=10, default='app')
    
    # Content stored in S3
    s3_key = models.CharField(max_length=255)
```

### ResourceFile

```python
class ResourceFile(models.Model):
    project = models.ForeignKey(Project, related_name='resources')
    file_name = models.CharField(max_length=100)
    kind = models.CharField(choices=[
        ('png', 'PNG'), ('png-trans', 'PNG (transparent)'),
        ('font', 'Font'), ('raw', 'Raw binary'), ('pbi', 'PBI')
    ])
    is_menu_icon = models.BooleanField()

class ResourceIdentifier(models.Model):
    resource_file = models.ForeignKey(ResourceFile, related_name='identifiers')
    resource_id = models.CharField(max_length=100)  # e.g., "IMAGE_LOGO"
    # Options: character_regex, tracking, compatibility, memory_format, etc.

class ResourceVariant(models.Model):
    resource_file = models.ForeignKey(ResourceFile, related_name='variants')
    tags = models.CharField(max_length=255)  # e.g., "aplite,basalt~bw"
```

### BuildResult

```python
class BuildResult(models.Model):
    project = models.ForeignKey(Project, related_name='builds')
    uuid = models.CharField(max_length=36)
    
    STATE_CHOICES = [
        (0, 'Waiting'), (1, 'Running'),
        (2, 'Succeeded'), (3, 'Failed')
    ]
    state = models.IntegerField(choices=STATE_CHOICES)
    
    started = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True)
    total_size = models.IntegerField(null=True)
    
    # S3 keys for artifacts
    pbw_key = models.CharField(max_length=255, null=True)
    build_log_key = models.CharField(max_length=255, null=True)

class BuildSize(models.Model):
    build = models.ForeignKey(BuildResult, related_name='sizes')
    platform = models.CharField(max_length=20)
    binary_size = models.IntegerField()
    resource_size = models.IntegerField()
    worker_size = models.IntegerField(null=True)
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
| `POST /ide/project/<id>/save_dependencies` | POST | Update npm dependencies |
| `POST /ide/project/<id>/delete` | POST | Delete project |
| `POST /ide/project/<id>/export` | POST | Start export task |

### Source Files

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /ide/project/<id>/create_source_file` | POST | Create file |
| `GET /ide/project/<id>/source/<file_id>/load` | GET | Load file content |
| `POST /ide/project/<id>/source/<file_id>/save` | POST | Save file content |
| `POST /ide/project/<id>/source/<file_id>/rename` | POST | Rename file |
| `POST /ide/project/<id>/source/<file_id>/delete` | POST | Delete file |

### Resources

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /ide/project/<id>/create_resource` | POST | Upload resource |
| `GET /ide/project/<id>/resource/<res_id>/info` | GET | Get resource info |
| `POST /ide/project/<id>/resource/<res_id>/update` | POST | Update resource |
| `POST /ide/project/<id>/resource/<res_id>/delete` | POST | Delete resource |

### Builds

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /ide/project/<id>/build/run` | POST | Start build |
| `GET /ide/project/<id>/build/last` | GET | Get last build |
| `GET /ide/project/<id>/build/history` | GET | Get build history |
| `GET /ide/project/<id>/build/<build_id>/log` | GET | Get build log |

### GitHub

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /ide/project/<id>/github/repo` | POST | Set GitHub repo |
| `POST /ide/project/<id>/github/repo/create` | POST | Create new repo |
| `POST /ide/project/<id>/github/commit` | POST | Push to GitHub |
| `POST /ide/project/<id>/github/pull` | POST | Pull from GitHub |

### Emulator

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /ide/emulator/launch` | POST | Launch emulator |
| `GET /ide/emulator/config` | GET | Emulator config page |

---

## Frontend Architecture

### JavaScript Files (57 total)

**Core:**
- `ide.js` - Main application entry point
- `sidebar.js` - Project navigation
- `editor.js` - CodeMirror wrapper

**Features:**
- `emulator.js` - QEMU integration, noVNC display
- `autocomplete.js` - YCMD WebSocket client
- `compilation.js` - Build management
- `github.js` - GitHub sync UI
- `resources.js` - Resource management
- `settings.js` - Project settings

**Libraries:**
- `libpebble/` - Pebble protocol implementation
- `noVNC/` - VNC client for emulator display

### Bower Dependencies

```javascript
// .bowerrc + manage.py bower install
BOWER_INSTALLED_APPS = [
    'jquery#~2.1.3',
    'underscore',
    'backbone',
    'codemirror#4.2.0',
    'bluebird#3.3.4',        // Promises
    'text-encoding',          // TextEncoder/Decoder polyfill
    'jshint/jshint',         // JavaScript linting
    'html.sortable#~0.3.1',  // Drag-drop sorting
    'jquery-textext',         // Tag input widget
    'kanaka/noVNC#v0.5',     // VNC client
    'Fuse',                   // Fuzzy search
]
```

---

## Build System

### SDK Structure

```
/sdk3/
├── pebble/
│   ├── waf              # Build tool (Python)
│   └── common/          # Build helpers
├── include/
│   ├── pebble.h         # Main API header
│   └── pebble_fonts.h   # Font definitions
├── lib/
│   ├── aplite/          # Platform libraries
│   ├── basalt/
│   ├── chalk/
│   └── diorite/
└── node_modules/        # JS build dependencies
```

### Build Command

```bash
# SDK 3/4
export PATH="/arm-cs-tools/bin:$PATH"
export NODE_PATH="/sdk3/node_modules"
/sdk3/pebble/waf configure build
```

### Output Structure

```
build/
├── aplite/
│   ├── pebble-app.bin      # App binary
│   ├── pebble-app.elf      # Debug symbols
│   ├── pebble-worker.bin   # Background worker (optional)
│   └── app_resources.pbpack # Resources
├── basalt/
│   └── ...
└── <project>.pbw           # Final package (ZIP)
```

---

## Data Flows

### Complete Build Flow

```
┌────────────┐      ┌────────────┐      ┌────────────┐      ┌────────────┐
│  Browser   │      │    Web     │      │   Celery   │      │     S3     │
└─────┬──────┘      └─────┬──────┘      └─────┬──────┘      └─────┬──────┘
      │                   │                   │                   │
      │ POST /build/run   │                   │                   │
      │──────────────────>│                   │                   │
      │                   │                   │                   │
      │                   │ Create BuildResult│                   │
      │                   │ (state=WAITING)   │                   │
      │                   │                   │                   │
      │                   │ Queue task        │                   │
      │                   │──────────────────>│                   │
      │                   │                   │                   │
      │ {build_id, task_id}                   │                   │
      │<──────────────────│                   │                   │
      │                   │                   │                   │
      │                   │                   │ Fetch project     │
      │                   │                   │──────────────────>│
      │                   │                   │<──────────────────│
      │                   │                   │                   │
      │                   │                   │ Create temp dir   │
      │                   │                   │ Write source files│
      │                   │                   │ npm install       │
      │                   │                   │ waf configure build
      │                   │                   │                   │
      │                   │                   │ Upload .pbw       │
      │                   │                   │──────────────────>│
      │                   │                   │                   │
      │                   │                   │ Update BuildResult│
      │                   │                   │ (state=SUCCEEDED) │
      │                   │                   │                   │
      │ Poll GET /build/last                  │                   │
      │──────────────────>│                   │                   │
      │                   │                   │                   │
      │ {state, download_url, sizes}          │                   │
      │<──────────────────│                   │                   │
```

### Emulator Session

```
┌────────────┐      ┌────────────┐      ┌────────────┐
│  Browser   │      │    Web     │      │    QEMU    │
└─────┬──────┘      └─────┬──────┘      └─────┬──────┘
      │                   │                   │
      │ POST /emulator/launch                 │
      │──────────────────────────────────────>│
      │                   │                   │
      │                   │    Spawn QEMU     │
      │                   │    Spawn pypkjs   │
      │                   │                   │
      │ {uuid, vnc_ws_port, ws_port}          │
      │<──────────────────────────────────────│
      │                   │                   │
      │ WebSocket /ws/vnc │                   │
      │═══════════════════════════════════════│
      │      VNC frames   │                   │
      │<══════════════════════════════════════│
      │                   │                   │
      │ WebSocket /ws/phone                   │
      │═══════════════════════════════════════│
      │   Install .pbw    │                   │
      │══════════════════════════════════════>│
      │                   │                   │
      │  Periodic ping    │                   │
      │──────────────────────────────────────>│
      │                   │                   │
```

### Code Completion

```
┌────────────┐      ┌────────────┐      ┌────────────┐
│  Browser   │      │    Web     │      │    YCMD    │
└─────┬──────┘      └─────┬──────┘      └─────┬──────┘
      │                   │                   │
      │ POST /autocomplete/init               │
      │──────────────────────────────────────>│
      │                   │                   │
      │                   │ Create temp dir   │
      │                   │ Write files       │
      │                   │ Spawn ycmd x4     │
      │                   │                   │
      │ {uuid, ws_port}   │                   │
      │<──────────────────────────────────────│
      │                   │                   │
      │ WebSocket /ycm/<uuid>/ws              │
      │═══════════════════════════════════════│
      │                   │                   │
      │ {cmd: "completions", data: {          │
      │   file: "src/main.c",                 │
      │   line: 42, column: 15,               │
      │   contents: "..."                     │
      │ }}                                    │
      │══════════════════════════════════════>│
      │                   │                   │
      │ {data: [{                             │
      │   kind: "FUNCTION",                   │
      │   insertion_text: "window_create",    │
      │   extra_menu_info: "Window *"         │
      │ }]}                                   │
      │<══════════════════════════════════════│
```

---

## Getting Started

### Prerequisites

- Docker Engine 19.03+
- Docker Compose 1.25+
- Git with submodule support
- 4GB+ RAM (QEMU + ycmd are memory-hungry)

### Installation

```bash
# 1. Clone with submodules
git clone --recursive https://github.com/pebble/cloudpebble-composed.git
cd cloudpebble-composed

# 2. Get your machine's LAN IP
# macOS:
ipconfig getifaddr en0
# Linux:
hostname -I | awk '{print $1}'

# 3. Update docker-compose.yml
# Replace all instances of 192.168.76.5 with your IP
sed -i '' 's/192.168.76.5/YOUR_IP/g' docker-compose.yml

# 4. Build and initialize
./dev_setup.sh

# 5. Start all services
docker-compose up

# 6. Create an account
open http://YOUR_IP/accounts/register/
```

### Development Workflow

```bash
# View logs
docker-compose logs -f web
docker-compose logs -f celery
docker-compose logs -f qemu

# Restart single service
docker-compose restart web

# Rebuild after code changes
docker-compose build web
docker-compose up -d web

# Access Django shell
docker-compose exec web python manage.py shell

# Run database migrations
docker-compose exec web python manage.py migrate
```

---

## Configuration Reference

### docker-compose.yml

```yaml
web:
  build: cloudpebble/
  ports:
    - "80:80"
  volumes:
    - "./cloudpebble/:/code"  # Live reload in dev
  links:
    - redis
    - postgres
    - s3
    - qemu
    - ycmd
  environment:
    - DEBUG=yes
    - RUN_WEB=yes
    - AWS_ENABLED=yes
    - PORT=80
    - AWS_S3_FAKE_S3=192.168.76.5:8003
    - MEDIA_URL=http://192.168.76.5:8003/builds.cloudpebble.net/
    - QEMU_URLS=http://192.168.76.5:8001/
    - YCM_URLS=http://192.168.76.5:8002/
    - PUBLIC_URL=http://192.168.76.5/
```

---

## Limitations

| Limitation | Reason | Workaround |
|------------|--------|------------|
| No Pebble SSO | Pebble's auth servers are gone | Use local accounts |
| No phone installs | Requires SSO token for WebSocket proxy | Use emulator only |
| Fixed IP address | Containers reference external IP | Edit docker-compose.yml |
| Python 2.7 | Original codebase requirement | None (modernization needed) |
| SDK 2 disabled | Broken in current setup | Use SDK 4 only |
| No HTTPS | Local dev setup | Add nginx reverse proxy |

---

## Modernization Proposal

### Current State Analysis

| Component | Current Version | Status | Risk Level |
|-----------|-----------------|--------|------------|
| Python | 2.7 | EOL Jan 2020 | 🔴 Critical |
| Django | 1.6 | EOL Oct 2015 | 🔴 Critical |
| Node.js | 10.15 (container) / 6.11 (package.json) | EOL Apr 2021 | 🔴 Critical |
| Celery | 3.1 | EOL 2019 | 🟡 High |
| PostgreSQL | Latest (image) | ✅ OK | 🟢 Low |
| Redis | Latest (image) | ✅ OK | 🟢 Low |
| jQuery | 2.1 | Old but functional | 🟡 Medium |
| Backbone | ~1.x | Outdated pattern | 🟡 Medium |
| CodeMirror | 4.2 | Very old (current: 6.x) | 🟡 Medium |
| ycmd | 2018 snapshot | Outdated | 🟡 Medium |
| QEMU | Pebble fork | Works, no updates needed | 🟢 Low |
| fake-s3 | Unmaintained | Works | 🟡 Medium |

### Recommended Approach: Incremental Modernization

Given the goal of simple Hetzner hosting, I recommend a phased approach:

---

### Phase 1: Infrastructure Modernization (1-2 weeks)

**Goal:** Get to supportable, modern infrastructure without rewriting application code.

#### 1.1 Python 2 → Python 3.11

```dockerfile
# New base image
FROM python:3.11-slim-bookworm

# Key changes needed:
# - print statements → print()
# - dict.iteritems() → dict.items()
# - unicode handling (mostly automatic)
# - Update all pip packages
```

**Estimated effort:** 2-3 days
- Use `2to3` tool for automatic conversion
- Run test suite (if exists) or manual testing
- Update requirements.txt with compatible versions

#### 1.2 Django 1.6 → Django 4.2 LTS

```python
# Major changes:
# - URL patterns: url() → path() / re_path()
# - MIDDLEWARE_CLASSES → MIDDLEWARE
# - render_to_response → render
# - South migrations → Django native migrations
# - Template context processors syntax
```

**Estimated effort:** 3-5 days
- Update settings.py structure
- Migrate South migrations to Django migrations
- Fix deprecated template tags
- Update authentication backends

#### 1.3 Replace fake-s3 with MinIO

```yaml
# docker-compose.yml
s3:
  image: minio/minio:latest
  command: server /data --console-address ":9001"
  ports:
    - "8003:9000"
    - "9001:9001"
  environment:
    - MINIO_ROOT_USER=cloudpebble
    - MINIO_ROOT_PASSWORD=cloudpebble123
  volumes:
    - minio_data:/data
```

**Benefits:**
- Actively maintained
- S3-compatible API
- Web console for debugging
- Production-ready

#### 1.4 Update Celery 3.1 → Celery 5.3

```python
# Key changes:
# - celery.task → celery.shared_task
# - CELERY_* settings → lowercase
# - Task base class changes
```

**Estimated effort:** 1 day

---

### Phase 2: Single-Server Docker Setup (2-3 days)

**Goal:** Optimized docker-compose for Hetzner deployment.

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.le.acme.httpchallenge.entrypoint=web"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_certs:/letsencrypt

  web:
    build:
      context: ./cloudpebble
      dockerfile: Dockerfile.prod
    environment:
      - DEBUG=no
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=postgres://cloudpebble:${DB_PASSWORD}@postgres/cloudpebble
      - REDIS_URL=redis://redis:6379
    labels:
      - "traefik.http.routers.web.rule=Host(`cloudpebble.example.com`)"
      - "traefik.http.routers.web.tls.certresolver=le"
    depends_on:
      - postgres
      - redis
      - minio

  celery:
    build:
      context: ./cloudpebble
      dockerfile: Dockerfile.prod
    command: celery -A cloudpebble worker -l info
    environment:
      - DATABASE_URL=postgres://cloudpebble:${DB_PASSWORD}@postgres/cloudpebble
      - REDIS_URL=redis://redis:6379

  qemu:
    build: ./cloudpebble-qemu-controller
    deploy:
      resources:
        limits:
          memory: 2G
    labels:
      - "traefik.http.routers.qemu.rule=Host(`cloudpebble.example.com`) && PathPrefix(`/qemu`)"

  ycmd:
    build: ./cloudpebble-ycmd-proxy
    deploy:
      resources:
        limits:
          memory: 1G

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=cloudpebble
      - POSTGRES_USER=cloudpebble
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=${MINIO_USER}
      - MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  redis_data:
  minio_data:
  traefik_certs:
```

**Hetzner Recommendation:**
- **CX31** (4 vCPU, 8GB RAM, 80GB SSD) - €8.98/month
- Sufficient for 5-10 concurrent users
- Scale to CX41 if needed

---

### Phase 3: Frontend Modernization (Optional, 2-4 weeks)

Three options based on effort/reward:

#### Option A: Minimal - Update CodeMirror Only

**Effort:** 3-5 days  
**Impact:** Better editor experience

```javascript
// Replace CodeMirror 4 with CodeMirror 6
import {EditorView, basicSetup} from "codemirror"
import {cpp} from "@codemirror/lang-cpp"
import {javascript} from "@codemirror/lang-javascript"

// Benefits:
// - Modern architecture
// - Better mobile support
// - LSP integration possible
```

#### Option B: Moderate - Replace Backbone with Alpine.js

**Effort:** 1-2 weeks  
**Impact:** Simpler, more maintainable frontend

```html
<!-- Before (Backbone) -->
<script>
var ProjectView = Backbone.View.extend({...});
</script>

<!-- After (Alpine.js) -->
<div x-data="projectManager()">
  <template x-for="file in files">
    <div @click="openFile(file)" x-text="file.name"></div>
  </template>
</div>
```

**Why Alpine.js:**
- Minimal learning curve
- Works with existing server-rendered HTML
- No build step required
- 15KB vs 80KB+ for React/Vue

#### Option C: Full Rewrite - Svelte/SvelteKit

**Effort:** 4-6 weeks  
**Impact:** Modern SPA, best UX

```svelte
<!-- src/routes/project/[id]/+page.svelte -->
<script>
  import { page } from '$app/stores';
  import CodeMirror from '$lib/CodeMirror.svelte';
  import Emulator from '$lib/Emulator.svelte';
  
  export let data; // from +page.server.js
</script>

<div class="ide-layout">
  <Sidebar files={data.files} />
  <CodeMirror bind:value={currentFile.content} />
  <Emulator platform={data.platform} />
</div>
```

**Why Svelte:**
- Smallest bundle size
- No virtual DOM overhead
- Great DX with SvelteKit
- Easy WebSocket integration

---

### Phase 4: YCMD Replacement (Optional, 1 week)

Replace ycmd with clangd (modern C/C++ language server):

```yaml
# New service
lsp:
  image: silkeh/clang:15
  command: clangd --background-index
  volumes:
    - sdk:/sdk:ro
```

**Benefits:**
- Actively maintained
- Better completion
- Faster
- Standard LSP protocol

**Frontend integration:**
```javascript
// Use monaco-editor with LSP
import * as monaco from 'monaco-editor';
import { MonacoLanguageClient } from 'monaco-languageclient';

const client = new MonacoLanguageClient({
  serverUri: 'ws://localhost:8002/lsp'
});
```

---

### Recommended Implementation Order

For a single Hetzner server with minimal maintenance:

| Phase | Priority | Effort | Impact |
|-------|----------|--------|--------|
| 1.1 Python 3 | 🔴 Must | 2-3 days | Security |
| 1.2 Django 4 | 🔴 Must | 3-5 days | Security |
| 1.3 MinIO | 🟡 Should | 1 day | Reliability |
| 1.4 Celery 5 | 🟡 Should | 1 day | Maintenance |
| 2 Docker Prod | 🔴 Must | 2-3 days | Deployment |
| 3A CodeMirror | 🟢 Nice | 3-5 days | UX |
| 3B Alpine.js | 🟢 Nice | 1-2 weeks | Maintenance |
| 4 clangd | 🟢 Nice | 1 week | Performance |

---

### Questions for Feedback

1. **Python/Django upgrade** - Should we attempt an in-place upgrade or start fresh with the same data models?

2. **Frontend strategy** - 
   - (A) Minimal: Just update CodeMirror, keep jQuery/Backbone
   - (B) Moderate: Replace Backbone with Alpine.js
   - (C) Full rewrite: Svelte or React

3. **Authentication** - 
   - Keep local accounts only?
   - Add OAuth (GitHub, Google)?
   - Add Rebble SSO (if they have an endpoint)?

4. **Emulator strategy** -
   - Keep QEMU/pypkjs as-is (it works)?
   - Explore WebAssembly Pebble emulator (future)?

5. **Hosting architecture** -
   - Single Hetzner server (simple, cheap)?
   - Split (web on Hetzner, builds on separate worker)?
   - Add CDN for static assets?

6. **Database** -
   - Migrate existing data?
   - Start fresh?

---

## Directory Structure

```
cloudpebble-composed/
├── docker-compose.yml          # Development orchestration
├── docker-compose.prod.yml     # Production setup (to create)
├── dev_setup.sh               # Initial build script
├── README.md                  # This file
│
├── cloudpebble/               # Main Django app (git submodule)
│   ├── Dockerfile
│   ├── docker_start.sh
│   ├── requirements.txt
│   ├── manage.py
│   ├── cloudpebble/           # Django project
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── ide/                   # Core IDE app
│   │   ├── api/              # REST endpoints
│   │   ├── models/           # Database models
│   │   ├── tasks/            # Celery tasks
│   │   ├── views/            # HTML views
│   │   ├── static/ide/       # JS/CSS (57 JS, 8 CSS)
│   │   ├── templates/        # Django templates
│   │   ├── utils/            # Helpers
│   │   └── migrations/       # 51 South migrations
│   ├── auth/                  # Authentication
│   ├── root/                  # Landing page
│   └── qr/                    # QR codes
│
├── cloudpebble-qemu-controller/  # Emulator service (git submodule)
│   ├── Dockerfile
│   ├── controller.py          # Flask API
│   ├── emulator.py           # QEMU/pypkjs management
│   ├── settings.py
│   └── qemu-tintin-images/   # Firmware
│
└── cloudpebble-ycmd-proxy/      # Code completion (git submodule)
    ├── Dockerfile
    ├── proxy.py               # Flask API
    ├── ycm.py                # ycmd interface
    ├── ycm_helpers.py        # Session management
    ├── filesync.py           # File synchronization
    ├── projectinfo.py        # Header generation
    └── ycm_conf/             # Compiler flag templates
```

---

## Credits

- Original CloudPebble by [Pebble Technology](https://github.com/pebble) / Katharine Berry
- Community revival at [Rebble](https://rebble.io)
- Docker compose setup by [iSevenDays](https://github.com/iSevenDays/cloudpebble-composed)
- Inspired by [Reddit guide](https://www.reddit.com/r/pebble/comments/bza6yq/)

---

## License

See individual submodule licenses:
- cloudpebble: MIT
- cloudpebble-qemu-controller: MIT
- cloudpebble-ycmd-proxy: MIT
