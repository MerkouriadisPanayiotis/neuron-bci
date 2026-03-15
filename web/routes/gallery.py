"""NEURON — Gallery API Routes."""

from __future__ import annotations

import os

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from web import db

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


@router.get("/{user_id}")
async def list_gallery(user_id: str, mode: Optional[str] = None, limit: int = 50):
    """List generated outputs for a user, optionally filtered by mode."""
    outputs = db.list_outputs(user_id, mode=mode, limit=limit)
    return outputs


@router.get("/{user_id}/{output_id}")
async def get_output_meta(user_id: str, output_id: str):
    """Get metadata for a specific output."""
    output = db.get_output(output_id)
    if not output or output["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Output not found")
    return output


@router.get("/{user_id}/{output_id}/file")
async def serve_output_file(user_id: str, output_id: str):
    """Serve the actual generated file."""
    output = db.get_output(output_id)
    if not output or output["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Output not found")

    file_path = output["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    media_types = {
        "py": "text/plain",
        "html": "text/html",
        "svg": "image/svg+xml",
        "png": "image/png",
        "jpg": "image/jpeg",
        "mp3": "audio/mpeg",
        "txt": "text/plain",
    }
    media_type = media_types.get(output.get("file_type", ""), "text/plain")

    return FileResponse(file_path, media_type=media_type)
