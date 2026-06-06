from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, FileResponse
from pydantic import BaseModel, Field, field_validator
from pathlib import Path

from roboplace_env import load_project_env

CANVAS_SIZE = 256

load_project_env(__file__)


class PaintFromDeviceRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    x: int = Field(ge=0, lt=CANVAS_SIZE)
    y: int = Field(ge=0, lt=CANVAS_SIZE)
    color: str


class CommandFromDeviceRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    command: str = Field(min_length=1, max_length=64)
    value: str | None = Field(default=None, max_length=64)
    target_player_id: str | None = Field(default=None, max_length=64)
    alliance_id: int | None = None


class PlaceFromDeviceRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    x: int
    y: int
    color: list[int]

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: list[int]) -> list[int]:
        if len(value) != 3:
            raise ValueError("color must be [r, g, b]")
        for c in value:
            if not isinstance(c, int) or c < 0 or c > 255:
                raise ValueError("color channels must be integers 0..255")
        return value

    @field_validator("x", "y")
    @classmethod
    def validate_xy(cls, value: int) -> int:
        if value < 0 or value >= CANVAS_SIZE:
            raise ValueError(f"x and y must be in 0..{CANVAS_SIZE - 1}")
        return value


class SerialLineRequest(BaseModel):
    line: str = Field(min_length=1)


class MacMappingRequest(BaseModel):
    mac: str = Field(min_length=1, max_length=64)
    player_id: str = Field(min_length=1, max_length=64)


class ImportCSVRequest(BaseModel):
    mode: str = Field(default="add", pattern="^(add|override)$")
    csv_text: str = Field(min_length=1)


def _db_path() -> Path:
    return Path(os.getenv("ROBOPLACE_CONNECTOR_DB_PATH", "connector/connector.db"))


def _server_url() -> str:
    return os.getenv("ROBOPLACE_SERVER_URL", "http://127.0.0.1:8000")


def _shared_secret() -> str:
    return os.getenv("ROBOPLACE_SHARED_SECRET", "")


def _serial_port() -> str:
    return os.getenv("ROBOPLACE_SERIAL_PORT", "/dev/ttyUSB0")


def _serial_baud() -> int:
    return int(os.getenv("ROBOPLACE_SERIAL_BAUD", "115200"))


def _default_player_id() -> str:
    return os.getenv("ROBOPLACE_DEFAULT_PLAYER_ID", "anonymous")


def _logo_path() -> Path:
    return Path(__file__).resolve().parent.parent / "webapp" / "logo.svg"


def _connect() -> sqlite3.Connection:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS connector_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac TEXT NOT NULL,
            raw_message TEXT NOT NULL,
            processed_at REAL NOT NULL,
            status TEXT NOT NULL,
            detail TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mac_map (
            mac TEXT PRIMARY KEY,
            player_id TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def log_event(mac: str, raw_message: str, status: str, detail: str = "") -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO connector_events (mac, raw_message, processed_at, status, detail)
        VALUES (?, ?, ?, ?, ?)
        """,
        (mac, raw_message, time.time(), status, detail),
    )
    conn.commit()
    conn.close()


def resolve_player_id(mac: str) -> str:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT player_id FROM mac_map WHERE mac = ?", (mac,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["player_id"]
    return _default_player_id()


def upsert_mac_mapping(mac: str, player_id: str) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO mac_map (mac, player_id, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(mac) DO UPDATE SET player_id = excluded.player_id, updated_at = excluded.updated_at
        """,
        (mac, player_id, time.time()),
    )
    conn.commit()
    conn.close()


