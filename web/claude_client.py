"""
NEURON — Claude Client
Two backends for Claude interaction:
  - NeuronClaudeAPI: Anthropic SDK (pay-per-token, streaming, async)
  - NeuronClaudeAgentSDK: Claude Agent SDK (uses Claude Code auth session, async)

All interpretation happens in Claude — this module handles transport only.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

import anthropic

from core.prompt import (
    SYSTEM_PROMPT,
    EXPERIMENT_SYSTEM_PROMPT,
    build_user_prompt,
)


class NeuronClaudeBase(ABC):
    """Abstract base for Claude backends."""

    @abstractmethod
    async def interpret_and_decide(
        self,
        neural_data_block: str,
        mode: str = "auto",
        calibration_context: str = "",
        profile_context: str = "",
        previous_outputs: Optional[list] = None,
    ) -> dict:
        """Phase 1: Claude reads brain data and returns a structured JSON decision.
        Returns: {"mode": "code|art|music", "interpretation": "...", "prompt": "...", "parameters": {...}}
        """
        ...

    @abstractmethod
    async def experiment_interpret(self, user_name: str, task_type: str,
                                    instruction: str, snapshot_blocks: list,
                                    existing_observations: Optional[list] = None,
                                    calibration_context: str = "") -> str:
        ...

    @abstractmethod
    async def experiment_design_tasks(self, user_name: str, phase: int,
                                       existing_profile: Optional[dict] = None,
                                       calibration_context: str = "") -> list:
        ...

    @abstractmethod
    async def build_discrimination_summary(self, user_name: str,
                                            all_observations: list,
                                            domain_baselines: dict,
                                            calibration_context: str = "") -> dict:
        ...


def _parse_json_response(text: str) -> dict:
    """Parse JSON from Claude's response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def _build_experiment_interpret_prompt(user_name, task_type, instruction,
                                       snapshot_blocks, existing_observations,
                                       calibration_context):
    snapshots_text = "\n---\n".join(snapshot_blocks[-10:])
    observations_text = ""
    if existing_observations:
        observations_text = "\n\nPrevious observations about this user:\n"
        for obs in existing_observations[-5:]:
            observations_text += f"- {obs.get('observation', '')}\n"

    return f"""Experiment task just completed for user "{user_name}".

Task type: {task_type}
Instruction given: "{instruction}"

{calibration_context}
{observations_text}

Neural data collected during this task (multiple snapshots):

{snapshots_text}

Analyze these snapshots. What patterns do you see? How does this user's brain behave during {task_type} thinking? Be specific about band powers, asymmetry, and trends. Compare to their baseline if calibration data is available.

Respond with ONLY your interpretation — a concise paragraph describing this user's neural signature for {task_type}."""


def _build_experiment_design_prompt(user_name, phase, existing_profile, calibration_context):
    profile_text = ""
    if existing_profile:
        if existing_profile.get("discrimination_summary"):
            profile_text += f"\nCurrent discrimination summary:\n{existing_profile['discrimination_summary']}\n"
        if existing_profile.get("confidence"):
            profile_text += f"\nCurrent confidence: {existing_profile['confidence']}\n"
        if existing_profile.get("claude_observations"):
            obs = existing_profile["claude_observations"]
            if obs:
                profile_text += "\nPrevious observations:\n"
                for o in obs[-5:]:
                    profile_text += f"- {o.get('observation', '')}\n"

    if phase == 1:
        phase_desc = """Phase 1: Domain Anchoring.
Design 9 tasks: for each of the 3 domains (coding, art, music), create:
1. A neutral reset task (30 seconds) — user clears mind
2. A guided visualization task (60 seconds) — vivid imagery for the domain
3. A free association task (30 seconds) — continue thinking without guidance

Order: neutral→guided→free for coding, then art, then music."""
    elif phase == 2:
        phase_desc = f"""Phase 2: Discrimination Refinement.
Based on what we've learned so far, design 4-6 targeted tasks to resolve ambiguities between domains.
{profile_text}
Focus on distinguishing the domains where confidence is lowest."""
    else:
        phase_desc = """Phase 3: Verification.
Design 6 blind test tasks — 2 for each domain (coding, art, music).
Each task should instruct the user to think about a specific domain for 30 seconds."""

    return f"""Design brain learning experiment tasks for user "{user_name}".

{phase_desc}

{calibration_context}

Respond with a JSON array of task objects, each with:
- "task_type": one of "neutral", "coding", "art", "music"
- "instruction": the exact text to show the user
- "duration_seconds": how long the task runs (30 or 60)

Respond with ONLY the JSON array, no other text."""


def _build_discrimination_prompt(user_name, all_observations, domain_baselines, calibration_context):
    obs_text = "\n".join(f"- [{o.get('task_type', 'unknown')}] {o.get('observation', '')}"
                         for o in all_observations)
    baselines_text = ""
    for domain, stats in domain_baselines.items():
        baselines_text += f"\n{domain}:\n"
        if isinstance(stats, dict):
            for band, vals in stats.items():
                if isinstance(vals, dict):
                    baselines_text += f"  {band}: mean={vals.get('mean', 0):.4f} std={vals.get('std', 0):.4f}\n"

    return f"""Build the neural discrimination summary for user "{user_name}".

All observations from experiments:
{obs_text}

Aggregated domain baselines:
{baselines_text}

{calibration_context}

Write two things:

1. A DISCRIMINATION SUMMARY — a concise paragraph (3-5 sentences) describing how to tell apart
this user's coding, art, and music brain states. Focus on the key differentiating features.
Write this as instructions to yourself for future interpretation.

2. CONFIDENCE SCORES — rate your confidence (0.0 to 1.0) in distinguishing each domain.

Respond in this exact JSON format:
{{"discrimination_summary": "your summary here", "confidence": {{"coding": 0.0, "art": 0.0, "music": 0.0}}}}

Respond with ONLY the JSON, no other text."""


