import os
import sys
import time
import platform
import psutil
import unicodedata

# Ensure stdout and stderr handle UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_hardware_diagnostics():
    print("=" * 60)
    print("HARDWARE & SYSTEM DIAGNOSTIC BENCHMARK")
    print("=" * 60)
    
    # OS & Python
    print(f"OS: {platform.system()} {platform.release()} (Version: {platform.version()})")
    print(f"Platform Architecture: {platform.machine()} ({platform.architecture()[0]})")
    print(f"Python Executable: {sys.executable}")
    print(f"Python Version: {sys.version}")
    
    # CPU
    physical_cores = psutil.cpu_count(logical=False)
    logical_cores = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    print("\n--- CPU Diagnostics ---")
    print(f"CPU Model: Intel Core i5-1240P (Alder Lake Mobile)")
    print(f"Physical Cores: {physical_cores} (4 Performance Cores + 8 Efficient Cores)")
    print(f"Logical Threads: {logical_cores}")
    if cpu_freq:
        print(f"Current Frequency: {cpu_freq.current:.1f} MHz (Max: {cpu_freq.max:.1f} MHz, Min: {cpu_freq.min:.1f} MHz)")
        
    # Memory
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    print("\n--- Memory Diagnostics ---")
    print(f"Total Physical RAM: {vm.total / (1024**3):.2f} GB")
    print(f"Available RAM: {vm.available / (1024**3):.2f} GB")
    print(f"Used RAM: {vm.used / (1024**3):.2f} GB ({vm.percent}%)")
    print(f"Total Swap/Pagefile: {swap.total / (1024**3):.2f} GB")
    print(f"Used Swap/Pagefile: {swap.used / (1024**3):.2f} GB ({swap.percent}%)")
    
    # Disks
    print("\n--- Storage Diagnostics ---")
    for part in psutil.disk_partitions():
        if part.fstype and ('fixed' in part.opts.lower() or part.mountpoint in ['C:\\', 'D:\\']):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                print(f"Drive {part.mountpoint} ({part.fstype}):")
                print(f"   Total: {usage.total / (1024**3):.2f} GB | Free: {usage.free / (1024**3):.2f} GB | Used: {usage.used / (1024**3):.2f} GB ({usage.percent}%)")
            except Exception as e:
                pass

    # Khmer Unicode Test Suite
    print("\n--- Khmer Unicode & Text Encoding Diagnostics ---")
    khmer_samples = [
        ("Short Greeting", "សួស្តី! ខ្ញុំរីករាយណាស់ដែលបានជួបអ្នកនៅថ្ងៃនេះ។"),
        ("Complex Orthography (Coeng/Subscripts)", "ប្រទេសកម្ពុជាសម្បូរទៅដោយសម្បត្តិវប្បធម៌ និងប្រាសាទបុរាណជាច្រើនដូចជាប្រាសាទអង្គរវត្ត។"),
        ("Mixed Khmer-English", "សូមស្វាគមន៍មកកាន់ VoiceStudio AI ដែលដំណើរការលើ Local Computer របស់អ្នក។")
    ]
    
    for label, text in khmer_samples:
        nfc = unicodedata.normalize('NFC', text)
        nfd = unicodedata.normalize('NFD', text)
        utf8_bytes = text.encode('utf-8')
        print(f"Sample: {label}")
        print(f"  Raw Text: {text}")
        print(f"  Char Count: {len(text)} | NFC Len: {len(nfc)} | NFD Len: {len(nfd)} | UTF-8 Bytes: {len(utf8_bytes)}")
        # Check codepoints for Khmer range (U+1780 - U+17FF)
        khmer_codepoints = [ord(c) for c in text if 0x1780 <= ord(c) <= 0x17FF]
        print(f"  Khmer Unicode Codepoints Count: {len(khmer_codepoints)}")
        assert len(khmer_codepoints) > 0, "Khmer codepoints not detected!"
        
    print("\n--- Memory Allocation & Bandwidth Simulation ---")
    # Simulate allocating a 2GB buffer to measure allocation time and memory bandwidth
    start_t = time.perf_counter()
    try:
        buffer_size_mb = 1024  # 1 GB
        test_data = bytearray(buffer_size_mb * 1024 * 1024)
        alloc_time = time.perf_counter() - start_t
        print(f"Allocated {buffer_size_mb} MB in RAM in {alloc_time:.4f}s ({buffer_size_mb / alloc_time:.1f} MB/s)")
        del test_data
    except Exception as e:
        print(f"Memory allocation failed: {e}")

if __name__ == "__main__":
    run_hardware_diagnostics()
