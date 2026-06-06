# RoboPlace

A multi-part Python r/place-style canvas system with an ESP32 serial connector, web viewer, manual painter, log viewer, and alliance/name commands.

Parts:
- `server`: authoritative canvas storage, cooldown, player names, alliances, event logging
- `connector`: ESP-NOW serial middleman + MAC-to-player mapping manager
- `webapp`: public read-only viewer with zoom, fit, heatmap toggle, stats, alliances tab
- `painter`: manual paint + command sender
- `logviewer`: filtered server event log reader

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
make logviewer
make services
```

### Server (backbone)

```bash
make server
```

Serves on `http://0.0.0.0:8000`.

Key endpoints:
- `GET /health`
- `GET /api/canvas`
- `POST /api/paint` (primary; legacy `POST /api/place`)
- `POST /api/command`
- `GET /api/cooldown/{player_id}`
- `GET /api/heatmap`
- `GET /api/stats`
- `GET /api/alliances`
- `GET /api/logs`

Server-managed behavior:
- per-player paint cooldown (`ROBOPLACE_COOLDOWN_SECONDS`)
- player display names (`set_name`)
- alliance lifecycle: create/join/leave/kick/delete
- event logging for paints, commands, and cooldown rejects

### Connector (ESP serial receiver + MAC manager)

```bash
make connector
```

Serves on `http://0.0.0.0:8001`.
MAC manager UI: `http://<host>:8001/mac`

Env:
- `ROBOPLACE_SERVER_URL` (default `http://127.0.0.1:8000`)
- `ROBOPLACE_SHARED_SECRET` (must match server)
- `ROBOPLACE_SERIAL_PORT` (default `/dev/ttyUSB0`)
- `ROBOPLACE_SERIAL_BAUD` (default `115200`)
- `ROBOPLACE_DEFAULT_PLAYER_ID` (default `anonymous`)

Endpoints:
- `GET /health`
- `POST /api/device/paint`
- `POST /api/device/command`
- `POST /api/device/serial-line`
- `GET /api/events/recent`
- `GET /api/mac-mappings`
- `POST /api/mac-mappings`
- `DELETE /api/mac-mappings/{mac}`
- `POST /api/mac-mappings/import`
- `DELETE /api/mac-mappings`
- `GET /api/mac-mappings/export`

Serial input line format:

```json
{"mac":"AA:BB:CC:DD:EE:FF","message":{"player_id":"p1","x":10,"y":20,"color":"753"}}
```

9-bit color is `000-777`. The connector converts it to RGB before forwarding to the server.

MAC mapping behavior:
- Unknown MACs resolve to `ROBOPLACE_DEFAULT_PLAYER_ID`
- Use `/mac` to add/override/delete mappings at runtime
- CSV import supports `add` (merge) and `override` (replace all)

### Webapp (read-only map)

```bash
make webapp
```

Open:
- `http://127.0.0.1:8002/`

Features:
- 256x256 canvas viewer
- pan by scrolling the map area
- zoom with `+` / `-` / `0` keys, `Ctrl+wheel`, or the `fit` button
- mode toggle: `color` or `heatmap`
- stats: placements, players, 24h active
- players tab: sorted list with name/alliance/last location
- alliances tab: alliance cards with members
- footer: `made by C2Coder • 2026`

### Painter (manual editor, no ESP required)

```bash
make painter
```

Open:
- `http://127.0.0.1:8003/`

- Sends pixel commands to server `POST /api/paint`
- Sends commands to server `POST /api/command` (`set_name`, alliance actions)

### LogViewer

```bash
make logviewer
```

Open:
- `http://127.0.0.1:8004/`

- Reads server event logs via `GET /api/logs`
- filter by event type, player_id, time range, limit

## 3) Data

- Server DB: `server/roboplace.db`
- Connector DB: `connector/connector.db`
- Full placement history is stored in `placements`
- Heatmap is available via `GET /api/heatmap`
- Server `event_log` records paints, commands, and cooldown rejections

## 4) Environment variables

- `ROBOPLACE_SHARED_SECRET`
- `ROBOPLACE_COOLDOWN_SECONDS`
- `ROBOPLACE_DB_PATH`
- `ROBOPLACE_CONNECTOR_DB_PATH`
- `ROBOPLACE_SERVER_URL`
- `ROBOPLACE_SERIAL_PORT`
- `ROBOPLACE_SERIAL_BAUD`
- `ROBOPLACE_DEFAULT_PLAYER_ID`

## 5) Nginx reverse proxy

See `nginx/roboplace.conf` for an example local-domain setup.

Example deployment:
```text
roboplace.robotickytabor.cz/        -> webapp
roboplace.robotickytabor.cz/painter -> painter (restricted)
roboplace.robotickytabor.cz/connector -> connector MAC manager (restricted)
roboplace.robotickytabor.cz/logs    -> logviewer (restricted)
```

## 6) Systemd services

Generate service files:

```bash
make services
```

Install and start:

```bash
sudo ./setup_services.sh --install
```

## 7) API reference

See `API.md` for full request/response examples and the commands reference (`set_name`, `alliance_create`, `alliance_join`, `alliance_leave`, `alliance_kick`, `alliance_delete`).

## 8) Notes

- The public web viewer is read-only.
- Restricted tools accept traffic from allowed IPs when behind nginx; otherwise they are open on localhost.
- Connector MAC mappings can be updated live without restarting.
