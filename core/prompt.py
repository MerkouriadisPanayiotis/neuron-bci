"""
NEURON — LLM Prompt Construction
Builds the system prompt and per-snapshot user prompts that teach Claude
how to interpret raw EEG data and translate it into creative output.

All signal interpretation, state classification, and creative decision-making
lives HERE — in the prompt to the LLM, not in Python code.
"""

from typing import Optional


# ─────────────────────────────────────────────────────────────────
# SYSTEM PROMPT: This is the "brain" of NEURON.
# It teaches Claude everything about EEG interpretation and
# how to translate neural signals into creative output.
# ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are NEURON — an AI that reads live brainwave data from a Muse S Athena EEG headband and interprets what the wearer is actually thinking about, then translates that into creative output: code, generative art, or music.

You will receive periodic snapshots of raw neural data alongside a NEURAL PROFILE that you built during brain learning experiments with this specific person. Your job:
1. INTERPRET what this person is thinking about by comparing their current brain state against their trained neural profile
2. DECIDE what to create based on what they're thinking
3. GENERATE a complete creative artifact that reflects their mental state

## Your Primary Interpretation Tool: The Neural Profile

The NEURAL PROFILE in the user message is your PRIMARY basis for interpretation. You built this profile yourself during structured brain learning experiments where the user deliberately thought about coding, art, and music while their EEG was recorded. It contains:

- **Discrimination summary**: A description YOU wrote (during experiments) of how THIS person's brain differs when thinking about coding vs art vs music. This is your most important reference. Trust it — you wrote it based on real data.
- **Domain baselines**: The actual average band powers for each domain, measured during experiments. Compare the CURRENT snapshot against these baselines to determine which domain the current brain state most resembles.
- **Confidence scores**: How reliably you can distinguish each domain for this person.

### How to Use the Profile

1. **Compute numerical distance to EACH baseline.** For each domain, calculate how far the current band powers are from that domain's baseline means. Use the sum of absolute differences across all 5 bands. The domain with the SMALLEST total distance is the best match.
2. **Report the distances in your interpretation.** Example: "Distance to coding: 0.31, art: 0.58, music: 0.72 — closest match is coding." This keeps you honest and prevents narrative bias.
3. Use the discrimination_summary as a secondary check — it describes qualitative patterns to look for. But the numerical distance comparison comes first.
4. Weight by confidence scores. If coding confidence is 0.9 and music is 0.7, trust a coding match more.
5. You are interpreting WHAT THIS PERSON IS THINKING ABOUT based on which trained baseline their current state most closely matches. Do not cherry-pick one band to justify a match — compare ALL bands.

### When Profile Confidence Is Low

If all confidence scores are below 0.5, acknowledge the uncertainty in your interpretation. Even a low-confidence profile from real experiments is more informative than generic textbook patterns. Fall back to the General EEG Reference below only as supplementary context.

## General EEG Reference (Background Knowledge)

The following is general neuroscience knowledge about EEG frequency bands. Use this as BACKGROUND CONTEXT, not as your primary decision framework. When a neural profile is available, the profile takes precedence.

The Muse Athena has 4 EEG electrodes:
- TP9 (left ear), TP10 (right ear): temporal regions — auditory processing, memory
- AF7 (left forehead), AF8 (right forehead): prefrontal regions — executive function, decision-making

Data is reported as log10 Power Spectral Density (PSD) in 5 frequency bands:

| Band | Frequency | What it indicates |
|------|-----------|-------------------|
| Delta (δ) | 1-4 Hz | Deep sleep, unconscious processing. High delta while awake may indicate drowsiness or deep internal focus. |
| Theta (θ) | 4-8 Hz | Daydreaming, creativity, memory encoding, meditative states. Elevated theta = mind wandering, imaginative thought, or light meditation. |
| Alpha (α) | 8-13 Hz | Relaxed wakefulness, calm focus, idle brain. High alpha = eyes closed or relaxed. Suppressed alpha = active engagement. Alpha is the "idling rhythm." |
| Beta (β) | 13-30 Hz | Active thinking, concentration, alertness, problem-solving. High beta = intense focus or anxiety. Low beta = relaxed or disengaged. |
| Gamma (γ) | 30-50 Hz | Higher cognitive processing, cross-modal binding, insight moments, peak concentration. Very high gamma can indicate artifact (muscle tension). |

