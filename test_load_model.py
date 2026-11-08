import os
import sys
import time
import psutil

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def test_load():
    from voxcpm import VoxCPM
    import torch

    # Restrict threads to 4 Performance cores for thermal control
    torch.set_num_threads(4)
    
    local_model_path = r"d:\Coding\Rak'sTTS\models\VoxCPM2"
    print(f"Loading VoxCPM2 from: {local_model_path} on CPU...")
    
    proc = psutil.Process()
    ram_before = proc.memory_info().rss / (1024**2)
    sys_ram_before = psutil.virtual_memory().available / (1024**2)
    
    t0 = time.perf_counter()
    model = VoxCPM.from_pretrained(
        local_model_path,
        device="cpu",
        optimize=False,
        load_denoiser=False
    )
    t1 = time.perf_counter()
    
    ram_after = proc.memory_info().rss / (1024**2)
    sys_ram_after = psutil.virtual_memory().available / (1024**2)
    
    print("=" * 50)
    print("MODEL LOAD SUCCESSFUL!")
    print(f"Model Load Time: {t1 - t0:.2f} seconds")
    print(f"Process RAM Before: {ram_before:.1f} MB -> After: {ram_after:.1f} MB (Delta: {ram_after - ram_before:.1f} MB)")
    print(f"System Available RAM Before: {sys_ram_before:.1f} MB -> After: {sys_ram_after:.1f} MB")
    print(f"Audio VAE Sample Rate: {model.tts_model.sample_rate} Hz")
    print("=" * 50)

if __name__ == "__main__":
    test_load()
