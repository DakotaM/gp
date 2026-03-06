import os
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
CHANNEL_ID = os.environ["SLACK_CHANNEL_ID"]


def post_digest_header() -> str:
    """Post the top-level digest message. Returns the thread timestamp (ts)."""
    today = datetime.utcnow()
    week_start = (today - timedelta(days=7)).strftime("%b %d")
    week_end = today.strftime("%b %d, %Y")

    text = (
        f":studio_microphone: *Weekly Podcast Digest* — {week_start}–{week_end}\n\n"
        f"This week's episodes summarized across your full list. "
        f"Each show gets its own reply below — scroll through and jump to what catches your eye.\n\n"
        f"_Reply to this thread anytime with feedback to shape next week's digest._"
    )

    resp = _client.chat_postMessage(channel=CHANNEL_ID, text=text, mrkdwn=True)
    return resp["ts"]


def post_episode_summary(thread_ts: str, podcast: str, title: str, summary: str, link: str = ""):
    """Post one episode digest as a threaded reply."""
    header = f"*{podcast}*"
    if link:
        header += f"  |  <{link}|:headphones: Listen>"

    full_text = f"{header}\n\n{summary}"

    # Slack caps blocks at ~3000 chars — chunk if needed
    chunks = _chunk_text(full_text, limit=2900)
    for chunk in chunks:
        _client.chat_postMessage(
            channel=CHANNEL_ID,
            thread_ts=thread_ts,
            text=chunk,
            mrkdwn=True,
        )


def post_recommendations(thread_ts: str, recommendations: str):
    """Post the recommendations section as a threaded reply."""
    text = f":bulb: *Recommendations This Week*\n\n{recommendations}"
    _client.chat_postMessage(
        channel=CHANNEL_ID,
        thread_ts=thread_ts,
        text=text,
        mrkdwn=True,
    )


def post_feedback_prompt(thread_ts: str):
    """Post the closing feedback prompt."""
    text = (
        "─────────────────────────────\n"
        ":speech_balloon: *Your feedback shapes next week's digest.*\n\n"
        "Reply here with anything useful:\n"
        "• Too long / too short on a specific show\n"
        "• Missed a key moment or topic\n"
        "• An episode was over- or under-rated\n"
        "• Tone, format, or anything else\n\n"
        "_All replies will be read before next Saturday's digest is generated._"
    )
    _client.chat_postMessage(
        channel=CHANNEL_ID,
        thread_ts=thread_ts,
        text=text,
        mrkdwn=True,
    )


def get_thread_replies(thread_ts: str) -> str:
    """
    Read all human replies in the previous digest thread.
    Returns them as a single string to pass into the summarization prompt.
    """
    try:
        resp = _client.conversations_replies(channel=CHANNEL_ID, ts=thread_ts)
        messages = resp.get("messages", [])
        # Skip index 0 (the original post), skip bot messages
        replies = [
            m["text"] for m in messages[1:]
            if not m.get("bot_id") and m.get("text")
        ]
        return "\n".join(replies) if replies else ""
    except SlackApiError as e:
        print(f"Could not read thread replies: {e}")
        return ""


def post_meeting_summary(summary_text: str, channel_id: str = None) -> str:
    """
    Post a meeting summary to a Slack channel.
    Returns the message timestamp (ts) for threading.

    Args:
        summary_text: Formatted meeting summary text (supports mrkdwn)
        channel_id: Optional channel ID override, defaults to CHANNEL_ID env var
    """
    target_channel = channel_id or CHANNEL_ID

    # Chunk if needed for long summaries
    chunks = _chunk_text(summary_text, limit=2900)
    ts = None

    for i, chunk in enumerate(chunks):
        if i == 0:
            # First chunk goes as main message
            resp = _client.chat_postMessage(
                channel=target_channel,
                text=chunk,
                mrkdwn=True,
            )
            ts = resp["ts"]
        else:
            # Additional chunks go in thread
            _client.chat_postMessage(
                channel=target_channel,
                thread_ts=ts,
                text=chunk,
                mrkdwn=True,
            )

    return ts


def post_meeting_to_channel(
    meeting_title: str,
    summary: str,
    action_items: list = None,
    channel_id: str = None
) -> str:
    """
    Post a structured meeting summary to Slack with action items.

    Args:
        meeting_title: Title of the meeting
        summary: Meeting summary text
        action_items: List of action item strings or dicts with 'task' and 'owner' keys
        channel_id: Optional channel ID override

    Returns:
        The message timestamp (ts)
    """
    target_channel = channel_id or CHANNEL_ID

    # Build the message
    lines = [
        f":studio_microphone: *Meeting Summary: {meeting_title}*",
        "",
        summary,
    ]

    if action_items:
        lines.append("")
        lines.append("*Next Steps:*")
        for item in action_items:
            if isinstance(item, dict):
                task = item.get("task", "")
                owner = item.get("owner", "")
                if owner:
                    lines.append(f"  - {task} (_{owner}_)")
                else:
                    lines.append(f"  - {task}")
            else:
                lines.append(f"  - {item}")

    full_text = "\n".join(lines)
    return post_meeting_summary(full_text, channel_id=target_channel)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk_text(text: str, limit: int = 2900) -> list:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to break on a newline
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
