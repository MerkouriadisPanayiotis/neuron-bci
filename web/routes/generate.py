"""NEURON — Generation API Routes.
Two-phase pipeline:
  Phase 1: Claude interprets brain data → structured JSON decision (mode + prompt)
  Phase 2: Route to appropriate backend (code → save, art → Imagen, music → ElevenLabs)
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from web import db
from web.models import GenerationRequest

router = APIRouter(prefix="/api/generate", tags=["generate"])


@router.post("/{user_id}")
async def trigger_generation(user_id: str, body: GenerationRequest, request: Request):
    """Trigger a creative generation from the current brain state."""
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Brain learning must be completed before generation is allowed
    profile = db.get_neural_profile(user_id)
    if not profile or profile.get("learning_phase", 0) < 1:
        raise HTTPException(
            status_code=403,
            detail="Brain learning required. Complete at least one experiment before generating.",
        )

    session_manager = request.app.state.session_manager
    session = session_manager.get_session_for_user(user_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active brain session")

    if session.is_generating:
        raise HTTPException(status_code=409, detail="Generation already in progress")

    snap = session.latest_snapshot
    if not snap or snap.signal_quality_pct < 0.1:
        raise HTTPException(status_code=400, detail="No brain data or signal too weak")

    session.is_generating = True
    await session.broadcast({"type": "generation_started", "mode": body.mode})

    try:
        # Build context
        neural_data_block = snap.to_prompt_block()

        profile_context = _build_profile_context(user["name"], profile)

        recent_outputs = db.list_outputs(user_id, limit=10)
        previous_headers = [o["neuron_header"] for o in recent_outputs if o.get("neuron_header")]

        # ─── Phase 1: Claude interprets brain data → JSON decision ───
        claude = request.app.state.claude_client

        await session.broadcast({"type": "generation_phase", "phase": "interpreting",
                                  "message": "Claude is reading your brain data..."})

        # Try streaming if API backend
        from web.claude_client import NeuronClaudeAPI
        decision = None

        if isinstance(claude, NeuronClaudeAPI):
            # Stream Claude's response for real-time feedback
            full_text = []
            async for chunk in claude.interpret_and_decide_streaming(
                neural_data_block=neural_data_block,
                mode=body.mode,
                calibration_context="",
                profile_context=profile_context,
                previous_outputs=previous_headers,
            ):
                full_text.append(chunk)
                await session.broadcast({"type": "generation_chunk", "text": chunk})

            raw_text = "".join(full_text)
            # Parse JSON from Claude's response
            try:
                from web.claude_client import _parse_json_response
                decision = _parse_json_response(raw_text)
            except (json.JSONDecodeError, ValueError):
                # Fallback: treat as raw code output
                decision = {
                    "mode": "code",
                    "interpretation": "Direct output (JSON parse failed)",
                    "prompt": raw_text,
                    "parameters": {},
                }
        else:
            # CLI backend — no streaming
            decision = await claude.interpret_and_decide(
                neural_data_block=neural_data_block,
                mode=body.mode,
                calibration_context="",
                profile_context=profile_context,
                previous_outputs=previous_headers,
            )

        detected_mode = decision.get("mode", "code")
        interpretation = decision.get("interpretation", "")
        prompt = decision.get("prompt", "")
        parameters = decision.get("parameters", {})

        await session.broadcast({
            "type": "generation_phase",
            "phase": "decided",
            "mode": detected_mode,
            "interpretation": interpretation,
        })

        # ─── Phase 2: Route to appropriate backend ───────────────────

        output_dir = request.app.state.config.get("output", {}).get("base_dir", "./outputs")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        gen_id = f"neuron_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session.generation_count + 1:04d}"

        if detected_mode == "code":
            # Save as self-contained HTML application
            file_type = "html"
            media_type = "text/html"
            file_path = os.path.join(output_dir, f"{gen_id}.html")
            with open(file_path, "w") as f:
                f.write(prompt)

            await session.broadcast({
                "type": "generation_phase", "phase": "saving",
                "message": "Deploying app locally...",
            })

        elif detected_mode == "art":
            # Generate image via Imagen 3
            file_type = "png"
            media_type = "image/png"
            file_path = os.path.join(output_dir, f"{gen_id}.png")

            imagen = request.app.state.imagen_client
            if not imagen or not imagen.available:
                # Fallback: save prompt as text
                file_type = "txt"
                media_type = "text/plain"
                file_path = os.path.join(output_dir, f"{gen_id}_art_prompt.txt")
                with open(file_path, "w") as f:
                    f.write(f"Art Prompt:\n{prompt}\n\nParameters:\n{json.dumps(parameters, indent=2)}")
                await session.broadcast({
                    "type": "generation_phase", "phase": "fallback",
                    "message": "GEMINI_API_KEY not set — saved prompt as text",
                })
            else:
                await session.broadcast({
                    "type": "generation_phase", "phase": "generating_image",
                    "message": "Imagen 3 is creating your image...",
                })
                aspect_ratio = parameters.get("aspect_ratio", "16:9")
                image_bytes = await imagen.generate(prompt=prompt, aspect_ratio=aspect_ratio)
                with open(file_path, "wb") as f:
                    f.write(image_bytes)

        elif detected_mode == "music":
            # Generate music via ElevenLabs
            file_type = "mp3"
            media_type = "audio/mpeg"
            file_path = os.path.join(output_dir, f"{gen_id}.mp3")

            elevenlabs = request.app.state.elevenlabs_client
            if not elevenlabs or not elevenlabs.available:
                # Fallback: save prompt as text
                file_type = "txt"
                media_type = "text/plain"
                file_path = os.path.join(output_dir, f"{gen_id}_music_prompt.txt")
                with open(file_path, "w") as f:
                    f.write(f"Music Prompt:\n{prompt}\n\nParameters:\n{json.dumps(parameters, indent=2)}")
                await session.broadcast({
                    "type": "generation_phase", "phase": "fallback",
                    "message": "ELEVENLABS_API_KEY not set — saved prompt as text",
                })
            else:
                await session.broadcast({
                    "type": "generation_phase", "phase": "generating_music",
                    "message": "ElevenLabs is composing your music...",
                })
                duration_s = parameters.get("duration_seconds", 30)
                duration_ms = int(duration_s * 1000)
                instrumental = parameters.get("instrumental", True)
                mp3_bytes = await elevenlabs.generate(
                    prompt=prompt, duration_ms=duration_ms, instrumental=instrumental)
                with open(file_path, "wb") as f:
                    f.write(mp3_bytes)

        else:
            # Unknown mode — save as text
            file_type = "txt"
            media_type = "text/plain"
            file_path = os.path.join(output_dir, f"{gen_id}.txt")
            with open(file_path, "w") as f:
                f.write(prompt)

        # ─── Save to database ────────────────────────────────────────

        neuron_header = f"NEURON: {interpretation} | mode: {detected_mode}"

        neural_summary = {
            "bands": snap.bands_average,
            "signal_quality": snap.signal_quality_pct,
            "snapshot_number": snap.snapshot_number,
        }

        output_record = db.create_output(
            user_id=user_id,
            file_path=file_path,
            file_type=file_type,
            detected_mode=detected_mode,
            neuron_header=neuron_header,
            neural_summary=neural_summary,
        )

        session.generation_count += 1

        await session.broadcast({
            "type": "generation_complete",
            "output": {
                "id": output_record["id"],
                "file_path": file_path,
                "file_type": file_type,
                "detected_mode": detected_mode,
                "neuron_header": neuron_header,
                "media_type": media_type,
            },
        })

        return {
            "id": output_record["id"],
            "file_type": file_type,
            "detected_mode": detected_mode,
            "neuron_header": neuron_header,
            "interpretation": interpretation,
            "file_path": file_path,
            "media_type": media_type,
        }

    except Exception as e:
        await session.broadcast({"type": "error", "message": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.is_generating = False


def _build_profile_context(user_name: str, profile: dict) -> str:
    """Build profile context for generation prompts — this is Claude's PRIMARY interpretation reference."""
    lines = [f"--- NEURAL PROFILE: {user_name} (PRIMARY INTERPRETATION REFERENCE) ---"]

    phase = profile.get("learning_phase", 0)
    lines.append(f"Learning phase: {phase}/4")

    confidence = profile.get("confidence", {})
    if confidence:
        parts = [f"{k.title()} {v:.2f}" for k, v in confidence.items()]
        lines.append(f"Confidence: {' | '.join(parts)}")

    baselines = profile.get("domain_baselines", {})
    if baselines:
        lines.append("\nDomain baselines (measured during brain learning — compare current snapshot against each):")
        for domain, stats in baselines.items():
            if isinstance(stats, dict):
                parts = []
                for band, vals in stats.items():
                    if isinstance(vals, dict):
                        parts.append(f"{band}={vals.get('mean', 0):+.3f}")
                    elif isinstance(vals, (int, float)):
                        parts.append(f"{band}={vals:+.3f}")
                if parts:
                    lines.append(f"  {domain}: {', '.join(parts)}")
        lines.append("\nTo decide mode: compute sum of |current_band - baseline_band| for each domain. Smallest total distance = best match.")

    summary = profile.get("discrimination_summary", "")
    if summary:
        lines.append(f"\nYOUR DISCRIMINATION KEY (you wrote this during brain learning):")
        lines.append(f'"{summary}"')
        lines.append("\nUse this as your primary guide for interpreting the current brain state.")

    return "\n".join(lines)
