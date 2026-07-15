from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from typing import Any


def profile_hardware() -> dict[str, Any]:
    """Best-effort CPU/RAM/GPU/VRAM profile (Windows-first, cross-platform safe)."""
    profile: dict[str, Any] = {
        "os": platform.system(),
        "os_release": platform.release(),
        "arch": platform.machine(),
        "cpu": {
            "processor": platform.processor() or None,
            "logical_cores": os.cpu_count(),
        },
        "ram": _ram_info(),
        "disk": _disk_info(),
        "gpu": _gpu_info(),
        "runtimes": {
            "ollama": _detect_ollama_version(),
        },
        "power_mode": _power_mode(),
    }
    return profile


def _ram_info() -> dict[str, Any]:
    total = None
    available = None
    if platform.system() == "Windows":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            total = int(stat.ullTotalPhys)
            available = int(stat.ullAvailPhys)
        except Exception:  # noqa: BLE001
            pass
    elif hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            total = int(pages * page_size)
        except Exception:  # noqa: BLE001
            pass
    return {
        "total_bytes": total,
        "available_bytes": available,
        "total_gb": round(total / (1024**3), 2) if total else None,
        "available_gb": round(available / (1024**3), 2) if available else None,
    }


def _disk_info() -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(os.path.expanduser("~"))
        return {
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "free_gb": round(usage.free / (1024**3), 2),
        }
    except Exception:  # noqa: BLE001
        return {"free_bytes": None, "total_bytes": None, "free_gb": None}


def _gpu_info() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    # NVIDIA nvidia-smi
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=3,
            stderr=subprocess.DEVNULL,
        )
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                gpus.append(
                    {
                        "vendor": "nvidia",
                        "name": parts[0],
                        "vram_total_mb": _float_or_none(parts[1]),
                        "vram_free_mb": _float_or_none(parts[2]) if len(parts) > 2 else None,
                        "driver": parts[3] if len(parts) > 3 else None,
                        "api": "cuda",
                    }
                )
    except Exception:  # noqa: BLE001
        pass

    if gpus:
        return gpus

    if platform.system() == "Windows":
        try:
            ps = (
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name, AdapterRAM | ConvertTo-Json -Compress"
            )
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps],
                text=True,
                timeout=5,
                stderr=subprocess.DEVNULL,
            )
            import json

            data = json.loads(out) if out.strip() else []
            if isinstance(data, dict):
                data = [data]
            for item in data or []:
                name = item.get("Name") or "unknown"
                ram = item.get("AdapterRAM")
                vendor = "unknown"
                low = name.lower()
                if "nvidia" in low:
                    vendor = "nvidia"
                elif "amd" in low or "radeon" in low:
                    vendor = "amd"
                elif "intel" in low:
                    vendor = "intel"
                gpus.append(
                    {
                        "vendor": vendor,
                        "name": name,
                        "vram_total_mb": round(ram / (1024 * 1024), 1) if isinstance(ram, int) and ram > 0 else None,
                        "vram_free_mb": None,
                        "driver": None,
                        "api": None,
                        "note": "AdapterRAM from Win32 may be truncated on some drivers",
                    }
                )
        except Exception:  # noqa: BLE001
            pass

    return gpus


def _detect_ollama_version() -> str | None:
    try:
        out = subprocess.check_output(
            ["ollama", "--version"],
            text=True,
            timeout=3,
            stderr=subprocess.STDOUT,
        )
        m = re.search(r"(\d+\.\d+\.\d+)", out)
        return m.group(1) if m else out.strip()[:80]
    except Exception:  # noqa: BLE001
        return None


def _power_mode() -> str | None:
    if platform.system() != "Windows":
        return None
    try:
        out = subprocess.check_output(
            ["powercfg", "/getactivescheme"],
            text=True,
            timeout=3,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()[-120:]
    except Exception:  # noqa: BLE001
        return None


def _float_or_none(v: str) -> float | None:
    try:
        return float(v)
    except ValueError:
        return None


def fit_budget_mb(hardware: dict[str, Any]) -> float:
    """Approximate usable model memory budget (MB) with safety margin."""
    ram = hardware.get("ram") or {}
    available = ram.get("available_bytes") or ram.get("total_bytes")
    if not available:
        return 4096.0
    # Keep 35% headroom for OS + KV + concurrency.
    usable = (available / (1024 * 1024)) * 0.65
    gpus = hardware.get("gpu") or []
    vrams = [g.get("vram_total_mb") for g in gpus if g.get("vram_total_mb")]
    if vrams:
        # Prefer GPU VRAM if present; still apply margin.
        usable = max(usable * 0.25, max(vrams) * 0.75)
    return float(usable)
