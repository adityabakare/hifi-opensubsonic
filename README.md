# Hifi-OpenSubsonic

A high-performance OpenSubsonic API wrapper for Tidal, powered by upstream `hifi-api` instances. This server allows you to use any Subsonic compatible client (Feishin, Tempus, Symfonium, etc.) to browse and stream music from Tidal.

## Features

- **Unified Search**: Search tracks, albums, and artists seamlessly.
- **Direct Streaming**: Streams original quality audio (up to Lossless/Hi-Res) directly from Tidal servers to your client (no transcoding bottleneck).
- **Multi-Instance Support**: Configure multiple upstream API instances for high availability and failover.
- **Cover Art Proxy**: Resolves high-resolution cover art directly from Tidal.
- **Subsonic Compatibility**: Implements core endpoints required by modern clients.

## Installation

### Prerequisites
- Python 3.9+
- `uv` (recommended) or `pip`

### Setup

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd hifi-opensubsonic2
   ```

2. **Install Dependencies**
   ```bash
   uv sync
   # OR
   pip install -r requirements.txt
   ```

3. **Configure Instances**
   Create a `instances.json` file in the root directory (see `instances.json.example`).
   ```json
   [
     "https://your-hifi-api-instance.com",
     "https://backup-instance.com"
   ]
   ```

4. **Run the Server**
   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## Usage

Connect your Subsonic client using the following details:
- **Server Address**: `http://<your-ip>:8000`
- **Username**: `any`
- **Password**: `any` (Auth is currently open/mocked)

## Development

Run tests:
```bash
uv run tests/verify_api.py
```