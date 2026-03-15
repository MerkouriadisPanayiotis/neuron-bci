"""
NEURON — Brain Learning Experiment Engine
Manages neural profiles and experiment sessions.
Collects and aggregates data (numpy only) — all interpretation is Claude's job.
"""

from __future__ import annotations

import json
import time
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.collector import BrainSnapshot, DataCollector


@dataclass
class ExperimentTrial:
    """One trial's worth of collected neural data."""
    task_type: str  # 'neutral', 'coding', 'art', 'music'
    instruction: str
    duration_seconds: int
    snapshots: list[str] = field(default_factory=list)  # to_prompt_block() outputs
    snapshot_stats: dict = field(default_factory=dict)  # Aggregated band stats
    interpretation: str = ""  # Claude's interpretation (filled after Claude call)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class NeuralProfile:
    """
    A user's learned neural profile.
    Stores raw aggregated stats (numpy) and Claude's natural language observations.
    All interpretation is in Claude's words — this class only manages data.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.learning_phase: int = 0
        self.domain_baselines: dict = {}  # {coding: {band: {mean, std}}, art: {...}, music: {...}}
        self.claude_observations: list[dict] = []
        self.discrimination_summary: str = ""
        self.confidence: dict = {}  # {coding: 0.85, art: 0.74, music: 0.78}

    def add_trial_stats(self, task_type: str, band_stats: dict):
        """Add a trial's aggregated band stats to the domain baseline.
        Pure numpy aggregation — no interpretation.
        """
        if task_type not in ("coding", "art", "music"):
            return

        if task_type not in self.domain_baselines:
            self.domain_baselines[task_type] = {}

        existing = self.domain_baselines[task_type]
        for band, new_stats in band_stats.items():
            if band not in existing:
                existing[band] = {"values": []}

            if isinstance(new_stats, dict) and "mean" in new_stats:
                existing[band]["values"] = existing[band].get("values", []) + [new_stats["mean"]]
            elif isinstance(new_stats, (int, float)):
                existing[band]["values"] = existing[band].get("values", []) + [new_stats]

        # Recompute aggregate stats
        for band in existing:
            vals = existing[band].get("values", [])
            if vals:
                arr = np.array(vals)
                existing[band]["mean"] = float(np.mean(arr))
                existing[band]["std"] = float(np.std(arr))
                existing[band]["min"] = float(np.min(arr))
                existing[band]["max"] = float(np.max(arr))

    def add_observation(self, task_type: str, observation: str):
        """Store one of Claude's observations."""
        self.claude_observations.append({
            "task_type": task_type,
            "observation": observation,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def to_live_context(self) -> str:
        """Build compact profile context for live generation prompts (~300 tokens).
        This is the key data that feeds into build_user_prompt().
        """
        if not self.discrimination_summary and not self.domain_baselines:
            return ""

        lines = [f"--- NEURAL PROFILE ---"]
        lines.append(f"Learning phase: {self.learning_phase}")

        if self.confidence:
            parts = [f"{k.title()} {v:.2f}" for k, v in self.confidence.items()]
            lines.append(f"Confidence: {' | '.join(parts)}")

        if self.domain_baselines:
            lines.append("\nDomain signatures:")
            for domain, bands in self.domain_baselines.items():
                parts = []
                for band, stats in bands.items():
                    if isinstance(stats, dict) and "mean" in stats:
                        parts.append(f"{band}={stats['mean']:+.3f}")
                if parts:
                    lines.append(f"  {domain.title()}: {', '.join(parts)}")

        if self.discrimination_summary:
            lines.append(f"\nDiscrimination key:\n\"{self.discrimination_summary}\"")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize for storage."""
        # Strip 'values' arrays from baselines for clean storage
        clean_baselines = {}
        for domain, bands in self.domain_baselines.items():
            clean_baselines[domain] = {}
            for band, stats in bands.items():
                if isinstance(stats, dict):
                    clean_baselines[domain][band] = {
                        k: v for k, v in stats.items() if k != "values"
                    }

        return {
            "user_id": self.user_id,
            "learning_phase": self.learning_phase,
            "domain_baselines": clean_baselines,
            "claude_observations": self.claude_observations,
            "discrimination_summary": self.discrimination_summary,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NeuralProfile":
        """Deserialize from storage."""
        profile = cls(user_id=data.get("user_id", ""))
        profile.learning_phase = data.get("learning_phase", 0)
        profile.domain_baselines = data.get("domain_baselines", {})
        profile.claude_observations = data.get("claude_observations", [])
        profile.discrimination_summary = data.get("discrimination_summary", "")
        profile.confidence = data.get("confidence", {})
        return profile


class ExperimentSession:
    """
    Manages a single learning experiment session.
    Collects snapshots during trial windows and formats them for Claude.
    No interpretation — just data collection and formatting.
    """

    def __init__(self, user_id: str, phase: int = 1):
        self.user_id = user_id
        self.phase = phase
        self.trials: list[ExperimentTrial] = []
        self._current_trial: Optional[ExperimentTrial] = None
        self._trial_snapshots: list[BrainSnapshot] = []

    def start_trial(self, task_type: str, instruction: str, duration_seconds: int):
        """Begin a new trial. Resets snapshot collection."""
        self._current_trial = ExperimentTrial(
            task_type=task_type,
            instruction=instruction,
            duration_seconds=duration_seconds,
            started_at=datetime.utcnow().isoformat(),
        )
        self._trial_snapshots = []

    def record_snapshot(self, snap: BrainSnapshot):
        """Record a snapshot during the current trial."""
        if self._current_trial:
            self._trial_snapshots.append(snap)
            self._current_trial.snapshots.append(snap.to_prompt_block())

    def end_trial(self) -> Optional[ExperimentTrial]:
        """End the current trial and compute aggregate stats (numpy only)."""
        if not self._current_trial:
            return None

        trial = self._current_trial
        trial.completed_at = datetime.utcnow().isoformat()

        # Aggregate band stats across all snapshots in this trial
        band_values: dict[str, list[float]] = {}
        for snap in self._trial_snapshots:
            for band, val in snap.bands_average.items():
                if band not in band_values:
                    band_values[band] = []
                band_values[band].append(val)

        for band, vals in band_values.items():
            arr = np.array(vals)
            trial.snapshot_stats[band] = {
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "samples": len(vals),
            }

        self.trials.append(trial)
        self._current_trial = None
        self._trial_snapshots = []
        return trial
