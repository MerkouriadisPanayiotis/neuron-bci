# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Identity

NEURON is an open-source brain-computer interface that connects a Muse S Athena EEG headband to Claude. It first **trains on the user's brain** through structured experiments, building a personal neural profile. Then during live sessions, Claude compares real-time EEG against the trained baselines to interpret what the user is thinking about — and generates creative artifacts (interactive apps, AI art, AI music) based on that interpretation.

The Python layer is intentionally a **thin data pipe** — all signal interpretation, state classification, and creative decision-making happens in the LLM via the system prompt in `core/prompt.py`.

## Architecture Invariant — DO NOT VIOLATE

**Python collects and formats. Claude interprets and creates.**

There must be NO signal processing, NO brain state classification, NO intent mapping, and NO creative decision logic in Python. No scipy. No sklearn. No threshold-based classifiers. No if/else trees that interpret EEG patterns. The Python layer touches raw data only to aggregate it (mean, std, min, max) and format it as structured text for the LLM.

If you're tempted to add a line like `if beta/theta > 2.0: state = "focused"` in Python — stop. That logic belongs in `core/prompt.py` as natural language instruction to the LLM.

## File Responsibilities

```
start.sh             One-command launcher. Creates venv, installs deps,
                     waits for Muse data stream, starts backend + frontend.

config.yaml          Connection settings, timing, output paths, Claude backend
                     selection. NO interpretation thresholds.

core/ingest.py       OSC and LSL data ingestion from Muse Athena via Mind Monitor
                     or Petal Metrics. Ring buffers, wait_for_data() for startup.
                     Two classes: OSCIngestor, LSLIngestor. Factory: create_ingestor().

core/collector.py    BrainSnapshot class captures a point-in-time view of all neural
                     data from the ingestor and formats it as structured text blocks
                     (to_prompt_block()). DataCollector manages windowing and trend
                     history. This is the bridge between raw data and LLM input.

core/prompt.py       THE BRAIN OF THE PROJECT. Contains SYSTEM_PROMPT that teaches
                     Claude how to read EEG using the trained neural profile as
                     primary reference. Also build_user_prompt() and
                     build_profile_context(). All interpretation logic lives here.

core/experiment.py   Experiment session management for brain learning.

web/app.py           FastAPI application. Lifespan waits for Muse connection
                     before starting. Initializes all clients and services.

web/claude_client.py Two Claude backends:
                     - NeuronClaudeAPI: Anthropic SDK (pay-per-token, streaming)
                     - NeuronClaudeAgentSDK: Claude Agent SDK (uses Claude Code auth)
                     Factory: create_claude_client().

web/media_generators.py  ImagenGenerator (Nano Banana 2 / Gemini Flash for images)
                         and ElevenLabsMusicGenerator (for AI music).

web/session_manager.py   BrainSession lifecycle. One active session at a time.
                         Captures snapshots, broadcasts via WebSocket.

web/db.py            SQLite persistence. Users, sessions, experiments, neural
                     profiles, outputs.

web/routes/          API endpoints:
  generate.py        Two-phase generation pipeline. Phase 1: Claude interprets
                     brain data → JSON decision. Phase 2: Route to backend
                     (code→HTML, art→Gemini, music→ElevenLabs).
                     GATED: requires learning_phase >= 1.
  experiments.py     Brain learning experiment flow. Start → design tasks →
                     record → interpret → finalize → build neural profile.
  sessions.py        Start/stop brain data sessions.
  users.py           User CRUD with neural profile data.
  gallery.py         Serve generated output files.

web/ws.py            WebSocket handler for real-time brain data streaming.

frontend/            Next.js React app (port 3000).
  app/dashboard/     Main 3-panel dashboard: brain viz, generation stream, controls.
  app/experiment/    Brain learning experiment flow page.
  app/gallery/       Output gallery.
  app/profile/       Neural profile viewer.
  components/        BrainViz, ExperimentFlow, GenerationStream, etc.
  hooks/             useBrainSocket (WebSocket), useApi.
```

## Data Flow