def list_mac_mappings() -> list[dict]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT mac, player_id, updated_at FROM mac_map ORDER BY updated_at DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def delete_all_mac_mappings() -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM mac_map")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def _import_csv(csv_text: str, mode: str) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV missing header row")

    lower_fields = [field.strip().lower() for field in reader.fieldnames]
    if "mac" not in lower_fields:
        raise HTTPException(status_code=400, detail="CSV must contain 'mac' column")
    if "player_id" not in lower_fields:
        raise HTTPException(status_code=400, detail="CSV must contain 'player_id' column")

    mac_idx = lower_fields.index("mac")
    player_id_idx = lower_fields.index("player_id")

    rows = []
    for row in reader:
        mac = row[reader.fieldnames[mac_idx]].strip()
        player_id = row[reader.fieldnames[player_id_idx]].strip()
        if not mac or not player_id:
            continue
        rows.append({"mac": mac, "player_id": player_id})

    if mode == "override":
        delete_all_mac_mappings()
        inserted = 0
        for item in rows:
            upsert_mac_mapping(item["mac"], item["player_id"])
            inserted += 1
        return {"mode": mode, "imported": inserted}
    inserted = 0
    updated = 0
    conn = _connect()
    cur = conn.cursor()
    for item in rows:
        cur.execute("SELECT mac FROM mac_map WHERE mac = ?", (item["mac"],))
        if cur.fetchone():
            upsert_mac_mapping(item["mac"], item["player_id"])
            updated += 1
        else:
            upsert_mac_mapping(item["mac"], item["player_id"])
            inserted += 1
    conn.close()
    return {"mode": mode, "inserted": inserted, "updated": updated}


def _export_csv() -> str:
    mappings = list_mac_mappings()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["mac", "player_id", "updated_at"])
    writer.writeheader()
    for row in mappings:
        writer.writerow(
            {
                "mac": row["mac"],
                "player_id": row["player_id"],
                "updated_at": int(row["updated_at"]) if row["updated_at"] is not None else "",
            }
        )
    return buf.getvalue()


def _server_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    secret = _shared_secret()
    if secret:
        headers["X-RoboPlace-Secret"] = secret
    return headers


def forward_paint(player_id: str, x: int, y: int, color_rgb: list[int], source_mac: str) -> dict:
    payload = {
        "player_id": player_id,
        "x": x,
        "y": y,
        "color": color_rgb,
        "source": f"espnow:{source_mac}",
    }
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(f"{_server_url()}/api/paint", json=payload, headers=_server_headers())
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


def forward_command(payload: dict) -> dict:
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(f"{_server_url()}/api/command", json=payload, headers=_server_headers())
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


def _decode_9bit_color(value: str | int) -> list[int]:
    if isinstance(value, int):
        value = f"{value:03d}"
    elif isinstance(value, str):
        value = value.strip()
    else:
        raise ValueError("color must be a 3-digit number/string in range 000-777")

    if len(value) != 3 or not value.isdigit():
        raise ValueError("color must be exactly 3 digits like 000-777")

    digits = [int(ch) for ch in value]
    if any(d < 0 or d > 7 for d in digits):
        raise ValueError("each color digit must be in range 0..7")

    return [round(d * 255 / 7) for d in digits]


def _extract_payload_from_serial_line(line: str) -> tuple[str, dict]:
    parsed = json.loads(line)
    mac = parsed.get("mac")
    if not isinstance(mac, str) or not mac.strip():
        raise ValueError("serial line must contain non-empty 'mac'")

    message = parsed.get("message", parsed)
    if isinstance(message, str):
        message = json.loads(message)
    if not isinstance(message, dict):
        raise ValueError("'message' must be a JSON object or JSON string")

    resolved_player_id = resolve_player_id(mac)

    if "command" in message:
        payload = {
            "kind": "command",
            "payload": {
                "player_id": message.get("player_id", resolved_player_id),
                "command": message.get("command"),
                "value": message.get("value"),
                "target_player_id": message.get("target_player_id"),
                "alliance_id": message.get("alliance_id"),
            },
        }
        return mac, payload

    raw_color = message.get("color")
    if raw_color is None:
        raise ValueError("message.color is required and must be 000-777")

    payload = {
        "kind": "paint",
        "payload": {
            "player_id": message.get("player_id", resolved_player_id),
            "x": message.get("x"),
            "y": message.get("y"),
            "color": _decode_9bit_color(raw_color),
        },
    }
    return mac, payload


