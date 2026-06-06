from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from roboplace_env import load_project_env

load_project_env(__file__)


def _server_url() -> str:
    return os.getenv("ROBOPLACE_SERVER_URL", "http://127.0.0.1:8000")


def _shared_secret() -> str:
    return os.getenv("ROBOPLACE_SHARED_SECRET", "")


def _logo_path() -> Path:
    return Path(__file__).resolve().parent / "logo.svg"


class PaintRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    x: int = Field(ge=0, le=255)
    y: int = Field(ge=0, le=255)
    color: list[int]


class CommandRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    command: str = Field(min_length=1, max_length=64)
    value: str | None = Field(default=None, max_length=64)
    target_player_id: str | None = Field(default=None, max_length=64)
    alliance_id: int | None = None


app = FastAPI(title="RoboPlace Painter")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "painter"}


@app.post("/api/paint")
def paint(req: PaintRequest) -> dict:
    payload = {
        "player_id": req.player_id,
        "x": req.x,
        "y": req.y,
        "color": req.color,
        "source": "manual:painter",
    }

    headers = {}
    if _shared_secret():
        headers["X-RoboPlace-Secret"] = _shared_secret()

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{_server_url()}/api/paint", json=payload, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"server unreachable: {exc}") from exc

    return {"status": "stored"}


@app.post("/api/command")
def command(req: CommandRequest) -> dict:
    headers = {}
    if _shared_secret():
        headers["X-RoboPlace-Secret"] = _shared_secret()
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{_server_url()}/api/command", json=req.model_dump(), headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"server unreachable: {exc}") from exc


@app.get("/logo.svg")
def logo() -> FileResponse:
    path = _logo_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="logo.svg not found")
    return FileResponse(path, media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RoboPlace Painter</title>
  <link rel="icon" type="image/svg+xml" href="/logo.svg" />
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #111823;
      --line: #253041;
      --text: #d8e0ea;
      --muted: #92a1b3;
      --accent: #46d6a8;
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
      max-width: 420px;
      margin: 10px auto;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: linear-gradient(180deg, #111823, #0f1520);
      display: grid;
      gap: 10px;
    }
    h1 { margin: 0 0 8px; font-size: 16px; }
    .row { display: grid; gap: 8px; margin-bottom: 8px; }
    label { font-size: 12px; color: var(--muted); }
    input { width: 100%; padding: 8px; border: 1px solid var(--line); border-radius: 8px; background: #0f141c; color: var(--text); }
    button { width: 100%; padding: 8px; border: 1px solid var(--line); border-radius: 8px; background: #16212f; color: var(--text); cursor: pointer; font: inherit; }
    #out { margin-top: 8px; font-size: 12px; color: var(--muted); white-space: pre-wrap; }
  </style>
</head>
<body>
  <div class="wrap">
    <div>
      <h1>Paint Pixel</h1>
      <div class="row"><label>player_id</label><input id="player" value="manual-user"></div>
      <div class="row"><label>x (0-255)</label><input id="x" type="number" min="0" max="255" value="0"></div>
      <div class="row"><label>y (0-255)</label><input id="y" type="number" min="0" max="255" value="0"></div>
      <div class="row"><label>color (#RRGGBB)</label><input id="color" value="#ff0000"></div>
      <button id="send">Paint Pixel</button>
    </div>

    <div>
      <h1>Command</h1>
      <div class="row"><label>player_id</label><input id="cmdPlayer" value="manual-user"></div>
      <div class="row"><label>command</label><input id="cmdName" value="set_name"></div>
      <div class="row"><label>value (name or alliance name)</label><input id="cmdValue" value=""></div>
      <div class="row"><label>target_player_id (for alliance_kick)</label><input id="cmdTarget" value=""></div>
      <div class="row"><label>alliance_id (optional)</label><input id="cmdAllianceId" type="number" min="1" value=""></div>
      <button id="sendCmd">Send Command</button>
    </div>

    <div id="out"></div>
  </div>

  <script>
    function hexToRgb(hex) {
      const clean = hex.replace('#', '').trim();
      if (!/^[0-9a-fA-F]{6}$/.test(clean)) throw new Error('invalid color');
      return [
        parseInt(clean.slice(0, 2), 16),
        parseInt(clean.slice(2, 4), 16),
        parseInt(clean.slice(4, 6), 16)
      ];
    }

    document.getElementById('send').addEventListener('click', async () => {
      const out = document.getElementById('out');
      out.textContent = 'sending...';
      const body = {
        player_id: document.getElementById('player').value.trim(),
        x: Number(document.getElementById('x').value),
        y: Number(document.getElementById('y').value),
        color: hexToRgb(document.getElementById('color').value)
      };

      try {
        const res = await fetch('/api/paint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        const text = await res.text();
        out.textContent = res.ok ? `ok: ${text}` : `error ${res.status}: ${text}`;
      } catch (err) {
        out.textContent = `error: ${err.message}`;
      }
    });

    document.getElementById('sendCmd').addEventListener('click', async () => {
      const out = document.getElementById('out');
      out.textContent = 'sending command...';
      const allianceRaw = document.getElementById('cmdAllianceId').value.trim();
      const value = document.getElementById('cmdValue').value.trim();
      const target = document.getElementById('cmdTarget').value.trim();
      const body = {
        player_id: document.getElementById('cmdPlayer').value.trim(),
        command: document.getElementById('cmdName').value.trim(),
        value: value || null,
        target_player_id: target || null,
        alliance_id: allianceRaw ? Number(allianceRaw) : null
      };

      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        const text = await res.text();
        out.textContent = res.ok ? `ok: ${text}` : `error ${res.status}: ${text}`;
      } catch (err) {
        out.textContent = `error: ${err.message}`;
      }
    });
  </script>
</body>
</html>
"""
