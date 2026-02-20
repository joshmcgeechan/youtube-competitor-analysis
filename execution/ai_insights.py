"""AI-powered insights via the Claude API.

Generates comparative analysis, video ideas, and strategic takeaways
from YouTube analytics data using Claude Sonnet.

Usage:
    # Called by main.py pipeline:
    from ai_insights import generate_insights
    insights = generate_insights(analytics)

    # Standalone test:
    python execution/ai_insights.py
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv


MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096

SYSTEM_PROMPT = (
    "You are an expert YouTube strategist analyzing competitive channel data. "
    "You provide specific, data-backed insights — never generic advice. "
    "Always reference actual channel names, video titles, and metrics from the "
    "data provided. Your recommendations are actionable and tailored to the "
    "specific channels being analyzed."
)


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context(analytics: dict) -> str:
    """Build a concise text summary of analytics data for Claude prompts."""
    channel = analytics["channel"]
    competitors = analytics["competitors"]
    comparative = analytics["comparative"]

    lines = []

    # Your channel
    lines.append("=== YOUR CHANNEL ===")
    lines.append(f"Name: {channel['channel_name']}")
    lines.append(f"Subscribers: {channel['subscriber_count']:,}")
    lines.append(f"Period Views: {channel['total_period_views']:,}")
    lines.append(f"Videos Published: {channel['video_count']}")
    lines.append(f"Avg Engagement: {channel['avg_engagement']:.2f}%")
    lines.append(f"Upload Frequency: {channel['upload_frequency']:.1f}/week")
    lines.append("Top Videos:")
    for v in channel["top_videos"][:5]:
        lines.append(
            f"  - \"{v['title']}\" — {v['views']:,} views, "
            f"{v['engagement']:.1f}% eng, {v['outlier_score']:.2f}x outlier"
        )

    # Competitors
    for comp in competitors:
        lines.append(f"\n=== COMPETITOR: {comp['channel_name']} ===")
        lines.append(f"Subscribers: {comp['subscriber_count']:,}")
        lines.append(f"Period Views: {comp['total_period_views']:,}")
        lines.append(f"Videos Published: {comp['video_count']}")
        lines.append(f"Avg Engagement: {comp['avg_engagement']:.2f}%")
        lines.append(f"Upload Frequency: {comp['upload_frequency']:.1f}/week")
        lines.append("Top Videos:")
        for v in comp["top_videos"][:5]:
            lines.append(
                f"  - \"{v['title']}\" — {v['views']:,} views, "
                f"{v['engagement']:.1f}% eng, {v['outlier_score']:.2f}x outlier"
            )

    # Comparative rankings
    lines.append("\n=== COMPARATIVE RANKINGS ===")
    lines.append("Views Ranking:")
    for r in comparative["views_ranking"]:
        lines.append(f"  {r['channel_name']}: {r['total_period_views']:,}")
    lines.append("Engagement Ranking:")
    for r in comparative["engagement_ranking"]:
        lines.append(f"  {r['channel_name']}: {r['avg_engagement']:.2f}%")
    lines.append(f"Top Performer: {comparative['top_performer']}")

    # Cross-channel leaderboard
    lines.append("\nCross-Channel Outlier Leaderboard:")
    for v in comparative["cross_channel_leaderboard"][:10]:
        lines.append(
            f"  - \"{v['title']}\" by {v['channel_name']} — "
            f"{v['views']:,} views, {v['outlier_score']:.2f}x outlier, "
            f"{v['engagement']:.1f}% eng"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Individual insight generators
# ---------------------------------------------------------------------------

def generate_comparative_analysis(analytics: dict, client: anthropic.Anthropic) -> dict:
    """Generate comparative analysis narrative via Claude API.

    Returns:
        {overview, key_trends, content_gaps, top_performer_note}
    """
    context = _build_context(analytics)
    channel_name = analytics["channel"]["channel_name"]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Analyze this YouTube competitive landscape data for {channel_name}.\n\n"
                    f"{context}\n\n"
                    "Return a JSON object with exactly this structure:\n"
                    "{\n"
                    '  "overview": "2-3 sentence summary of the competitive landscape, '
                    'referencing specific channels and metrics",\n'
                    '  "key_trends": [\n'
                    '    "Trend 1 — specific, referencing channel names and video performance",\n'
                    '    "Trend 2 — specific",\n'
                    '    "Trend 3 — specific"\n'
                    "  ],\n"
                    '  "content_gaps": [\n'
                    f'    "Gap 1 — topics or formats competitors cover that {channel_name} '
                    'doesn\'t, backed by data",\n'
                    '    "Gap 2 — specific",\n'
                    '    "Gap 3 — specific"\n'
                    "  ],\n"
                    '  "top_performer_note": "One short line with a key efficiency metric like '
                    "avg views per video and the number, highlighting content quality — "
                    'max 80 characters"\n'
                    "}\n\n"
                    "Return ONLY valid JSON, no other text."
                ),
            },
            {
                "role": "assistant",
                "content": "{",
            },
        ],
    )

    raw = "{" + response.content[0].text
    return json.loads(raw)


def _load_hooks_sop() -> str:
    """Load the hooks SOP from directives/sops/hooks.md if it exists."""
    sop_path = Path(__file__).resolve().parent.parent / "directives" / "sops" / "hooks.md"
    if sop_path.exists():
        return sop_path.read_text(encoding="utf-8")
    return ""


def generate_video_ideas(analytics: dict, comparative: dict,
                         client: anthropic.Anthropic) -> list[dict]:
    """Generate 5 video ideas based on analytics and comparative analysis.

    Returns:
        List of 5 dicts, each with:
        {title: str, title_variations: [str x5], hooks: [str, str], topic: str}
    """
    context = _build_context(analytics)
    channel_name = analytics["channel"]["channel_name"]
    hooks_sop = _load_hooks_sop()

    system_msg = (
        "You are an expert YouTube strategist creating data-backed video ideas. "
        "Each idea should capitalize on proven formats and topics from the competitive "
        "analysis. Ideas must be specific and actionable — not generic. Title variations "
        "should be distinct clickable titles, not minor word swaps."
    )
    if hooks_sop:
        system_msg += (
            "\n\nUse the following Hook SOP to structure each hook. Every hook MUST "
            "follow the 5-part formula: (1) Bold Claim/Surprising Fact, "
            "(2) Credibility Marker with specific numbers, (3) Specific Promise, "
            "(4) Transformation/Benefit. Hooks should be written as spoken word — "
            "approximately 30 seconds when read aloud.\n\n"
            f"=== HOOK SOP ===\n{hooks_sop}\n=== END HOOK SOP ==="
        )
    else:
        system_msg += (
            " Hooks should be written as spoken word — the first 15 seconds of the "
            "video, as if the creator is speaking directly to camera."
        )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0.5,
        system=system_msg,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Based on this competitive analysis for {channel_name}, "
                    "generate 5 video ideas.\n\n"
                    f"{context}\n\n"
                    "Comparative Analysis Summary:\n"
                    f"- Overview: {comparative.get('overview', 'N/A')}\n"
                    f"- Key Trends: {json.dumps(comparative.get('key_trends', []))}\n"
                    f"- Content Gaps: {json.dumps(comparative.get('content_gaps', []))}\n\n"
                    "Each idea should:\n"
                    "1. Be inspired by specific outlier videos or content gaps in the data\n"
                    f"2. Be adapted for {channel_name}'s style and audience\n"
                    "3. Have a compelling, clickable main title\n"
                    "4. Include 5 distinct title variations (different angles, not minor rewording)\n"
                    "5. Include 2 hooks following the Hook SOP formula (bold claim, credibility, promise, transformation) — ~30 seconds spoken word each\n"
                    "6. Include a topic field that explains WHERE this idea comes from — "
                    "cite specific competitor videos with their metrics. When multiple "
                    "competitors have had success with a similar formula, reference ALL of "
                    "them (e.g. 'JerryRig's durability tests (2.86x) AND LTT's teardown "
                    "content (2.29x) both prove this format works'). 1-2 sentences max.\n\n"
                    "Return a JSON array of exactly 5 ideas:\n"
                    "[\n"
                    "  {\n"
                    '    "title": "Main video title",\n'
                    '    "title_variations": ["Alt 1", "Alt 2", "Alt 3", "Alt 4", "Alt 5"],\n'
                    '    "hooks": [\n'
                    '      "Hook 1 — spoken word, first 15 seconds",\n'
                    '      "Hook 2 — different angle, first 15 seconds"\n'
                    "    ],\n"
                    '    "topic": "Where this idea comes from — cite multiple competitors and their video metrics when applicable"\n'
                    "  }\n"
                    "]\n\n"
                    "Return ONLY valid JSON, no other text."
                ),
            },
            {
                "role": "assistant",
                "content": "[",
            },
        ],
    )

    raw = "[" + response.content[0].text
    ideas = json.loads(raw)
    return ideas[:5]


def generate_takeaways(analytics: dict, comparative: dict,
                       client: anthropic.Anthropic) -> list[str]:
    """Generate 3 strategic takeaways.

    Returns:
        List of 3 actionable takeaway strings.
    """
    context = _build_context(analytics)
    channel_name = analytics["channel"]["channel_name"]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0.3,
        system=(
            "You are an expert YouTube strategist providing actionable recommendations. "
            "Each takeaway must be specific to the channels analyzed — never generic advice "
            "like 'post consistently' or 'engage with your audience'. Reference actual "
            "metrics and competitor performance."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Based on this competitive analysis for {channel_name}, "
                    "provide 3 strategic takeaways.\n\n"
                    f"{context}\n\n"
                    "Comparative Analysis Summary:\n"
                    f"- Overview: {comparative.get('overview', 'N/A')}\n"
                    f"- Key Trends: {json.dumps(comparative.get('key_trends', []))}\n"
                    f"- Content Gaps: {json.dumps(comparative.get('content_gaps', []))}\n\n"
                    "Each takeaway should:\n"
                    f"1. Be specific and actionable for {channel_name}\n"
                    "2. Reference actual competitor data and metrics\n"
                    "3. Be 2-3 sentences max\n"
                    "4. Focus on what to do differently, not just what was observed\n\n"
                    "Return a JSON array of exactly 3 strings:\n"
                    '["Takeaway 1...", "Takeaway 2...", "Takeaway 3..."]\n\n'
                    "Return ONLY valid JSON, no other text."
                ),
            },
            {
                "role": "assistant",
                "content": "[",
            },
        ],
    )

    raw = "[" + response.content[0].text
    takeaways = json.loads(raw)
    return takeaways[:3]


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def generate_insights(analytics: dict) -> dict:
    """Generate all AI insights from analytics data.

    Args:
        analytics: Processed analytics dict (from .tmp/analytics.json)

    Returns:
        Dict with keys: comparative_analysis, video_ideas, takeaways.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set in .env file.\n"
            "Add your Anthropic API key to .env to enable AI insights."
        )

    client = anthropic.Anthropic(api_key=api_key)

    print("  Generating comparative analysis...")
    comparative = generate_comparative_analysis(analytics, client)

    print("  Generating video ideas...")
    video_ideas = generate_video_ideas(analytics, comparative, client)

    print("  Generating takeaways...")
    takeaways = generate_takeaways(analytics, comparative, client)

    return {
        "comparative_analysis": comparative,
        "video_ideas": video_ideas,
        "takeaways": takeaways,
    }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    analytics_path = Path(__file__).resolve().parent.parent / ".tmp" / "analytics.json"
    if not analytics_path.exists():
        print(f"Error: {analytics_path} not found. Run the pipeline first.")
        raise SystemExit(1)

    with open(analytics_path, "r", encoding="utf-8") as f:
        analytics = json.load(f)

    insights = generate_insights(analytics)

    # Save to .tmp/insights.json
    insights_path = Path(__file__).resolve().parent.parent / ".tmp" / "insights.json"
    with open(insights_path, "w", encoding="utf-8") as f:
        json.dump(insights, f, indent=2, ensure_ascii=False)

    print(f"\n  Insights saved: {insights_path}")
    print(f"  Comparative overview: {insights['comparative_analysis']['overview'][:100]}...")
    print(f"  Video ideas: {len(insights['video_ideas'])}")
    print(f"  Takeaways: {len(insights['takeaways'])}")
