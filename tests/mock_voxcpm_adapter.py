"""
Deterministic Mock VoxCPM2 Adapter for fast, compute-free queue & lifecycle testing.
Generates valid 48kHz audio arrays instantaneously without loading PyTorch weights or CPU inference.
"""
import time
from typing import Optional, Tuple
import numpy as np

class MockVoxCPM2Adapter:
    """Mock TTS Engine producing real 48,000 Hz audio arrays in milliseconds."""
    def __init__(self, delay_sec: float = 0.01, fail_on_chunk: Optional[int] = None, tone_duration_sec: float = 0.25):
        self.delay_sec = delay_sec
        self.fail_on_chunk = fail_on_chunk
        self.tone_duration_sec = tone_duration_sec
        self.call_count = 0
        self.sample_rate = 48000
        self.calls_log = []

    def _generate_synthetic_tone(self, duration_sec: float = 0.2) -> Tuple[np.ndarray, int, float]:
        self.call_count += 1
        if self.fail_on_chunk and self.call_count == self.fail_on_chunk:
            raise RuntimeError(f"Simulated synthesis failure on call #{self.call_count}")

        if self.delay_sec > 0:
            time.sleep(self.delay_sec)

        num_samples = int(self.sample_rate * duration_sec)
        t = np.linspace(0, duration_sec, num_samples, endpoint=False, dtype=np.float32)
        # 440 Hz gentle sine tone
        wav_np = 0.3 * np.sin(2 * np.pi * 440.0 * t)
        return wav_np, self.sample_rate, round(self.delay_sec, 3)

    def generate_tts(
        self,
        text: str,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10
    ) -> Tuple[np.ndarray, int, float]:
        self.calls_log.append({
            "method": "tts",
            "text": text,
            "cfg_value": cfg_value,
            "inference_timesteps": inference_timesteps,
        })
        return self._generate_synthetic_tone(duration_sec=self.tone_duration_sec)

    def generate_voice_cloning(
        self,
        text: str,
        reference_wav_path: str,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10
    ) -> Tuple[np.ndarray, int, float]:
        self.calls_log.append({
            "method": "cloning",
            "text": text,
            "reference_wav_path": reference_wav_path,
            "cfg_value": cfg_value,
            "inference_timesteps": inference_timesteps,
        })
        return self._generate_synthetic_tone(duration_sec=self.tone_duration_sec)

    def generate_ultimate_cloning(
        self,
        text: str,
        prompt_wav_path: str,
        prompt_text: str,
        reference_wav_path: Optional[str] = None,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10
    ) -> Tuple[np.ndarray, int, float]:
        self.calls_log.append({
            "method": "ultimate_cloning",
            "text": text,
            "prompt_wav_path": prompt_wav_path,
            "prompt_text": prompt_text,
            "reference_wav_path": reference_wav_path,
            "cfg_value": cfg_value,
            "inference_timesteps": inference_timesteps,
        })
        return self._generate_synthetic_tone(duration_sec=self.tone_duration_sec)
