# Hifi-OpenSubsonic

A high-performance OpenSubsonic API wrapper for Tidal, powered by upstream `hifi-api` instances. This server allows you to use any Subsonic compatible client (Feishin, Tempus, Narjo, etc.) to browse and stream music. It includes an integrated Web UI for user management.

## Features

- **Unified Search**: Search tracks, albums, and artists seamlessly.
- **Direct Streaming**: Streams original quality audio (up to Lossless) directly from HiFi API instances to your client.
- **Resilient Upstream Handling**: Features in-memory caching, circuit breakers, and automatic failover across multiple upstream instances.
- **Integrated Web UI**: Manage accounts, settings, and view server status from your browser.
- **Last.fm Integration**: Scrobble your listening history directly to your Last.fm account.
- **OpenSubsonic Compatibility**: Implements core endpoints required by modern clients.

## Quick Start (GHCR)

The easiest way to run the server is using Docker Compose and our pre-built GitHub Container Registry (GHCR) image. You don't need to clone the whole repository, just a few configuration files.

1. **Create your `docker-compose.yml`:**
   You can either download it or create a file named `docker-compose.yml` with the following content:
   ```yaml
   services:
     db:
       image: postgres:15-alpine
       restart: unless-stopped
       environment:
         POSTGRES_USER: ${POSTGRES_USER:-subsonic}
         POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-subsonic}
         POSTGRES_DB: ${POSTGRES_DB:-subsonic}
       volumes:
         - db_data:/var/lib/postgresql/data
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-subsonic}"]
         interval: 5s
         timeout: 5s
         retries: 5
       networks:
         - hifi-net

     hifi:
       container_name: hifi
       image: ghcr.io/adityabakare/hifi-opensubsonic:latest
       restart: unless-stopped
       ports:
         - "${HIFI_PORT:-8000}:8000"
       depends_on:
         db:
           condition: service_healthy
       env_file: .env
       environment:
         - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-subsonic}:${POSTGRES_PASSWORD:-subsonic}@db:5432/${POSTGRES_DB:-subsonic}
       networks:
         - hifi-net

   volumes:
     db_data:

   networks:
     hifi-net:
       driver: bridge
   ```

2. **Download setup helpers (Highly Recommended):**
   ```bash
   curl -O https://raw.githubusercontent.com/adityabakare/hifi-opensubsonic/main/Makefile
   curl -O https://raw.githubusercontent.com/adityabakare/hifi-opensubsonic/main/.env.example
   ```

2. **Generate your configuration:**
   ```bash
   make env
   ```
   *This automatically creates a `.env` file with secure, randomly generated passwords and encryption keys.*

3. **Configure HTTP/HTTPS (Important!)**
   Open the generated `.env` file in a text editor to configure your security settings:
   - **`COOKIE_SECURE`**:
     - Set to `true` (default) if you are putting the app behind a reverse proxy with SSL/HTTPS (like Nginx/Traefik).
     - Set to `false` if you are running it on a local home network over plain HTTP. **If you leave it `true` on HTTP, you will not be able to log in to the Web UI.**
   - **`ALLOW_PUBLIC_REGISTRATION`**: 
     - Set to `true` if you want to allow anyone visiting your site to create an account. Defaults to `false`.

4. **Start the server:**
   ```bash
   docker compose up -d
   ```

The Web UI and Subsonic API will now be available at `http://localhost:8000`.

## Connecting a Subsonic Client

Point your favorite Subsonic client (like Feishin, Symfonium, etc.) to your server:
- **Server Address**: `http://<your-server-ip>:8000`
- **Username / Password**: The credentials you created via the Web UI.

## Local Development Setup

If you want to contribute or run from source:

1. **Clone the repository**
   ```bash
   git clone https://github.com/adityabakare/hifi-opensubsonic.git
   cd hifi-opensubsonic
   ```

2. **Setup Environment**
   It's highly recommended to use [uv](https://github.com/astral-sh/uv).
   ```bash
   make env
   uv sync
   # Install UI dependencies
   cd web-ui && npm install && cd ..
   ```

3. **Start Development Servers**
   To work on both the API and the UI simultaneously:
   ```bash
   # Terminal 1: API backend
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   
   # Terminal 2: Web UI
   cd web-ui && npm run dev
   ```

4. **Run Tests**
   ```bash
   make test
   ```