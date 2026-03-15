"""
NEURON — FastAPI Application
Main web server that bridges the brain data pipeline to the React frontend.
"""

from __future__ import annotations

import asyncio
import os
import socket
import yaml
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from web import db
from web.session_manager import SessionManager
from web.claude_client import create_claude_client
from web.media_generators import ImagenGenerator, ElevenLabsMusicGenerator
from web.ws import brain_websocket
from web.routes import users, sessions, experiments, generate, gallery


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Load .env file
    load_dotenv()

    # Load config
    config = load_config()
    app.state.config = config

    # Wait for Muse headband connection before launching anything else
    conn_cfg = config.get("connection", {})
    source = conn_cfg.get("source", "osc")
    osc_host = conn_cfg.get("osc", {}).get("host", "0.0.0.0")
    osc_port = conn_cfg.get("osc", {}).get("port", 5000)

    print(f"[NEURON] Waiting for Muse data stream on {source} ({osc_host}:{osc_port})...")
    print(f"[NEURON] Open Mind Monitor → Settings → OSC Stream Target IP → this machine's IP, port {osc_port}")
    print(f"[NEURON] Tap 'Stream' in Mind Monitor to begin.")

    # Listen with a raw UDP socket — doesn't hold the port after closing
    def _wait_for_udp_packet(host: str, port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind((host, port))
        sock.recv(1024)  # Block until any UDP packet arrives
        sock.close()

    await asyncio.get_event_loop().run_in_executor(
        None, _wait_for_udp_packet, osc_host, osc_port
    )

    print(f"[NEURON] Muse data stream detected! Starting up...")

    # Initialize database
    db.init_db()

    # Initialize session manager
    session_manager = SessionManager(config)
    app.state.session_manager = session_manager

    # Initialize Claude client (API or Agent SDK backend based on config)
    claude_client = create_claude_client(config)
    app.state.claude_client = claude_client

    # Initialize Nano Banana 2 client (for AI image generation)
    image_gen_cfg = config.get("image_gen", {})
    app.state.imagen_client = ImagenGenerator(
        api_key=os.environ.get("GEMINI_API_KEY"),
        model=image_gen_cfg.get("model", "gemini-3.1-flash-image-preview"),
    )

    # Initialize ElevenLabs client (for AI music generation)
    el_cfg = config.get("elevenlabs", {})
    app.state.elevenlabs_client = ElevenLabsMusicGenerator(
        api_key=os.environ.get("ELEVENLABS_API_KEY"),
        model_id=el_cfg.get("model_id", "music_v1"),
        default_duration_ms=el_cfg.get("default_duration_ms", 30000),
        force_instrumental=el_cfg.get("force_instrumental", True),
        output_format=el_cfg.get("output_format", "mp3_44100_128"),
    )

    # Log which backends are active
    backend_type = config.get("claude", {}).get("backend", "api")
    print(f"[NEURON] Claude backend: {backend_type}")
    print(f"[NEURON] Nano Banana 2: {'ready' if app.state.imagen_client.available else 'no GEMINI_API_KEY'}")
    print(f"[NEURON] ElevenLabs: {'ready' if app.state.elevenlabs_client.available else 'no ELEVENLABS_API_KEY'}")

    # Start background broadcast loop
    broadcast_task = asyncio.create_task(session_manager.broadcast_loop())

    yield

    # Cleanup
    broadcast_task.cancel()
    session_manager.stop_session()


app = FastAPI(
    title="NEURON",
    description="Brain-Computer Interface — EEG to Creative Artifacts via Claude",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(users.router)
app.include_router(sessions.router)
app.include_router(experiments.router)
app.include_router(generate.router)
app.include_router(gallery.router)

# Serve generated output files
outputs_dir = Path("outputs")
outputs_dir.mkdir(exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")


# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await brain_websocket(websocket, user_id, app.state.session_manager)


@app.get("/api/health")
async def health():
    session_mgr = app.state.session_manager
    return {
        "status": "ok",
        "service": "neuron",
        "claude_backend": app.state.config.get("claude", {}).get("backend", "api"),
        "imagen_available": app.state.imagen_client.available,
        "elevenlabs_available": app.state.elevenlabs_client.available,
        "active_session": session_mgr.active_session is not None,
    }
