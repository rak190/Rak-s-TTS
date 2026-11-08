"""
Main desktop application entry point for VoiceStudio AI (Stage 5C).
Includes:
- Pre-flight instance detection (prevents duplicate processes and redundant model loads).
- Port conflict diagnostics (friendly error reporting without killing foreign apps).
- User preferences integration (auto-browser launch, model preload).
- Signal handling for graceful shutdown.
"""
import argparse
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from typing import Optional, Tuple

# Enforce UTF-8 across all standard streams
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.config import (
    BASE_DIR,
    STORAGE_DIR,
    MODELS_DIR,
    SERVER_HOST,
    SERVER_PORT,
    DEFAULT_CPU_THREADS
)
from app.database.connection import DatabaseManager
from app.engines.model_manager import ModelManager
from app.queue.generation_queue import GenerationQueue
from app.services.settings_service import SettingsService
from app.ui.layout import build_app_ui

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("VoiceStudioAI")


def check_port_and_existing_instance(host: str, port: int) -> Tuple[str, Optional[str]]:
    """
    Checks if host:port is already listening.
    Returns:
        ("free", None): Port is available.
        ("voicestudio", app_url): VoiceStudio AI is already running.
        ("foreign", details_str): An unrelated process occupies the port.
    """
    # 1. Test exclusive bind to detect if port is occupied
    test_sock = None
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform == "win32":
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        test_sock.bind((host, port))
        test_sock.close()
        return "free", None
    except OSError:
        # Port cannot be bound, meaning another process or VoiceStudio is holding it
        pass
    finally:
        if test_sock:
            try:
                test_sock.close()
            except Exception:
                pass

    # Port is occupied. Probe if it's VoiceStudio
    url = f"http://{host}:{port}/"
    try:
        req = urllib.request.urlopen(url, timeout=1.5)
        content = req.read().decode("utf-8", errors="ignore")
        if "VoiceStudio" in content:
            return "voicestudio", url
    except Exception:
        pass

    # Unrelated foreign process is occupying the port
    details = f"Unknown process on port {port}"
    if sys.platform == "win32":
        try:
            cmd = ["netstat", "-ano", "-p", "tcp"]
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if f":{port}" in line and "LISTENING" in line.upper():
                    parts = line.strip().split()
                    pid = parts[-1]
                    p_out = subprocess.check_output(
                        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                        text=True, stderr=subprocess.DEVNULL
                    )
                    p_name = p_out.split(",")[0].strip('"') if p_out else "Unknown"
                    details = f"Process '{p_name}' (PID: {pid})"
                    break
        except Exception:
            pass

    return "foreign", details


def initialize_application():
    """Initializes local infrastructure, SQLite schema, thread limits, and settings."""
    logger.info("Initializing VoiceStudio AI on Windows...")
    logger.info(f"Project Base Directory: {BASE_DIR}")
    logger.info(f"Storage Directory: {STORAGE_DIR}")
    logger.info(f"Model Directory: {MODELS_DIR}")
    
    # 1. Initialize Database & Schema v3
    db = DatabaseManager.get_instance()
    logger.info("Database schema initialized and verified.")

    # 2. Configure Model Manager CPU limits
    mgr = ModelManager.get_instance()
    logger.info(f"Configured CPU inference thread limit to {DEFAULT_CPU_THREADS} Performance cores.")

    # 3. Start Generation Queue
    queue = GenerationQueue.get_instance()
    logger.info("Single-worker generation queue active.")


def schedule_browser_open(url: str, delay_sec: float = 1.2):
    """Opens browser automatically in a background thread after Gradio starts."""
    def _open():
        time.sleep(delay_sec)
        try:
            logger.info(f"Opening VoiceStudio AI in default browser: {url}")
            webbrowser.open(url)
        except Exception as e:
            logger.warning(f"Could not open browser automatically: {e}")

    threading.Thread(target=_open, daemon=True).start()


def setup_graceful_shutdown():
    """Registers signal handlers to clean up queues and model state."""
    def _signal_handler(sig, frame):
        logger.info("Received termination signal. Shutting down VoiceStudio AI gracefully...")
        try:
            GenerationQueue.get_instance().stop()
            ModelManager.get_instance().unload_model()
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")
        logger.info("VoiceStudio AI stopped cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


def main():
    parser = argparse.ArgumentParser(description="VoiceStudio AI - Local Multilingual TTS Studio")
    parser.add_argument("--host", default=SERVER_HOST, help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="Port to bind (default: 7860)")
    parser.add_argument("--preload", action="store_true", help="Pre-load VoxCPM2 model on startup")
    parser.add_argument("--no-browser", action="store_true", help="Do not open web browser automatically")
    parser.add_argument("--tab", default=None, help="Initial tab ID to select on startup")
    args = parser.parse_args()

    # Pre-flight check: Detect running instance or port conflict
    port_status, details = check_port_and_existing_instance(args.host, args.port)

    if port_status == "voicestudio":
        print("\n" + "=" * 65)
        print(f"🎙️ VoiceStudio AI is ALREADY RUNNING at {details}")
        print("Opening the studio interface in your default browser...")
        print("=" * 65 + "\n")
        if not args.no_browser:
            webbrowser.open(details)
        sys.exit(0)

    elif port_status == "foreign":
        print("\n" + "!" * 65)
        print(f"⚠️ PORT CONFLICT: Port {args.port} is already in use by another application:")
        print(f"   {details}")
        print("   VoiceStudio AI will not terminate foreign processes.")
        print(f"   Please close that application or launch on an alternative port:")
        print(f"   python -m app.main --port {args.port + 1}")
        print("!" * 65 + "\n")
        sys.exit(1)

    # Clean port: Proceed with startup
    setup_graceful_shutdown()
    initialize_application()

    settings_svc = SettingsService()
    should_preload = args.preload or (settings_svc.get_setting("preload_model") == "true")
    if should_preload:
        logger.info("Pre-loading VoxCPM2 into RAM per startup preferences...")
        ModelManager.get_instance().load_model()
        logger.info("Model pre-loaded successfully.")

    auto_open = (not args.no_browser) and (settings_svc.get_setting("auto_open_browser") == "true")
    app_url = f"http://{args.host}:{args.port}"
    if auto_open:
        schedule_browser_open(app_url, delay_sec=1.5)

    demo = build_app_ui(default_tab=args.tab)
    logger.info(f"Starting VoiceStudio Pro Web Studio at {app_url}")
    import gradio as gr
    from app.ui.styles import STUDIO_PRO_CSS
    from app.ui.theme import theme_bootstrap_js
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=False,
        theme=gr.themes.Base(
            primary_hue=gr.themes.colors.violet,
            secondary_hue=gr.themes.colors.violet,
            neutral_hue=gr.themes.colors.slate,
            radius_size="md",
            spacing_size="md",
            font=["Segoe UI", "Inter", "sans-serif"]
        ),
        css=STUDIO_PRO_CSS,
        js=theme_bootstrap_js(settings_svc.get_setting("theme", "system"))
    )


if __name__ == "__main__":
    main()
