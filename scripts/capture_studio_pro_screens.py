"""
Comprehensive visual screenshot capture for VoiceStudio Pro (Stage 5C).
Captures real headless Chrome screenshots across Desktop (1440px), Dark Mode,
Tablet (768px), Mobile (390px), and all 7 individual Studio Tabs.
Saves to assets/screenshots/ and copies to conversation artifact directory.
"""
import os
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.main import initialize_application
from app.ui.layout import build_app_ui
from app.ui.styles import STUDIO_PRO_CSS

SCREENSHOTS_DIR = BASE_DIR / "assets" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path(r"C:\Users\Admin\.gemini\antigravity\brain\e3e827c0-c00b-48a0-a29d-b56319b1e921")
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

def find_free_port(start: int = 7861) -> int:
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 7861

def wait_for_server(url: str, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.urlopen(url, timeout=1.0)
            if req.getcode() == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False

def capture_chrome(url: str, out_file: Path, width: int, height: int, dark: bool = False):
    args = [
        str(CHROME_PATH),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        "--virtual-time-budget=5000",
        f"--screenshot={out_file}",
    ]
    if dark:
        args.extend(["--force-dark-mode", "--enable-features=WebContentsForceDark"])
    args.append(url)
    subprocess.run(args, capture_output=True, timeout=20)
    if out_file.exists() and out_file.stat().st_size > 0:
        print(f"  ✓ {out_file.name} ({out_file.stat().st_size / 1024:.1f} KB)")
        if ARTIFACT_DIR.exists():
            shutil.copy2(out_file, ARTIFACT_DIR / out_file.name)
        return True
    else:
        print(f"  ✗ Failed: {out_file.name}")
        return False

def main():
    print(f"Starting VoiceStudio Pro visual screenshot generator...")
    initialize_application()
    port = find_free_port(7861)
    print(f"Using local port: {port}")
    url = f"http://127.0.0.1:{port}/"

    # Tab specifications: (tab_id, filename, description)
    tabs = [
        ("tab_tts", "tts_studio_prototype_1440.png", "Flagship Speech Studio (1440x900)"),
        ("tab_tts", "voicestudio_desktop_1440.png", "Desktop Default View (1440x900)"),
        ("tab_dashboard", "tab_1_dashboard.png", "Tab 1: System Dashboard"),
        ("tab_tts", "tab_2_tts_studio.png", "Tab 2: Speech Studio"),
        ("tab_cloning", "tab_3_cloning_studio.png", "Tab 3: Voice Cloning Studio"),
        ("tab_mastering", "tab_4_mastering_studio.png", "Tab 4: Audio Mastering Studio"),
        ("tab_library", "tab_5_voice_library.png", "Tab 5: Voice Library"),
        ("tab_history", "tab_6_generation_history.png", "Tab 6: Media History"),
        ("tab_settings", "tab_7_settings.png", "Tab 7: Settings & Privacy"),
    ]

    # Responsive and theme targets on tab_tts
    viewports = [
        ("voicestudio_dark_1440.png", 1440, 900, True, "Linear Dark Mode (1440x900)"),
        ("voicestudio_tablet_768.png", 768, 1024, False, "iPad / Tablet (768x1024)"),
        ("voicestudio_mobile_390.png", 390, 844, False, "iPhone Mobile (390x844)"),
    ]

    # 1. Capture tab_tts views + responsive
    print(f"\n--- Launching Speech Studio (tab_tts) ---")
    demo = build_app_ui(default_tab="tab_tts")
    demo.launch(server_name="127.0.0.1", server_port=port, prevent_thread_lock=True, css=STUDIO_PRO_CSS)
    if not wait_for_server(url):
        print("Failed to reach server.")
        demo.close()
        return

    capture_chrome(url, SCREENSHOTS_DIR / "tts_studio_prototype_1440.png", 1440, 900, False)
    capture_chrome(url, SCREENSHOTS_DIR / "voicestudio_desktop_1440.png", 1440, 900, False)
    for fname, w, h, dark, desc in viewports:
        print(f"Capturing {desc}...")
        capture_chrome(url, SCREENSHOTS_DIR / fname, w, h, dark)

    demo.close()
    time.sleep(1.0)

    # 2. Capture remaining individual tabs
    other_tabs = [
        ("tab_dashboard", "tab_1_dashboard.png"),
        ("tab_tts", "tab_2_tts_studio.png"),
        ("tab_cloning", "tab_3_cloning_studio.png"),
        ("tab_mastering", "tab_4_mastering_studio.png"),
        ("tab_library", "tab_5_voice_library.png"),
        ("tab_history", "tab_6_generation_history.png"),
        ("tab_settings", "tab_7_settings.png"),
    ]

    for tab_id, fname in other_tabs:
        if fname == "tab_2_tts_studio.png":
            # Can just copy tts_studio_prototype_1440.png
            src = SCREENSHOTS_DIR / "tts_studio_prototype_1440.png"
            dst = SCREENSHOTS_DIR / fname
            shutil.copy2(src, dst)
            if ARTIFACT_DIR.exists():
                shutil.copy2(dst, ARTIFACT_DIR / fname)
            print(f"  ✓ {fname} (from Speech Studio)")
            continue

        port = find_free_port(port + 1)
        url = f"http://127.0.0.1:{port}/"
        print(f"\n--- Launching {tab_id} on port {port} ---")
        demo = build_app_ui(default_tab=tab_id)
        demo.launch(server_name="127.0.0.1", server_port=port, prevent_thread_lock=True, css=STUDIO_PRO_CSS)
        if wait_for_server(url):
            capture_chrome(url, SCREENSHOTS_DIR / fname, 1440, 900, False)
        demo.close()
        time.sleep(0.5)

    print("\n✅ All screenshots captured and updated successfully!")

if __name__ == "__main__":
    main()
