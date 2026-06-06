# RoboPlace API Reference

## Base URLs

- Server: `http://127.0.0.1:8000`
- Connector: `http://127.0.0.1:8001`
- Webapp: `http://127.0.0.1:8002`
- Painter: `http://127.0.0.1:8003`

## Authentication

Server endpoints that modify state require the shared secret:

```
X-RoboPlace-Secret: <secret>
```

Configure via `.env`:
```
ROBOPLACE_SHARED_SECRET=your-secret-here
```

The connector, painter, and ESP devices use this header automatically when configured.

---

## Server API

### `POST /api/paint`

Paint a pixel on the canvas. Requires `X-RoboPlace-Secret` header.

**Request body:**
```json
{
  "player_id": "string (1-64 chars)",
  "x": 0,
  "y": 0,
  "color": [255, 0, 0],
  "source": "optional string"
}
```

**Response:**
```json
{
  "status": "stored",
  "cooldown_seconds": 10
}
```

**Errors:**
- `401` - missing `X-RoboPlace-Secret`
- `403` - invalid secret
- `409` - cooldown active
- `422` - invalid coordinates or color

### `POST /api/command`

Execute a player command (set name, alliance actions). Requires `X-RoboPlace-Secret` header.

**Request body:**
```json
{
  "player_id": "string (1-64 chars)",
  "command": "string (1-64 chars)",
  "value": "optional string (0-64 chars)",
  "target_player_id": "optional string (1-64 chars)",
  "alliance_id": "optional integer"
}
```

**Commands:**

| Command | Description |
|---------|-------------|
| `set_name` | Set display name. Requires `value` (1-32 chars). |
| `alliance_create` | Create new alliance. Requires `value` (alliance name, 1-32 chars). Player must not already be in an alliance. |
| `alliance_join` | Join an alliance. Use `value` (alliance name) or `alliance_id`. Player must not already be in an alliance. |
| `alliance_leave` | Leave current alliance. Creator cannot leave; must delete instead. |
| `alliance_kick` | Kick a member. Requires `target_player_id`. Only creator can kick. Creator cannot kick themselves. |
| `alliance_delete` | Delete alliance and remove all members. Only creator can delete. |

**set_name response:**
```json
{
  "status": "ok",
  "command": "set_name",
  "display_name": "New Name"
}
```

**alliance_create response:**
```json
{
  "status": "ok",
  "command": "alliance_create",
  "alliance_id": 1,
  "name": "My Alliance"
}
```

**alliance_join response:**
```json
{
  "status": "ok",
  "command": "alliance_join",
  "alliance_id": 1,
  "name": "My Alliance"
}
```

**alliance_leave response:**
```json
{
  "status": "ok",
  "command": "alliance_leave"
}
```

**alliance_kick response:**
```json
{
  "status": "ok",
  "command": "alliance_kick",
  "kicked": "player-id"
}
```

**alliance_delete response:**
```json
{
  "status": "ok",
  "command": "alliance_delete",
  "deleted_alliance_id": 1
}
```

**Errors:**
- `400` - invalid command or missing required fields
- `401` - missing secret
- `403` - insufficient permissions
- `404` - alliance/player not found
- `409` - already in alliance or name exists

### `GET /api/cooldown/{player_id}`

Check remaining cooldown for a player.

**Response:**
```json
{
  "player_id": "player-id",
  "cooldown_seconds": 10,
  "remaining_seconds": 0.0,
  "can_paint": true
}
```

### `GET /api/canvas`

Get current canvas state (256x256 RGB pixels).

**Response:**
```json
{
  "size": 256,
  "pixels": [
    [[255,255,255], ...],
    ...
  ]
}
```

### `GET /api/stats`

Get player statistics.

**Response:**
```json
{
  "total_placements": 1234,
  "total_players": 56,
  "active_players_24h": 23,
  "cooldown_seconds": 10,
  "players": [
    {
      "player_id": "player-1",
      "display_name": "RoboPilot",
      "placements": 50,
      "unique_pixels": 45,
      "first_placement": 1700000000.0,
      "last_placement": 1700003600.0,
      "last_x": 100,
      "last_y": 200,
      "alliance_id": 1,
      "alliance_name": "Team Red"
    }
  ]
}
```

### `GET /api/alliances`

Get all alliances with members.

