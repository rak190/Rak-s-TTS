"""Abstract base class for TTS runtime engines."""
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np

class BaseTTSEngine(ABC):
    """Decoupled TTS interface ensuring the application can support alternative runtimes."""

    @abstractmethod
    def generate_tts(
        self,
        text: str,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10
    ) -> Tuple[np.ndarray, int, float]:
        """
        Synthesize speech from text.
        Returns: (waveform_numpy_array, sample_rate_hz, elapsed_seconds)
        """
        pass

    @abstractmethod
    def generate_voice_cloning(
        self,
        text: str,
        reference_wav_path: str,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10
    ) -> Tuple[np.ndarray, int, float]:
        """
        Synthesize speech in the cloned voice using a reference audio clip.
        Returns: (waveform_numpy_array, sample_rate_hz, elapsed_seconds)
        """
        pass

    @abstractmethod
    def generate_ultimate_cloning(
        self,
        text: str,
        prompt_wav_path: str,
        prompt_text: str,
        reference_wav_path: Optional[str] = None,
        cfg_value: float = 2.0,
        inference_timesteps: int = 10
    ) -> Tuple[np.ndarray, int, float]:
        """
        Ultimate / Continuation cloning using reference audio paired with its exact verbatim transcript.
        Returns: (waveform_numpy_array, sample_rate_hz, elapsed_seconds)
        """
        pass

    @abstractmethod
    def get_sample_rate(self) -> int:
        """Returns the native audio sample rate of the model."""
        pass
