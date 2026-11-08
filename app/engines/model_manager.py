"""Singleton Model Manager for thread-safe model lifecycle and caching."""
import gc
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any
import psutil

from app.config import (
    MODELS_DIR,
    DEFAULT_CPU_THREADS,
    DEVICE,
    OPTIMIZE,
    LOAD_DENOISER
)

class ModelManager:
    """
    Singleton Manager ensuring VoxCPM2 is loaded only once and safely reused.
    Enforces CPU thread limits (4 cores) to maintain thermal and system stability.
    """
    _instance: Optional["ModelManager"] = None
    _lock = threading.Lock()

    def __init__(self, model_dir: Path = MODELS_DIR):
        self.model_dir = Path(model_dir)
        self.model = None
        self._load_lock = threading.Lock()
        self.load_time_sec: float = 0.0
        self.is_loading: bool = False
        self.last_error: Optional[str] = None
        self._configure_cpu_environment()

    @classmethod
    def get_instance(cls, model_dir: Path = MODELS_DIR) -> "ModelManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(model_dir=model_dir)
            return cls._instance

    def _configure_cpu_environment(self):
        """Sets thread limits and CPU execution flags."""
        import torch
        torch.set_num_threads(DEFAULT_CPU_THREADS)
        if hasattr(torch, "set_num_interop_threads"):
            try:
                torch.set_num_interop_threads(2)
            except Exception:
                pass

    def is_loaded(self) -> bool:
        return self.model is not None

    def get_status(self) -> Dict[str, Any]:
        """Reports live model status and host memory consumption."""
        proc = psutil.Process()
        mem_rss_mb = round(proc.memory_info().rss / (1024**2), 1)
        sys_avail_gb = round(psutil.virtual_memory().available / (1024**3), 2)
        sample_rate = self.model.tts_model.sample_rate if self.model else 48000
        
        import torch
        return {
            "is_loaded": self.is_loaded(),
            "is_loading": self.is_loading,
            "load_time_sec": self.load_time_sec,
            "sample_rate_hz": sample_rate,
            "num_threads": torch.get_num_threads(),
            "process_rss_mb": mem_rss_mb,
            "system_available_gb": sys_avail_gb,
            "model_path": str(self.model_dir),
            "last_error": self.last_error
        }

    def load_model(self):
        """Loads VoxCPM2 from local weights on Drive D: thread-safely."""
        if self.model is not None:
            return self.model

        with self._load_lock:
            if self.model is not None:
                return self.model

            self.is_loading = True
            self.last_error = None
            t0 = time.perf_counter()

            if not self.model_dir.exists():
                err = f"Model directory not found: {self.model_dir}"
                self.last_error = err
                self.is_loading = False
                raise FileNotFoundError(err)

            try:
                self._configure_cpu_environment()
                from voxcpm import VoxCPM

                # Load directly from verified local weights
                self.model = VoxCPM.from_pretrained(
                    str(self.model_dir),
                    device=DEVICE,
                    optimize=OPTIMIZE,
                    load_denoiser=LOAD_DENOISER
                )
                self.load_time_sec = round(time.perf_counter() - t0, 2)
                return self.model
            except MemoryError as me:
                self.last_error = f"Out of Memory error loading VoxCPM2: {me}"
                self.unload_model()
                raise
            except Exception as e:
                self.last_error = f"Failed to load VoxCPM2: {e}"
                self.unload_model()
                raise
            finally:
                self.is_loading = False

    def unload_model(self):
        """Gracefully unloads model from RAM to free system resources."""
        with self._load_lock:
            self.model = None
            gc.collect()
            try:
                import torch
                if hasattr(torch, "cuda") and torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
