"""
NEURON — Data Collector
Thin layer that captures snapshots of raw brainwave data
and formats them for LLM consumption. No interpretation happens here —
all signal processing, state classification, and creative decision-making
is delegated to Claude.
"""

import time
import json
import numpy as np
from collections import deque
from typing import Optional


class BrainSnapshot:
    """
    A point-in-time capture of all available neural data from the Muse Athena,
    formatted as structured text for LLM interpretation.
    """

    def __init__(self):
        self.timestamp: float = 0.0

        # Band powers (log10 PSD from Mind Monitor, or raw µV² if from LSL)
        # Per-channel: TP9 (left ear), AF7 (left forehead), AF8 (right forehead), TP10 (right ear)
        self.bands_per_channel: dict[str, dict[str, float]] = {}
        # Combined average
        self.bands_average: dict[str, float] = {}

        # Raw EEG samples (last N seconds, per channel)
        self.raw_eeg_stats: dict[str, dict] = {}  # channel → {mean, std, min, max, samples}

        # Sensor quality
        self.horseshoe: list[float] = []  # 1=good, 2=ok, 3=bad, 4=off per sensor
        self.touching_forehead: bool = False
        self.signal_quality_pct: float = 0.0

        # Motion data
        self.accelerometer: dict = {}  # {mean_magnitude, std_magnitude, x_mean, y_mean, z_mean}
        self.gyroscope: dict = {}

        # Time-series context (last several snapshots for trend)
        self.band_history: list[dict] = []  # last ~10 readings for trend detection

        # Session context
        self.session_duration_seconds: float = 0.0
        self.snapshot_number: int = 0

    def to_prompt_block(self) -> str:
        """
        Format all neural data as a structured text block
        that Claude can reason about directly.
        """
        lines = []
        lines.append("=" * 60)
        lines.append("NEURAL DATA SNAPSHOT")
        lines.append(f"Timestamp: {time.strftime('%H:%M:%S', time.localtime(self.timestamp))}")
        lines.append(f"Session Duration: {self.session_duration_seconds:.0f}s")
        lines.append(f"Snapshot #{self.snapshot_number}")
        lines.append("=" * 60)

        # Signal quality
        lines.append("")
        lines.append("--- SIGNAL QUALITY ---")
        lines.append(f"Forehead contact: {self.touching_forehead}")
        lines.append(f"Overall quality: {self.signal_quality_pct:.0%}")
        if self.horseshoe:
            sensor_names = ["TP9 (L ear)", "AF7 (L forehead)", "AF8 (R forehead)", "TP10 (R ear)"]
            quality_labels = {1: "GOOD", 2: "OK", 3: "BAD", 4: "OFF"}
            for name, val in zip(sensor_names, self.horseshoe):
                lines.append(f"  {name}: {quality_labels.get(int(val), 'UNKNOWN')} ({val})")

        # Band powers (the primary data for interpretation)
        lines.append("")
        lines.append("--- EEG BAND POWERS (log10 PSD) ---")
        lines.append("Frequency bands: Delta(1-4Hz) Theta(4-8Hz) Alpha(8-13Hz) Beta(13-30Hz) Gamma(30-50Hz)")
        lines.append("")

        if self.bands_average:
            lines.append("Combined average across all channels:")
            for band, val in self.bands_average.items():
                bar = self._ascii_bar(val, -2.0, 2.0, width=30)
                lines.append(f"  {band:6s}: {val:+.4f}  {bar}")

        if self.bands_per_channel:
            lines.append("")
            lines.append("Per-channel breakdown:")
            for channel, bands in self.bands_per_channel.items():
                vals = "  ".join(f"{b}:{v:+.3f}" for b, v in bands.items())
                lines.append(f"  {channel}: {vals}")

            # Frontal asymmetry (raw values for Claude to interpret)
            if "AF7" in self.bands_per_channel and "AF8" in self.bands_per_channel:
                lines.append("")
                lines.append("Frontal asymmetry (AF8 - AF7, right minus left):")
                af7 = self.bands_per_channel["AF7"]
                af8 = self.bands_per_channel["AF8"]
                for band in af7:
                    diff = af8.get(band, 0) - af7.get(band, 0)
                    lines.append(f"  {band}: {diff:+.4f}")

        # Raw EEG statistics
        if self.raw_eeg_stats:
            lines.append("")
            lines.append("--- RAW EEG STATISTICS (µV, last 2s window) ---")
            for channel, stats in self.raw_eeg_stats.items():
                lines.append(f"  {channel}: mean={stats['mean']:.2f} std={stats['std']:.2f} "
                             f"min={stats['min']:.2f} max={stats['max']:.2f} "
                             f"samples={stats['samples']}")

        # Motion
        if self.accelerometer:
            lines.append("")
            lines.append("--- MOTION (Accelerometer) ---")
            lines.append(f"  Magnitude: mean={self.accelerometer.get('mean_magnitude', 0):.3f} "
                         f"std={self.accelerometer.get('std_magnitude', 0):.3f}")
            lines.append(f"  Axes: x={self.accelerometer.get('x_mean', 0):.3f} "
                         f"y={self.accelerometer.get('y_mean', 0):.3f} "
                         f"z={self.accelerometer.get('z_mean', 0):.3f}")

        # Trend data (last several readings for temporal context)
        if self.band_history:
            lines.append("")
            lines.append(f"--- BAND POWER TREND (last {len(self.band_history)} readings) ---")
            lines.append("Oldest → Newest")
            for band in ["delta", "theta", "alpha", "beta", "gamma"]:
                trend_vals = [h.get(band, 0) for h in self.band_history]
                sparkline = self._sparkline(trend_vals)
                if trend_vals:
                    delta_change = trend_vals[-1] - trend_vals[0]
                    lines.append(f"  {band:6s}: {sparkline}  Δ{delta_change:+.3f}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def _ascii_bar(value: float, min_val: float, max_val: float, width: int = 30) -> str:
        """Simple ASCII bar visualization."""
        normalized = (value - min_val) / (max_val - min_val)
        normalized = max(0.0, min(1.0, normalized))
        filled = int(normalized * width)
        return "█" * filled + "░" * (width - filled)

    @staticmethod
    def _sparkline(values: list[float]) -> str:
        """Unicode sparkline for trend visualization."""
        if not values:
            return ""
        chars = "▁▂▃▄▅▆▇█"
        mn, mx = min(values), max(values)
        if mx == mn:
            return chars[3] * len(values)
        return "".join(
            chars[int((v - mn) / (mx - mn) * (len(chars) - 1))]
            for v in values
        )


class DataCollector:
    """
    Collects raw data from the ingestor and produces BrainSnapshots.
    This is intentionally thin — it aggregates and formats, it does NOT interpret.
    """

    def __init__(self, window_seconds: float = 2.0, history_length: int = 10):
        self.window_seconds = window_seconds
        self.history_length = history_length

        self._band_history: deque = deque(maxlen=history_length)
        self._snapshot_count = 0
        self._session_start = time.time()

    def capture(self, ingestor) -> BrainSnapshot:
        """
        Capture a snapshot from the ingestor's current buffers.
        Returns structured data ready for LLM consumption.
        """
        snap = BrainSnapshot()
        snap.timestamp = time.time()
        snap.snapshot_number = self._snapshot_count
        snap.session_duration_seconds = time.time() - self._session_start
        self._snapshot_count += 1

        # Sensor quality
        snap.horseshoe = list(ingestor.horseshoe)
        snap.touching_forehead = getattr(ingestor, 'touching_forehead', True)
        snap.signal_quality_pct = ingestor.signal_quality

        # Band powers (from Mind Monitor's pre-computed FFT via OSC)
        recent_bands = ingestor.get_recent_bands(seconds=self.window_seconds)
        bands_avg = {}
        for band, vals in recent_bands.items():
            if len(vals) > 0:
                bands_avg[band] = float(np.mean(vals))
            else:
                bands_avg[band] = 0.0
        snap.bands_average = bands_avg

        # Store in history for trend
        if any(v != 0.0 for v in bands_avg.values()):
            self._band_history.append(bands_avg.copy())
        snap.band_history = list(self._band_history)

        # Raw EEG statistics (not raw samples — just stats to keep prompt reasonable)
        raw_eeg = ingestor.get_recent_eeg(seconds=self.window_seconds)
        for channel, samples in raw_eeg.items():
            if len(samples) > 10:
                snap.raw_eeg_stats[channel] = {
                    "mean": float(np.mean(samples)),
                    "std": float(np.std(samples)),
                    "min": float(np.min(samples)),
                    "max": float(np.max(samples)),
                    "samples": len(samples),
                }

        # Per-channel band powers (if available — Mind Monitor in separate sensor mode)
        # For OSC, we may not have per-channel band power easily. We derive from raw EEG stats.
        # For a richer per-channel view, the user can switch Mind Monitor to "separate sensor" mode.
        # We'll include per-channel raw stats which Claude can reason about.

        # Motion
        if hasattr(ingestor, 'acc_buffer') and len(ingestor.acc_buffer) > 0:
            cutoff = time.time() - self.window_seconds
            recent_acc = [v for t, v in ingestor.acc_buffer if t >= cutoff]
            if recent_acc:
                arr = np.array(recent_acc)
                magnitudes = np.sqrt(np.sum(arr ** 2, axis=1))
                snap.accelerometer = {
                    "mean_magnitude": float(np.mean(magnitudes)),
                    "std_magnitude": float(np.std(magnitudes)),
                    "x_mean": float(np.mean(arr[:, 0])),
                    "y_mean": float(np.mean(arr[:, 1])),
                    "z_mean": float(np.mean(arr[:, 2])),
                }

        if hasattr(ingestor, 'gyro_buffer') and len(ingestor.gyro_buffer) > 0:
            cutoff = time.time() - self.window_seconds
            recent_gyro = [v for t, v in ingestor.gyro_buffer if t >= cutoff]
            if recent_gyro:
                arr = np.array(recent_gyro)
                snap.gyroscope = {
                    "x_mean": float(np.mean(arr[:, 0])),
                    "y_mean": float(np.mean(arr[:, 1])),
                    "z_mean": float(np.mean(arr[:, 2])),
                }

        return snap
