"""NEURON — Brain Session API Routes."""

from fastapi import APIRouter, HTTPException, Request

from web import db
from web.models import SessionStart, SessionStatus

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("/{user_id}/start", response_model=SessionStatus)
async def start_session(user_id: str, body: SessionStart, request: Request):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session_manager = request.app.state.session_manager

    # Create DB record
    db_session = db.create_brain_session(user_id=user_id, source=body.source)

    # Start the live session
    brain_session = session_manager.start_session(
        user_id=user_id,
        session_id=db_session["id"],
        source=body.source,
    )

    return SessionStatus(
        id=db_session["id"],
        user_id=user_id,
        active=brain_session.is_active,
        source=body.source,
        snapshot_count=0,
        generation_count=0,
    )


@router.post("/{user_id}/stop")
async def stop_session(user_id: str, request: Request):
    session_manager = request.app.state.session_manager
    session = session_manager.get_session_for_user(user_id)

    if not session:
        raise HTTPException(status_code=404, detail="No active session for this user")

    session_id = session.session_id
    counts = session_manager.stop_session()

    if counts:
        db.end_brain_session(session_id, snapshot_count=counts[0], generation_count=counts[1])

    return {"status": "stopped", "session_id": session_id}


@router.get("/{user_id}/status", response_model=SessionStatus)
async def get_session_status(user_id: str, request: Request):
    session_manager = request.app.state.session_manager
    session = session_manager.get_session_for_user(user_id)

    if not session:
        return SessionStatus(
            id="",
            user_id=user_id,
            active=False,
            source="osc",
            snapshot_count=0,
            generation_count=0,
        )

    signal_quality = 0.0
    if session.latest_snapshot:
        signal_quality = session.latest_snapshot.signal_quality_pct

    return SessionStatus(
        id=session.session_id,
        user_id=user_id,
        active=session.is_active,
        source=session.source,
        snapshot_count=session.snapshot_count,
        generation_count=session.generation_count,
        signal_quality=signal_quality,
    )
