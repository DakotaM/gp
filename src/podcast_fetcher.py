import hashlib
import time
import requests
import os
from datetime import datetime, timedelta

PODCAST_INDEX_BASE = "https://api.podcastindex.org/api/1.0"

PODCASTS = [
    {"name": "TBPN", "search": "TBPN Turpentine Business podcast"},
    {"name": "All-In Podcast", "search": "All-In Pod Chamath Palihapitiya Jason Calacanis"},
    {"name": "Invest Like the Best", "search": "Invest Like the Best Patrick O'Shaughnessy"},
    {"name": "Uncapped with Jack Altman", "search": "Uncapped Jack Altman"},
    {"name": "Cheeky Pint", "search": "Cheeky Pint"},
    {"name": "Lenny's Podcast", "search": "Lenny's Podcast Product Growth"},
    {"name": "Dwarkesh Podcast", "search": "Dwarkesh Patel Podcast"},
    {"name": "Stratechery", "search": "Stratechery Ben Thompson", "free_only": True},
    {"name": "Long Strange Trip", "search": "Long Strange Trip CEO Brian Halligan"},
    {"name": "a16z Podcast", "search": "a16z Andreessen Horowitz Podcast"},
    {"name": "The Riff", "search": "The Riff Turpentine Erik Torenberg"},
    {"name": "Turpentine VC", "search": "Turpentine VC Startup Investing"},
    {"name": "Dalton and Michael", "search": "Dalton Caldwell Michael Seibel YC"},
]


def _get_headers():
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
    try:
        resp = requests.get(
            f"{PODCAST_INDEX_BASE}/search/byterm",
            params={"q": search_term, "max": 3},
            headers=_get_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        feeds = resp.json().get("feeds", [])
        return feeds[0]["id"] if feeds else None
    except Exception as e:
        print(f"  Feed search error: {e}")
        return None


def _get_recent_episodes(feed_id, days=7):
    since = int((datetime.utcnow() - timedelta(days=days)).timestamp())
    try:
        resp = requests.get(
            f"{PODCAST_INDEX_BASE}/episodes/byfeedid",
            params={"id": feed_id, "since": since, "max": 1},
            headers=_get_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        print(f"  Episode fetch error: {e}")
        return []


def _fetch_transcript(episode):
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