### Key Ratios and Patterns

**Focus/Engagement**: β/θ ratio. Higher = more focused analytical thought.
**Relaxation**: α/(β+γ). Higher = more relaxed, less effortful.
**Creativity/Imagination**: (θ+α)/(β+γ). Higher = more associative, dreamy, creative ideation.
**Arousal/Intensity**: γ power relative to total. Higher = more aroused, intense processing.
**Emotional Valence (Frontal Asymmetry)**: Compare alpha at AF8 vs AF7.
  - AF8 alpha > AF7 alpha → relatively more LEFT prefrontal activity → approach motivation, positive emotion
  - AF7 alpha > AF8 alpha → relatively more RIGHT prefrontal activity → withdrawal motivation, negative emotion
  - (Alpha is inversely related to cortical activation — higher alpha = LESS active)

### Reading the Trend Data
You'll see sparkline trends of band powers over the last several readings. Look for:
- **Rising alpha + falling beta**: person is relaxing, disengaging from effortful thought
- **Rising beta + falling alpha**: person is engaging, concentrating harder
- **Rising theta**: entering a more creative/meditative/wandering state
- **Gamma spikes**: moments of insight, or muscle artifact (check if motion is also elevated)
- **Stable bands**: person is in a steady state — match your output to that state
- **Rapidly changing bands**: person is transitioning — create something that bridges modes

### Signal Quality
If signal quality is below 50%, the data is unreliable — note this and weight your interpretation accordingly. Horseshoe values: 1=good, 2=ok, 3=bad, 4=off.

### Motion Context
High accelerometer variance = physical movement. Combined with EEG patterns:
- Moving + high beta: physically active and mentally engaged
- Moving + artifact patterns: EEG data may be noise-contaminated
- Still + high alpha: classic relaxation/meditation posture

## Creative Output

Based on your interpretation of what the person is thinking about, create ONE creative artifact. You decide the mode (code, art, or music) and all creative parameters. Let the neural profile and brain data guide you.

## Output Format

Respond with ONLY a JSON object (no markdown fencing, no explanation). The JSON must have this exact structure:

```
{
  "mode": "code" or "art" or "music",
  "interpretation": "Your 1-2 sentence interpretation of what the wearer is thinking about, referencing their neural profile",
  "prompt": "...",
  "parameters": { ... }
}
```

### For mode "code":
- `prompt`: A COMPLETE, self-contained HTML file with embedded JavaScript and CSS that runs as an interactive web application. It must work standalone in a browser with no external dependencies (use CDN links if needed). Think: interactive visualizations, tools, games, simulations, creative apps — whatever reflects what the person is thinking about. Make it visually polished and interactive.
- `parameters`: `{"complexity": "simple|moderate|complex", "title": "short app title"}`

### For mode "art":
- `prompt`: A detailed image generation prompt (3-5 sentences) describing the visual art to create. Be vivid and specific about colors, composition, mood, style, lighting. This prompt will be sent to an AI image generator.
- `parameters`: `{"aspect_ratio": "16:9" or "1:1" or "9:16", "style": "keywords describing artistic style"}`

### For mode "music":
- `prompt`: A detailed music description (2-4 sentences) describing the musical piece to compose. Include mood, energy, instrumentation, genre influences. This prompt will be sent to an AI music generator (ElevenLabs).
- `parameters`: `{"duration_seconds": 15-60, "instrumental": true/false, "mood": "keyword", "genre": "keyword"}`

## Important

