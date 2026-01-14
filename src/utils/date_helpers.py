"""Date and time utility functions."""

from datetime import datetime, timedelta, timezone
from typing import Optional


def parse_iso_datetime(iso_string: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO format datetime string to datetime object.

    Args:
        iso_string: ISO format datetime string (e.g., "2024-01-15T10:30:00Z")

    Returns:
        datetime object or None if parsing fails
    """
    if not iso_string:
        return None

    try:
        # Handle 'Z' suffix for UTC
        normalized = iso_string.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_game_time(minutes: int, added_time: int = 0) -> str:
    """
    Format game time for display in podcast.

    Args:
        minutes: Current game minute
        added_time: Added/injury time minutes

    Returns:
        Formatted string like "45+2" or "90"
    """
    if added_time > 0:
        return f"{minutes}+{added_time}"
    return str(minutes)


def is_within_hours(dt: Optional[datetime], hours: int, future: bool = True) -> bool:
    """
    Check if datetime is within specified hours from now.

    Args:
        dt: Datetime to check
        hours: Number of hours
        future: If True, check future; if False, check past

    Returns:
        True if within range
    """
    if not dt:
        return False

    now = datetime.now(timezone.utc)

    # Ensure dt is timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = timedelta(hours=hours)

    if future:
        return now <= dt <= now + delta
    else:
        return now - delta <= dt <= now


def format_datetime_for_speech(dt: Optional[datetime]) -> str:
    """
    Format datetime for natural speech in podcast.

    Args:
        dt: Datetime to format

    Returns:
        Human-readable string like "Saturday at 3 PM"
    """
    if not dt:
        return "an unknown time"

    # Format for speech
    day_name = dt.strftime("%A")
    hour = dt.strftime("%I").lstrip("0")
    am_pm = dt.strftime("%p").upper()

    return f"{day_name} at {hour} {am_pm}"


def get_date_range_for_recap(hours_back: int = 24, hours_forward: int = 24) -> tuple[str, str]:
    """
    Get date range strings for API queries.

    Args:
        hours_back: Hours to look back for ended games
        hours_forward: Hours to look forward for upcoming games

    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours_back)
    end = now + timedelta(hours=hours_forward)

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
