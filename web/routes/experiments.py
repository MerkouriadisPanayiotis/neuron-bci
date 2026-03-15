"""NEURON — Brain Learning Experiment API Routes."""

from __future__ import annotations

import json
import time
import asyncio
import numpy as np
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Request

from web import db
from web.models import ExperimentStart, ExperimentResponse

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.post("/{user_id}/start", response_model=ExperimentResponse)
async def start_experiment(user_id: str, body: ExperimentStart, request: Request):
    """Start a new brain learning experiment for a user."""
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for active session
    session_manager = request.app.state.session_manager
    session = session_manager.get_session_for_user(user_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active brain session. Start a session first.")

    # Cancel any stale active experiment so we can start fresh
    active = db.get_active_experiment(user_id)
    if active:
        db.update_experiment(
            active["id"],
            status="cancelled",
            completed_at=datetime.utcnow().isoformat(),
        )

    # Create experiment
    experiment = db.create_experiment(user_id=user_id, phase=body.phase)

    # Ask Claude to design the experiment tasks
    claude = request.app.state.claude_client
    profile = db.get_neural_profile(user_id)

    calibration_context = ""
    # TODO: Load calibration from DB if available

    tasks = await claude.experiment_design_tasks(
        user_name=user["name"],
        phase=body.phase,
        existing_profile=profile,
        calibration_context=calibration_context,
    )

    # Create task records
    for i, task in enumerate(tasks):
        db.create_experiment_task(
            experiment_id=experiment["id"],
            task_order=i,
            task_type=task["task_type"],
            instruction=task["instruction"],
            duration_seconds=task.get("duration_seconds", 60),
        )

    all_tasks = db.get_experiment_tasks(experiment["id"])

    # Notify via WebSocket
    if session:
        await session.broadcast({
            "type": "experiment_started",
            "experiment_id": experiment["id"],
            "total_tasks": len(all_tasks),
            "first_task": all_tasks[0] if all_tasks else None,
            "all_tasks": all_tasks,
        })

    return ExperimentResponse(
        id=experiment["id"],
        user_id=user_id,
        phase=body.phase,
        status="active",
        started_at=experiment["started_at"],
        completed_at=None,
        current_task=all_tasks[0] if all_tasks else None,
        all_tasks=all_tasks,
        total_tasks=len(all_tasks),
        completed_tasks=0,
    )


@router.post("/{user_id}/tasks/{task_id}/start")
async def start_task(user_id: str, task_id: str, request: Request):
    """Begin recording brain data for an experiment task."""
    session_manager = request.app.state.session_manager
    session = session_manager.get_session_for_user(user_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active brain session")

    db.update_experiment_task(task_id, started_at=datetime.utcnow().isoformat())

    # Broadcast instruction to client
    tasks = db.get_experiment_tasks(
        db.get_experiment(
            # Get experiment_id from task
            db.get_connection().execute(
                "SELECT experiment_id FROM experiment_tasks WHERE id = ?", (task_id,)
            ).fetchone()["experiment_id"]
        )["id"]
    )
    task = next((t for t in tasks if t["id"] == task_id), None)

    if task and session:
        await session.broadcast({
            "type": "experiment_instruction",
            "task_id": task_id,
            "task_type": task["task_type"],
            "instruction": task["instruction"],
            "duration_seconds": task["duration_seconds"],
        })

    return {"status": "recording", "task_id": task_id}


@router.post("/{user_id}/tasks/{task_id}/complete")
async def complete_task(user_id: str, task_id: str, request: Request):
    """Complete a task: collect snapshots, send to Claude for interpretation."""
    session_manager = request.app.state.session_manager
    session = session_manager.get_session_for_user(user_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active brain session")

    # Get task info
    conn = db.get_connection()
    task_row = conn.execute("SELECT * FROM experiment_tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if not task_row:
        raise HTTPException(status_code=404, detail="Task not found")
    task = dict(task_row)

    # Capture current snapshot as the task's final data point
    snap = session.capture_snapshot()
    snapshot_block = snap.to_prompt_block()

    # Get all snapshots collected during this task (from session history)
    # For now, use the latest snapshot + any recent ones
    snapshots = [snapshot_block]

    # Compute aggregate stats (pure numpy — no interpretation)
    stats = {}
    if snap.bands_average:
        stats = {band: {"mean": val, "std": 0.0} for band, val in snap.bands_average.items()}

    # Update task record
    db.update_experiment_task(
        task_id,
        completed_at=datetime.utcnow().isoformat(),
        snapshots=snapshots,
        snapshot_stats=stats,
    )

    # Send to Claude for interpretation (unless neutral reset)
    interpretation = ""
    if task["task_type"] != "neutral":
        user = db.get_user(user_id)
        claude = request.app.state.claude_client
        profile = db.get_neural_profile(user_id)

        existing_obs = []
        if profile and profile.get("claude_observations"):
            existing_obs = profile["claude_observations"]

        interpretation = await claude.experiment_interpret(
            user_name=user["name"],
            task_type=task["task_type"],
            instruction=task["instruction"],
            snapshot_blocks=snapshots,
            existing_observations=existing_obs,
            calibration_context="",
        )

        db.update_experiment_task(task_id, interpretation=interpretation)

        # Add observation to neural profile
        obs_entry = {
            "task_type": task["task_type"],
            "observation": interpretation,
            "timestamp": datetime.utcnow().isoformat(),
        }
        current_obs = existing_obs + [obs_entry]
        db.upsert_neural_profile(user_id, claude_observations=current_obs)

    # Broadcast interpretation to client
    if session:
        await session.broadcast({
            "type": "experiment_interpretation",
            "task_id": task_id,
            "task_type": task["task_type"],
            "interpretation": interpretation,
        })

    # Check if all tasks are complete
    conn = db.get_connection()
    exp_id = task["experiment_id"]
    all_tasks = db.get_experiment_tasks(exp_id)
    completed_count = sum(1 for t in all_tasks if t["completed_at"])
    conn.close()

    return {
        "status": "completed",
        "task_id": task_id,
        "interpretation": interpretation,
        "completed_tasks": completed_count,
        "total_tasks": len(all_tasks),
    }


@router.post("/{user_id}/experiments/{experiment_id}/finalize")
async def finalize_experiment(user_id: str, experiment_id: str, request: Request):
    """Finalize an experiment: build the discrimination summary."""
    experiment = db.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    user = db.get_user(user_id)
    claude = request.app.state.claude_client
    profile = db.get_neural_profile(user_id)

    observations = profile["claude_observations"] if profile else []

    # Build domain baselines from completed tasks
    tasks = db.get_experiment_tasks(experiment_id)
    domain_baselines = {}
    for task in tasks:
        if task["task_type"] in ("coding", "art", "music") and task["snapshot_stats"]:
            stats = json.loads(task["snapshot_stats"]) if isinstance(task["snapshot_stats"], str) else task["snapshot_stats"]
            if task["task_type"] not in domain_baselines:
                domain_baselines[task["task_type"]] = stats
            else:
                # Merge stats
                existing = domain_baselines[task["task_type"]]
                for band in stats:
                    if band in existing and isinstance(existing[band], dict) and isinstance(stats[band], dict):
                        existing[band]["mean"] = (existing[band].get("mean", 0) + stats[band].get("mean", 0)) / 2

    # Ask Claude to build the discrimination summary
    result = await claude.build_discrimination_summary(
        user_name=user["name"],
        all_observations=observations,
        domain_baselines=domain_baselines,
        calibration_context="",
    )

    # Update neural profile
    new_phase = min((profile["learning_phase"] if profile else 0) + 1, 4)
    db.upsert_neural_profile(
        user_id,
        learning_phase=new_phase,
        domain_baselines=domain_baselines,
        discrimination_summary=result.get("discrimination_summary", ""),
        confidence=result.get("confidence", {}),
    )

    # Mark experiment complete
    db.update_experiment(
        experiment_id,
        status="completed",
        completed_at=datetime.utcnow().isoformat(),
    )

    # Broadcast to client
    session_manager = request.app.state.session_manager
    session = session_manager.get_session_for_user(user_id)
    if session:
        await session.broadcast({
            "type": "experiment_complete",
            "experiment_id": experiment_id,
            "discrimination_summary": result.get("discrimination_summary", ""),
            "confidence": result.get("confidence", {}),
            "learning_phase": new_phase,
        })

    return {
        "status": "completed",
        "discrimination_summary": result.get("discrimination_summary", ""),
        "confidence": result.get("confidence", {}),
        "learning_phase": new_phase,
    }


@router.get("/{user_id}", response_model=List[ExperimentResponse])
async def list_experiments(user_id: str):
    experiments = db.list_experiments(user_id)
    result = []
    for exp in experiments:
        tasks = db.get_experiment_tasks(exp["id"])
        completed_count = sum(1 for t in tasks if t["completed_at"])
        result.append(ExperimentResponse(
            id=exp["id"],
            user_id=user_id,
            phase=exp["phase"],
            status=exp["status"],
            started_at=exp["started_at"],
            completed_at=exp["completed_at"],
            total_tasks=len(tasks),
            completed_tasks=completed_count,
        ))
    return result


@router.get("/{user_id}/profile")
async def get_profile(user_id: str):
    """Get the user's neural profile (learned brain patterns)."""
    profile = db.get_neural_profile(user_id)
    if not profile:
        return {
            "user_id": user_id,
            "learning_phase": 0,
            "domain_baselines": {},
            "discrimination_summary": "",
            "confidence": {},
            "claude_observations": [],
        }
    return profile