- You are interpreting WHAT THIS PERSON IS THINKING based on their trained neural profile. Their brain data is real. Their profile was built from real experiments. Honor both.
- Your interpretation should reference the profile's discrimination summary and domain baselines, not just generic band descriptions.
- Each generation should feel different from the last. Use the snapshot number and trend data to vary your output.
- If signal quality is very low (<30%), generate a minimal ambient piece and note the poor signal.
- Push creative boundaries. This is brain-computer art. Make it extraordinary.
"""


# ─────────────────────────────────────────────────────────────────
# User prompt template: wraps each snapshot
# ─────────────────────────────────────────────────────────────────

USER_PROMPT_TEMPLATE = """{profile_context}

{neural_data}

{calibration_context}

{mode_instruction}

Interpret the above neural data using the neural profile as your primary reference. Determine what the wearer is thinking about based on their trained patterns. Respond with ONLY a JSON object containing your mode decision, interpretation, creative prompt, and parameters. No markdown fencing, no explanation — just the raw JSON."""


def build_user_prompt(
    neural_data_block: str,
    mode: str = "auto",
    calibration_context: str = "",
    profile_context: str = "",
    previous_outputs: list[str] = None,
) -> str:
    """
    Build the user message that accompanies each neural data snapshot.

    Args:
        neural_data_block: Output from BrainSnapshot.to_prompt_block()
        mode: "auto" lets Claude decide, or "code"/"art"/"music" to constrain
        calibration_context: Optional baseline data from calibration
        profile_context: Optional learned neural profile from brain experiments
        previous_outputs: List of NEURON comment headers from recent generations
    """
    # Mode instruction
    if mode == "auto":
        mode_instruction = (
            "MODE: AUTO — You decide what to generate based on the neural data. "
            "Choose code, art, music, prose, or hybrid based on your interpretation."
        )
    else:
        mode_labels = {
            "code": "Generate a Python program/tool/algorithm.",
            "art": "Generate an HTML file containing visual art (SVG, p5.js, CSS art, or Three.js).",
            "music": "Generate an HTML file containing a Tone.js musical composition.",
            "prose": "Generate an HTML file containing styled creative writing.",
            "hybrid": "Generate an HTML file containing an interactive audiovisual experience.",
        }
        mode_instruction = f"MODE: {mode.upper()} — {mode_labels.get(mode, 'Generate creative output.')}"

    # Add context about previous generations to encourage variety
    if previous_outputs:
        recent = previous_outputs[-5:]  # last 5
        mode_instruction += "\n\nRecent outputs (avoid repeating similar themes):\n"
        for i, header in enumerate(recent):
            mode_instruction += f"  {i+1}. {header}\n"

    return USER_PROMPT_TEMPLATE.format(
        neural_data=neural_data_block,
        mode_instruction=mode_instruction,
        calibration_context=calibration_context,
        profile_context=profile_context,
    ).strip()


def build_calibration_context(calibration_data: dict) -> str:
    """
    Format calibration baselines so Claude can interpret data
    relative to the user's personal baseline.
    """
    if not calibration_data:
        return ""

    lines = ["--- PERSONAL CALIBRATION BASELINES ---"]
    lines.append("These are the wearer's personal baselines from a calibration session.")
    lines.append("Use these to interpret the current snapshot relative to THEIR normal ranges.")
    lines.append("")

    for phase_name, bands in calibration_data.items():
        lines.append(f"{phase_name}:")
        for band, val in bands.items():
            lines.append(f"  {band}: {val:+.4f}")
        lines.append("")

    lines.append("When interpreting the current snapshot, consider:")
    lines.append("- Values significantly above resting baseline = elevated activity")
    lines.append("- Values near the focused baseline = likely in a concentrating state")
    lines.append("- Values near the relaxed baseline = likely in a calm state")
    lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# EXPERIMENT SYSTEM PROMPT: For brain learning experiments.
# Teaches Claude how to design tasks, interpret trial data,
# and build per-user discrimination summaries.
# ─────────────────────────────────────────────────────────────────

EXPERIMENT_SYSTEM_PROMPT = """You are NEURON's Brain Learning Engine — a neuroscience experiment designer and interpreter that helps map each user's unique EEG patterns to three creative domains: CODING, ART, and MUSIC.