def process_serial_line(line: str) -> dict:
    mac = "unknown"
    try:
        mac, wrapped = _extract_payload_from_serial_line(line)
        if wrapped["kind"] == "command":
            req = CommandFromDeviceRequest(**wrapped["payload"])
            result = forward_command(req.model_dump())
            log_event(mac, line, "command_forwarded", "")
            return {"status": "forwarded", "kind": "command", "result": result}

        req = PlaceFromDeviceRequest(**wrapped["payload"])
        result = forward_paint(req.player_id, req.x, req.y, req.color, mac)
        log_event(mac, line, "paint_forwarded", "")
        return {"status": "forwarded", "kind": "paint", "result": result}
    except HTTPException as exc:
        log_event(mac, line, "error", str(exc.detail))
        return {"status": "error", "detail": exc.detail}
    except Exception as exc:  # noqa: BLE001
        log_event(mac, line, "error", str(exc))
        return {"status": "error", "detail": str(exc)}


def _serial_loop() -> None:
    import serial

    while True:
        try:
            with serial.Serial(_serial_port(), _serial_baud(), timeout=1) as ser:
                while True:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    process_serial_line(line)
        except Exception:
            time.sleep(2)


def start_serial_worker() -> None:
    thread = threading.Thread(target=_serial_loop, daemon=True)
    thread.start()


app = FastAPI(title="RoboPlace Connector")


@app.on_event("startup")
def startup() -> None:
    init_db()
    start_serial_worker()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "connector",
        "serial_port": _serial_port(),
        "serial_baud": _serial_baud(),
        "default_player_id": _default_player_id(),
    }


@app.post("/api/device/paint")
def paint_from_device(req: PaintFromDeviceRequest) -> dict:
    color_rgb = _decode_9bit_color(req.color)
    result = forward_paint(req.player_id, req.x, req.y, color_rgb, "http")
    return {"status": "forwarded", "kind": "paint", "result": result}


@app.post("/api/device/command")
def command_from_device(req: CommandFromDeviceRequest) -> dict:
    result = forward_command(req.model_dump())
    return {"status": "forwarded", "kind": "command", "result": result}


@app.post("/api/device/place")
def place_from_device_legacy(req: PlaceFromDeviceRequest) -> dict:
    result = forward_paint(req.player_id, req.x, req.y, req.color, "http")
    return {"status": "forwarded", "kind": "paint", "result": result}


@app.post("/api/device/serial-line")
def ingest_serial_line(req: SerialLineRequest) -> dict:
    return process_serial_line(req.line)


