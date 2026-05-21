from typing import List, Dict, Any


def sec_to_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def timestamp_to_sec(timestamp: str) -> float:
    """Convert HH:MM:SS or MM:SS to seconds."""
    parts = timestamp.split(":")
    if len(parts) == 3:
        h, m, s = map(int, parts)
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = map(int, parts)
        return m * 60 + s
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}")


def create_windows(
    duration_seconds: float, window_size: int = 30
) -> List[Dict[str, float]]:
    """Create timeline windows for analysis."""
    windows = []
    start = 0.0

    while start < duration_seconds:
        end = min(start + window_size, duration_seconds)
        windows.append({"start_sec": start, "end_sec": end})
        start = end

    return windows


def merge_overlapping_windows(
    windows: List[Dict[str, Any]], overlap_threshold: float = 5.0
) -> List[Dict[str, Any]]:
    """Merge windows that overlap significantly."""
    if not windows:
        return []

    # Sort by start time
    sorted_windows = sorted(windows, key=lambda w: w["start_sec"])
    merged = [sorted_windows[0].copy()]

    for window in sorted_windows[1:]:
        last = merged[-1]
        if window["start_sec"] - last["end_sec"] < overlap_threshold:
            # Merge
            last["end_sec"] = max(last["end_sec"], window["end_sec"])
            # Merge other fields as needed
            if "issues" in window and "issues" in last:
                last["issues"] = list(set(last["issues"] + window["issues"]))
        else:
            merged.append(window.copy())

    return merged


def find_window_for_timestamp(
    windows: List[Dict[str, float]], timestamp: float
) -> Dict[str, float]:
    """Find the window containing a specific timestamp."""
    for window in windows:
        if window["start_sec"] <= timestamp <= window["end_sec"]:
            return window
    return None
