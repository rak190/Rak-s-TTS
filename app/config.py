"""Application configuration for VoiceStudio AI."""
import os
import sys
from pathlib import Path

# Enforce UTF-8 encoding across Windows console & streams
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# Base Directory (Drive D:)
BASE_DIR = Path(__file__).resolve().parent.parent

# Storage Directories on Drive D:
STORAGE_DIR = BASE_DIR / "storage"
VOICES_DIR = STORAGE_DIR / "voices"
REFERENCES_DIR = STORAGE_DIR / "references"
GENERATED_DIR = STORAGE_DIR / "generated"
LONGFORM_DIR = STORAGE_DIR / "longform"
PROJECTS_DIR = STORAGE_DIR / "projects"
IMPORTS_DIR = STORAGE_DIR / "imports"
TEMP_DIR = STORAGE_DIR / "temp"
LOGS_DIR = STORAGE_DIR / "logs"

# Model & Cache Paths (Drive D:)
MODELS_DIR = BASE_DIR / "models" / "VoxCPM2"
HF_CACHE_DIR = BASE_DIR / "hf_cache"
os.environ["HF_HOME"] = str(HF_CACHE_DIR)

# SQLite Database Path
DB_PATH = STORAGE_DIR / "voicestudio.db"

# Inference Settings (Validated in Stage 2A)
DEFAULT_CPU_THREADS = 4
DEVICE = "cpu"
OPTIMIZE = False
LOAD_DENOISER = False
DEFAULT_CFG_VALUE = 2.0
DEFAULT_INFERENCE_TIMESTEPS = 10
NATIVE_SAMPLE_RATE = 48000

# Web Server Settings (Strictly Local)
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7860
SHARE_PUBLIC = False

# Ensure all critical storage directories exist
for path in [STORAGE_DIR, VOICES_DIR, REFERENCES_DIR, GENERATED_DIR, LONGFORM_DIR, PROJECTS_DIR, IMPORTS_DIR, TEMP_DIR, LOGS_DIR]:
    path.mkdir(parents=True, exist_ok=True)
