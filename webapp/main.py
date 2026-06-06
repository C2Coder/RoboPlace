from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from roboplace_env import load_project_env

load_project_env(__file__)


def _server_url() -> str:
    return os.getenv("ROBOPLACE_SERVER_URL", "http://127.0.0.1:8000")


def _logo_path() -> Path:
    return Path(__file__).resolve().parent / "logo.svg"


app = FastAPI(title="RoboPlace Webapp")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "webapp"}


@app.get("/api/canvas")
def proxy_canvas() -> dict:
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{_server_url()}/api/canvas")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"failed to load canvas: {exc}") from exc


@app.get("/api/stats")
def proxy_stats() -> dict:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{_server_url()}/api/stats")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"failed to load stats: {exc}") from exc


@app.get("/api/alliances")
def proxy_alliances() -> dict:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{_server_url()}/api/alliances")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"failed to load alliances: {exc}") from exc


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
  <title>RoboPlace</title>
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
      grid-template-columns: 1fr;
      gap: 10px;
      padding: 10px;
      height: calc(100vh);
    }

    @media (min-width: 980px) {
      .layout { grid-template-columns: 1fr 320px; }
    }

    .viewer, .side {
      background: linear-gradient(180deg, #111823, #0f1520);
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
    }

    .viewer {
      display: flex;
      align-items: stretch;
      gap: 10px;
      padding: 10px;
    }

    .fitBtn, .tabBtn {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #16212f;
      color: var(--text);
      cursor: pointer;
      font: inherit;
      font-size: 12px;
      padding: 8px 6px;
      width: 100%;
    }
    .tabBtn.active {
      background: #1e3046;
      border-color: #36547a;
    }

    .canvasViewport {
      flex: 1;
      overflow: auto;
      min-width: 0;
      min-height: 0;
    }



    .side {
      padding: 10px;
      overflow: hidden;
      height: 100%;
      max-height: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .sideTop {
      display: grid;
      gap: 8px;
    }

    .tabs {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
    }

    .tabBtn {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #16212f;
      color: var(--text);
      cursor: pointer;
      font: inherit;
      font-size: 12px;
      padding: 7px 6px;
      width: 100%;
    }

    .tabBtn.active {
      background: #1e3046;
      border-color: #36547a;
    }

    .status {
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .totals {
      display: grid;
      gap: 6px;
      margin-bottom: 10px;
      font-size: 13px;
    }

    .totals b { color: var(--accent); }

    #canvas {
      width: 256px;
      height: 256px;
      image-rendering: pixelated;
      image-rendering: crisp-edges;
      border: 1px solid var(--line);
      background: #000;
      display: block;
    }

    .players {
      display: grid;
      gap: 8px;
      overflow-y: auto;
      flex: 1;
      min-height: 0;
      align-content: start;
    }

    .player {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      font-size: 12px;
      color: var(--muted);
    }

    .player b {
      color: var(--text);
      font-size: 13px;
    }

    .alliances {
      display: grid;
      gap: 8px;
      overflow-y: auto;
      flex: 1;
      min-height: 0;
      align-content: start;
    }

    .alliance {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      font-size: 12px;
      color: var(--muted);
      display: grid;
      gap: 4px;
    }

    .alliance b {
      color: var(--text);
      font-size: 13px;
    }

    .hidden {
      display: none;
    }
  </style>
</head>
<body>
  <main class="layout">
    <section class="viewer" id="viewer">
      <div class="canvasViewport" id="canvasViewport">
        <canvas id="canvas" width="256" height="256"></canvas>
      </div>
    </section>
    <aside class="side">
      <div class="sideTop">
        <p id="status" class="status">loading...</p>
        <button id="fitBtn" class="fitBtn" type="button">fit</button>
        <div class="tabs">
          <button id="tabPlayers" class="tabBtn active" type="button">players</button>
          <button id="tabAlliances" class="tabBtn" type="button">alliances</button>
        </div>
      </div>
      <div class="totals">
        <div>placements: <b id="total">-</b></div>
        <div>players: <b id="playersCount">-</b></div>
        <div>24h active: <b id="active24h">-</b></div>
      </div>
      <div id="players" class="players"></div>
      <div id="alliances" class="alliances hidden"></div>
    </aside>
  </main>

  <script>
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const canvasViewport = document.getElementById('canvasViewport');
    const viewer = document.getElementById('viewer');
    const statusEl = document.getElementById('status');
    const fitBtn = document.getElementById('fitBtn');
    const tabPlayersBtn = document.getElementById('tabPlayers');
    const tabAlliancesBtn = document.getElementById('tabAlliances');
    const totalEl = document.getElementById('total');
    const playersCountEl = document.getElementById('playersCount');
    const active24hEl = document.getElementById('active24h');
    const playersEl = document.getElementById('players');
    const alliancesEl = document.getElementById('alliances');

    let activeTab = 'players';

    const minScale = 1;
    const maxScale = 20;
    let scale = 4;

    function setZoom(nextScale) {
      scale = Math.max(minScale, Math.min(maxScale, nextScale));
      const size = Math.round(256 * scale);
      canvas.style.width = size + 'px';
      canvas.style.height = size + 'px';
      statusEl.textContent = `live ${Math.round(scale * 100)}%`;
    }

    function fitToViewport() {
      const rect = canvasViewport.getBoundingClientRect();
      const availableWidth = Math.max(1, rect.width - 20);
      const availableHeight = Math.max(1, rect.height);
      const fitScale = Math.min(availableWidth / 256, availableHeight / 256);
      setZoom(fitScale);
    }

    function drawCanvas(pixels) {
      const image = ctx.createImageData(256, 256);
      let idx = 0;
      for (let y = 0; y < 256; y++) {
        for (let x = 0; x < 256; x++) {
          const [r, g, b] = pixels[y][x];
          image.data[idx++] = r;
          image.data[idx++] = g;
          image.data[idx++] = b;
          image.data[idx++] = 255;
        }
      }
      ctx.putImageData(image, 0, 0);
    }

    function renderPlayers(players) {
      playersEl.innerHTML = '';
      if (!players.length) {
        return;
      }
      const ordered = [...players].sort((a, b) => String(a.player_id).localeCompare(String(b.player_id)));
      for (const p of ordered) {
        const div = document.createElement('div');
        div.className = 'player';
        const coords = (p.last_x === null || p.last_y === null) ? '-' : `${p.last_x},${p.last_y}`;
        const label = p.display_name && p.display_name !== p.player_id
          ? `${p.display_name} (${p.player_id})`
          : p.player_id;
        const alliance = p.alliance_name ? `<br>alliance: ${p.alliance_name}` : '';
        div.innerHTML = `<b>${label}</b><br>${p.placements} px / ${p.unique_pixels ?? 0} unique<br>${coords}${alliance}`;
        playersEl.appendChild(div);
      }
    }

    function renderAlliances(alliances) {
      alliancesEl.innerHTML = '';
      if (!alliances.length) {
        alliancesEl.innerHTML = '<div class="alliance">no alliances</div>';
        return;
      }
      for (const a of alliances) {
        const div = document.createElement('div');
        div.className = 'alliance';
        const members = (a.members || []).map((m) => {
          if (m.display_name && m.display_name !== m.player_id) {
            return `${m.display_name} (${m.player_id})`;
          }
          return m.player_id;
        }).join(', ');
        div.innerHTML = `<b>${a.name}</b><span>creator: ${a.created_by}</span><span>members (${a.member_count}): ${members || '-'}</span>`;
        alliancesEl.appendChild(div);
      }
    }

    function applyTab() {
      const showPlayers = activeTab === 'players';
      playersEl.classList.toggle('hidden', !showPlayers);
      alliancesEl.classList.toggle('hidden', showPlayers);
      tabPlayersBtn.classList.toggle('active', showPlayers);
      tabAlliancesBtn.classList.toggle('active', !showPlayers);
    }

    async function refresh() {
      try {
        const [canvasRes, statsRes, alliancesRes] = await Promise.all([
          fetch('/api/canvas'),
          fetch('/api/stats'),
          fetch('/api/alliances')
        ]);
        if (!canvasRes.ok || !statsRes.ok || !alliancesRes.ok) {
          throw new Error('api error');
        }
        const canvasData = await canvasRes.json();
        const statsData = await statsRes.json();
        const alliancesData = await alliancesRes.json();
        drawCanvas(canvasData.pixels);
        totalEl.textContent = statsData.total_placements ?? 0;
        playersCountEl.textContent = statsData.total_players ?? 0;
        active24hEl.textContent = statsData.active_players_24h ?? 0;
        renderPlayers(statsData.players || []);
        renderAlliances(alliancesData.alliances || []);
        statusEl.textContent = `live ${Math.round(scale * 100)}%`;
      } catch (_err) {
        statusEl.textContent = 'error';
      }
    }

    window.addEventListener('keydown', (event) => {
      if (event.target && (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA')) {
        return;
      }
      if (event.key === '+' || event.key === '=') {
        event.preventDefault();
        setZoom(scale + 1);
      } else if (event.key === '-') {
        event.preventDefault();
        setZoom(scale - 1);
      } else if (event.key === '0') {
        event.preventDefault();
        setZoom(4);
      }
    });

    canvasViewport.addEventListener('wheel', (event) => {
      if (!event.ctrlKey) {
        return;
      }
      event.preventDefault();
      setZoom(scale + (event.deltaY < 0 ? 1 : -1));
    }, { passive: false });

    fitBtn.addEventListener('click', fitToViewport);
    tabPlayersBtn.addEventListener('click', () => {
      activeTab = 'players';
      applyTab();
    });
    tabAlliancesBtn.addEventListener('click', () => {
      activeTab = 'alliances';
      applyTab();
    });

    window.addEventListener('resize', () => {
      fitToViewport();
    });

    setZoom(scale);
    applyTab();
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""
