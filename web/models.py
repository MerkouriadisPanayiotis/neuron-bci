"""
NEURON — Pydantic Models
Request/response validation for the web API.
"""

from pydantic import BaseModel
from typing import Any, Optional, Dict, List


# ─── Users ──────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    avatar_color: str = "#6366f1"


class UserResponse(BaseModel):
    id: str
    name: str
    created_at: str
    avatar_color: str
    preferences: str
    has_profile: bool = False
    learning_phase: int = 0
    confidence: dict = {}


# ─── Sessions ──────────────────────────────────────────────

class SessionStart(BaseModel):
    source: str = "osc"


class SessionStatus(BaseModel):
    id: str
    user_id: str
    active: bool
    source: str
    snapshot_count: int
    generation_count: int
    signal_quality: float = 0.0


# ─── Experiments ───────────────────────────────────────────

class ExperimentStart(BaseModel):
    phase: int = 1


class ExperimentTaskResult(BaseModel):
    task_id: str
    snapshots: List[str] = []
    snapshot_stats: dict = {}


class ExperimentResponse(BaseModel):
    id: str
    user_id: str
    phase: int
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_task: Optional[dict] = None
    all_tasks: Optional[List[dict]] = None
    total_tasks: int = 0
    completed_tasks: int = 0


# ─── Generation ────────────────────────────────────────────

class GenerationRequest(BaseModel):
    mode: str = "auto"


class GenerationDecision(BaseModel):
    """Structured JSON output from Claude's brain interpretation."""
    mode: str                          # code, art, music
    interpretation: str                # Brain state interpretation
    prompt: str                        # Creative prompt or code content
    parameters: Dict[str, Any] = {}    # Mode-specific params


class OutputResponse(BaseModel):
    id: str
    user_id: str
    file_path: str
    file_type: str
    detected_mode: str
    neuron_header: str
    media_type: str = "text/plain"
    created_at: str


# ─── Brain Data (WebSocket frames) ─────────────────────────

class BrainDataFrame(BaseModel):
    type: str = "brain_data"
    signal_quality: float
    bands: Dict[str, float]
    horseshoe: List[float]
    trend: Dict[str, List[float]]
    accelerometer: dict = {}
    snapshot_number: int
    session_duration: float