**Response:**
```json
{
  "alliances": [
    {
      "id": 1,
      "name": "Team Red",
      "created_by": "creator-player-id",
      "created_at": 1700000000.0,
      "member_count": 5,
      "members": [
        {
          "player_id": "member-1",
          "display_name": "PixelPainter"
        }
      ]
    }
  ]
}
```

### `GET /api/heatmap`

Get placement heatmap data.

**Response:**
```json
{
  "size": 256,
  "heatmap": [
    [0, 5, 12, ...],
    ...
  ]
}
```

### `GET /health`

Health check.

**Response:**
```json
{
  "status": "ok",
  "service": "server",
  "cooldown_seconds": 10
}
```

---

## Connector API

The connector acts as a middleman between ESP devices and the server. It reads serial data and forwards validated messages.

### `POST /api/device/paint`

Forward a paint command from a device using 9-bit color format.

**Request body:**
```json
{
  "player_id": "string (1-64 chars)",
  "x": 0,
  "y": 0,
  "color": "753"
}
```

**color format:** `000-777` (3 digits, each 0-7 representing R, G, B channels).

**Response:**
```json
{
  "status": "forwarded",
  "kind": "paint",
  "result": {
    "status": "stored",
    "cooldown_seconds": 10
  }
}
```

### `POST /api/device/command`

Forward a command from a device.

**Request body:**
```json
{
  "player_id": "string (1-64 chars)",
  "command": "string (1-64 chars)",
  "value": "optional string",
  "target_player_id": "optional string",
  "alliance_id": "optional integer"
}
```

**Response:**
```json
{
  "status": "forwarded",
  "kind": "command",
  "result": {
    "status": "ok",
    "command": "set_name",
    "display_name": "New Name"
  }
}
```

### `POST /api/device/place`

Legacy endpoint using RGB array instead of 9-bit color.

**Request body:**
```json
{
  "player_id": "string (1-64 chars)",
  "x": 0,
  "y": 0,
  "color": [120, 50, 200]
}
```

**Response:**
```json
{
  "status": "forwarded",
  "kind": "paint",
  "result": {
    "status": "stored",
    "cooldown_seconds": 10
  }
}
```

### `POST /api/device/serial-line`

Inject a single serial line for testing.

**Request body:**
```json
"{\"mac\":\"AA:BB:CC:DD:EE:FF\",\"message\":{\"player_id\":\"p1\",\"x\":10,\"y\":20,\"color\":\"753\"}}"
```

**Response:**
```json
{
  "status": "forwarded",
  "kind": "paint",
  "result": {
    "status": "stored",
    "cooldown_seconds": 10
  }
}
```

### `GET /api/events/recent`

Get recent connector events.

**Query params:**
- `limit` (1-200, default 50)

**Response:**
```json
{
  "events": [
    {
      "id": 1,
      "mac": "AA:BB:CC:DD:EE:FF",
      "raw_message": "...",
      "processed_at": 1700000000.0,
      "status": "paint_forwarded",
      "detail": ""
    }
  ]
}
```

### `GET /health`

Connector health check.

**Response:**
```json
{
  "status": "ok",
  "service": "connector",
  "serial_port": "/dev/ttyUSB0",
  "serial_baud": 115200
}
```

---

## Webapp API

### `GET /api/canvas`

Proxy to server canvas endpoint.

**Response:** Same as server `/api/canvas`.

### `GET /api/stats`

Proxy to server stats endpoint.

**Response:** Same as server `/api/stats`.

### `GET /api/alliances`

Proxy to server alliances endpoint.

**Response:** Same as server `/api/alliances`.

### `GET /`

Serves the web viewer HTML page.

---

## Painter API

### `POST /api/paint`

Send a paint command directly to the server (manual editor).

**Request body:**
```json
{
  "player_id": "string (1-64 chars)",
  "x": 0,
  "y": 0,
  "color": [255, 0, 0]
}
```

**Response:**
```json
{
  "status": "stored"
}
```

### `POST /api/command`

Send a command directly to the server (manual editor).

**Request body:**
```json
{
  "player_id": "string (1-64 chars)",
  "command": "set_name",
  "value": "My Name",
  "target_player_id": "optional",
  "alliance_id": "optional integer"
}
```

**Response:** Same as server `/api/command`.

### `GET /`

Serves the painter HTML page.

---

## Serial Message Format

ESP devices send JSON lines over serial. Each line is a complete JSON object.

### Paint Message

```json
{
  "mac": "AA:BB:CC:DD:EE:FF",
  "message": {
    "player_id": "player-1",
    "x": 100,
    "y": 200,
    "color": "753"
  }
}
```

