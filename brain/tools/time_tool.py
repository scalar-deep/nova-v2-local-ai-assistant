"""
Time tool - returns current time and date.
"""

from datetime import datetime


def get_current_time() -> str:
    """Get current time formatted for speech."""
    now = datetime.now()
    
    # Format for natural speech
    # Use cross-platform compatible format codes
    hour = now.hour % 12 or 12
    minute = now.strftime("%M")
    ampm = "AM" if now.hour < 12 else "PM"
    time_str = f"{hour}:{minute} {ampm}"
    
    day_name = now.strftime("%A")
    month_name = now.strftime("%B")
    day = now.day
    date_str = f"{day_name}, {month_name} {day}"
    
    return f"It's {time_str} on {date_str}."
