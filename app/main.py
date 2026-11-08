"""Main application entry point for VoiceStudio AI."""
import argparse
import logging
import os
import sys

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
from app.ui.layout import build_app_ui

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("VoiceStudioAI")

def initialize_application():
    """Initializes local infrastructure, SQLite schema, and thread limits."""
    logger.info("Initializing VoiceStudio AI on Windows...")
    logger.info(f"Project Base Directory: {BASE_DIR}")
    logger.info(f"Storage Directory: {STORAGE_DIR}")
    logger.info(f"Model Directory: {MODELS_DIR}")
    
    # 1. Initialize Database
    db = DatabaseManager.get_instance()
    logger.info("Database schema initialized and verified.")

    # 2. Configure Model Manager CPU limits
    mgr = ModelManager.get_instance()
    logger.info(f"Configured CPU inference thread limit to {DEFAULT_CPU_THREADS} Performance cores.")

    # 3. Start Generation Queue
    queue = GenerationQueue.get_instance()
    logger.info("Single-worker generation queue active.")

def main():
    parser = argparse.ArgumentParser(description="VoiceStudio AI - Local Multilingual TTS Studio")
    parser.add_argument("--host", default=SERVER_HOST, help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="Port to bind (default: 7860)")
    parser.add_argument("--preload", action="store_true", help="Pre-load VoxCPM2 model on startup")
    args = parser.parse_args()

    initialize_application()

    if args.preload:
        logger.info("Pre-loading VoxCPM2 into RAM...")
        ModelManager.get_instance().load_model()
        logger.info("Model pre-loaded successfully.")

    demo = build_app_ui()
    logger.info(f"Starting VoiceStudio AI Web Studio at http://{args.host}:{args.port}")
    import gradio as gr
    theme = gr.themes.Soft(primary_hue="blue", secondary_hue="slate")
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=False,
        theme=theme
    )

if __name__ == "__main__":
    main()