# ─── API Backend (Anthropic SDK) ────────────────────────────────

class NeuronClaudeAPI(NeuronClaudeBase):
    """Anthropic SDK — pay-per-token, streaming, async.
    Requires ANTHROPIC_API_KEY in .env."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

    async def interpret_and_decide(
        self,
        neural_data_block: str,
        mode: str = "auto",
        calibration_context: str = "",
        profile_context: str = "",
        previous_outputs: Optional[list] = None,
    ) -> dict:
        user_prompt = build_user_prompt(
            neural_data_block=neural_data_block,
            mode=mode,
            calibration_context=calibration_context,
            profile_context=profile_context,
            previous_outputs=previous_outputs,
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return _parse_json_response(response.content[0].text)

    async def interpret_and_decide_streaming(
        self,
        neural_data_block: str,
        mode: str = "auto",
        calibration_context: str = "",
        profile_context: str = "",
        previous_outputs: Optional[list] = None,
    ) -> AsyncIterator[str]:
        """Streaming version — yields text chunks. Caller must parse JSON from full text."""
        user_prompt = build_user_prompt(
            neural_data_block=neural_data_block,
            mode=mode,
            calibration_context=calibration_context,
            profile_context=profile_context,
            previous_outputs=previous_outputs,
        )

        async with self.client.messages.stream(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def experiment_interpret(self, user_name, task_type, instruction,
                                    snapshot_blocks, existing_observations=None,
                                    calibration_context=""):
        prompt = _build_experiment_interpret_prompt(
            user_name, task_type, instruction, snapshot_blocks,
            existing_observations, calibration_context)
        response = await self.client.messages.create(
            model=self.model, max_tokens=1000,
            system=EXPERIMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}])
        return response.content[0].text

    async def experiment_design_tasks(self, user_name, phase,
                                       existing_profile=None, calibration_context=""):
        prompt = _build_experiment_design_prompt(
            user_name, phase, existing_profile, calibration_context)
        response = await self.client.messages.create(
            model=self.model, max_tokens=3000,
            system=EXPERIMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}])
        return _parse_json_response(response.content[0].text)

    async def build_discrimination_summary(self, user_name, all_observations,
                                            domain_baselines, calibration_context=""):
        prompt = _build_discrimination_prompt(
            user_name, all_observations, domain_baselines, calibration_context)
        response = await self.client.messages.create(
            model=self.model, max_tokens=1000,
            system=EXPERIMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}])
        return _parse_json_response(response.content[0].text)


# ─── Agent SDK Backend (Claude Code auth session) ───────────────

class NeuronClaudeAgentSDK(NeuronClaudeBase):
    """Claude Agent SDK — uses your Claude Code authentication session.
    No separate API key required. Async-native."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    async def _query(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt via the Agent SDK and collect the full text response."""
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
        )
        if self.model:
            options.model = self.model

        response_text = ""
        async for message in query(prompt=user_prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text

        return response_text

    async def interpret_and_decide(self, neural_data_block, mode="auto",
                                    calibration_context="", profile_context="",
                                    previous_outputs=None):
        user_prompt = build_user_prompt(
            neural_data_block=neural_data_block, mode=mode,
            calibration_context=calibration_context,
            profile_context=profile_context,
            previous_outputs=previous_outputs)
        text = await self._query(SYSTEM_PROMPT, user_prompt)
        return _parse_json_response(text)

    async def experiment_interpret(self, user_name, task_type, instruction,
                                    snapshot_blocks, existing_observations=None,
                                    calibration_context=""):
        prompt = _build_experiment_interpret_prompt(
            user_name, task_type, instruction, snapshot_blocks,
            existing_observations, calibration_context)
        return await self._query(EXPERIMENT_SYSTEM_PROMPT, prompt)

    async def experiment_design_tasks(self, user_name, phase,
                                       existing_profile=None, calibration_context=""):
        prompt = _build_experiment_design_prompt(
            user_name, phase, existing_profile, calibration_context)
        text = await self._query(EXPERIMENT_SYSTEM_PROMPT, prompt)
        return _parse_json_response(text)

    async def build_discrimination_summary(self, user_name, all_observations,
                                            domain_baselines, calibration_context=""):
        prompt = _build_discrimination_prompt(
            user_name, all_observations, domain_baselines, calibration_context)
        text = await self._query(EXPERIMENT_SYSTEM_PROMPT, prompt)
        return _parse_json_response(text)


# ─── Factory ────────────────────────────────────────────────────

def create_claude_client(config: dict) -> NeuronClaudeBase:
    """Create the appropriate Claude backend based on config."""
    claude_cfg = config.get("claude", {})
    backend = claude_cfg.get("backend", "api")

    if backend == "agent-sdk":
        return NeuronClaudeAgentSDK(
            model=claude_cfg.get("model"),
        )
    else:
        return NeuronClaudeAPI(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            model=claude_cfg.get("model", "claude-sonnet-4-20250514"),
        )
