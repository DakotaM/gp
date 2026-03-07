"""
timestamp_links.py — converts [~HH:MM] timestamps in summary text
into clickable platform-aware deep links using the episode URL.
"""

import re


def detect_platform(url: str) -> str:
    if not url:
        return "default"
    url = url.lower()
    if "spotify.com" in url:
        return "spotify"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "podcasts.apple.com" in url or "itunes.apple.com" in url:
        return "apple"
    return "default"


def hms_to_seconds(timestamp: str) -> int:
    """Convert HH:MM or MM:SS string to total seconds."""
    parts = timestamp.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        pass
    return 0


def build_timestamp_link(episode_url: str, seconds: int, platform: str) -> str:
    """Build a platform-aware deep link URL."""
    sep = "&" if "?" in episode_url else "?"
    if platform == "spotify":
        return f"{episode_url}{sep}t={seconds}"
    elif platform == "youtube":
        return f"{episode_url}{sep}t={seconds}s"
    elif platform == "apple":
        m = seconds // 60
        s = str(seconds % 60).zfill(2)
        return f"{episode_url}#t={m}:{s}"
    return episode_url


def linkify_timestamps(summary_text: str, episode_url: str) -> str:
    """
    Find all [~HH:MM] or [~MM:SS] patterns in summary text and replace
    them with Slack-formatted clickable links.

    Input:  [~18:42] — Great explanation of the framework.
    Output: <https://open.spotify.com/episode/abc?t=1122|[~18:42]> — Great explanation.
    """
    if not episode_url:
        return summary_text

    platform = detect_platform(episode_url)
    pattern = re.compile(r'\[~(\d{1,2}:\d{2}(?::\d{2})?)\]')

    def replace_match(m):
        ts_str = m.group(1)
        seconds = hms_to_seconds(ts_str)
        if seconds == 0:
            return m.group(0)  # leave unchanged if we can't parse
        link = build_timestamp_link(episode_url, seconds, platform)
        return f"<{link}|[~{ts_str}]>"

    return pattern.sub(replace_match, summary_text)
