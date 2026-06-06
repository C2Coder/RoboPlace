from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from roboplace_env import load_project_env

CANVAS_SIZE = 256
DEFAULT_COLOR = (255, 255, 255)
DEFAULT_COOLDOWN_SECONDS = 10
DEFAULT_PLAYER_ID = "anonymous"

load_project_env(__file__)


class PaintPixelRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    x: int
    y: int
    color: list[int]
    source: str = "connector"

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: list[int]) -> list[int]:
        if len(value) != 3:
            raise ValueError("color must have 3 integer values [r, g, b]")
        for channel in value:
            if not isinstance(channel, int) or channel < 0 or channel > 255:
                raise ValueError("each color channel must be 0..255")
        return value

    @field_validator("x", "y")
    @classmethod
    def validate_xy(cls, value: int) -> int:
        if value < 0 or value >= CANVAS_SIZE:
            raise ValueError(f"x and y must be in range 0..{CANVAS_SIZE - 1}")
        return value


class CommandRequest(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    command: str = Field(min_length=1, max_length=64)
    value: str | None = Field(default=None, max_length=64)
    target_player_id: str | None = Field(default=None, max_length=64)
    alliance_id: int | None = None


def _db_path() -> Path:
    return Path(os.getenv("ROBOPLACE_DB_PATH", "server/roboplace.db"))


def _server_shared_secret() -> str:
    return os.getenv("ROBOPLACE_SHARED_SECRET", "")


def _cooldown_seconds() -> int:
    return int(os.getenv("ROBOPLACE_COOLDOWN_SECONDS", str(DEFAULT_COOLDOWN_SECONDS)))


def _connect() -> sqlite3.Connection:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def _log_event(
    conn: sqlite3.Connection,
    event_type: str,
    player_id: str,
    payload: dict | None = None,
    details: str = "",
    source: str = "server",
) -> None:
    now = time.time()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO event_log (event_type, player_id, payload, details, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (event_type, player_id, json.dumps(payload or {}), details, source, now),
    )


def init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            display_name TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS player_cooldowns (
            player_id TEXT PRIMARY KEY,
            last_paint_at REAL NOT NULL,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alliances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_by TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (created_by) REFERENCES players(player_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alliance_members (
            player_id TEXT PRIMARY KEY,
            alliance_id INTEGER NOT NULL,
            joined_at REAL NOT NULL,
            FOREIGN KEY (player_id) REFERENCES players(player_id),
            FOREIGN KEY (alliance_id) REFERENCES alliances(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pixels (
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            r INTEGER NOT NULL,
            g INTEGER NOT NULL,
            b INTEGER NOT NULL,
            updated_at REAL NOT NULL,
            updated_by TEXT NOT NULL,
            PRIMARY KEY (x, y)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS placements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            r INTEGER NOT NULL,
            g INTEGER NOT NULL,
            b INTEGER NOT NULL,
            source TEXT NOT NULL,
            placed_at REAL NOT NULL,
            FOREIGN KEY (player_id) REFERENCES players(player_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            player_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            details TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_log_created_at ON event_log(created_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_event_log_player_id ON event_log(player_id)"
    )

    cur.execute(
        """
        INSERT OR IGNORE INTO players (player_id, display_name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (DEFAULT_PLAYER_ID, "Default Player", time.time(), time.time()),
    )

    cur.execute("SELECT COUNT(*) AS n FROM pixels")
    row = cur.fetchone()
    if row and row["n"] == 0:
        now = time.time()
        data = [
            (x, y, DEFAULT_COLOR[0], DEFAULT_COLOR[1], DEFAULT_COLOR[2], now, "system")
            for y in range(CANVAS_SIZE)
            for x in range(CANVAS_SIZE)
        ]
        cur.executemany(
            """
            INSERT INTO pixels (x, y, r, g, b, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )

    conn.commit()
    conn.close()


def _require_secret(x_roboplace_secret: str | None) -> None:
    required_secret = _server_shared_secret()
    if required_secret:
        if not x_roboplace_secret:
            raise HTTPException(status_code=401, detail="missing connector secret")
        if x_roboplace_secret != required_secret:
            raise HTTPException(status_code=403, detail="invalid connector secret")


def ensure_player(conn: sqlite3.Connection, player_id: str) -> None:
    now = time.time()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO players (player_id, display_name, created_at, updated_at)
        VALUES (?, NULL, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (player_id, now, now),
    )


def get_remaining_cooldown(conn: sqlite3.Connection, player_id: str) -> float:
    cur = conn.cursor()
    cur.execute("SELECT last_paint_at FROM player_cooldowns WHERE player_id = ?", (player_id,))
    row = cur.fetchone()
    if row is None:
        return 0.0
    remaining = _cooldown_seconds() - (time.time() - row["last_paint_at"])
    return max(0.0, remaining)


def mark_painted_now(conn: sqlite3.Connection, player_id: str) -> None:
    now = time.time()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO player_cooldowns (player_id, last_paint_at)
        VALUES (?, ?)
        ON CONFLICT(player_id) DO UPDATE SET last_paint_at = excluded.last_paint_at
        """,
        (player_id, now),
    )


def store_paint(conn: sqlite3.Connection, req: PaintPixelRequest) -> None:
    now = time.time()
    r, g, b = req.color
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pixels (x, y, r, g, b, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(x, y)
        DO UPDATE SET
            r = excluded.r,
            g = excluded.g,
            b = excluded.b,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (req.x, req.y, r, g, b, now, req.player_id),
    )
    cur.execute(
        """
        INSERT INTO placements (player_id, x, y, r, g, b, source, placed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (req.player_id, req.x, req.y, r, g, b, req.source, now),
    )
    _log_event(
        conn,
        "paint",
        req.player_id,
        {"x": req.x, "y": req.y, "color": req.color, "source": req.source},
        f"paint at {req.x},{req.y}",
        req.source,
    )


def _get_player_alliance(conn: sqlite3.Connection, player_id: str) -> sqlite3.Row | None:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id, a.name, a.created_by
        FROM alliance_members m
        JOIN alliances a ON a.id = m.alliance_id
        WHERE m.player_id = ?
        """,
        (player_id,),
    )
    return cur.fetchone()


def execute_command(req: CommandRequest) -> dict:
    command = req.command.strip().lower()
    conn = _connect()
    cur = conn.cursor()
    ensure_player(conn, req.player_id)

    if command == "set_name":
        value = (req.value or "").strip()
        if not value or len(value) > 32:
            conn.close()
            raise HTTPException(status_code=400, detail="set_name requires value with 1..32 chars")
        cur.execute(
            "UPDATE players SET display_name = ?, updated_at = ? WHERE player_id = ?",
            (value, time.time(), req.player_id),
        )
        conn.commit()
        _log_event(
            conn, "command", req.player_id, {"command": command, "value": value}, "set_name"
        )
        conn.close()
        return {"status": "ok", "command": command, "display_name": value}

    if command == "alliance_create":
        value = (req.value or "").strip()
        if not value or len(value) > 32:
            conn.close()
            raise HTTPException(status_code=400, detail="alliance_create requires value with 1..32 chars")
        if _get_player_alliance(conn, req.player_id):
            conn.close()
            raise HTTPException(status_code=409, detail="player already in an alliance")
        now = time.time()
        try:
            cur.execute(
                "INSERT INTO alliances (name, created_by, created_at) VALUES (?, ?, ?)",
                (value, req.player_id, now),
            )
        except sqlite3.IntegrityError as exc:
            conn.close()
            raise HTTPException(status_code=409, detail="alliance name already exists") from exc
        alliance_id = cur.lastrowid
        cur.execute(
            "INSERT INTO alliance_members (player_id, alliance_id, joined_at) VALUES (?, ?, ?)",
            (req.player_id, alliance_id, now),
        )
        conn.commit()
        _log_event(
            conn,
            "command",
            req.player_id,
            {"command": command, "alliance_id": alliance_id, "name": value},
            "alliance_create",
        )
        conn.close()
        return {"status": "ok", "command": command, "alliance_id": alliance_id, "name": value}

    if command == "alliance_join":
        if _get_player_alliance(conn, req.player_id):
            conn.close()
            raise HTTPException(status_code=409, detail="player already in an alliance")

        alliance_row = None
        if req.alliance_id is not None:
            cur.execute("SELECT id, name, created_by FROM alliances WHERE id = ?", (req.alliance_id,))
            alliance_row = cur.fetchone()
        else:
            value = (req.value or "").strip()
            if not value:
                conn.close()
                raise HTTPException(status_code=400, detail="alliance_join requires alliance_id or value(name)")
            cur.execute("SELECT id, name, created_by FROM alliances WHERE name = ?", (value,))
            alliance_row = cur.fetchone()

        if alliance_row is None:
            conn.close()
            raise HTTPException(status_code=404, detail="alliance not found")

        cur.execute(
            "INSERT INTO alliance_members (player_id, alliance_id, joined_at) VALUES (?, ?, ?)",
            (req.player_id, alliance_row["id"], time.time()),
        )
        conn.commit()
        _log_event(
            conn,
            "command",
            req.player_id,
            {"command": command, "alliance_id": alliance_row["id"], "name": alliance_row["name"]},
            "alliance_join",
        )
        conn.close()
        return {
            "status": "ok",
            "command": command,
            "alliance_id": alliance_row["id"],
            "name": alliance_row["name"],
        }

    if command == "alliance_leave":
        current = _get_player_alliance(conn, req.player_id)
        if current is None:
            conn.close()
            raise HTTPException(status_code=404, detail="player is not in an alliance")
        if current["created_by"] == req.player_id:
            conn.close()
            raise HTTPException(status_code=409, detail="creator cannot leave; use alliance_delete")
        cur.execute("DELETE FROM alliance_members WHERE player_id = ?", (req.player_id,))
        conn.commit()
        _log_event(conn, "command", req.player_id, {"command": command}, "alliance_leave")
        conn.close()
        return {"status": "ok", "command": command}

    if command == "alliance_kick":
        target = (req.target_player_id or "").strip()
        if not target:
            conn.close()
            raise HTTPException(status_code=400, detail="alliance_kick requires target_player_id")

        current = _get_player_alliance(conn, req.player_id)
        if current is None:
            conn.close()
            raise HTTPException(status_code=404, detail="player is not in an alliance")
        if current["created_by"] != req.player_id:
            conn.close()
            raise HTTPException(status_code=403, detail="only creator can kick")
        if target == req.player_id:
            conn.close()
            raise HTTPException(status_code=400, detail="creator cannot kick self")

        cur.execute(
            "DELETE FROM alliance_members WHERE player_id = ? AND alliance_id = ?",
            (target, current["id"]),
        )
        if cur.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="target is not a member of your alliance")
        conn.commit()
        _log_event(
            conn,
            "command",
            req.player_id,
            {"command": command, "kicked": target},
            "alliance_kick",
        )
        conn.close()
        return {"status": "ok", "command": command, "kicked": target}

    if command == "alliance_delete":
        current = _get_player_alliance(conn, req.player_id)
        if current is None:
            conn.close()
            raise HTTPException(status_code=404, detail="player is not in an alliance")
        if current["created_by"] != req.player_id:
            conn.close()
            raise HTTPException(status_code=403, detail="only creator can delete")

        cur.execute("DELETE FROM alliance_members WHERE alliance_id = ?", (current["id"],))
        cur.execute("DELETE FROM alliances WHERE id = ?", (current["id"],))
        conn.commit()
        _log_event(
            conn,
            "command",
            req.player_id,
            {"command": command, "deleted_alliance_id": current["id"]},
            "alliance_delete",
        )
        conn.close()
        return {"status": "ok", "command": command, "deleted_alliance_id": current["id"]}

    conn.close()
    raise HTTPException(status_code=400, detail="unknown command")


def load_canvas() -> list[list[list[int]]]:
    canvas = [
        [[DEFAULT_COLOR[0], DEFAULT_COLOR[1], DEFAULT_COLOR[2]] for _ in range(CANVAS_SIZE)]
        for _ in range(CANVAS_SIZE)
    ]
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT x, y, r, g, b FROM pixels")
    for row in cur.fetchall():
        canvas[row["y"]][row["x"]] = [row["r"], row["g"], row["b"]]
    conn.close()
    return canvas


def load_heatmap() -> list[list[int]]:
    heatmap = [[0 for _ in range(CANVAS_SIZE)] for _ in range(CANVAS_SIZE)]
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT x, y, COUNT(*) AS cnt FROM placements GROUP BY x, y")
    for row in cur.fetchall():
        heatmap[row["y"]][row["x"]] = row["cnt"]
    conn.close()
    return heatmap


def load_player_stats() -> dict:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            pl.player_id,
            COALESCE(pl.display_name, pl.player_id) AS display_name,
            COALESCE(COUNT(p.id), 0) AS placements,
            COALESCE(COUNT(DISTINCT CAST(p.x AS TEXT) || ':' || CAST(p.y AS TEXT)), 0) AS unique_pixels,
            MIN(p.placed_at) AS first_placement,
            MAX(p.placed_at) AS last_placement,
            (
                SELECT p2.x
                FROM placements p2
                WHERE p2.player_id = pl.player_id
                ORDER BY p2.placed_at DESC
                LIMIT 1
            ) AS last_x,
            (
                SELECT p2.y
                FROM placements p2
                WHERE p2.player_id = pl.player_id
                ORDER BY p2.placed_at DESC
                LIMIT 1
            ) AS last_y,
            a.id AS alliance_id,
            a.name AS alliance_name
        FROM players pl
        LEFT JOIN placements p ON p.player_id = pl.player_id
        LEFT JOIN alliance_members am ON am.player_id = pl.player_id
        LEFT JOIN alliances a ON a.id = am.alliance_id
        GROUP BY pl.player_id, pl.display_name, a.id, a.name
        ORDER BY pl.player_id ASC
        """
    )
    players = [dict(row) for row in cur.fetchall()]

    cur.execute("SELECT COUNT(*) AS n FROM placements")
    total_placements = cur.fetchone()["n"]

    cur.execute("SELECT COUNT(*) AS n FROM players")
    total_players = cur.fetchone()["n"]

    since_24h = time.time() - 86400
    cur.execute(
        "SELECT COUNT(DISTINCT player_id) AS n FROM placements WHERE placed_at >= ?",
        (since_24h,),
    )
    active_players_24h = cur.fetchone()["n"]

    conn.close()
    return {
        "total_placements": total_placements,
        "total_players": total_players,
        "active_players_24h": active_players_24h,
        "cooldown_seconds": _cooldown_seconds(),
        "players": players,
    }


def load_alliances() -> list[dict]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.id, a.name, a.created_by, a.created_at, COUNT(am.player_id) AS member_count
        FROM alliances a
        LEFT JOIN alliance_members am ON am.alliance_id = a.id
        GROUP BY a.id, a.name, a.created_by, a.created_at
        ORDER BY a.name ASC
        """
    )
    alliances = []
    for row in cur.fetchall():
        cur.execute(
            """
            SELECT p.player_id, COALESCE(p.display_name, p.player_id) AS display_name
            FROM alliance_members am
            JOIN players p ON p.player_id = am.player_id
            WHERE am.alliance_id = ?
            ORDER BY p.player_id ASC
            """,
            (row["id"],),
        )
        members = [dict(m) for m in cur.fetchall()]
        alliance = dict(row)
        alliance["members"] = members
        alliances.append(alliance)
    conn.close()
    return alliances


def load_event_log(
    conn: sqlite3.Connection,
    limit: int = 200,
    event_type: str | None = None,
    player_id: str | None = None,
    start_ts: float | None = None,
    end_ts: float | None = None,
) -> list[dict]:
    cur = conn.cursor()
    query = "SELECT id, event_type, player_id, payload, details, source, created_at FROM event_log WHERE 1=1"
    params: list = []
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if player_id:
        query += " AND player_id = ?"
        params.append(player_id)
    if start_ts is not None:
        query += " AND created_at >= ?"
        params.append(start_ts)
    if end_ts is not None:
        query += " AND created_at <= ?"
        params.append(end_ts)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = []
    for row in cur.fetchall():
        item = dict(row)
        item["payload"] = json.loads(item.get("payload") or "{}")
        rows.append(item)
    return rows


app = FastAPI(title="RoboPlace Server")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "server", "cooldown_seconds": _cooldown_seconds()}


@app.get("/api/canvas")
def get_canvas() -> dict:
    return {"size": CANVAS_SIZE, "pixels": load_canvas()}


def _paint_with_secret(req: PaintPixelRequest, x_roboplace_secret: str | None) -> dict:
    _require_secret(x_roboplace_secret)
    conn = _connect()
    try:
        ensure_player(conn, req.player_id)
        remaining = get_remaining_cooldown(conn, req.player_id)
        if remaining > 0:
            _log_event(
                conn,
                "cooldown_rejected",
                req.player_id,
                {"x": req.x, "y": req.y, "remaining_seconds": round(remaining, 3)},
                "cooldown_active",
                req.source,
            )
            conn.commit()
            conn.close()
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "cooldown_active",
                    "remaining_seconds": round(remaining, 3),
                    "cooldown_seconds": _cooldown_seconds(),
                },
            )
        store_paint(conn, req)
        mark_painted_now(conn, req.player_id)
        conn.commit()
    except HTTPException:
        if conn.in_transaction:
            conn.rollback()
        conn.close()
        raise
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    conn.close()
    return {"status": "stored", "cooldown_seconds": _cooldown_seconds()}


@app.post("/api/paint")
def paint_pixel(req: PaintPixelRequest, x_roboplace_secret: str | None = Header(default=None)) -> dict:
    return _paint_with_secret(req, x_roboplace_secret)


@app.post("/api/place")
def place_pixel(req: PaintPixelRequest, x_roboplace_secret: str | None = Header(default=None)) -> dict:
    return _paint_with_secret(req, x_roboplace_secret)


@app.get("/api/cooldown/{player_id}")
def get_cooldown(player_id: str) -> dict:
    conn = _connect()
    ensure_player(conn, player_id)
    remaining = get_remaining_cooldown(conn, player_id)
    conn.commit()
    conn.close()
    return {
        "player_id": player_id,
        "cooldown_seconds": _cooldown_seconds(),
        "remaining_seconds": round(remaining, 3),
        "can_paint": remaining <= 0,
    }


@app.post("/api/command")
def run_command(req: CommandRequest, x_roboplace_secret: str | None = Header(default=None)) -> dict:
    _require_secret(x_roboplace_secret)
    return execute_command(req)


@app.get("/api/heatmap")
def get_heatmap() -> dict:
    return {"size": CANVAS_SIZE, "heatmap": load_heatmap()}


@app.get("/api/stats")
def get_stats() -> dict:
    return load_player_stats()


@app.get("/api/alliances")
def get_alliances() -> dict:
    return {"alliances": load_alliances()}


@app.get("/api/logs")
def get_logs(
    limit: int = 200,
    event_type: str | None = None,
    player_id: str | None = None,
    start_ts: str | None = None,
    end_ts: str | None = None,
) -> dict:
    def _parse_ts(raw: str | None) -> float | None:
        if raw is None:
            return None
        raw = raw.strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid timestamp; expected unix seconds")
        return value

    conn = _connect()
    try:
        rows = load_event_log(
            conn,
            limit=limit,
            event_type=(event_type or "").strip() or None,
            player_id=(player_id or "").strip() or None,
            start_ts=_parse_ts(start_ts),
            end_ts=_parse_ts(end_ts),
        )
    finally:
        conn.close()
    return {"logs": rows}
