import anthropic
import os
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ---------------------------------------------------------------------------
# Episode summary prompt
# ---------------------------------------------------------------------------

EPISODE_PROMPT = """\
You are writing a weekly podcast digest for a VC fund manager who follows AI, \
developer infrastructure, startups, and investment trends closely. \
Your reader wants to know what is worth their time and what they can skip.

Write a digest entry for the episode below. Structure it exactly like this:

---

**{podcast} — {title}**
_{date}_

**Themes & Context**
[1–2 paragraphs connecting this episode's main ideas to the broader tech and VC \
news happening this week. Be specific — name the companies, debates, or macro forces \
this episode speaks to. If the relevance score you assign is 4 or 5, write 3 paragraphs.]

**Key Moments Worth Your Time**
[2–5 bullet points. Each should be a specific, substantive moment from the episode. \
Include approximate timestamps in the format `[~HH:MM]` wherever you can infer them \
from the transcript. Format: `[~timestamp] — What happens and why it matters.` \
If no transcript is available, surface the most interesting claims from the description.]

**Verdict:** [One sentence. One of: "Listen fully", "Jump to [specific sections]", or "Skip — here's why."]

**Relevance Score:** [X/5] — [One sentence justification.]

---

Be direct. Be opinionated. No filler. Write like a sharp colleague who already listened.

---

EPISODE INFO
Podcast: {podcast}
Title: {title}
Published: {date}
Duration: {duration}

Description:
{description}

Transcript (may be partial or absent):
{transcript}

Reader feedback from last week to incorporate:
{feedback}

Write the digest entry now.
"""

# ---------------------------------------------------------------------------
# Recommendations prompt
# ---------------------------------------------------------------------------

RECOMMENDATIONS_PROMPT = """\
Based on the weekly themes gathered from the podcasts below, recommend 2–3 additional \
pieces of content the reader should check out this week. These can be essays, newsletters, \
YouTube videos, Twitter/X threads, or other podcast episodes — anything that would add \
genuine signal to what they've already heard.

Only recommend things that complement or go deeper on this week's themes. \
Do not pad with generic suggestions.

Weekly themes:
{themes}

Format each as:
• **[Title / Source / Author]** — One sentence on why it's relevant this week and where to find it.
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def summarize_episode(episode: dict, feedback: str = "None yet.") -> str:
    duration_min = episode.get("duration", 0) // 60
    duration_str = f"{duration_min} min" if duration_min else "Unknown length"

    transcript_text = episode.get("transcript") or (
        "No transcript available. Base your key moments on the description only, "
        "and note that timestamps are estimated."
    )

    prompt = EPISODE_PROMPT.format(
        podcast=episode["podcast"],
        title=episode["title"],
        date=_format_date(episode.get("date_published", 0)),
        duration=duration_str,
        description=(episode.get("description") or "")[:2000],
        transcript=transcript_text[:40000],
        feedback=feedback,
    )

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def generate_recommendations(all_summaries: list) -> str:
    themes_block = "\n\n".join(
        f"**{s['podcast']} — {s['title']}**\n{s['summary'][:600]}"
        for s in all_summaries
    )

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=800,
        messages=[
            {"role": "user", "content": RECOMMENDATIONS_PROMPT.format(themes=themes_block)}
        ],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_date(unix_ts: int) -> str:
    if not unix_ts:
        return "Unknown date"
    try:
        return datetime.utcfromtimestamp(unix_ts).strftime("%B %d, %Y")
    for attempt in range(5):
        try:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except anthropic.OverloadedError:
            if attempt < 4:
                wait = 60 * (attempt + 1)
                print(f"  API overloaded, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
