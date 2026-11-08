"""
Automated Tab-by-Tab Visual Screenshot Capture via Chrome DevTools Protocol (CDP).
Iterates through all 7 studio tabs, clicks each tab, and captures high-resolution screenshots.
"""
import asyncio
import base64
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
import websockets

BASE_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = BASE_DIR / "assets" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path(r"C:\Users\Admin\.gemini\antigravity\brain\e3e827c0-c00b-48a0-a29d-b56319b1e921")
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

async def send_cdp(ws, method, params=None, msg_id=1):
    req = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(req))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            return resp

async def capture_all_tabs():
    user_data = BASE_DIR / "storage" / "temp" / "chrome_user_data"
    user_data.mkdir(parents=True, exist_ok=True)

    chrome_proc = subprocess.Popen([
        str(CHROME_PATH),
        "--headless=new",
        "--remote-debugging-port=9222",
        f"--user-data-dir={user_data}",
        "--window-size=1440,960",
        "--disable-gpu",
        "--no-sandbox",
        "http://127.0.0.1:7860/"
    ])

    try:
        # Wait for CDP endpoint to respond
        ws_url = None
        for _ in range(15):
            time.sleep(1.0)
            try:
                with urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=2) as r:
                    pages = json.loads(r.read().decode())
                    if pages and "webSocketDebuggerUrl" in pages[0]:
                        ws_url = pages[0]["webSocketDebuggerUrl"]
                        break
            except Exception:
                pass

        if not ws_url:
            print("Failed to connect to Chrome DevTools port 9222.")
            return

        print(f"Connected to Chrome CDP at: {ws_url}")

        async with websockets.connect(ws_url, max_size=25_000_000) as ws:
            msg_id = 1
            await send_cdp(ws, "Page.enable", msg_id=msg_id)
            msg_id += 1

            # Give page 3 seconds to complete initial Gradio setup
            await asyncio.sleep(3.5)

            # Query tab buttons
            eval_tabs_js = """
            Array.from(document.querySelectorAll('.tabs > .tab-nav > button')).map(b => b.innerText.trim())
            """
            eval_res = await send_cdp(ws, "Runtime.evaluate", {
                "expression": eval_tabs_js,
                "returnByValue": True
            }, msg_id=msg_id)
            msg_id += 1

            tab_names = eval_res.get("result", {}).get("result", {}).get("value", [])
            print(f"Found {len(tab_names)} studio tabs: {tab_names}")

            for idx, tab_title in enumerate(tab_names):
                clean_name = tab_title.replace(" ", "_").replace("🎙️", "").replace("📊", "").replace("✂️", "").replace("🔊", "").replace("🎚️", "").replace("📜", "").replace("⚙️", "").strip("_")
                clean_name = f"tab_{idx+1}_{clean_name.lower()}"
                print(f"Switching to Tab {idx+1}: '{tab_title}' -> {clean_name}...")

                # Click the tab button
                click_js = f"""
                document.querySelectorAll('.tabs > .tab-nav > button')[{idx}].click();
                """
                await send_cdp(ws, "Runtime.evaluate", {"expression": click_js}, msg_id=msg_id)
                msg_id += 1

                # Wait for tab transition and contents render
                await asyncio.sleep(1.2)

                # Capture screenshot
                shot_res = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=msg_id)
                msg_id += 1

                b64_data = shot_res.get("result", {}).get("data")
                if b64_data:
                    img_bytes = base64.b64decode(b64_data)
                    out_path = SCREENSHOTS_DIR / f"{clean_name}.png"
                    out_path.write_bytes(img_bytes)
                    print(f"Saved: {out_path} ({len(img_bytes)/1024:.1f} KB)")

                    if ARTIFACT_DIR.exists():
                        shutil.copy2(out_path, ARTIFACT_DIR / f"{clean_name}.png")

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()
        print("Chrome CDP capture session closed.")

if __name__ == "__main__":
    asyncio.run(capture_all_tabs())
