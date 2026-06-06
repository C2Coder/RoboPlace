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


def _logo_path() -> Path:
    return Path(__file__).resolve().parent / "logo.svg"


app = FastAPI(title="RoboPlace LogViewer")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "logviewer"}


@app.get("/api/logs")
def proxy_logs(
    limit: int = 200,
    event_type: str | None = None,
    player_id: str | None = None,
    start_ts: float | None = None,
    end_ts: float | None = None,
) -> dict:
    params: dict[str, str | int | float] = {"limit": limit}
    if event_type:
        params["event_type"] = event_type
    if player_id:
        params["player_id"] = player_id
    if start_ts is not None:
        params["start_ts"] = start_ts
    if end_ts is not None:
        params["end_ts"] = end_ts
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{_server_url()}/api/logs",
                params=params,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"failed to load logs: {exc}") from exc


@app.get("/logo.svg")
def logo() -> FileResponse:
    path = _logo_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="logo.svg not found")
    return FileResponse(path, media_type="image/svg+xml")


class Query(BaseModel):
    limit: int = Field(default=200, ge=1, le=1000)
    event_type: str | None = Field(default=None, max_length=64)
    player_id: str | None = Field(default=None, max_length=64)
    start_ts: float | None = None
    end_ts: float | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RoboPlace LogViewer</title>
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
    }
    .layout {
      display: grid;
      gap: 10px;
      padding: 10px;
      min-height: 100vh;
    }
    @media (min-width: 980px) {
      .layout { grid-template-columns: 1fr 500px; }
    }
    .viewer, .side {
      background: linear-gradient(180deg, #111823, #0f1520);
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: auto;
    }
    .viewer {
      padding: 10px;
    }
    .side {
      padding: 10px;
      display: grid;
      gap: 10px;
    }
    .filters {
      display: grid;
      gap: 8px;
    }
    label { color: var(--muted); font-size: 12px; }
    input, select, textarea {
      width: 100%;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0f141c;
      color: var(--text);
      font: inherit;
    }
    textarea {
      min-height: 120px;
      white-space: pre;
      overflow-x: auto;
    }
    button {
      width: 100%;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #16212f;
      color: var(--text);
      cursor: pointer;
      font: inherit;
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
      vertical-align: top;
    }
    th { color: var(--muted); }
    .payload { color: var(--muted); word-break: break-all; max-width: 360px; }
    .details { color: var(--muted); }
    .muted { color: var(--muted); }
  </style>
</head>
<body>
  <main class="layout">
    <section class="viewer" id="viewer">
      <p id="status" class="muted">loading...</p>
      <div style="overflow-x:auto;">
        <table id="logs">
          <thead>
            <tr>
              <th>id</th>
              <th>event_type</th>
              <th>player_id</th>
              <th>payload</th>
              <th>details</th>
              <th>source</th>
              <th>created_at</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </section>
    <aside class="side">
      <div class="filters">
        <label>event_type</label>
        <select id="eventType">
          <option value="">any</option>
          <option>paint</option>
          <option>command</option>
          <option>cooldown_rejected</option>
          <option>error</option>
        </select>
        <label>player_id</label>
        <input id="playerId" />
        <label>limit</label>
        <input id="limit" type="number" value="200" min="1" max="1000" />
        <label>start_ts</label>
        <input id="startTs" type="number" step="any" placeholder="optional unix seconds" />
        <label>end_ts</label>
        <input id="endTs" type="number" step="any" placeholder="optional unix seconds" />
        <button id="load">Load logs</button>
        <button id="clearFilters">Clear filters</button>
      </div>
      <div id="meta" class="muted"></div>
    </aside>
  </main>

  <script>
    const params = new URLSearchParams(window.location.search);
    document.getElementById('eventType').value = params.get('event_type') || '';
    document.getElementById('playerId').value = params.get('player_id') || '';
    document.getElementById('limit').value = params.get('limit') || '200';
    document.getElementById('startTs').value = params.get('start_ts') || '';
    document.getElementById('endTs').value = params.get('end_ts') || '';

    function buildQuery() {
      const q = new URLSearchParams();
      const limit = document.getElementById('limit').value.trim();
      if (limit) q.set('limit', limit);
      const et = document.getElementById('eventType').value.trim();
      if (et) q.set('event_type', et);
      const pid = document.getElementById('playerId').value.trim();
      if (pid) q.set('player_id', pid);
      const st = document.getElementById('startTs').value.trim();
      if (st) q.set('start_ts', st);
      const ets = document.getElementById('endTs').value.trim();
      if (ets) q.set('end_ts', ets);
      return q;
    }

    async function load() {
      const statusEl = document.getElementById('status');
      const metaEl = document.getElementById('meta');
      const qs = buildQuery();
      window.history.replaceState(null, '', '?' + qs.toString());
      statusEl.textContent = 'loading...';
      metaEl.textContent = '';
      try {
        const res = await fetch('/api/logs?' + qs.toString(), { cache: 'no-store' });
        if (!res.ok) {
          throw new Error('api error: ' + res.status);
        }
        const data = await res.json();
        render(data.logs || []);
        statusEl.textContent = `loaded ${(data.logs || []).length} logs`;
        metaEl.textContent = `q=${qs.toString()}`;
      } catch (err) {
        statusEl.textContent = 'error';
        console.error(err);
      }
    }

    function formatTs(ts) {
      if (!ts) return '-';
      const d = new Date(Number(ts) * 1000);
      if (Number.isNaN(d.getTime())) return String(ts);
      return d.toLocaleString();
    }

    function render(logs) {
      const tbody = document.querySelector('#logs tbody');
      tbody.innerHTML = '';
      if (!logs.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="muted">no logs</td></tr>';
        return;
      }
      for (const row of logs) {
        const tr = document.createElement('tr');
        const payload = row.payload && Object.keys(row.payload).length ? JSON.stringify(row.payload) : '';
        tr.innerHTML = `
          <td>${row.id ?? '-'}</td>
          <td>${row.event_type ?? '-'}</td>
          <td>${row.player_id ?? '-'}</td>
          <td class="payload">${escapeHtml(payload)}</td>
          <td class="details">${escapeHtml(row.details || '')}</td>
          <td>${escapeHtml(row.source || '')}</td>
          <td>${formatTs(row.created_at)}</td>
        `;
        tbody.appendChild(tr);
      }
    }

    function escapeHtml(text) {
      return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    document.getElementById('load').addEventListener('click', load);
    document.getElementById('clearFilters').addEventListener('click', () => {
      document.getElementById('eventType').value = '';
      document.getElementById('playerId').value = '';
      document.getElementById('limit').value = '200';
      document.getElementById('startTs').value = '';
      document.getElementById('endTs').value = '';
      load();
    });
    load();
  </script>
</body>
</html>
"""
