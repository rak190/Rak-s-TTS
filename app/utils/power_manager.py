"""
Windows Power Management Utility for VoiceStudio AI.
Prevents system sleep/standby during active speech synthesis (Overnight Batch Mode)
and restores default OS power behavior when idle, with safe post-completion actions.
"""
import ctypes
import logging
import os
import platform
import subprocess
import threading
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Windows SetThreadExecutionState flags
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040

class WindowsPowerManager:
    """
    Manages Windows sleep inhibition during long-running batch speech generation.
    Thread-safe and fails gracefully on non-Windows platforms or permission restrictions.
    """
    _instance: Optional["WindowsPowerManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._is_windows = platform.system() == "Windows"
        self._sleep_inhibited = False
        self._reason = ""

    @classmethod
    def get_instance(cls) -> "WindowsPowerManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def is_windows(self) -> bool:
        return self._is_windows

    @property
    def is_sleep_inhibited(self) -> bool:
        return self._sleep_inhibited

    def inhibit_sleep(self, reason: str = "VoiceStudio AI Batch Generation") -> bool:
        """
        Informs the Windows kernel that active computation is taking place,
        preventing the system from entering idle sleep / standby.
        Allows the screen to turn off normally (Away Mode).
        """
        if not self._is_windows:
            logger.info("Non-Windows OS detected; sleep inhibition skipped.")
            return False

        with self._lock:
            try:
                # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
                flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
                ret = ctypes.windll.kernel32.SetThreadExecutionState(flags)
                if ret != 0:
                    self._sleep_inhibited = True
                    self._reason = reason
                    logger.info(f"Windows sleep inhibited successfully. Reason: {reason}")
                    return True
                else:
                    logger.warning("SetThreadExecutionState returned 0. Could not inhibit sleep.")
                    return False
            except Exception as e:
                logger.warning(f"Error calling SetThreadExecutionState: {e}")
                return False

    def restore_sleep(self) -> bool:
        """
        Clears the sleep inhibition flags, restoring normal operating system sleep timeouts.
        Must be called whenever batch generation pauses, fails, or completes.
        """
        if not self._is_windows:
            return False

        with self._lock:
            try:
                # ES_CONTINUOUS clears previous requirements
                ret = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                self._sleep_inhibited = False
                self._reason = ""
                logger.info("Windows sleep restoration applied: normal power timeouts restored.")
                return True
            except Exception as e:
                logger.warning(f"Error restoring default power state: {e}")
                return False

    def execute_post_completion_action(self, action: str) -> Tuple[bool, str]:
        """
        Executes a user-selected post-completion action safely.
        Options:
            'none'     - Do nothing (default)
            'notify'   - Play gentle acoustic notification
            'sleep'    - Put machine to sleep (opt-in only)
            'shutdown' - Shut down machine after 60s delay (opt-in only)
        """
        action = (action or "none").strip().lower()

        if action in ("none", "do nothing", ""):
            return True, "No post-completion action required."

        if action in ("notify", "play notification", "chime"):
            try:
                if self._is_windows:
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                else:
                    print("\a", flush=True)
                return True, "Local notification chime played."
            except Exception as e:
                logger.warning(f"Failed to play notification chime: {e}")
                return False, f"Notification failed: {e}"

        if action in ("sleep", "sleep pc"):
            if not self._is_windows:
                return False, "Sleep action only supported on Windows."
            try:
                logger.info("Opt-in post-completion action: Requesting Windows Sleep.")
                # Call SetSuspendState(0, 1, 0)
                ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
                return True, "Windows put to sleep."
            except Exception as e:
                logger.error(f"Failed to sleep computer: {e}")
                return False, f"Sleep failed: {e}"

        if action in ("shutdown", "shutdown pc", "shut down"):
            if not self._is_windows:
                return False, "Shutdown action only supported on Windows."
            try:
                logger.warning("Opt-in post-completion action: Initiating shutdown in 60 seconds.")
                subprocess.Popen(
                    ["shutdown.exe", "/s", "/t", "60", "/c", "VoiceStudio batch generation complete. Shutting down in 60s. Run 'shutdown /a' to abort."],
                    shell=True
                )
                return True, "Windows shutdown initiated (60 second timer; abort with 'shutdown /a')."
            except Exception as e:
                logger.error(f"Failed to initiate shutdown: {e}")
                return False, f"Shutdown failed: {e}"

        return False, f"Unknown post-completion action: {action}"
