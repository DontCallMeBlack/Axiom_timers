import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

def parse_timestamp(timestamp_str):
    """Parse a timestamp string and ensure it's UTC."""
    try:
        if not timestamp_str:
            return None
            
        dt = datetime.fromisoformat(timestamp_str)
        
        # If the timestamp has no timezone info, assume it's UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.error(f"Error parsing timestamp {timestamp_str}: {e}")
        return None

def get_current_utc():
    """Get current time in UTC."""
    return datetime.now(timezone.utc)