- `mac`: ESP32 MAC address
- `player_id`: player identifier (falls back to MAC if missing)
- `x`, `y`: coordinates (0-255)
- `color`: 9-bit color code `000-777`

### Command Message

```json
{
  "mac": "AA:BB:CC:DD:EE:FF",
  "message": {
    "player_id": "player-1",
    "command": "set_name",
    "value": "RoboPilot"
  }
}
```

```json
{
  "mac": "AA:BB:CC:DD:EE:FF",
  "message": {
    "player_id": "player-1",
    "command": "alliance_create",
    "value": "My Alliance"
  }
}
```

```json
{
  "mac": "AA:BB:CC:DD:EE:FF",
  "message": {
    "player_id": "player-1",
    "command": "alliance_kick",
    "target_player_id": "player-to-kick"
  }
}
```

**Supported commands in serial:**
- `set_name` with `value` (name)
- `alliance_create` with `value` (alliance name)
- `alliance_join` with `value` (alliance name) or `alliance_id`
- `alliance_leave`
- `alliance_kick` with `target_player_id`
- `alliance_delete`

---

## Commands Reference

### `set_name`

Set a player's display name.

**Required:** `value` (1-32 characters)

**Example:**
```json
{
  "player_id": "player-1",
  "command": "set_name",
  "value": "RoboPilot"
}
```

**Result:**
```json
{
  "status": "ok",
  "command": "set_name",
  "display_name": "RoboPilot"
}
```

### `alliance_create`

Create a new alliance. Player becomes the creator.

**Required:** `value` (alliance name, 1-32 characters)
**Restrictions:** Player must not already be in an alliance.

**Example:**
```json
{
  "player_id": "player-1",
  "command": "alliance_create",
  "value": "Pixel Warriors"
}
```

**Result:**
```json
{
  "status": "ok",
  "command": "alliance_create",
  "alliance_id": 1,
  "name": "Pixel Warriors"
}
```

### `alliance_join`

Join an existing alliance.

**Required:** Either `value` (alliance name) or `alliance_id`
**Restrictions:** Player must not already be in an alliance.

**Example (by name):**
```json
{
  "player_id": "player-2",
  "command": "alliance_join",
  "value": "Pixel Warriors"
}
```

**Example (by ID):**
```json
{
  "player_id": "player-2",
  "command": "alliance_join",
  "alliance_id": 1
}
```

**Result:**
```json
{
  "status": "ok",
  "command": "alliance_join",
  "alliance_id": 1,
  "name": "Pixel Warriors"
}
```

### `alliance_leave`

Leave current alliance.

**Restrictions:** Alliance creator cannot leave; must use `alliance_delete`.

**Example:**
```json
{
  "player_id": "player-2",
  "command": "alliance_leave"
}
```

**Result:**
```json
{
  "status": "ok",
  "command": "alliance_leave"
}
```

### `alliance_kick`

Kick a member from your alliance.

**Required:** `target_player_id`
**Restrictions:** Only alliance creator can kick. Cannot kick yourself.

**Example:**
```json
{
  "player_id": "player-1",
  "command": "alliance_kick",
  "target_player_id": "player-2"
}
```

**Result:**
```json
{
  "status": "ok",
  "command": "alliance_kick",
  "kicked": "player-2"
}
```

### `alliance_delete`

Delete an alliance permanently.

**Restrictions:** Only alliance creator can delete.

**Example:**
```json
{
  "player_id": "player-1",
  "command": "alliance_delete"
}
```

**Result:**
```json
{
  "status": "ok",
  "command": "alliance_delete",
  "deleted_alliance_id": 1
}
```

---

## 9-Bit Color Format

Colors use a 3-digit format where each digit represents an RGB channel intensity from 0-7.

**Format:** `000` to `777`

**Mapping to 24-bit RGB:**
- `0` -> `0`
- `1` -> `36`
- `2` -> `73`
- `3` -> `109`
- `4` -> `146`
- `5` -> `182`
- `6` -> `219`
- `7` -> `255`

**Examples:**
| 9-bit | RGB |
|-------|-----|
| `000` | (0, 0, 0) - Black |
| `777` | (255, 255, 255) - White |
| `700` | (255, 0, 0) - Red |
| `070` | (0, 255, 0) - Green |
| `007` | (0, 0, 255) - Blue |
| `753` | (255, 182, 109) - Orange |

This reduces ESP payload size from 3 bytes to 1 byte per color.
