"""
granola_client.py — Interface with Granola MCP server to fetch meeting notes.

Granola MCP provides access to meeting transcripts and summaries.
This module handles fetching recent meetings and filtering by participant/company.
"""

import json
import os
import subprocess
from datetime import datetime, timedelta
from typing import Optional


# Default MCP server command - can be overridden via environment variable
GRANOLA_MCP_COMMAND = os.environ.get(
    "GRANOLA_MCP_COMMAND",
    "npx -y @anthropic-ai/mcp-client granola"
)


def _call_mcp(method: str, params: Optional[dict] = None) -> dict:
    """
    Call the Granola MCP server using the MCP protocol.
    Returns the result from the MCP response.
    """
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }

    try:
        result = subprocess.run(
            GRANOLA_MCP_COMMAND.split(),
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise RuntimeError(f"MCP call failed: {result.stderr}")

        response = json.loads(result.stdout)
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")

        return response.get("result", {})
    except subprocess.TimeoutExpired:
        raise RuntimeError("MCP call timed out")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid MCP response: {e}")


def get_recent_meetings(days: int = 1) -> list:
    """
    Fetch meetings from the last N days.
    Returns a list of meeting objects with title, date, participants, summary, etc.
    """
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    result = _call_mcp("tools/call", {
        "name": "get_meetings",
        "arguments": {
            "since": since,
            "include_transcript": False,
            "include_summary": True
        }
    })

    return result.get("meetings", [])


def get_meeting_summary(meeting_id: str) -> dict:
    """
    Fetch the full summary and details for a specific meeting.
    """
    result = _call_mcp("tools/call", {
        "name": "get_meeting",
        "arguments": {
            "meeting_id": meeting_id,
            "include_transcript": True,
            "include_summary": True,
            "include_action_items": True
        }
    })

    return result


def get_meetings_with_company(company_name: str, days: int = 1) -> list:
    """
    Fetch meetings from the last N days that involve a specific company.
    Filters by meeting title, participants, or company field.
    """
    meetings = get_recent_meetings(days=days)

    company_lower = company_name.lower()
    matching = []

    for meeting in meetings:
        # Check meeting title
        title = meeting.get("title", "").lower()
        if company_lower in title:
            matching.append(meeting)
            continue

        # Check participants
        participants = meeting.get("participants", [])
        for p in participants:
            if company_lower in p.get("name", "").lower():
                matching.append(meeting)
                break
            if company_lower in p.get("company", "").lower():
                matching.append(meeting)
                break

        # Check company/organization field
        if company_lower in meeting.get("company", "").lower():
            matching.append(meeting)
            continue
        if company_lower in meeting.get("organization", "").lower():
            matching.append(meeting)

    return matching


def format_meeting_for_slack(meeting: dict) -> str:
    """
    Format a meeting summary for posting to Slack.
    Returns a nicely formatted Slack message with mrkdwn.
    """
    title = meeting.get("title", "Untitled Meeting")
    date = meeting.get("date", "")
    summary = meeting.get("summary", "No summary available.")
    action_items = meeting.get("action_items", [])
    participants = meeting.get("participants", [])

    # Format date
    if date:
        try:
            dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
            date_str = dt.strftime("%B %d, %Y at %I:%M %p")
        except ValueError:
            date_str = date
    else:
        date_str = "Unknown date"

    # Build participant list
    if participants:
        participant_names = [p.get("name", "Unknown") for p in participants]
        participants_str = ", ".join(participant_names)
    else:
        participants_str = "Not recorded"

    # Build the Slack message
    lines = [
        f":studio_microphone: *Meeting Summary: {title}*",
        f"_Date: {date_str}_",
        f"_Participants: {participants_str}_",
        "",
        "*Summary:*",
        summary,
    ]

    # Add action items if present
    if action_items:
        lines.append("")
        lines.append("*Action Items:*")
        for item in action_items:
            owner = item.get("owner", "")
            task = item.get("task", item) if isinstance(item, dict) else item
            if owner:
                lines.append(f"  - {task} (_{owner}_)")
            else:
                lines.append(f"  - {task}")

    return "\n".join(lines)
