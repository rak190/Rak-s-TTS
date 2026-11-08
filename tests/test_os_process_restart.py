"""Verify actual operating-system-level process restart persistence across independent Python processes."""
import os
import sys
import unittest
import subprocess
from pathlib import Path

PYTHON_EXE = sys.executable

class TestOSProcessRestart(unittest.TestCase):
    """Verifies that database and storage persist across independent OS process executions."""

    def test_independent_os_process_persistence(self):
        script_proc1 = """
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
from app.config import NATIVE_SAMPLE_RATE, TEMP_DIR
from app.database.connection import DatabaseManager
from app.database.models import VoiceProfile, GenerationRecord

test_dir = TEMP_DIR / "os_test"
test_dir.mkdir(parents=True, exist_ok=True)
orig_p = test_dir / "os_orig.wav"
ref_p = test_dir / "os_ref.wav"
gen_p = test_dir / "os_gen.wav"

audio = (np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, NATIVE_SAMPLE_RATE))).astype(np.float32)
sf.write(str(orig_p), audio, NATIVE_SAMPLE_RATE, subtype="PCM_16")
sf.write(str(ref_p), audio, NATIVE_SAMPLE_RATE, subtype="PCM_16")
sf.write(str(gen_p), audio, NATIVE_SAMPLE_RATE, subtype="PCM_16")

db = DatabaseManager.get_instance()
prof = VoiceProfile(
    id="prof_os_restart_test",
    name="OS Restart Test Voice",
    description="Created in separate OS Process 1",
    language="khmer",
    original_audio_path=str(orig_p),
    reference_segment_path=str(ref_p),
    transcript="សាកល្បងដំណើរការដាច់ដោយឡែក",
    duration_sec=1.0,
    sample_rate=NATIVE_SAMPLE_RATE
)
db.create_voice_profile(prof)

gen = GenerationRecord(
    id="gen_os_restart_test",
    voice_profile_id=prof.id,
    voice_name=prof.name,
    target_text="អត្ថបទ Process 1",
    mode="cloning",
    language="khmer",
    output_audio_path=str(gen_p),
    duration_sec=1.0,
    generation_time_sec=12.5,
    rtf=12.5,
    sample_rate=NATIVE_SAMPLE_RATE,
    status="completed"
)
db.create_generation(gen)
print("PROCESS_1_SUCCESS")
"""

        # Run Process 1 to write data
        res1 = subprocess.run(
            [PYTHON_EXE, "-c", script_proc1],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("PROCESS_1_SUCCESS", res1.stdout)

        script_proc2 = """
import sys
from pathlib import Path
import soundfile as sf
from app.config import NATIVE_SAMPLE_RATE, TEMP_DIR
from app.database.connection import DatabaseManager

db = DatabaseManager.get_instance()
prof = db.get_voice_profile("prof_os_restart_test")
assert prof is not None, "Profile not found in Process 2!"
assert prof.name == "OS Restart Test Voice"
assert Path(prof.reference_segment_path).exists(), "Ref file missing!"

info_ref = sf.info(prof.reference_segment_path)
assert info_ref.samplerate == NATIVE_SAMPLE_RATE

history = db.list_generations(limit=100)
matching = [g for g in history if g.id == "gen_os_restart_test"]
assert len(matching) == 1, "Gen record missing in Process 2!"
assert Path(matching[0].output_audio_path).exists(), "Gen audio missing!"

# Cleanup test records
db.delete_voice_profile(prof.id)
db.delete_generation("gen_os_restart_test")

test_dir = TEMP_DIR / "os_test"
for f in [test_dir / "os_orig.wav", test_dir / "os_ref.wav", test_dir / "os_gen.wav"]:
    if f.exists():
        f.unlink()
if test_dir.exists():
    test_dir.rmdir()

print("PROCESS_2_SUCCESS")
"""

        # Run Process 2 in a completely fresh OS process
        res2 = subprocess.run(
            [PYTHON_EXE, "-c", script_proc2],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("PROCESS_2_SUCCESS", res2.stdout)

if __name__ == "__main__":
    unittest.main()
