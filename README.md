# CloudPebble Composed

This repo contains the key components of CloudPebble as Docker containers with a
`docker-compose` file that assembles them into a working CloudPebble instance.

**Updated February 2026** to work with modern Docker, fix EOL Debian repos, and support HTTPS deployments.

## Quick Start (Local Development)

1. Install Docker and docker-compose
2. Clone this repo:
   ```bash
   git clone https://github.com/ericmigi/cloudpebble.git
   cd cloudpebble
   ```
3. Set your public URL:
   ```bash
   export PUBLIC_URL=http://localhost:8080
   ```
4. Build and run:
   ```bash
   docker compose build
   docker compose up
   ```
5. Open http://localhost:8080 and register an account

## HTTPS Deployment (e.g. exe.dev, cloud VPS)

For HTTPS deployments behind a reverse proxy:

```bash
export PUBLIC_URL=https://your-domain.com
export EXPECT_SSL=yes
docker compose build
docker compose up -d
```

The nginx container listens on port 8080. Configure your reverse proxy to forward HTTPS traffic to it.

## Architecture

The stack includes:

| Container | Purpose |
|-----------|---------|
| nginx | Reverse proxy, websocket routing, S3 builds proxy |
| web | Django CloudPebble web app |
| celery | Background task worker (builds) |
| qemu | Pebble emulator controller |
| ycmd | Code completion server |
| redis | Celery broker |
| postgres | Database |
| s3 | Fake S3 for build artifacts |

## Key Changes from Original

1. **Debian EOL fixes**: All Dockerfiles patched to use archive.debian.org
2. **Node.js updates**: Upgraded to Node 16.x (cloudpebble), skipped dead GPG keyservers
3. **Docker Compose v2**: Updated to modern compose file format
4. **HTTPS support**: Added EXPECT_SSL env var, nginx for websocket proxying
5. **SSL verification disabled**: Internal requests skip SSL verification (required for self-signed/proxy setups)

## Limitations

- Pebble SSO is not available; only local accounts work
- Websocket installs require the emulator (phone pairing not available)
- Timeline sync to Pebble servers will fail (servers are down)

## Troubleshooting

**Emulator won't start**: Check that QEMU_URLS points to your PUBLIC_URL

**App install fails**: Verify /s3builds/ proxy is working:
```bash
curl -I ${PUBLIC_URL}/s3builds/test
```

**SSL errors**: Make sure EXPECT_SSL=yes for HTTPS deployments

## Credits

Based on the original [cloudpebble-composed](https://github.com/nicmcd/CloudPebble-Composed) work.

Special thanks to the Rebble community for keeping Pebble alive! 🎉
