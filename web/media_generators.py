"""
NEURON — Media Generation Backends
Wraps Nano Banana 2 (images) and ElevenLabs (music) APIs.
Python calls these APIs with prompts crafted by Claude — no interpretation here.
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional


class ImagenGenerator:
    """Wraps Google Nano Banana 2 (Gemini Flash image gen) API.
    Claude crafts the prompt. This class just calls the API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.1-flash-image-preview"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        output_mime_type: str = "image/png",
    ) -> bytes:
        """Generate an image from a text prompt.
        Returns raw PNG bytes."""
        from google.genai import types

        client = self._get_client()

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        )

        # Run in thread pool since the SDK may be synchronous
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        )

        parts = response.candidates[0].content.parts
        for part in parts:
            if part.inline_data is not None:
                return part.inline_data.data

        raise RuntimeError("Nano Banana 2 returned no image data")

    @property
    def available(self) -> bool:
        return bool(self.api_key)


class ElevenLabsMusicGenerator:
    """Wraps ElevenLabs Music API for AI music generation.
    Claude crafts the prompt and parameters. This class just calls the API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "music_v1",
        default_duration_ms: int = 30000,
        force_instrumental: bool = True,
        output_format: str = "mp3_44100_128",
    ):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.model_id = model_id
        self.default_duration_ms = default_duration_ms
        self.force_instrumental = force_instrumental
        self.output_format = output_format
        self._client = None

    def _get_client(self):
        if self._client is None:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        duration_ms: Optional[int] = None,
        instrumental: Optional[bool] = None,
    ) -> bytes:
        """Generate music from a text prompt.
        Returns raw MP3 bytes."""
        client = self._get_client()
        duration = duration_ms or self.default_duration_ms
        is_instrumental = instrumental if instrumental is not None else self.force_instrumental

        # Run in thread pool since the SDK is synchronous
        loop = asyncio.get_event_loop()
        track_chunks = await loop.run_in_executor(
            None,
            lambda: client.music.compose(
                prompt=prompt,
                music_length_ms=duration,
                model_id=self.model_id,
                force_instrumental=is_instrumental,
            )
        )

        # Collect all chunks into bytes
        mp3_data = bytearray()
        for chunk in track_chunks:
            mp3_data.extend(chunk)

        return bytes(mp3_data)

    @property
    def available(self) -> bool:
        return bool(self.api_key)
