# NEURON

### Your brain. Claude's interpretation. Creative artifacts out.

https://github.com/SlowHurts/neuron-bci/raw/main/assets/neuron-demo.mp4

> 90 seconds: brain training, live EEG interpretation, and real-time generation of code, art, and music from brainwaves.

NEURON is an open-source brain-computer interface that connects a [Muse S Athena](https://choosemuse.com/products/muse-s-athena) EEG headband to Claude, which learns your personal neural patterns and then interprets what you're thinking about in real-time — generating interactive apps, AI art, and AI music directly from your brain state.

**What makes it different:** Most BCI projects hard-code threshold logic — `if beta/theta > 2.0: state = "focused"`. NEURON sends raw brainwave data to Claude and lets the LLM do ALL the interpretation. But it goes further: NEURON first **trains on your brain** through structured experiments, building a personal neural profile. Then when generating, Claude compares your live EEG against your trained baselines to determine what you're *actually thinking about* — not just what your brainwaves generically look like.

```
  Muse Athena        Mind Monitor        NEURON             Claude
  ┌─────────┐       ┌───────────┐      ┌──────────┐      ┌─────────────────┐
  │ EEG     │──BLE──│ OSC       │──UDP─│ collect  │─────▸│ compare against │
  │ Accel   │       │ stream    │      │ format   │      │ trained profile │
  │ Gyro    │       │           │      │ snapshot │      │ interpret intent│
  └─────────┘       └───────────┘      └──────────┘      │ generate output │
                                        ↑ thin pipe       └─────────────────┘
                                        no interpretation    ↑ all reasoning
                                                             lives here
```

---

## How It Works

1. **Brain Learning** — You wear the headband and NEURON guides you through mental imagery exercises: think about coding, think about art, think about music. Claude analyzes your EEG during each task and builds a discrimination summary — a personal neural fingerprint that captures how YOUR brain differs across creative domains.

2. **Live Interpretation** — With your profile trained, Claude receives live EEG snapshots and computes the numerical distance between your current brain state and each trained baseline. The closest match determines what you're thinking about.

3. **Generation** — Based on the interpretation, Claude generates a creative artifact:
   - **Code** → A self-contained interactive HTML/JS application, served locally and displayed in a modal
   - **Art** → An AI-generated image via Google's Nano Banana 2 (Gemini Flash)
   - **Music** → An AI-composed track via ElevenLabs

Everything happens in a web UI with real-time brain visualization, live generation streaming, and an interactive output modal.

---

## Quick Start

### Prerequisites

- **Muse S Athena** headband (Muse 2 / Muse S also compatible)
- **Mind Monitor** app ([iOS](https://apps.apple.com/app/mind-monitor/id988527143) / [Android](https://play.google.com/store/apps/details?id=com.sonicPenguins.museMonitor))
- **Python 3.10+**
- **Node.js 18+**
- **Claude Code** CLI ([install guide](https://docs.anthropic.com/en/docs/claude-code/overview)) — uses your Claude Pro/Max subscription via the Agent SDK

### Setup

```bash
git clone https://github.com/slowhurts/neuron-bci.git
cd neuron-bci

# Copy environment file and add your API keys
cp .env.example .env
# Edit .env with your GEMINI_API_KEY and ELEVENLABS_API_KEY
```

### Connect Your Headband

1. Put on the Muse Athena
2. Open Mind Monitor → pair via Bluetooth
3. In Mind Monitor settings, set OSC stream target to your computer's IP address, port `5000`
4. Start streaming

### Run

```bash
./start.sh
```

This will:
1. Create a Python virtual environment and install dependencies
2. Install frontend dependencies
3. Wait for the Muse data stream to be detected
4. Launch the backend (port 8000) and frontend (port 3000)

Open `http://localhost:3000` in your browser.

### First Session

1. Click **Connect** to start the brain data stream
2. Click **Brain Learning** — NEURON will guide you through ~15 minutes of mental imagery exercises
3. Once training completes, you'll see your confidence scores for each domain
4. Click **Generate Now** — Claude reads your brain and creates something based on what you're thinking

---

## Architecture

```
neuron-bci/
├── start.sh              # One-command launcher
├── config.yaml           # Connection + timing config (no interpretation logic)
├── requirements.txt      # Python dependencies
├── .env.example          # API key template
├── CLAUDE.md             # Instructions for Claude Code when working on this repo
├── core/
│   ├── ingest.py         # OSC/LSL stream ingestion from Muse
│   ├── collector.py      # BrainSnapshot capture + structured text formatting
│   ├── prompt.py         # System prompt — THE BRAIN OF NEURON
│   └── experiment.py     # Experiment session management
├── web/
│   ├── app.py            # FastAPI server (waits for Muse, then starts)
│   ├── claude_client.py  # Claude backends (Anthropic API + Agent SDK)
│   ├── media_generators.py  # Nano Banana 2 (images) + ElevenLabs (music)
│   ├── session_manager.py   # Brain data session lifecycle
│   ├── db.py             # SQLite persistence
│   ├── ws.py             # WebSocket for real-time brain data
│   └── routes/           # API endpoints
└── frontend/             # Next.js React app
    ├── app/              # Pages: dashboard, experiment, gallery, profile
    ├── components/       # BrainViz, ExperimentFlow, GenerationStream, etc.
    └── hooks/            # useBrainSocket, useApi
```

### The Architecture Invariant

**Python collects and formats. Claude interprets and creates.**

There is NO signal processing, NO brain state classification, and NO creative decision logic in Python. The entire interpretation engine is natural language in `core/prompt.py`. You tune NEURON's behavior by editing that prompt — no code changes required.

---

## Configuration

`config.yaml` controls the thin pipe:

```yaml
connection:
  source: osc
  osc:
    host: "0.0.0.0"
    port: 5000

claude:
  backend: "agent-sdk"    # Uses Claude Code auth (no separate API key)
  model: "claude-sonnet-4-20250514"

image_gen:
  model: "gemini-3.1-flash-image-preview"   # Nano Banana 2

elevenlabs:
  model_id: "music_v1"
  default_duration_ms: 30000
```

### Claude Backends

| Backend | Auth | Streaming | Cost |
|---------|------|-----------|------|
| `agent-sdk` | Claude Code session (Pro/Max subscription) | No | Included in subscription |
| `api` | `ANTHROPIC_API_KEY` | Yes | Pay-per-token |

---

## Brain Learning

NEURON's key differentiator is **personalized neural profiling**. Instead of using generic EEG heuristics, Claude learns YOUR specific patterns:

1. **Phase 1: Domain Anchoring** — Guided visualization tasks for coding, art, and music with neutral resets between each
2. **Phase 2+: Refinement** — Additional experiments to improve discrimination accuracy
3. **Profile Output** — A discrimination summary (written by Claude), domain baselines, and per-domain confidence scores

During live generation, Claude computes the numerical distance between your current EEG and each trained baseline. The closest match wins — no narrative cherry-picking.

---

## Supported Hardware

| Device | EEG | Status |
|--------|-----|--------|
| **Muse S Athena** | 4ch + ref | Primary target |
| Muse 2 | 4ch + ref | Compatible |
| Muse S (Gen 2) | 4ch + ref | Compatible |

### Streaming Options

| App | Platform | Protocol |
|-----|----------|----------|
| **Mind Monitor** | iOS, Android | OSC (recommended) |
| **Petal Metrics** | Win, Mac, Linux | LSL + OSC |
| **muselsl** | Python | LSL |

---

## API Keys

| Service | Required? | What it does | Get it from |
|---------|-----------|-------------|-------------|
| Claude Code | Yes | Brain interpretation + code generation | [claude.ai](https://claude.ai) (Pro/Max subscription) |
| Gemini API | For art mode | Image generation (Nano Banana 2) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| ElevenLabs | For music mode | AI music composition | [elevenlabs.io](https://elevenlabs.io/app/settings/api-keys) |

Code mode works without any API keys beyond Claude Code.

---

## Contributing

1. Fork and clone the repo
2. Set up your Muse headband + Mind Monitor
3. Run `./start.sh` and try a brain learning session
4. The most impactful place to experiment is `core/prompt.py` — that's where all the interpretation logic lives
5. Open issues for bugs, ideas, or interesting results from your own brain

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE)

---

*NEURON was built as an exploration of what happens when you stop hard-coding the interpretation layer and let an LLM reason about raw neural signals — then train it on your specific brain. The answer is more interesting than any threshold could produce.*
