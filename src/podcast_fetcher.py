import hashlib
import time
import requests
import os
from datetime import datetime, timedelta

PODCAST_INDEX_BASE = "https://api.podcastindex.org/api/1.0"

# Your podcast list — search terms tuned for Podcast Index accuracy
PODCASTS = [
    PODCASTS = [
    {"name": "TBPN", "search": "TBPN.com"},
    {"name": "All-In Podcast", "search": "All-In with Chamath Jason Sacks David"},
    {"name": "Invest Like the Best", "search": "Invest Like the Best"},
    {"name": "Uncapped with Jack Altman", "search": "Uncapped Jack Altman"},
    {"name": "Cheeky Pint", "search": "Cheeky Pint"},
    {"name": "Lenny's Podcast", "search": "Lenny Rachitsky Product"},
    {"name": "Dwarkesh Podcast", "search": "Dwarkesh Patel"},
    {"name": "Stratechery", "search": "Stratechery Daily Update Ben Thompson", "free_only": True},
    {"name": "Long Strange Trip: CEO to CEO", "search": "Long Strange Trip Brian Halligan"},
    {"name": "a16z Podcast", "search": "a16z podcast technology culture"},
    {"name": "The Riff", "search": "The Riff Erik Torenberg Turpentine"},
    {"name": "Turpentine VC", "search": "Turpentine VC venture capital"},
    {"name": "Dalton & Michael", "search": "Dalton Caldwell Michael Seibel"},
],
]


def _get_headers():
    """Build Podcast Index auth headers. Required on every request."""
    api_key = os.environ["PODCAST_INDEX_API_KEY"]
    api_secret = os.environ["PODCAST_INDEX_API_SECRET"]
    epoch_time = int(time.time())
    sha1_hash = hashlib.sha1(
        (api_key + api_secret + str(epoch_time)).encode()
    ).hexdigest()
    return {
        "X-Auth-Date": str(epoch_time),
        "X-Auth-Key": api_key,
        "Authorization": sha1_hash,
        "User-Agent": "PodcastDigestBot/1.0",
    }


def _search_feed_id(search_term):
    """Return the Podcast Index feed ID for the best match."""
    resp = requests.get(
        f"{PODCAST_INDEX_BASE}/search/byterm",
        params={"q": search_term, "max": 1},
        headers=_get_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    feeds = resp.json().get("feeds", [])
    return feeds[0]["id"] if feeds else None


def _get_recent_episodes(feed_id, days=7):
    """Return episodes published in the last `days` days."""
    since = int((datetime.utcnow() - timedelta(days=days)).timestamp())
    resp = requests.get(
        f"{PODCAST_INDEX_BASE}/episodes/byfeedid",
        params={"id": feed_id, "since": since, "max": 10},
        headers=_get_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def _fetch_transcript(episode):
    """
    Try to pull a transcript from the episode's transcripts array.
    Podcast Index surfaces VTT / SRT / plain-text URLs when podcasters publish them.
    Returns raw text (capped at 60k chars) or None.
    """
    for t in episode.get("transcripts", []):
        url = t.get("url", "")
        if not url:
            continue
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.text[:60000]
        except Exception:
            continue
    return None


def fetch_all_episodes():
    """
    Main entry point. Returns a list of episode dicts ready for summarization.
    """
    results = []

    for podcast in PODCASTS:
        print(f"→ {podcast['name']}")
        feed_id = _search_feed_id(podcast["search"])
        if not feed_id:
            print(f"  ⚠ Could not find feed — skipping")
            continue

        episodes = _get_recent_episodes(feed_id)
        if not episodes:
            print(f"  No new episodes this week")
            continue

        for ep in episodes:
            # For Stratechery, skip paywalled episodes (they have no enclosure or a login URL)
            if podcast.get("free_only"):
                description = ep.get("description", "").lower()
                if "members only" in description or "subscriber" in description:
                    print(f"  Skipping paywalled: {ep.get('title')}")
                    continue

            transcript = _fetch_transcript(ep)
            print(f"  ✓ {ep.get('title')} {'[transcript found]' if transcript else '[no transcript]'}")

            results.append({
                "podcast": podcast["name"],
                "title": ep.get("title", "Untitled"),
                "description": ep.get("description", ""),
                "duration": ep.get("duration", 0),
                "link": ep.get("link", ""),
                "date_published": ep.get("datePublished", 0),
                "transcript": transcript,
            })

    return results
