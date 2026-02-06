"""Utility functions for time formatting"""

def format_hours_to_hhmm(hours: float) -> str:
    """Convert decimal hours (e.g., 1.5) to HH:MM format (e.g., 1:30)
    
    Args:
        hours: Decimal hours (e.g., 1.5, 8.25)
    
    Returns:
        Formatted string in HH:MM format (e.g., "1:30", "8:15")
    """
    if hours is None or hours < 0:
        return "0:00"
    
    whole_hours = int(hours)
    minutes = int((hours - whole_hours) * 60)
    
    return f"{whole_hours}:{minutes:02d}"

def format_hours_to_text(hours: float) -> str:
    """Convert decimal hours to human-readable text format
    
    Args:
        hours: Decimal hours (e.g., 1.5, 8.25)
    
    Returns:
        Formatted string (e.g., "1 ч 30 мин", "8 ч 15 мин")
    """
    if hours is None or hours < 0:
        return "0 ч"
    
    whole_hours = int(hours)
    minutes = int((hours - whole_hours) * 60)
    
    if whole_hours == 0:
        return f"{minutes} мин"
    elif minutes == 0:
        return f"{whole_hours} ч"
    else:
        return f"{whole_hours} ч {minutes} мин"
