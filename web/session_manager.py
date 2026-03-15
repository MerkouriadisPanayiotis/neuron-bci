"""
NEURON — Brain Session Manager
Manages the lifecycle of active brain data sessions.
Wraps existing core/ingest.py and core/collector.py.
Enforces one active headband session at a time.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from fastapi import WebSocket

from core.ingest import create_ingestor, OSCIngestor, LSLIngestor
from core.collector import DataCollector, BrainSnapshot


class BrainSession:
    """An active brain data streaming session for one user."""

    def __init__(self, user_id: str, session_id: str, source: str, config: dict):
        self.user_id = user_id
        self.session_id = session_id
        self.source = source
        self.ingestor = create_ingestor(source, config)
        self.collector = DataCollector(
            window_seconds=config.get("signal", {}).get("window_size", 2.0),
            history_length=config.get("collector", {}).get("history_length", 10),
        )
        self.websocket_clients: set[WebSocket] = set()
        self.is_generating = False
        self.last_generation_time: float = 0
        self.snapshot_count = 0
        self.generation_count = 0
        self._latest_snapshot: Optional[BrainSnapshot] = None
        self._running = False

    def start(self):
        """Start the data ingestor."""
        self.ingestor.start()
        self._running = True

    def stop(self):
        """Stop the data ingestor."""
        self._running = False
        self.ingestor.stop()

    @property
    def is_active(self) -> bool:
        return self._running

    def capture_snapshot(self) -> BrainSnapshot:
        """Capture a snapshot from the ingestor. Thin wrapper — no interpretation."""
        snap = self.collector.capture(self.ingestor)
        self._latest_snapshot = snap
        self.snapshot_count += 1
        return snap

    @property
    def latest_snapshot(self) -> Optional[BrainSnapshot]:
        return self._latest_snapshot

    def snapshot_to_dict(self, snap: BrainSnapshot) -> dict:
        """Convert a BrainSnapshot to a JSON-serializable dict for WebSocket.
        Pure data conversion — no interpretation."""
        trend = {}
        if snap.band_history:
            for band in ["delta", "theta", "alpha", "beta", "gamma"]:
                trend[band] = [h.get(band, 0) for h in snap.band_history]

        return {
            "type": "brain_data",
            "signal_quality": snap.signal_quality_pct,
            "bands": snap.bands_average,
            "horseshoe": snap.horseshoe,
            "trend": trend,
            "accelerometer": snap.accelerometer,
            "snapshot_number": snap.snapshot_number,
            "session_duration": snap.session_duration_seconds,
            "touching_forehead": snap.touching_forehead,
        }

    async def broadcast(self, data: dict):
        """Broadcast data to all connected WebSocket clients."""
        disconnected = set()
        for ws in self.websocket_clients:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)
        self.websocket_clients -= disconnected


class SessionManager:
    """Manages active brain sessions. One active session at a time."""

    def __init__(self, config: dict):
        self.config = config
        self._active_session: Optional[BrainSession] = None
        self._broadcast_task: Optional[asyncio.Task] = None

    @property
    def active_session(self) -> Optional[BrainSession]:
        return self._active_session

    def start_session(self, user_id: str, session_id: str, source: str = "osc") -> BrainSession:
        """Start a new brain session. Stops any existing session first."""
        if self._active_session:
            self.stop_session()

        session = BrainSession(user_id, session_id, source, self.config)
        session.start()
        self._active_session = session
        return session

    def stop_session(self) -> Optional[tuple[int, int]]:
        """Stop the active session. Returns (snapshot_count, generation_count)."""
        if not self._active_session:
            return None
        session = self._active_session
        session.stop()
        counts = (session.snapshot_count, session.generation_count)
        self._active_session = None
        return counts

    def get_session_for_user(self, user_id: str) -> Optional[BrainSession]:
        """Get the active session if it belongs to this user."""
        if self._active_session and self._active_session.user_id == user_id:
            return self._active_session
        return None

    async def broadcast_loop(self):
        """Background loop that captures snapshots and broadcasts to WebSocket clients."""
        while True:
            if self._active_session and self._active_session.is_active:
                try:
                    snap = self._active_session.capture_snapshot()
                    data = self._active_session.snapshot_to_dict(snap)
                    await self._active_session.broadcast(data)
                except Exception:
                    pass  # Don't crash the loop on transient errors
            await asyncio.sleep(0.5)  # 2Hz
