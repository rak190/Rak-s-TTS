"""Adapter implementing BaseTTSEngine using the official VoxCPM2 Python SDK."""
import time
from typing import Optional, Tuple
import numpy as np

from app.engines.base import BaseTTSEngine
from app.engines.model_manager import ModelManager
from app.config import (
    DEFAULT_CFG_VALUE,
    DEFAULT_INFERENCE_TIMESTEPS,
    NATIVE_SAMPLE_RATE
)

class VoxCPM2Adapter(BaseTTSEngine):
    """
    Adapter isolating VoxCPM2 execution from UI and service logic.
    Ensures safe, thread-controlled CPU generation.
    """

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager.get_instance()

    def _get_active_model(self):
        """Retrieves or loads the cached model."""
        return self.model_manager.load_model()

    def get_sample_rate(self) -> int:
        if self.model_manager.is_loaded():
            return int(self.model_manager.model.tts_model.sample_rate)
        return NATIVE_SAMPLE_RATE

    def generate_tts(
        self,
        text: str,
        cfg_value: float = DEFAULT_CFG_VALUE,
        inference_timesteps: int = DEFAULT_INFERENCE_TIMESTEPS
    ) -> Tuple[np.ndarray, int, float]:
        """Synthesizes speech from text using the model's base voice."""
        model = self._get_active_model()
        sample_rate = int(model.tts_model.sample_rate)

        t0 = time.perf_counter()
        wav = model.generate(
            text=text,
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps
        )
        elapsed = round(time.perf_counter() - t0, 2)

        if not isinstance(wav, np.ndarray):
            wav = np.array(wav, dtype=np.float32)

        return wav, sample_rate, elapsed

    def generate_voice_cloning(
        self,
        text: str,
        reference_wav_path: str,
        cfg_value: float = DEFAULT_CFG_VALUE,
        inference_timesteps: int = DEFAULT_INFERENCE_TIMESTEPS
    ) -> Tuple[np.ndarray, int, float]:
        """Synthesizes speech cloning the timbre from reference_wav_path."""
        model = self._get_active_model()
        sample_rate = int(model.tts_model.sample_rate)

        t0 = time.perf_counter()
        wav = model.generate(
            text=text,
            reference_wav_path=reference_wav_path,
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps
        )
        elapsed = round(time.perf_counter() - t0, 2)

        if not isinstance(wav, np.ndarray):
            wav = np.array(wav, dtype=np.float32)

        return wav, sample_rate, elapsed

    def generate_ultimate_cloning(
        self,
        text: str,
        prompt_wav_path: str,
        prompt_text: str,
        reference_wav_path: Optional[str] = None,
        cfg_value: float = DEFAULT_CFG_VALUE,
        inference_timesteps: int = DEFAULT_INFERENCE_TIMESTEPS
    ) -> Tuple[np.ndarray, int, float]:
        """
        Ultimate / Continuation voice cloning using prompt audio paired with its exact verbatim transcript.
        """
        if not prompt_text or not prompt_text.strip():
            raise ValueError("Ultimate cloning strictly requires an exact verbatim prompt transcript.")

        model = self._get_active_model()
        sample_rate = int(model.tts_model.sample_rate)

        t0 = time.perf_counter()
        wav = model.generate(
            text=text,
            prompt_wav_path=prompt_wav_path,
            prompt_text=prompt_text,
            reference_wav_path=reference_wav_path or prompt_wav_path,
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps
        )
        elapsed = round(time.perf_counter() - t0, 2)

        if not isinstance(wav, np.ndarray):
            wav = np.array(wav, dtype=np.float32)

        return wav, sample_rate, elapsed
