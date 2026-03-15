"""
NEURON — SQLite Database Layer
Schema, migrations, and CRUD functions for users, experiments, outputs, and sessions.
"""

from __future__ import annotations

import sqlite3
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent.parent / "data" / "neuron.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            avatar_color TEXT DEFAULT '#6366f1',
            preferences TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS calibrations (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            phase_data TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS neural_profiles (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE UNIQUE,
            learning_phase INTEGER DEFAULT 0,
            domain_baselines TEXT DEFAULT '{}',
            claude_observations TEXT DEFAULT '[]',
            discrimination_summary TEXT DEFAULT '',
            confidence TEXT DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            phase INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            results TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS experiment_tasks (
            id TEXT PRIMARY KEY,
            experiment_id TEXT REFERENCES experiments(id) ON DELETE CASCADE,
            task_order INTEGER,
            task_type TEXT,
            instruction TEXT,
            duration_seconds INTEGER DEFAULT 60,
            snapshots TEXT DEFAULT '[]',
            snapshot_stats TEXT DEFAULT '{}',
            interpretation TEXT DEFAULT '',
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS outputs (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            file_type TEXT,
            detected_mode TEXT,
            neuron_header TEXT,
            neural_summary TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS brain_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
            source TEXT DEFAULT 'osc',
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            snapshot_count INTEGER DEFAULT 0,
            generation_count INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


def _gen_id() -> str:
    return str(uuid.uuid4())


# ─── Users ──────────────────────────────────────────────────

def create_user(name: str, avatar_color: str = "#6366f1") -> dict:
    conn = get_connection()
    user_id = _gen_id()
    conn.execute(
        "INSERT INTO users (id, name, avatar_color) VALUES (?, ?, ?)",
        (user_id, name, avatar_color),
    )
    conn.commit()
    user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    conn.close()
    return user


def get_user(user_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_users() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_user(user_id: str):
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# ─── Neural Profiles ───────────────────────────────────────

def get_neural_profile(user_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM neural_profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        result = dict(row)
        result["domain_baselines"] = json.loads(result["domain_baselines"])
        result["claude_observations"] = json.loads(result["claude_observations"])
        result["confidence"] = json.loads(result["confidence"])
        return result
    return None


def upsert_neural_profile(user_id: str, **kwargs) -> dict:
    conn = get_connection()
    existing = conn.execute("SELECT id FROM neural_profiles WHERE user_id = ?", (user_id,)).fetchone()

    # Serialize JSON fields
    for key in ("domain_baselines", "claude_observations", "confidence"):
        if key in kwargs and not isinstance(kwargs[key], str):
            kwargs[key] = json.dumps(kwargs[key])

    kwargs["updated_at"] = datetime.utcnow().isoformat()

    if existing:
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        conn.execute(f"UPDATE neural_profiles SET {sets} WHERE user_id = ?", vals)
    else:
        profile_id = _gen_id()
        kwargs["id"] = profile_id
        kwargs["user_id"] = user_id
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        conn.execute(f"INSERT INTO neural_profiles ({cols}) VALUES ({placeholders})", list(kwargs.values()))

    conn.commit()
    result = get_neural_profile(user_id)
    conn.close()
    return result


# ─── Experiments ────────────────────────────────────────────

def create_experiment(user_id: str, phase: int = 1) -> dict:
    conn = get_connection()
    exp_id = _gen_id()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO experiments (id, user_id, phase, status, started_at) VALUES (?, ?, ?, 'active', ?)",
        (exp_id, user_id, phase, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM experiments WHERE id = ?", (exp_id,)).fetchone()
    conn.close()
    return dict(row)


def get_experiment(experiment_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_experiment(user_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM experiments WHERE user_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_experiment(experiment_id: str, **kwargs) -> dict:
    conn = get_connection()
    if "results" in kwargs and not isinstance(kwargs["results"], str):
        kwargs["results"] = json.dumps(kwargs["results"])
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [experiment_id]
    conn.execute(f"UPDATE experiments SET {sets} WHERE id = ?", vals)
    conn.commit()
    row = conn.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    conn.close()
    return dict(row)


def list_experiments(user_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM experiments WHERE user_id = ? ORDER BY started_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Experiment Tasks ───────────────────────────────────────

def create_experiment_task(experiment_id: str, task_order: int, task_type: str,
                           instruction: str, duration_seconds: int = 60) -> dict:
    conn = get_connection()
    task_id = _gen_id()
    conn.execute(
        """INSERT INTO experiment_tasks (id, experiment_id, task_order, task_type, instruction, duration_seconds)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (task_id, experiment_id, task_order, task_type, instruction, duration_seconds),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM experiment_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row)


def update_experiment_task(task_id: str, **kwargs) -> dict:
    conn = get_connection()
    for key in ("snapshots", "snapshot_stats"):
        if key in kwargs and not isinstance(kwargs[key], str):
            kwargs[key] = json.dumps(kwargs[key])
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [task_id]
    conn.execute(f"UPDATE experiment_tasks SET {sets} WHERE id = ?", vals)
    conn.commit()
    row = conn.execute("SELECT * FROM experiment_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row)


def get_experiment_tasks(experiment_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM experiment_tasks WHERE experiment_id = ? ORDER BY task_order",
        (experiment_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Outputs ───────────────────────────────────────────────

def create_output(user_id: str, file_path: str, file_type: str, detected_mode: str,
                  neuron_header: str = "", neural_summary: Optional[dict] = None) -> dict:
    conn = get_connection()
    output_id = _gen_id()
    conn.execute(
        """INSERT INTO outputs (id, user_id, file_path, file_type, detected_mode, neuron_header, neural_summary)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (output_id, user_id, file_path, file_type, detected_mode, neuron_header,
         json.dumps(neural_summary or {})),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM outputs WHERE id = ?", (output_id,)).fetchone()
    conn.close()
    return dict(row)


def list_outputs(user_id: str, mode: Optional[str] = None, limit: int = 50) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM outputs WHERE user_id = ?"
    params: list = [user_id]
    if mode:
        query += " AND detected_mode = ?"
        params.append(mode)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_output(output_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM outputs WHERE id = ?", (output_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Brain Sessions ────────────────────────────────────────

def create_brain_session(user_id: str, source: str = "osc") -> dict:
    conn = get_connection()
    session_id = _gen_id()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO brain_sessions (id, user_id, source, started_at) VALUES (?, ?, ?, ?)",
        (session_id, user_id, source, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM brain_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row)


def end_brain_session(session_id: str, snapshot_count: int = 0, generation_count: int = 0):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE brain_sessions SET ended_at = ?, snapshot_count = ?, generation_count = ? WHERE id = ?",
        (now, snapshot_count, generation_count, session_id),
    )
    conn.commit()
    conn.close()
