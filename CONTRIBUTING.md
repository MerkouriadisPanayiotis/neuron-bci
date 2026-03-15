# Contributing to NEURON

Thanks for your interest in NEURON! Here's how to get involved.

## Getting Started

1. Fork the repo and clone it locally
2. You'll need a Muse headband (Athena, S, or 2) and the Mind Monitor app
3. Copy `.env.example` to `.env` and add your API keys
4. Run `./start.sh` to start the app

## Where to Contribute

### The System Prompt (`core/prompt.py`)

This is the most impactful place to experiment. The entire interpretation engine is a single string — the `SYSTEM_PROMPT`. Changes here affect how Claude reads EEG data and what it creates. No Python changes needed.

### Brain Learning Experiments (`web/routes/experiments.py`)

The experiment flow that trains NEURON on a user's brain. Improvements to task design, data collection, or profile building go here.

### Frontend Components (`frontend/components/`)

React components for brain visualization, experiment flow, and generation display.

### New Hardware Support

Want to add support for a different EEG headband? Add a new ingestor class in `core/ingest.py` following the `OSCIngestor` / `LSLIngestor` pattern.

## Architecture Rules

**Python collects and formats. Claude interprets and creates.**

- No signal processing in Python (no scipy, sklearn, mne)
- No brain state classification in Python (no `if beta > X: state = "focused"`)
- No creative decision logic in Python
- All interpretation lives in the system prompt as natural language

## Pull Requests

- Keep PRs focused on a single change
- Test with an actual headband if possible
- If modifying the system prompt, describe what changed and why

## Reporting Issues

- Include your headband model and streaming app
- Include browser console errors if it's a frontend issue
- Include the Python traceback if it's a backend issue

## Code of Conduct

Be respectful. This is an experimental project at the intersection of neuroscience and AI. We're all learning.
