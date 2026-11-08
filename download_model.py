import os
import sys
import shutil
import psutil
from huggingface_hub import snapshot_download

# Force UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def download_voxcpm2():
    model_id = "openbmb/VoxCPM2"
    target_dir = r"d:\Coding\Rak'sTTS\models\VoxCPM2"
    cache_dir = r"d:\Coding\Rak'sTTS\hf_cache"
    
    # 1. Check disk space on D:
    d_usage = psutil.disk_usage("D:\\")
    free_gb = d_usage.free / (1024**3)
    print(f"Current Free Space on Drive D: {free_gb:.2f} GB")
    
    required_gb = 6.0  # Model is ~4.73 GB
    if free_gb < required_gb:
        raise RuntimeError(f"Insufficient disk space on Drive D: {free_gb:.2f} GB free, {required_gb} GB required.")
        
    print(f"Disk check passed. Proceeding with download of '{model_id}' to '{target_dir}'...")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    
    # Set HF_HOME environment variable
    os.environ["HF_HOME"] = cache_dir
    
    local_path = snapshot_download(
        repo_id=model_id,
        local_dir=target_dir,
        cache_dir=cache_dir,
        local_dir_use_symlinks=False,  # On Windows, copy directly to avoid symlink privilege issues
        resume_download=True
    )
    
    print(f"Model successfully downloaded to: {local_path}")
    
    # Verify downloaded files
    total_size = 0
    for root, dirs, files in os.walk(local_path):
        for f in files:
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            total_size += sz
            print(f" - {f}: {sz / (1024**2):.2f} MB")
            
    print(f"Total downloaded model size: {total_size / (1024**3):.2f} GB")
    return local_path

if __name__ == "__main__":
    download_voxcpm2()
