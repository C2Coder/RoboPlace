# RoboPlace

Three-part Python implementation of a small r/place clone backend stack:

- `server`: authoritative storage for a 256x256 canvas and full placement history.
- `webapp`: read-only map viewer with zoom + scroll and player statistics.
- `connector`: ESP32 serial middleman for ESP-NOW packets; forwards valid paint/command messages to server.

## 1) Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `ROBOPLACE_SHARED_SECRET` in `.env` to a long random value.

## 2) Run services

Start each service in its own terminal from project root.

Short commands via Makefile:

```bash
make server
make connector
make webapp
make painter
make services
```

### Server (backbone)

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Server endpoints:

- `GET /health`
- `GET /api/canvas`
- `POST /api/paint`
- `POST /api/command`
- `GET /api/cooldown/{player_id}`
- `GET /api/heatmap`
- `GET /api/stats`
- `GET /api/alliances`

`POST /api/paint` is protected with the `X-RoboPlace-Secret` header when `ROBOPLACE_SHARED_SECRET` is set.

Server responsibilities now include:

- 10s per-player paint cooldown (configurable via `ROBOPLACE_COOLDOWN_SECONDS`)
- player display names
- alliance lifecycle and membership commands

### Connector (ESP serial receiver)

```bash
uvicorn connector.main:app --host 0.0.0.0 --port 8001 --reload
```

Connector environment variables:

- `ROBOPLACE_SERVER_URL` (default `http://127.0.0.1:8000`)
- `ROBOPLACE_SHARED_SECRET` (must match server)
- `ROBOPLACE_SERIAL_PORT` (default `/dev/ttyUSB0`)
- `ROBOPLACE_SERIAL_BAUD` (default `115200`)

Connector endpoints:

- `GET /health`
- `POST /api/device/paint` (manual HTTP test path using 9-bit color)
- `POST /api/device/command` (manual HTTP command path)
- `POST /api/device/serial-line` (inject one serial line manually)
- `GET /api/events/recent`

Serial input line format (one JSON object per line):

```json
{"mac":"AA:BB:CC:DD:EE:FF","message":{"player_id":"p1","x":10,"y":20,"color":"753"}}
```

9-bit color format uses `000-777` (`R G B`, each digit 0..7). Connector validates this and converts to RGB for server storage.

The connector reads serial continuously, parses each line, and forwards paint/command messages to server.

Serial command example:

```json
{"mac":"AA:BB:CC:DD:EE:FF","message":{"player_id":"p1","command":"set_name","value":"RoboPilot"}}
```

Example manual test request to connector:

```bash
curl -X POST http://127.0.0.1:8001/api/device/paint \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": "player-a",
    "x": 10,
    "y": 20,
    "color": "753"
  }'
```

### Webapp (read-only map)

```bash
uvicorn webapp.main:app --host 0.0.0.0 --port 8002 --reload
```

Webapp environment variables:

- `ROBOPLACE_SERVER_URL` (default `http://127.0.0.1:8000`)

Open:

- `http://127.0.0.1:8002/`

Features:

- Shows the 256x256 map in read-only mode.
- Scroll/pan within the map container.
- Zoom with keyboard shortcuts (+ / - / 0) and Ctrl+mouse wheel, plus fit button.
- Displays player statistics:
  - total placements
  - total players
  - active players in the last 24h
  - per-player placements, unique pixels, first placement, and latest coordinates/time
- Includes tab for alliances showing alliance members.

### Painter (manual editor, no ESP required)

```bash
make painter
```

Open:

- `http://127.0.0.1:8003/`

This sends pixel and command requests directly to the server (`/api/paint`, `/api/command`) using the shared secret from `.env`.

## Data and stats

- Server stores current canvas in `server/roboplace.db`.
- Server stores every placement event in `placements` table for later heatmap/stat generation.
- Heatmap data is available via `GET /api/heatmap`.

## Optional environment variables

- `ROBOPLACE_DB_PATH` for custom server DB path.
- `ROBOPLACE_CONNECTOR_DB_PATH` for custom connector DB path.

## Service files (systemd)

Generate service files with absolute, correct paths:

```bash
./setup_services.sh
```

Generated files are written to `services/`.

Install and start services:

```bash
./setup_services.sh --install
```
