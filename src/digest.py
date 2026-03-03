"""
digest.py — main entry point for the weekly podcast digest.
Run from the src/ directory: python digest.py
"""

import json
import os
import sys
import time

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

THREAD_TS_FILE = os.path.join(os.path.dirname(__file__), "..", "thread_ts.json")
PAUSE_BETWEEN_EPISODES = 45  # seconds between API calls


def load_previous_thread_ts():
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
    # Step 1: Load last week's feedback
    # -------------------------------------------------------------------------
    print("\n📖 Loading previous feedback...")
    previous_ts = load_previous_thread_ts()
    feedback = ""
    if previous_ts:
        feedback = get_thread_replies(previous_ts)
        print(f"  Found feedback ({len(feedback)} chars)" if feedback else "  No feedback from last week")
    else:
        print("  First run — no previous thread")

    # -------------------------------------------------------------------------
    # Step 2: Fetch episodes
    # -------------------------------------------------------------------------
    print("\n📡 Fetching episodes from Podcast Index...")
    episodes = fetch_all_episodes()
    print(f"\n  {len(episodes)} episode(s) found")

    if not episodes:
        print("Nothing to post this week. Exiting.")
        return

    # -------------------------------------------------------------------------
    # Step 3: Post digest header
    # -------------------------------------------------------------------------
    print("\n📨 Posting digest header to Slack...")
    thread_ts = post_digest_header()
    save_thread_ts(thread_ts)
    print(f"  Thread ts: {thread_ts}")

    # -------------------------------------------------------------------------
    # Step 4: Summarize all episodes, collect into one document
    # -------------------------------------------------------------------------
    all_summaries = []
    full_digest_parts = []

    for i, episode in enumerate(episodes):
        label = f"{episode['podcast']} — {episode['title']}"
        print(f"\n✍️  [{i+1}/{len(episodes)}] Summarizing: {label}")

        try:
            summary = summarize_episode(episode, feedback=feedback or "None yet.")
            all_summaries.append({
                "podcast": episode["podcast"],
                "title": episode["title"],
                "summary": summary,
                "link": episode.get("link", ""),
            })
            full_digest_parts.append(summary)
            print(f"  ✓ Done")
        except Exception as e:
            print(f"  ⚠ Failed — skipping. Error: {e}")

        if i < len(episodes) - 1:
            print(f"  Pausing {PAUSE_BETWEEN_EPISODES}s...")
            time.sleep(PAUSE_BETWEEN_EPISODES)

    # -------------------------------------------------------------------------
    # Step 5: Post all summaries as one combined document
    # -------------------------------------------------------------------------
    print("\n📬 Posting full digest to Slack...")
    divider = "\n\n" + "─" * 40 + "\n\n"
    full_digest = divider.join(full_digest_parts)
    post_episode_summary(
        thread_ts=thread_ts,
        podcast="",
        title="",
        summary=full_digest,
        link="",
    )

    # -------------------------------------------------------------------------
    # Step 6: Recommendations
    # -------------------------------------------------------------------------
    if all_summaries:
        print("\n💡 Generating recommendations...")
        try:
            recs = generate_recommendations(all_summaries)
            post_recommendations(thread_ts, recs)
        except Exception as e:
            print(f"  ⚠ Recommendations failed: {e}")

    # -------------------------------------------------------------------------
    # Step 7: Feedback prompt
    # -------------------------------------------------------------------------
    post_feedback_prompt(thread_ts)

    print("\n✅ Weekly digest posted successfully.\n")


if __name__ == "__main__":
    main()
