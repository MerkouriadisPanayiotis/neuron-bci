"""
NEURON — Data Ingestion Layer
Handles OSC (Mind Monitor) and LSL (Petal Metrics / muselsl) streams
from the Muse S Athena headband.
"""

import threading
import time
import numpy as np
from collections import deque
from typing import Callable, Optional

# ─── OSC Ingestion (Mind Monitor) ───────────────────────────────

class OSCIngestor:
    """
    Receives OSC data from Mind Monitor.

    Mind Monitor OSC paths (default combined mode):
        /muse/eeg          — raw EEG (4 channels: TP9, AF7, AF8, TP10)
        /muse/eeg/dropped  — dropped sample count
        /muse/acc           — accelerometer (x, y, z)
        /muse/gyro          — gyroscope (x, y, z)
        /muse/batt          — battery level
        /muse/elements/horseshoe       — sensor fit (1=good, 2=ok, 3=bad, 4=off)
        /muse/elements/touching_forehead — headband contact boolean
        /muse/elements/delta_absolute  — delta band power (log10)
        /muse/elements/theta_absolute  — theta band power (log10)
        /muse/elements/alpha_absolute  — alpha band power (log10)
        /muse/elements/beta_absolute   — beta band power (log10)
        /muse/elements/gamma_absolute  — gamma band power (log10)

    When Mind Monitor is set to "separate sensor" mode, each band path
    sends 4 values (one per channel) instead of a single average.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5000,
                 buffer_seconds: float = 10.0, sample_rate: int = 256):
        self.host = host
        self.port = port
        self.sample_rate = sample_rate
        self.buffer_size = int(buffer_seconds * sample_rate)

        # Raw EEG ring buffers — 4 channels
        self.eeg_buffers = {
            ch: deque(maxlen=self.buffer_size)
            for ch in ["TP9", "AF7", "AF8", "TP10"]
        }
        # Band power buffers (from Mind Monitor's onboard FFT)
        self.band_buffers = {
            band: deque(maxlen=int(buffer_seconds * 10))  # ~10Hz from MM
            for band in ["delta", "theta", "alpha", "beta", "gamma"]
        }
        # Accelerometer / gyro
        self.acc_buffer = deque(maxlen=int(buffer_seconds * 52))
        self.gyro_buffer = deque(maxlen=int(buffer_seconds * 52))

        # Sensor quality
        self.horseshoe = [4, 4, 4, 4]  # default: sensors off
        self.touching_forehead = False

        self._server = None
        self._thread = None
        self._running = False
        self._callbacks: list[Callable] = []
        self._data_received = threading.Event()

    def on_data(self, callback: Callable):
        """Register a callback invoked on each data batch."""
        self._callbacks.append(callback)

    def start(self):
        """Start the OSC server in a background thread."""
        from pythonosc import dispatcher, osc_server

        disp = dispatcher.Dispatcher()

        # Raw EEG
        disp.map("/muse/eeg", self._handle_eeg)

        # Band powers (combined average from Mind Monitor)
        disp.map("/muse/elements/delta_absolute", self._handle_band, "delta")
        disp.map("/muse/elements/theta_absolute", self._handle_band, "theta")
        disp.map("/muse/elements/alpha_absolute", self._handle_band, "alpha")
        disp.map("/muse/elements/beta_absolute", self._handle_band, "beta")
        disp.map("/muse/elements/gamma_absolute", self._handle_band, "gamma")

        # Sensor quality
        disp.map("/muse/elements/horseshoe", self._handle_horseshoe)
        disp.map("/muse/elements/touching_forehead", self._handle_touch)

        # Motion
        disp.map("/muse/acc", self._handle_acc)
        disp.map("/muse/gyro", self._handle_gyro)

        self._server = osc_server.ThreadingOSCUDPServer(
            (self.host, self.port), disp
        )
        self._running = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"[INGEST] OSC server listening on {self.host}:{self.port}")

    def stop(self):
        self._running = False
        if self._server:
            self._server.shutdown()

    def _handle_eeg(self, address, *args):
        """Raw EEG: 4 float values (TP9, AF7, AF8, TP10)."""
        channels = ["TP9", "AF7", "AF8", "TP10"]
        ts = time.time()
        for i, ch in enumerate(channels):
            if i < len(args):
                self.eeg_buffers[ch].append((ts, args[i]))
        self._fire_callbacks("eeg")

    def _handle_band(self, address, fixed_args, *args):
        """Band power: single log10(PSD) value or 4 per-channel values."""
        band_name = fixed_args[0] if isinstance(fixed_args, list) else fixed_args
        ts = time.time()
        if len(args) == 1:
            # Combined mode: single average
            self.band_buffers[band_name].append((ts, args[0]))
        elif len(args) >= 4:
            # Separate sensor mode: average the 4 channels
            avg = np.mean(args[:4])
            self.band_buffers[band_name].append((ts, avg))
        self._fire_callbacks("band")

    def _handle_horseshoe(self, address, *args):
        self.horseshoe = list(args[:4]) if len(args) >= 4 else self.horseshoe

    def _handle_touch(self, address, *args):
        self.touching_forehead = bool(args[0]) if args else False

    def _handle_acc(self, address, *args):
        self.acc_buffer.append((time.time(), list(args[:3])))

    def _handle_gyro(self, address, *args):
        self.gyro_buffer.append((time.time(), list(args[:3])))

    def wait_for_data(self, timeout: Optional[float] = None) -> bool:
        """Block until the first OSC data arrives. Returns True if data received, False on timeout."""
        return self._data_received.wait(timeout=timeout)

    def _fire_callbacks(self, data_type: str):
        self._data_received.set()
        for cb in self._callbacks:
            try:
                cb(data_type, self)
            except Exception as e:
                print(f"[INGEST] Callback error: {e}")

    def get_recent_bands(self, seconds: float = 2.0) -> dict:
        """Get recent band powers as a dict of band_name → np.array."""
        cutoff = time.time() - seconds
        result = {}
        for band, buf in self.band_buffers.items():
            vals = [v for t, v in buf if t >= cutoff]
            result[band] = np.array(vals) if vals else np.array([])
        return result

    def get_recent_eeg(self, seconds: float = 2.0) -> dict:
        """Get recent raw EEG as dict of channel → np.array."""
        cutoff = time.time() - seconds
        result = {}
        for ch, buf in self.eeg_buffers.items():
            vals = [v for t, v in buf if t >= cutoff]
            result[ch] = np.array(vals) if vals else np.array([])
        return result

    @property
    def signal_quality(self) -> float:
        """0.0 (bad) to 1.0 (good) based on horseshoe values."""
        if not self.touching_forehead:
            return 0.0
        # horseshoe: 1=good, 2=ok, 3=bad, 4=off
        scores = [(4 - h) / 3.0 for h in self.horseshoe]
        return np.clip(np.mean(scores), 0.0, 1.0)


# ─── LSL Ingestion (Petal Metrics / muselsl) ────────────────────

class LSLIngestor:
    """
    Receives EEG data via Lab Streaming Layer.
    Works with Petal Metrics, muselsl, or any LSL-compatible streamer.
    """

    def __init__(self, stream_name: str = "Muse", stream_type: str = "EEG",
                 buffer_seconds: float = 10.0, sample_rate: int = 256):
        self.stream_name = stream_name
        self.stream_type = stream_type
        self.sample_rate = sample_rate
        self.buffer_size = int(buffer_seconds * sample_rate)

        self.eeg_buffers = {
            ch: deque(maxlen=self.buffer_size)
            for ch in ["TP9", "AF7", "AF8", "TP10"]
        }
        # Band powers computed locally from raw EEG
        self.band_buffers = {
            band: deque(maxlen=int(buffer_seconds * 4))  # at ~4Hz update rate
            for band in ["delta", "theta", "alpha", "beta", "gamma"]
        }

        self._inlet = None
        self._thread = None
        self._running = False
        self._callbacks: list[Callable] = []

        # Simulated quality (LSL doesn't have horseshoe)
        self.horseshoe = [1, 1, 1, 1]
        self.touching_forehead = True

    def on_data(self, callback: Callable):
        self._callbacks.append(callback)

    def start(self):
        """Resolve the LSL stream and start pulling data."""
        import pylsl

        print(f"[INGEST] Resolving LSL stream '{self.stream_name}'...")
        streams = pylsl.resolve_byprop('name', self.stream_name, timeout=10.0)
        if not streams:
            streams = pylsl.resolve_byprop('type', self.stream_type, timeout=10.0)
        if not streams:
            raise RuntimeError(
                f"No LSL stream found with name='{self.stream_name}' "
                f"or type='{self.stream_type}'. "
                "Ensure your streaming app (muselsl, Petal Metrics) is running."
            )

        self._inlet = pylsl.StreamInlet(streams[0], max_buflen=360)
        info = streams[0]
        print(f"[INGEST] Connected to LSL stream: {info.name()} "
              f"({info.channel_count()} channels @ {info.nominal_srate()}Hz)")

        self._running = True
        self._thread = threading.Thread(target=self._pull_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _pull_loop(self):
        channels = ["TP9", "AF7", "AF8", "TP10"]
        while self._running:
            try:
                sample, timestamp = self._inlet.pull_sample(timeout=1.0)
                if sample is not None:
                    for i, ch in enumerate(channels):
                        if i < len(sample):
                            self.eeg_buffers[ch].append((timestamp, sample[i]))
                    self._fire_callbacks("eeg")
            except Exception as e:
                print(f"[INGEST] LSL pull error: {e}")
                time.sleep(0.1)

    def _fire_callbacks(self, data_type: str):
        for cb in self._callbacks:
            try:
                cb(data_type, self)
            except Exception as e:
                print(f"[INGEST] Callback error: {e}")

    def get_recent_eeg(self, seconds: float = 2.0) -> dict:
        cutoff = time.time() - seconds
        result = {}
        for ch, buf in self.eeg_buffers.items():
            vals = [v for t, v in buf if t >= cutoff]
            result[ch] = np.array(vals) if vals else np.array([])
        return result

    def get_recent_bands(self, seconds: float = 2.0) -> dict:
        cutoff = time.time() - seconds
        result = {}
        for band, buf in self.band_buffers.items():
            vals = [v for t, v in buf if t >= cutoff]
            result[band] = np.array(vals) if vals else np.array([])
        return result

    @property
    def signal_quality(self) -> float:
        """Estimate signal quality from data availability."""
        expected = self.sample_rate * 2  # 2 seconds of data
        actual = min(len(buf) for buf in self.eeg_buffers.values())
        return np.clip(actual / expected, 0.0, 1.0)


def create_ingestor(source: str, config: dict):
    """Factory function to create the appropriate ingestor."""
    if source == "osc":
        cfg = config.get("connection", {}).get("osc", {})
        return OSCIngestor(
            host=cfg.get("host", "0.0.0.0"),
            port=cfg.get("port", 5000),
        )
    elif source == "lsl":
        cfg = config.get("connection", {}).get("lsl", {})
        return LSLIngestor(
            stream_name=cfg.get("stream_name", "Muse"),
            stream_type=cfg.get("stream_type", "EEG"),
        )
    else:
        raise ValueError(f"Unknown source: {source}. Use 'osc' or 'lsl'.")
