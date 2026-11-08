"""System and hardware telemetry utilities."""
import os
import psutil
from typing import Dict, Any
from app.config import STORAGE_DIR

def get_system_telemetry() -> Dict[str, Any]:
    """Returns live CPU, RAM, and Disk metrics."""
    proc = psutil.Process()
    vm = psutil.virtual_memory()
    
    # Drive D: usage where app & models live
    drive_d_path = str(STORAGE_DIR.anchor)
    try:
        disk = psutil.disk_usage(drive_d_path)
        disk_free_gb = round(disk.free / (1024**3), 2)
        disk_total_gb = round(disk.total / (1024**3), 2)
    except Exception:
        disk_free_gb = 0.0
        disk_total_gb = 0.0

    freq = psutil.cpu_freq()

    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_threads_logical": psutil.cpu_count(logical=True),
        "cpu_freq_mhz": round(freq.current, 1) if freq else 0.0,
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "ram_available_gb": round(vm.available / (1024**3), 2),
        "ram_percent": vm.percent,
        "process_ram_mb": round(proc.memory_info().rss / (1024**2), 1),
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb
    }