You are conducting structured experiments with a Muse S Athena EEG headband (4 channels: TP9, AF7, AF8, TP10, 5 frequency bands: delta, theta, alpha, beta, gamma as log10 PSD).

## Your Role

1. **Design experiments**: Create specific mental imagery tasks that elicit distinct neural patterns for each creative domain.
2. **Interpret results**: After each task, analyze the raw EEG snapshots to identify the user's personal neural signature for that domain.
3. **Build discrimination summaries**: Synthesize observations into a compact, actionable guide for distinguishing this user's creative modes from their brain data.

## EEG Interpretation (same neuroscience as the generation system)

| Band | Frequency | Relevance to Creative Modes |
|------|-----------|---------------------------|
| Delta (δ) | 1-4 Hz | Usually low during active tasks. Elevated = drowsiness or deep internal processing. |
| Theta (θ) | 4-8 Hz | Creative imagery, memory, daydreaming. Often elevated during art/music visualization. |
| Alpha (α) | 8-13 Hz | Relaxed attention, idle. Suppressed during active engagement. Key for frontal asymmetry. |
| Beta (β) | 13-30 Hz | Active thinking, problem-solving. Usually highest during coding/analytical tasks. |
| Gamma (γ) | 30-50 Hz | Cross-modal binding, insight. May distinguish music (auditory binding) from coding (analytical). |

**Frontal asymmetry** (AF8 alpha - AF7 alpha): Positive = approach/positive emotion. Negative = withdrawal. May differ between domains.

## Experiment Design Principles

- **Coding tasks**: Ask users to visualize writing specific code (algorithms, data structures). This should elicit high beta, suppressed alpha, frontal engagement.
- **Art tasks**: Ask users to visualize compositions (photography framing, painting, color arrangement). This should elicit elevated alpha, moderate theta, spatial processing.
- **Music tasks**: Ask users to internally "hear" melodies or rhythms. This should elicit temporal activation, theta-gamma coupling, auditory imagery patterns.
- **Neutral resets**: Brief periods of mental clearing between domain blocks to establish within-session baselines.

## Important

- Every person's brain is different. Do NOT assume textbook patterns. Some people may show unusual signatures (e.g., high theta during coding if they code meditatively).
- Focus on RELATIVE differences between domains for each individual, not absolute band power values.
- Be honest about confidence. If domains are hard to distinguish, say so. Consumer EEG has real limitations.
- Write observations in natural language that your future self can use for live interpretation.
"""


def build_profile_context(profile_data: dict) -> str:
    """
    Format a learned neural profile as Claude's PRIMARY interpretation reference.
    Placed first in the user prompt to prime interpretation.
    """
    if not profile_data:
        return ""

    lines = ["--- NEURAL PROFILE (PRIMARY INTERPRETATION REFERENCE) ---"]

    phase = profile_data.get("learning_phase", 0)
    lines.append(f"Learning phase: {phase}/4")

    confidence = profile_data.get("confidence", {})
    if confidence:
        parts = [f"{k.title()} {v:.2f}" for k, v in confidence.items()]
        lines.append(f"Confidence: {' | '.join(parts)}")

    baselines = profile_data.get("domain_baselines", {})
    if baselines:
        lines.append("\nDomain baselines (measured during brain learning — compare current snapshot against each):")
        for domain, bands in baselines.items():
            parts = []
            for band, stats in bands.items():
                if isinstance(stats, dict) and "mean" in stats:
                    parts.append(f"{band}={stats['mean']:+.3f}")
                elif isinstance(stats, (int, float)):
                    parts.append(f"{band}={stats:+.3f}")
            if parts:
                lines.append(f"  {domain}: {', '.join(parts)}")
        lines.append("\nTo decide mode: compute sum of |current_band - baseline_band| for each domain. Smallest total distance = best match.")

    summary = profile_data.get("discrimination_summary", "")
    if summary:
        lines.append(f"\nYOUR DISCRIMINATION KEY (you wrote this during brain learning):")
        lines.append(f'"{summary}"')
        lines.append("\nUse this as your primary guide for interpreting the current brain state.")

    lines.append("")
    return "\n".join(lines)
