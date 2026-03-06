#!/usr/bin/env python3
"""
granola_slack_sync.py — Automatically post Granola meeting summaries to Slack.

This script fetches recent meetings from Granola MCP and posts summaries
to Slack for meetings that match specified criteria (e.g., meetings with Perpetual).

Usage:
    # Post all meetings with Perpetual from the last 24 hours
    python granola_slack_sync.py --company Perpetual

    # Check for new meetings every 15 minutes
    python granola_slack_sync.py --company Perpetual --watch

    # Post to a specific channel
    python granola_slack_sync.py --company Perpetual --channel C0AH3K9TV9C

Environment Variables:
    SLACK_BOT_TOKEN: Slack bot token with chat:write permission
    SLACK_CHANNEL_ID: Default channel to post to
    GRANOLA_MCP_COMMAND: Optional override for MCP server command
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from granola_client import (
    get_meetings_with_company,
    get_meeting_summary,
    format_meeting_for_slack,
)
from slack_client import post_meeting_summary


# Track which meetings we've already posted
POSTED_MEETINGS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "posted_meetings.json"
)


def load_posted_meetings() -> set:
    """Load the set of meeting IDs we've already posted."""
    path = os.path.abspath(POSTED_MEETINGS_FILE)
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            return set(data.get("meeting_ids", []))
    return set()


def save_posted_meetings(meeting_ids: set):
    """Save the set of posted meeting IDs."""
    path = os.path.abspath(POSTED_MEETINGS_FILE)
    with open(path, "w") as f:
        json.dump({
            "meeting_ids": list(meeting_ids),
            "last_updated": datetime.utcnow().isoformat()
        }, f, indent=2)


def sync_meetings(company: str, channel_id: str = None, days: int = 1) -> int:
    """
    Fetch meetings with the specified company and post new ones to Slack.

    Args:
        company: Company name to filter meetings by
        channel_id: Slack channel ID to post to
        days: Number of days back to check for meetings

    Returns:
        Number of new meetings posted
    """
    print(f"\nFetching meetings with {company} from the last {days} day(s)...")

    try:
        meetings = get_meetings_with_company(company, days=days)
    except Exception as e:
        print(f"  Error fetching meetings: {e}")
        return 0

    if not meetings:
        print(f"  No meetings found with {company}")
        return 0

    print(f"  Found {len(meetings)} meeting(s) with {company}")

    # Load already-posted meetings
    posted_ids = load_posted_meetings()
    new_posted = 0

    for meeting in meetings:
        meeting_id = meeting.get("id", meeting.get("meeting_id"))
        if not meeting_id:
            # Generate a pseudo-ID from title and date
            meeting_id = f"{meeting.get('title', '')}-{meeting.get('date', '')}"

        if meeting_id in posted_ids:
            print(f"  Skipping already-posted: {meeting.get('title', 'Untitled')}")
            continue

        # Get full meeting details if needed
        if "summary" not in meeting or not meeting["summary"]:
            try:
                meeting = get_meeting_summary(meeting_id)
            except Exception as e:
                print(f"  Could not fetch details for {meeting_id}: {e}")
                continue

        # Format and post to Slack
        title = meeting.get("title", "Untitled Meeting")
        print(f"  Posting: {title}")

        try:
            slack_text = format_meeting_for_slack(meeting)
            post_meeting_summary(slack_text, channel_id=channel_id)
            posted_ids.add(meeting_id)
            new_posted += 1
            print(f"    Posted successfully")
        except Exception as e:
            print(f"    Failed to post: {e}")

    # Save updated posted meetings list
    save_posted_meetings(posted_ids)

    return new_posted


def watch_mode(company: str, channel_id: str, interval_minutes: int = 15):
    """
    Continuously watch for new meetings and post them.

    Args:
        company: Company name to filter meetings by
        channel_id: Slack channel ID to post to
        interval_minutes: How often to check for new meetings
    """
    print(f"\nWatching for new {company} meetings (checking every {interval_minutes} min)")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            new_count = sync_meetings(company, channel_id=channel_id, days=1)
            if new_count > 0:
                print(f"  Posted {new_count} new meeting(s)")
            else:
                print(f"  No new meetings to post")
        except Exception as e:
            print(f"  Error during sync: {e}")

        next_check = datetime.now().strftime("%H:%M")
        print(f"  Next check in {interval_minutes} minutes...")

        try:
            time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            print("\nStopping watch mode.")
            break


def main():
    parser = argparse.ArgumentParser(
        description="Sync Granola meeting summaries to Slack"
    )
    parser.add_argument(
        "--company", "-c",
        required=True,
        help="Company name to filter meetings by (e.g., Perpetual)"
    )
    parser.add_argument(
        "--channel",
        help="Slack channel ID to post to (defaults to SLACK_CHANNEL_ID env var)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=1,
        help="Number of days back to check for meetings (default: 1)"
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Continuously watch for new meetings"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=15,
        help="Minutes between checks in watch mode (default: 15)"
    )

    args = parser.parse_args()

    if args.watch:
        watch_mode(args.company, args.channel, args.interval)
    else:
        posted = sync_meetings(args.company, channel_id=args.channel, days=args.days)
        print(f"\nDone. Posted {posted} new meeting summary(ies).\n")


if __name__ == "__main__":
    main()
