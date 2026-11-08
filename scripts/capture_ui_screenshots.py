"""
Automated Visual Screenshot and Viewport Validation Script for VoiceStudio AI (Stage 5C).
Captures real headless browser screenshots across Desktop (1440px), Tablet (768px),
iPhone Mobile (390px), Dark Mode, and all 7 individual Studio Tabs.
Copies assets into the conversation artifact directory.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = BASE_DIR / "assets" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACT_DIR = Path(r"C:\Users\Admin\.gemini\antigravity\brain\e3e827c0-c00b-48a0-a29d-b56319b1e921")
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
EDGE_PATH = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

def find_browser() -> Path:
    if CHROME_PATH.exists():
        return CHROME_PATH
    if EDGE_PATH.exists():
        return EDGE_PATH
    raise FileNotFoundError("Neither Google Chrome nor Microsoft Edge could be located.")

def is_server_running(port: int = 7860) -> bool:
    try:
        url = f"http://127.0.0.1:{port}/"
        req = urllib.request.urlopen(url, timeout=2.0)
        return req.getcode() == 200
    except Exception:
        return False

def wait_for_server(port: int = 7860, timeout: float = 20.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_server_running(port):
            return True
        time.sleep(0.8)
    return False

def capture_screenshot(browser: Path, url: str, output_path: Path, width: int, height: int, dark_mode: bool = False):
    print(f"Capturing {output_path.name} ({width}x{height}, Dark={dark_mode})...")
    args = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--virtual-time-budget=6000",
        f"--screenshot={output_path}",
    ]
    if dark_mode:
        args.extend(["--force-dark-mode", "--enable-features=WebContentsForceDark"])
    args.append(url)

    proc = subprocess.run(args, capture_output=True, text=True, timeout=25)
    if not output_path.exists() or output_path.stat().st_size == 0:
        print(f"Warning: Screenshot failed: {output_path}")
        return False
    print(f"Captured: {output_path.name} ({output_path.stat().st_size / 1024:.1f} KB)")

    if ARTIFACT_DIR.exists():
        shutil.copy2(output_path, ARTIFACT_DIR / output_path.name)
    return True

def capture_tab(browser: Path, tab_id: str, file_name: str, port: int = 7865):
    print(f"\n--- Launching instance for {tab_id} on port {port} ---")
    cmd = [sys.executable, "-m", "app.main", "--no-browser", "--port", str(port), "--tab", tab_id]
    proc = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    try:
        if not wait_for_server(port=port):
            print(f"Error: Server failed to start on port {port} for tab {tab_id}")
            return False
        out_file = SCREENSHOTS_DIR / file_name
        return capture_screenshot(browser, f"http://127.0.0.1:{port}/", out_file, 1440, 960, False)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=4)
        except Exception:
            proc.kill()
        time.sleep(1.0)

def main():
    browser = find_browser()
    print(f"Using browser: {browser}")

    # 1. Base viewports & themes on running server 7860
    base_targets = [
        ("voicestudio_desktop_1440.png", 1440, 900, False),
        ("voicestudio_tablet_768.png", 768, 1024, False),
        ("voicestudio_mobile_390.png", 390, 844, False),
        ("voicestudio_dark_1440.png", 1440, 900, True),
    ]

    server_7860_proc = None
    if not is_server_running(7860):
        print("Starting base server on port 7860...")
        server_7860_proc = subprocess.Popen(
            [sys.executable, "-m", "app.main", "--no-browser", "--port", "7860"],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        wait_for_server(7860)

    try:
        for name, w, h, dark in base_targets:
            capture_screenshot(browser, "http://127.0.0.1:7860/", SCREENSHOTS_DIR / name, w, h, dark)
    finally:
        if server_7860_proc:
            server_7860_proc.terminate()
            try:
                server_7860_proc.wait(timeout=4)
            except Exception:
                server_7860_proc.kill()
            time.sleep(1.0)

    # 2. Individual studio tabs
    tabs = [
        ("tab_dashboard", "tab_1_dashboard.png"),
        ("tab_tts", "tab_2_tts_studio.png"),
        ("tab_cloning", "tab_3_cloning_studio.png"),
        ("tab_mastering", "tab_4_mastering_studio.png"),
        ("tab_library", "tab_5_voice_library.png"),
        ("tab_history", "tab_6_generation_history.png"),
        ("tab_settings", "tab_7_settings.png"),
    ]

    for tab_id, fname in tabs:
        capture_tab(browser, tab_id, fname, port=7865)

    print("\nVisual QA Screenshot generation completed.")

if __name__ == "__main__":
    main()