```
Muse Athena → BLE → Mind Monitor app → OSC UDP :5000
                                            ↓
                                    OSCIngestor (ingest.py)
                                    Ring buffers per channel/band
                                            ↓
                                    DataCollector.capture() (collector.py)
                                    BrainSnapshot with raw stats + trend sparklines
                                            ↓
                                    BrainSnapshot.to_prompt_block()
                                    Structured text: bands, asymmetry, trends, motion
                                            ↓
                                    build_user_prompt() (prompt.py)
                                    Neural profile FIRST, then snapshot, then mode
                                            ↓
                                    Claude (API or Agent SDK)
                                    Compares live EEG against trained baselines
                                    Returns JSON: {mode, interpretation, prompt, parameters}
                                            ↓
                                    Route to backend:
                                    code → save as .html, serve in modal
                                    art  → Gemini Flash image generation
                                    music → ElevenLabs music composition
                                            ↓
                                    WebSocket → frontend dashboard → output modal
```

## Key Technical Details

### EEG Data Format
- Mind Monitor streams band powers as log10(PSD) via OSC at ~10Hz
- OSC paths: `/muse/elements/{delta,theta,alpha,beta,gamma}_absolute`
- Raw EEG on `/muse/eeg` at 256Hz (4 channels: TP9, AF7, AF8, TP10)
- Sensor quality on `/muse/elements/horseshoe` (1=good, 2=ok, 3=bad, 4=off)

### Claude Backends
- **Agent SDK** (`backend: "agent-sdk"`): Uses Claude Code authentication session. No separate API key. Async via `claude_agent_sdk.query()`.
- **Anthropic API** (`backend: "api"`): Pay-per-token, streaming support. Requires `ANTHROPIC_API_KEY`.

### Generation Pipeline
- Generation is GATED behind brain learning (learning_phase >= 1)
- Claude receives the neural profile as PRIMARY interpretation reference
- Claude computes numerical distance to each domain baseline
- Output: JSON with mode, interpretation, creative prompt, and parameters
- Code mode generates self-contained HTML apps (not Python scripts)

### Brain Learning
- Structured experiments: mental imagery tasks for coding, art, music
- Claude designs the tasks, interprets EEG during each, builds discrimination summary
- Profile contains: domain baselines, confidence scores, discrimination key
- Audio cues guide eyes-closed users (tones at 2s, 1s, 0s remaining)

## When Editing the System Prompt

The system prompt in `core/prompt.py` is the most important file. When modifying it:

- The neural profile section is the PRIMARY interpretation tool — don't demote it
- The EEG reference section is BACKGROUND knowledge, not the decision framework
- Claude should interpret what the person is THINKING ABOUT, not just react to wave shapes
- Output format must be JSON: `{mode, interpretation, prompt, parameters}`
- Test with a live session: `./start.sh`, connect headband, complete brain learning, generate

## Common Tasks

### Adding a new creative mode
1. Add mode to `GenerationRequest` choices
2. Add a mode label in `build_user_prompt()` in `core/prompt.py`
3. Add handling in `web/routes/generate.py` Phase 2
4. Update `GenerationStream.tsx` to render the new output type

### Adding a new data source (e.g., fNIRS from Athena)
1. Add OSC handler in `OSCIngestor` for the new data path
2. Add a buffer and accessor method
3. Add a section in `BrainSnapshot.to_prompt_block()` to format the data
4. Add interpretation guidance in the SYSTEM_PROMPT
5. Do NOT process or interpret the data in Python

### Testing without a headband
- Edit `collector.py` to add a `MockCollector` that generates synthetic data
- Or use a UDP packet sender to simulate OSC data on port 5000

## Build & Run

```bash
./start.sh    # Creates venv, installs deps, waits for Muse, starts backend + frontend
```

Or manually:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add API keys
uvicorn web.app:app --host 0.0.0.0 --port 8000  # Backend
cd frontend && npm install && npm run dev          # Frontend
```

## Code Style

- Python 3.10+ (uses `X | Y` union syntax in type hints)
- Docstrings on all public classes and functions
- Keep the dependency list minimal — the thin pipe philosophy extends to imports
- Frontend: Next.js with TypeScript, Tailwind CSS