@app.get("/api/events/recent")
def recent_events(limit: int = 50) -> dict:
    safe_limit = max(1, min(200, limit))
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, mac, raw_message, processed_at, status, detail
        FROM connector_events
        ORDER BY id DESC
        LIMIT ?
        """,
        (safe_limit,),
    )
    events = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"events": events}


@app.get("/api/mac-mappings")
def get_mac_mappings() -> dict:
    return {"mappings": list_mac_mappings(), "default_player_id": _default_player_id()}


@app.post("/api/mac-mappings")
def set_mac_mapping(req: MacMappingRequest) -> dict:
    upsert_mac_mapping(req.mac, req.player_id)
    return {"status": "updated", "mac": req.mac, "player_id": req.player_id}


@app.delete("/api/mac-mappings/{mac:path}")
def delete_mac_mapping(mac: str) -> dict:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM mac_map WHERE mac = ?", (mac,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "mac": mac}


@app.post("/api/mac-mappings/import")
def import_mac_mappings(req: ImportCSVRequest) -> dict:
    mode = req.mode.strip().lower()
    if mode not in {"add", "override"}:
        raise HTTPException(status_code=400, detail="mode must be add or override")
    if mode == "override":
        delete_all_mac_mappings()
    return _import_csv(req.csv_text, mode)


@app.delete("/api/mac-mappings")
def delete_all_mappings() -> dict:
    deleted = delete_all_mac_mappings()
    return {"status": "deleted", "deleted_count": deleted}


@app.get("/api/mac-mappings/export")
def export_mac_mappings() -> dict:
    csv_text = _export_csv()
    return {"csv": csv_text, "count": len(list_mac_mappings())}


@app.get("/", response_class=RedirectResponse)
def redirect_to_mac() -> RedirectResponse:
    return RedirectResponse(url="/mac", status_code=302)


@app.get("/mac", response_class=HTMLResponse)
def mac_page() -> str:
    return MAC_PAGE_HTML


@app.get("/logo.svg")
def logo() -> FileResponse:
    path = _logo_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="logo.svg not found")
    return FileResponse(path, media_type="image/svg+xml")


MAC_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Connector - MAC Manager</title>
  <link rel="icon" type="image/svg+xml" href="/logo.svg" />
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #111823;
      --line: #253041;
      --text: #d8e0ea;
      --muted: #92a1b3;
      --accent: #46d6a8;
      --danger: #f87171;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(1200px 700px at 10% -10%, #132033, transparent 50%),
                  radial-gradient(900px 500px at 90% 0%, #1a1c2d, transparent 55%),
                  var(--bg);
      color: var(--text);
      font-family: "JetBrains Mono", "Consolas", monospace;
      min-height: 100vh;
      padding: 10px;
    }
    .wrap {
      max-width: 1100px;
      margin: 0px auto;
      padding: 10px;
      display: grid;
      gap: 10px;
    }
    .panel {
      background: linear-gradient(180deg, #111823, #0f1520);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
    }
    h1 {
      margin: 0;
      font-size: 16px;
    }
    .row {
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }
    @media (min-width: 700px) {
      .row { grid-template-columns: 1fr 1fr; }
    }
    label {
      color: var(--muted);
      font-size: 12px;
    }
    input, select, textarea, button {
      width: 100%;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0f141c;
      color: var(--text);
      font: inherit;
    }
    textarea {
      min-height: 140px;
      white-space: pre;
      overflow-x: auto;
    }
    button {
      background: #16212f;
      cursor: pointer;
      margin-top: 6px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 6px;
      text-align: left;
    }
    th { color: var(--muted); }
    .actions { display: flex; gap: 6px; align-items: center; }
    .danger { color: var(--danger); }
    .muted { color: var(--muted); }
    .status { color: var(--muted); font-size: 12px; min-height: 18px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1>MAC Manager</h1>
      <p class="status" id="status">loading...</p>
      <div class="row">
        <div>
          <label>mac</label>
          <input id="mac" placeholder="AA:BB:CC:DD:EE:FF" />
        </div>
        <div>
          <label>player_id</label>
          <input id="playerId" placeholder="player-1" />
        </div>
      </div>
      <div class="row">
        <button id="add">Add / Override</button>
        <button id="refresh">Refresh</button>
      </div>
    </div>

    <div class="panel">
      <h1>Import / Export CSV</h1>
      <div class="row">
        <div>
          <label>mode</label>
          <select id="mode">
            <option value="add">add (keep existing, override matching MACs)</option>
            <option value="override">override all (remove all first)</option>
          </select>
        </div>
        <div>
          <label>csv</label>
          <textarea id="csv" placeholder="mac,player_id&#10;AA:BB:CC:DD:EE:FF,player-1"></textarea>
        </div>
      </div>
      <div class="row">
        <button id="import">Import</button>
        <button id="export">Export CSV</button>
      </div>
    </div>

    <div class="panel">
      <h1>Mappings (<span id="count">0</span>)</h1>
      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>mac</th>
              <th>player_id</th>
              <th>updated_at</th>
              <th>actions</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const statusEl = document.getElementById('status');
    const rowsEl = document.getElementById('rows');
    const countEl = document.getElementById('count');

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function formatTs(ts) {
      if (!ts) return '-';
      const d = new Date(Number(ts) * 1000);
      if (Number.isNaN(d.getTime())) return String(ts);
      return d.toLocaleString();
    }

    async function load() {
      statusEl.textContent = 'loading...';
      try {
        const res = await fetch('/api/mac-mappings');
        if (!res.ok) throw new Error('api error: ' + res.status);
        const data = await res.json();
        render(data.mappings || []);
        statusEl.textContent = `default player_id: ${data.default_player_id}`;
        countEl.textContent = (data.mappings || []).length;
      } catch (err) {
        statusEl.textContent = 'error';
        console.error(err);
      }
    }

    function render(mappings) {
      rowsEl.innerHTML = '';
      if (!mappings.length) {
        rowsEl.innerHTML = '<tr><td colspan="4" class="muted">no mappings</td></tr>';
        return;
      }
      for (const row of mappings) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${escapeHtml(row.mac)}</td>
          <td>${escapeHtml(row.player_id)}</td>
          <td>${escapeHtml(formatTs(row.updated_at))}</td>
          <td class="actions">
            <button data-action="delete" data-mac="${escapeHtml(row.mac)}">delete</button>
          </td>
        `;
        rowsEl.appendChild(tr);
      }
    }

    async function addMapping() {
      const mac = document.getElementById('mac').value.trim();
      const player_id = document.getElementById('playerId').value.trim();
      if (!mac || !player_id) {
        statusEl.textContent = 'mac and player_id required';
        return;
      }
      statusEl.textContent = 'saving...';
      try {
        const res = await fetch('/api/mac-mappings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mac, player_id })
        });
        const text = await res.text();
        statusEl.textContent = res.ok ? 'saved' : ('error: ' + text);
        document.getElementById('mac').value = '';
        document.getElementById('playerId').value = '';
        await load();
      } catch (err) {
        statusEl.textContent = 'error';
      }
    }

    async function deleteMapping(mac) {
      statusEl.textContent = 'deleting...';
      try {
        const res = await fetch('/api/mac-mappings/' + encodeURIComponent(mac), { method: 'DELETE' });
        const text = await res.text();
        statusEl.textContent = res.ok ? 'deleted' : ('error: ' + text);
        await load();
      } catch (err) {
        statusEl.textContent = 'error';
      }
    }

    async function importCsv() {
      const csvText = document.getElementById('csv').value.trim();
      const mode = document.getElementById('mode').value;
      if (!csvText) {
        statusEl.textContent = 'csv empty';
        return;
      }
      statusEl.textContent = 'importing...';
      try {
        const res = await fetch('/api/mac-mappings/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode, csv_text: csvText })
        });
        const data = await res.json();
        statusEl.textContent = res.ok ? 'imported ' + JSON.stringify(data) : ('error: ' + JSON.stringify(data));
        document.getElementById('csv').value = '';
        await load();
      } catch (err) {
        statusEl.textContent = 'error';
      }
    }

    async function exportCsv() {
      statusEl.textContent = 'exporting...';
      try {
        const res = await fetch('/api/mac-mappings/export');
        const data = await res.json();
        document.getElementById('csv').value = data.csv || '';
        statusEl.textContent = 'exported ' + (data.count ?? '?') + ' rows';
      } catch (err) {
        statusEl.textContent = 'error';
      }
    }

    document.getElementById('add').addEventListener('click', addMapping);
    document.getElementById('refresh').addEventListener('click', load);
    document.getElementById('import').addEventListener('click', importCsv);
    document.getElementById('export').addEventListener('click', exportCsv);

    rowsEl.addEventListener('click', (event) => {
      const btn = event.target.closest('button[data-action="delete"]');
      if (!btn) return;
      const mac = btn.getAttribute('data-mac');
      if (confirm('delete mapping for ' + mac + '?')) {
        deleteMapping(mac);
      }
    });

    load();
  </script>
</body>
</html>"""
