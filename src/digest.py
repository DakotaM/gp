"""
digest.py — main entry point for the weekly podcast digest.
Run from the src/ directory: python digest.py
"""

import json
import os
import sys

# Make sure sibling modules are importable when run directly
sys.path.insert(0, os.path.dirname(__file__))

from podcast_fetcher import fetch_all_episodes
from summarize import summarize_episode, generate_recommendations
from slack_client import (
    post_digest_header,
    post_episode_summary,
    post_recommendations,
    post_feedback_prompt,
    get_thread_replies,
)

# Stored one directory up (repo root) so the GitHub Actions artifact step finds it
THREAD_TS_FILE = os.path.join(os.path.dirname(__file__), "..", "thread_ts.json")


def load_previous_thread_ts() -> str | None:
    path = os.path.abspath(THREAD_TS_FILE)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("thread_ts")
    return None


def save_thread_ts(ts: str):
    path = os.path.abspath(THREAD_TS_FILE)
    with open(path, "w") as f:
        json.dump({"thread_ts": ts}, f)


def main():
    # -------------------------------------------------------------------------
    # Step 1: Load last week's feedback from Slack thread replies
    # -------------------------------------------------------------------------
    print("\n📖 Loading previous feedback...")
    previous_ts = load_previous_thread_ts()
    feedback = ""
    if previous_ts:
        feedback = get_thread_replies(previous_ts)
        if feedback:
            print(f"  Found feedback ({len(feedback)} chars)")
        else:
            print("  No feedback found from last week")
    else:
        print("  First run — no previous thread")

    # -------------------------------------------------------------------------
    # Step 2: Fetch this week's episodes
    # -------------------------------------------------------------------------
    print("\n📡 Fetching episodes from Podcast Index...")
    episodes = fetch_all_episodes()
    print(f"\n  {len(episodes)} episode(s) found across all podcasts")

    if not episodes:
        print("Nothing to post this week. Exiting.")
        return

    # -------------------------------------------------------------------------
    # Step 3: Post the digest header and save the thread ts
    # -------------------------------------------------------------------------
    print("\n📨 Posting digest header to Slack...")
    thread_ts = post_digest_header()
    save_thread_ts(thread_ts)
    print(f"  Thread ts: {thread_ts}")

    # -------------------------------------------------------------------------
    # Step 4: Summarize and post each episode
    # -------------------------------------------------------------------------
    all_summaries = []

    for episode in episodes:
        label = f"{episode['podcast']} — {episode['title']}"
        print(f"\n✍️  Summarizing: {label}")

        summary = summarize_episode(episode, feedback=feedback or "None yet.")

        post_episode_summary(
            thread_ts=thread_ts,
            podcast=episode["podcast"],
            title=episode["title"],
            summary=summary,
            link=episode.get("link", ""),
        )

        all_summaries.append({
            "podcast": episode["podcast"],
            "title": episode["title"],
            "summary": summary,
        })
        print(f"  ✓ Posted")

    # -------------------------------------------------------------------------
    # Step 5: Post recommendations
    # -------------------------------------------------------------------------
    print("\n💡 Generating recommendations...")
    recs = generate_recommendations(all_summaries)
    post_recommendations(thread_ts, recs)

    # -------------------------------------------------------------------------
    # Step 6: Post the feedback prompt so the reader knows to reply
    # -------------------------------------------------------------------------
    post_feedback_prompt(thread_ts)

    print("\n✅ Weekly digest posted successfully.\n")


if __name__ == "__main__":
    main()
