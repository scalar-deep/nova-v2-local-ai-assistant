"""
System status tool - reports Raspberry Pi health info.
"""

import os


def get_system_status() -> str:
    """
    Get Raspberry Pi system status formatted for speech.

    Reads CPU temperature, memory usage, uptime, and disk usage.
    """
    parts = []

    # CPU temperature
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp_c = int(f.read().strip()) / 1000
        parts.append(f"My CPU temperature is {temp_c:.0f} degrees Celsius")
    except Exception:
        pass

    # Memory usage
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, value = line.split(":", 1)
                meminfo[key.strip()] = int(value.strip().split()[0])
        total_gb = meminfo["MemTotal"] / 1048576
        available_gb = meminfo["MemAvailable"] / 1048576
        used_gb = total_gb - available_gb
        parts.append(
            f"I'm using {used_gb:.1f} out of {total_gb:.1f} gigabytes of RAM"
        )
    except Exception:
        pass

    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_seconds = float(f.read().split()[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        if days > 0:
            parts.append(f"I've been running for {days} days and {hours} hours")
        elif hours > 0:
            parts.append(f"I've been running for {hours} hours and {minutes} minutes")
        else:
            parts.append(f"I've been running for {minutes} minutes")
    except Exception:
        pass

    # Disk usage
    try:
        stat = os.statvfs("/")
        total_gb = (stat.f_blocks * stat.f_frsize) / (1024 ** 3)
        free_gb = (stat.f_bfree * stat.f_frsize) / (1024 ** 3)
        used_gb = total_gb - free_gb
        parts.append(
            f"Disk usage is {used_gb:.0f} of {total_gb:.0f} gigabytes"
        )
    except Exception:
        pass

    if parts:
        return ". ".join(parts) + "."
    return "Sorry, I couldn't read my system status right now."
