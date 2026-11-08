"""
Captures high-resolution browser screenshot of the new VoiceStudio Pro TTS Studio prototype.
"""
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

def capture(port: int = 7860):
    server_proc = None
    if not is_server_running(port):
        print(f"Starting server on port {port}...")
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "app.main", "--no-browser", "--port", str(port), "--tab", "tab_tts"],
            cwd=str(BASE_DIR)
        )
        if not wait_for_server(port):
            print("Failed to start server.")
            if server_proc:
                server_proc.terminate()
            return

    try:
        out_file = SCREENSHOTS_DIR / "tts_studio_prototype_1440.png"
        print(f"Capturing {out_file.name}...")
        args = [
            str(CHROME_PATH),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--window-size=1440,900",
            "--virtual-time-budget=6000",
            f"--screenshot={out_file}",
            f"http://127.0.0.1:{port}/"
        ]
        subprocess.run(args, capture_output=True, timeout=25)
        print(f"Captured: {out_file} ({out_file.stat().st_size / 1024:.1f} KB)")
        if ARTIFACT_DIR.exists():
            shutil.copy2(out_file, ARTIFACT_DIR / out_file.name)
            print(f"Copied to artifact dir: {ARTIFACT_DIR / out_file.name}")
    finally:
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=4)
            except Exception:
                server_proc.kill()

if __name__ == "__main__":
    capture(7860)
