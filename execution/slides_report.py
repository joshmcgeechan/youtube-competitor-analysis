"""Report generator — copies the template and fills it with analytics data.

Usage:
    # Called by main.py pipeline:
    from slides_report import generate_report
    url = generate_report(analytics, insights=None)

    # Standalone test:
    python execution/slides_report.py
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.errors import HttpError

from auth import build_slides_service, build_drive_service
from slides_template import (
    WHITE, LIGHT_GRAY, GREEN, BLUE_LIGHT, RED_ACCENT, ORANGE_ACCENT,
    FONT_FAMILY, FONT_DISPLAY, FONT_MONO, EMU_PT,
    PAGE_COMPETITOR, PAGE_IDEA,
)


# ---------------------------------------------------------------------------
# Element ID registry — all objectIds on duplicable slides
# ---------------------------------------------------------------------------

def _competitor_element_ids() -> list[str]:
    """All objectIds on the competitor template slide."""
    prefix = "comp"
    ids = [
        f"tmpl_{prefix}_gradient", f"tmpl_{prefix}_label",
        f"tmpl_{prefix}_name", f"tmpl_{prefix}_line",
        f"tmpl_{prefix}_top_header",
    ]
    for key in ("subscribers", "views", "videos", "engagement"):
        ids += [f"tmpl_{prefix}_{key}_{part}"
                for part in ("bg", "accent", "label", "value")]
    for v in range(1, 6):
        ids += [f"tmpl_{prefix}_v{v}_{part}"
                for part in ("bg", "rank", "title", "views", "engagement")]
    return ids


def _idea_element_ids() -> list[str]:
    """All objectIds on the idea template slide."""
    ids = [
        "tmpl_idea_circle", "tmpl_idea_number", "tmpl_idea_label",
        "tmpl_idea_title", "tmpl_idea_accent",
        "tmpl_idea_titles_bg", "tmpl_idea_titles_accent", "tmpl_idea_titles_header",
        "tmpl_idea_hooks_bg", "tmpl_idea_hooks_accent", "tmpl_idea_hooks_header",
        "tmpl_idea_bottom_bg", "tmpl_idea_badge_bg", "tmpl_idea_badge", "tmpl_idea_topic",
    ]
    for i in range(1, 6):
        ids.append(f"tmpl_idea_tv{i}_text")
    for i in range(1, 3):
        ids += [f"tmpl_idea_hook{i}_label", f"tmpl_idea_hook{i}_text"]
    return ids


def _build_object_ids_map(page_id: str, element_ids: list[str], suffix: str) -> dict:
    """Build an objectIds mapping for duplicateObject: old_id -> new_id."""
    mapping = {page_id: f"{page_id}_{suffix}"}
    for eid in element_ids:
        mapping[eid] = f"{eid}_{suffix}"
    return mapping

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_number(n) -> str:
    """Format a number with commas: 1234567 -> '1,234,567'."""
    if n is None:
        return "N/A"
    return f"{int(n):,}"


def _fmt_engagement(val) -> str:
    """Format engagement as percentage: 4.1 -> '4.10%'."""
    if val is None:
        return "N/A"
    return f"{val:.2f}%"


def _fmt_outlier(val) -> str:
    """Format outlier score: 1.01 -> '1.01x'."""
    if val is None:
        return "N/A"
    return f"{val:.2f}x"


def _truncate(text: str, max_len: int = 50) -> str:
    """Truncate text with ellipsis if too long."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _retry_api(func, *args, max_retries: int = 3, delay: float = 2.0, **kwargs):
    """Retry API calls with exponential backoff on 429/500/503.

    Follows the same pattern as _retry in youtube_api.py.
    """
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            status = e.resp.status
            if status in (429, 500, 503) and attempt < max_retries:
                wait = delay * (2 ** attempt)
                print(f"  Slides API error {status} (attempt {attempt + 1}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
        except Exception:
            if attempt < max_retries:
                wait = delay * (2 ** attempt)
                print(f"  Error (attempt {attempt + 1}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Text replacement helpers
# ---------------------------------------------------------------------------

def _map_id(template_id: str, id_map: dict | None) -> str:
    """Translate a template objectId to its duplicated counterpart via mapping.

    If id_map is None (original slide, not a duplicate), return the template_id as-is.
    """
    if id_map is None:
        return template_id
    return id_map.get(template_id, template_id)


def _replace_shape_text(object_id: str, text: str, font_size: int, color: dict,
                        bold: bool = False, id_map: dict | None = None,
                        font_family: str | None = None) -> list[dict]:
    """Replace all text in a shape and re-apply styling.

    Pattern: deleteText → insertText → updateTextStyle
    This avoids replaceAllText which is presentation-wide.
    """
    oid = _map_id(object_id, id_map)
    reqs = [
        {"deleteText": {"objectId": oid, "textRange": {"type": "ALL"}}},
    ]
    if text:
        reqs.append({"insertText": {"objectId": oid, "text": text, "insertionIndex": 0}})
        reqs.append({
            "updateTextStyle": {
                "objectId": oid,
                "style": {
                    "foregroundColor": {"opaqueColor": {"rgbColor": color}},
                    "fontSize": {"magnitude": font_size, "unit": "PT"},
                    "bold": bold,
                    "fontFamily": font_family or FONT_FAMILY,
                },
                "textRange": {"type": "ALL"},
                "fields": "foregroundColor,fontSize,bold,fontFamily",
            }
        })
    return reqs


def _fill_colored_bullets(object_id: str, items: list[str], colors: list[dict],
                          font_size: int = 9) -> list[dict]:
    """Fill a text box with bullets, each colored differently.

    Each bullet point (full text) gets a different foreground color from the
    colors list. Double-spaced between bullets for scannability.
    """
    if not items:
        items = ["No data available"]

    text = "\n\n".join(f"• {item}" for item in items[:3])

    reqs = [
        {"deleteText": {"objectId": object_id, "textRange": {"type": "ALL"}}},
        {"insertText": {"objectId": object_id, "text": text, "insertionIndex": 0}},
        # Base style: white text
        {
            "updateTextStyle": {
                "objectId": object_id,
                "style": {
                    "foregroundColor": {"opaqueColor": {"rgbColor": WHITE}},
                    "fontSize": {"magnitude": font_size, "unit": "PT"},
                    "bold": False,
                    "fontFamily": FONT_FAMILY,
                },
                "textRange": {"type": "ALL"},
                "fields": "foregroundColor,fontSize,bold,fontFamily",
            }
        },
    ]

    # Color just the bullet marker (•), keep body text white
    pos = 0
    for i, item in enumerate(items[:3]):
        bullet_text = f"• {item}"
        if i < len(colors):
            reqs.append({
                "updateTextStyle": {
                    "objectId": object_id,
                    "style": {
                        "foregroundColor": {"opaqueColor": {"rgbColor": colors[i]}},
                        "bold": True,
                    },
                    "textRange": {
                        "type": "FIXED_RANGE",
                        "startIndex": pos,
                        "endIndex": pos + 1,  # just the "•"
                    },
                    "fields": "foregroundColor,bold",
                }
            })
        pos += len(bullet_text) + 2  # +2 for "\n\n"

    return reqs


# ---------------------------------------------------------------------------
# Slide fill builders
# ---------------------------------------------------------------------------

def _fill_title_slide(analytics: dict) -> list[dict]:
    """Fill the title slide with current month/year, analysis window, and channel name."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %Y")
    days = analytics.get("days", 60)

    reqs = []
    reqs += _replace_shape_text("tmpl_title_date", f"{date_str}  |  {days}-Day Analysis Window",
                                16, LIGHT_GRAY)

    # Channel name
    channel_name = analytics.get("channel", {}).get("channel_name", "")
    if channel_name:
        reqs += _replace_shape_text("tmpl_title_channel", channel_name,
                                    24, WHITE, bold=True,
                                    font_family=FONT_DISPLAY)
    return reqs


def _fill_data_slide(data: dict, prefix: str, id_map: dict | None = None) -> list[dict]:
    """Fill a channel or competitor data slide from analytics data."""
    reqs = []

    # Channel name — display font
    reqs += _replace_shape_text(f"tmpl_{prefix}_name", data["channel_name"],
                                32, WHITE, bold=True, id_map=id_map,
                                font_family=FONT_DISPLAY)

    # Metric boxes — mono font for numbers (14pt to fit 10+ char numbers)
    reqs += _replace_shape_text(f"tmpl_{prefix}_subscribers_value",
                                _fmt_number(data.get("subscriber_count")),
                                14, WHITE, bold=True, id_map=id_map,
                                font_family=FONT_MONO)

    views_label_text = f"VIEWS ({data.get('days', 60)}D)" if 'days' in data else "VIEWS (60D)"
    reqs += _replace_shape_text(f"tmpl_{prefix}_views_value",
                                _fmt_number(data.get("total_period_views")),
                                14, WHITE, bold=True, id_map=id_map,
                                font_family=FONT_MONO)

    reqs += _replace_shape_text(f"tmpl_{prefix}_videos_value",
                                str(data.get("video_count", 0)),
                                14, WHITE, bold=True, id_map=id_map,
                                font_family=FONT_MONO)

    reqs += _replace_shape_text(f"tmpl_{prefix}_engagement_value",
                                _fmt_engagement(data.get("avg_engagement")),
                                14, WHITE, bold=True, id_map=id_map,
                                font_family=FONT_MONO)

    # Top 5 videos
    top_videos = data.get("top_videos", [])
    for v in range(1, 6):
        if v <= len(top_videos):
            video = top_videos[v - 1]
            reqs += _replace_shape_text(f"tmpl_{prefix}_v{v}_title",
                                        _truncate(video.get("title", "")),
                                        11, WHITE, id_map=id_map)
            reqs += _replace_shape_text(f"tmpl_{prefix}_v{v}_views",
                                        _fmt_number(video.get("views")),
                                        11, GREEN, bold=True, id_map=id_map,
                                        font_family=FONT_MONO)
            reqs += _replace_shape_text(f"tmpl_{prefix}_v{v}_engagement",
                                        _fmt_engagement(video.get("engagement")),
                                        11, LIGHT_GRAY, id_map=id_map,
                                        font_family=FONT_MONO)
        else:
            # Empty row
            reqs += _replace_shape_text(f"tmpl_{prefix}_v{v}_title", "—",
                                        11, LIGHT_GRAY, id_map=id_map)
            reqs += _replace_shape_text(f"tmpl_{prefix}_v{v}_views", "",
                                        11, GREEN, id_map=id_map)
            reqs += _replace_shape_text(f"tmpl_{prefix}_v{v}_engagement", "",
                                        11, LIGHT_GRAY, id_map=id_map)

    return reqs


def _fill_comparative_slide(analytics: dict, insights: dict | None = None) -> list[dict]:
    """Fill the comparative analysis slide."""
    reqs = []
    comparative = analytics.get("comparative", {})

    if insights and insights.get("comparative_analysis"):
        # Use AI-generated insights
        ai = insights["comparative_analysis"]
        overview = ai.get("overview", "")
        trends = ai.get("key_trends", [])
        gaps = ai.get("content_gaps", [])
    else:
        # Data-driven fallback
        overview = _build_fallback_overview(analytics)
        trends = _build_fallback_trends(analytics)
        gaps = _build_fallback_gaps(analytics)

    reqs += _replace_shape_text("tmpl_comp_overview_text", overview, 10, WHITE)

    # Format trends with colored bullets (green, blue, amber)
    bullet_colors = [GREEN, BLUE_LIGHT, ORANGE_ACCENT]
    reqs += _fill_colored_bullets("tmpl_comp_trends_text", trends, bullet_colors, font_size=9)

    # Format gaps with colored bullets (green, blue, amber)
    reqs += _fill_colored_bullets("tmpl_comp_gaps_text", gaps, bullet_colors, font_size=9)

    # Top performer — name + contextual note with dual styling
    top_performer = comparative.get("top_performer", "N/A")

    if insights and insights.get("comparative_analysis", {}).get("top_performer_note"):
        note = insights["comparative_analysis"]["top_performer_note"]
    else:
        note = _build_fallback_top_performer_note(analytics)

    oid = "tmpl_comp_top_name"
    full_text = f"{top_performer}\n{note}"
    name_end = len(top_performer)

    reqs += [
        {"deleteText": {"objectId": oid, "textRange": {"type": "ALL"}}},
        {"insertText": {"objectId": oid, "text": full_text, "insertionIndex": 0}},
        # Style the name (first line) — bold, 18pt, white, display font
        {
            "updateTextStyle": {
                "objectId": oid,
                "style": {
                    "foregroundColor": {"opaqueColor": {"rgbColor": WHITE}},
                    "fontSize": {"magnitude": 18, "unit": "PT"},
                    "bold": True,
                    "fontFamily": FONT_DISPLAY,
                },
                "textRange": {"type": "FIXED_RANGE", "startIndex": 0, "endIndex": name_end},
                "fields": "foregroundColor,fontSize,bold,fontFamily",
            }
        },
        # Style the note (second line) — regular, 9pt, light gray
        {
            "updateTextStyle": {
                "objectId": oid,
                "style": {
                    "foregroundColor": {"opaqueColor": {"rgbColor": LIGHT_GRAY}},
                    "fontSize": {"magnitude": 9, "unit": "PT"},
                    "bold": False,
                    "fontFamily": FONT_FAMILY,
                },
                "textRange": {
                    "type": "FIXED_RANGE",
                    "startIndex": name_end + 1,
                    "endIndex": len(full_text),
                },
                "fields": "foregroundColor,fontSize,bold,fontFamily",
            }
        },
    ]

    return reqs


def _fill_idea_slide(idea: dict, number: int, id_map: dict | None = None) -> list[dict]:
    """Fill a video idea slide."""
    reqs = []

    reqs += _replace_shape_text("tmpl_idea_number", str(number),
                                18, WHITE, bold=True, id_map=id_map,
                                font_family=FONT_DISPLAY)
    reqs += _replace_shape_text("tmpl_idea_title", idea.get("title", f"Video Idea #{number}"),
                                24, WHITE, bold=True, id_map=id_map,
                                font_family=FONT_DISPLAY)

    # Title variations (11pt to match top performing videos section)
    variations = idea.get("title_variations", [])
    for i in range(1, 6):
        if i <= len(variations):
            reqs += _replace_shape_text(f"tmpl_idea_tv{i}_text",
                                        f"{i}. {variations[i-1]}",
                                        11, WHITE, id_map=id_map)
        else:
            reqs += _replace_shape_text(f"tmpl_idea_tv{i}_text", "",
                                        11, WHITE, id_map=id_map)

    # Hooks
    hooks = idea.get("hooks", [])
    for i in range(1, 3):
        if i <= len(hooks):
            reqs += _replace_shape_text(f"tmpl_idea_hook{i}_text",
                                        hooks[i-1], 9, WHITE, id_map=id_map)
        else:
            reqs += _replace_shape_text(f"tmpl_idea_hook{i}_text", "",
                                        9, WHITE, id_map=id_map)

    # Topic
    topic = idea.get("topic", "")
    reqs += _replace_shape_text("tmpl_idea_topic", f"Topic: {topic}" if topic else "",
                                9, WHITE, id_map=id_map)

    return reqs


def _fill_takeaways_slide(analytics: dict, insights: dict | None = None) -> list[dict]:
    """Fill the key takeaways slide."""
    reqs = []

    if insights and insights.get("takeaways"):
        takeaways = insights["takeaways"]
    else:
        takeaways = _build_fallback_takeaways(analytics)

    for i in range(1, 4):
        if i <= len(takeaways):
            reqs += _replace_shape_text(f"tmpl_take_{i}_text", takeaways[i-1], 11, WHITE)
        else:
            reqs += _replace_shape_text(f"tmpl_take_{i}_text", "", 11, WHITE)

    return reqs


# ---------------------------------------------------------------------------
# Fallback content generators (when insights=None, Feature 4 not built)
# ---------------------------------------------------------------------------

def _build_fallback_overview(analytics: dict) -> str:
    """Generate a data-driven overview from analytics rankings."""
    channel = analytics.get("channel", {})
    comparative = analytics.get("comparative", {})
    competitors = analytics.get("competitors", [])

    channel_name = channel.get("channel_name", "Your channel")
    top_performer = comparative.get("top_performer", "N/A")
    num_competitors = len(competitors)

    views_ranking = comparative.get("views_ranking", [])
    channel_views_rank = next(
        (i + 1 for i, r in enumerate(views_ranking) if r["channel_name"] == channel_name),
        None
    )
    eng_ranking = comparative.get("engagement_ranking", [])
    channel_eng_rank = next(
        (i + 1 for i, r in enumerate(eng_ranking) if r["channel_name"] == channel_name),
        None
    )

    parts = [
        f"Analysis of {channel_name} against {num_competitors} competitors.",
    ]
    if channel_views_rank:
        parts.append(f"{channel_name} ranks #{channel_views_rank} in total period views")
    if channel_eng_rank:
        parts[-1] += f" and #{channel_eng_rank} in average engagement."
    else:
        parts[-1] += "."

    parts.append(f"Top performer by views: {top_performer}.")

    leaderboard = comparative.get("cross_channel_leaderboard", [])
    if leaderboard:
        top_vid = leaderboard[0]
        parts.append(
            f"Highest outlier video: \"{_truncate(top_vid['title'], 40)}\" "
            f"by {top_vid['channel_name']} ({_fmt_outlier(top_vid['outlier_score'])} median, "
            f"{_fmt_number(top_vid['views'])} views)."
        )

    return " ".join(parts)


def _build_fallback_trends(analytics: dict) -> list[str]:
    """Generate data-driven trend bullets."""
    comparative = analytics.get("comparative", {})
    trends = []

    views_ranking = comparative.get("views_ranking", [])
    if len(views_ranking) >= 2:
        top = views_ranking[0]
        trends.append(
            f"{top['channel_name']} leads in views with {_fmt_number(top['total_period_views'])} total period views"
        )

    eng_ranking = comparative.get("engagement_ranking", [])
    if eng_ranking:
        top_eng = eng_ranking[0]
        trends.append(
            f"{top_eng['channel_name']} has highest engagement at {_fmt_engagement(top_eng['avg_engagement'])}"
        )

    leaderboard = comparative.get("cross_channel_leaderboard", [])
    if leaderboard:
        outlier_channels = set(v["channel_name"] for v in leaderboard[:5])
        if len(outlier_channels) == 1:
            trends.append(f"{list(outlier_channels)[0]} dominates the top outlier videos")
        else:
            trends.append(f"Top outlier videos spread across {', '.join(list(outlier_channels)[:3])}")

    return trends[:3]


def _build_fallback_gaps(analytics: dict) -> list[str]:
    """Generate data-driven content gap bullets."""
    channel = analytics.get("channel", {})
    competitors = analytics.get("competitors", [])
    gaps = []

    channel_freq = channel.get("upload_frequency", 0)
    high_freq_comps = [c for c in competitors if c.get("upload_frequency", 0) > channel_freq * 1.5]
    if high_freq_comps:
        names = ", ".join(c["channel_name"] for c in high_freq_comps[:2])
        gaps.append(f"Upload frequency gap: {names} publish significantly more often")

    channel_eng = channel.get("avg_engagement", 0)
    higher_eng = [c for c in competitors if c.get("avg_engagement", 0) > channel_eng * 1.2]
    if higher_eng:
        names = ", ".join(c["channel_name"] for c in higher_eng[:2])
        gaps.append(f"Engagement gap: {names} achieve higher engagement rates")

    channel_views = channel.get("total_period_views", 0)
    higher_views = [c for c in competitors if c.get("total_period_views", 0) > channel_views * 1.5]
    if higher_views:
        names = ", ".join(c["channel_name"] for c in higher_views[:2])
        gaps.append(f"Views gap: {names} generate significantly more total views")

    if not gaps:
        gaps.append("No significant content gaps identified — channel is competitive across key metrics")

    return gaps[:3]


def _build_fallback_top_performer_note(analytics: dict) -> str:
    """Generate a data-driven note for the top performer."""
    comparative = analytics.get("comparative", {})
    top_name = comparative.get("top_performer", "N/A")

    all_channels = [analytics.get("channel", {})] + analytics.get("competitors", [])
    top_ch = next((c for c in all_channels if c.get("channel_name") == top_name), None)

    if not top_ch:
        return ""

    video_count = top_ch.get("video_count", 0)
    total_views = top_ch.get("total_period_views", 0)
    avg_views = total_views // video_count if video_count else 0

    return f"{_fmt_number(avg_views)} avg views/video across {video_count} videos"


def _build_fallback_ideas(analytics: dict) -> list[dict]:
    """Generate placeholder video ideas based on cross-channel leaderboard."""
    leaderboard = analytics.get("comparative", {}).get("cross_channel_leaderboard", [])
    ideas = []

    for i, video in enumerate(leaderboard[:5]):
        ideas.append({
            "title": f"Inspired by: {_truncate(video['title'], 45)}",
            "title_variations": [
                f"Variation on: {_truncate(video['title'], 40)}",
                f"Our take on {video['channel_name']}'s top video",
                f"Why \"{_truncate(video['title'], 30)}\" went viral",
                f"Response to {video['channel_name']}: {_truncate(video['title'], 25)}",
                f"Deep dive: {_truncate(video['title'], 35)}",
            ],
            "hooks": [
                f"This video by {video['channel_name']} got {_fmt_number(video['views'])} views "
                f"and scored {_fmt_outlier(video['outlier_score'])} — here's what made it work.",
                f"With {_fmt_engagement(video['engagement'])} engagement, this topic clearly "
                f"resonates with the audience. Here's how to put your own spin on it.",
            ],
            "topic": f"Based on {video['channel_name']}'s outlier ({_fmt_outlier(video['outlier_score'])})",
        })

    # Pad to 5 if leaderboard has fewer entries
    while len(ideas) < 5:
        ideas.append({
            "title": f"Video Idea #{len(ideas) + 1} — AI insights pending",
            "title_variations": ["AI-generated ideas will appear here after Feature 4 is enabled"] * 5,
            "hooks": ["Hook content will be generated by Claude AI analysis."] * 2,
            "topic": "Pending AI analysis",
        })

    return ideas


def _build_fallback_takeaways(analytics: dict) -> list[str]:
    """Generate data-driven takeaway bullets."""
    channel = analytics.get("channel", {})
    comparative = analytics.get("comparative", {})
    takeaways = []

    top_performer = comparative.get("top_performer", "N/A")
    channel_name = channel.get("channel_name", "Your channel")

    views_ranking = comparative.get("views_ranking", [])
    channel_rank = next(
        (i + 1 for i, r in enumerate(views_ranking) if r["channel_name"] == channel_name),
        len(views_ranking)
    )
    takeaways.append(
        f"{channel_name} ranks #{channel_rank} of {len(views_ranking)} channels in total period views. "
        f"Top performer is {top_performer}."
    )

    leaderboard = comparative.get("cross_channel_leaderboard", [])
    if leaderboard:
        top_vid = leaderboard[0]
        takeaways.append(
            f"The highest-performing video across all channels is \"{_truncate(top_vid['title'], 40)}\" "
            f"by {top_vid['channel_name']} with {_fmt_outlier(top_vid['outlier_score'])} median performance."
        )

    takeaways.append(
        "Enable AI insights (Feature 4) for personalized content strategy recommendations "
        "and data-driven video ideas."
    )

    return takeaways[:3]


# ---------------------------------------------------------------------------
# Core report generator
# ---------------------------------------------------------------------------

def generate_report(analytics: dict, insights: dict | None = None, server_mode: bool = False) -> str:
    """Generate a filled Google Slides report from analytics data.

    Args:
        analytics: Processed analytics dict (from .tmp/analytics.json)
        insights: Optional AI insights dict (from .tmp/insights.json)
        server_mode: If True, use env-var-based auth (no browser).

    Returns:
        Google Slides URL for the generated report.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    template_id = os.getenv("GOOGLE_SLIDES_TEMPLATE_ID")
    if not template_id:
        raise ValueError(
            "GOOGLE_SLIDES_TEMPLATE_ID not set in .env file.\n"
            "Run 'python execution/slides_template.py' first to create the template."
        )

    slides_service = build_slides_service(server_mode)
    drive_service = build_drive_service(server_mode)

    # Step 1: Copy template via Drive API
    now = datetime.now(timezone.utc)
    channel_name = analytics.get("channel", {}).get("channel_name", "")
    if channel_name:
        report_title = f"{channel_name} YouTube Analytics Report — {now.strftime('%B %Y')}"
    else:
        report_title = f"YouTube Analytics Report — {now.strftime('%B %Y')}"

    copy_response = _retry_api(
        drive_service.files().copy(
            fileId=template_id,
            body={"name": report_title},
        ).execute
    )
    report_id = copy_response["id"]
    print(f"  Report created: {report_title}")

    # Collect all fill requests
    fill_requests = []

    # Step 2: Fill title slide
    fill_requests += _fill_title_slide(analytics)

    # Step 3: Fill channel slide (uses original objectIds, no id_map needed)
    channel_data = analytics.get("channel", {})
    fill_requests += _fill_data_slide(channel_data, "channel")

    # Step 4: Duplicate competitor slide N times (reverse order)
    competitors = analytics.get("competitors", [])
    competitor_id_maps = []
    comp_elements = _competitor_element_ids()

    for i in range(len(competitors) - 1, -1, -1):
        id_map = _build_object_ids_map(PAGE_COMPETITOR, comp_elements, f"c{i}")
        _retry_api(
            slides_service.presentations().batchUpdate(
                presentationId=report_id,
                body={"requests": [
                    {"duplicateObject": {
                        "objectId": PAGE_COMPETITOR,
                        "objectIds": id_map,
                    }}
                ]},
            ).execute
        )
        competitor_id_maps.insert(0, (i, id_map))

    # Step 5: Fill each competitor slide using mapped IDs
    for comp_index, id_map in competitor_id_maps:
        comp_data = competitors[comp_index]
        fill_requests += _fill_data_slide(comp_data, "comp", id_map=id_map)

    # Step 6: Delete original competitor template slide
    fill_requests.append({"deleteObject": {"objectId": "tmpl_competitor"}})

    # Step 7: Duplicate idea slide 5 times (reverse order)
    if insights and insights.get("video_ideas"):
        ideas = insights["video_ideas"][:5]
    else:
        ideas = _build_fallback_ideas(analytics)

    # Pad to 5
    while len(ideas) < 5:
        ideas.append({
            "title": f"Video Idea #{len(ideas) + 1}",
            "title_variations": [],
            "hooks": [],
            "topic": "",
        })

    idea_id_maps = []
    idea_elements = _idea_element_ids()

    for i in range(4, -1, -1):  # 5 ideas: indices 4,3,2,1,0
        id_map = _build_object_ids_map(PAGE_IDEA, idea_elements, f"i{i}")
        _retry_api(
            slides_service.presentations().batchUpdate(
                presentationId=report_id,
                body={"requests": [
                    {"duplicateObject": {
                        "objectId": PAGE_IDEA,
                        "objectIds": id_map,
                    }}
                ]},
            ).execute
        )
        idea_id_maps.insert(0, (i, id_map))

    # Step 8: Fill each idea slide
    for idea_index, id_map in idea_id_maps:
        fill_requests += _fill_idea_slide(ideas[idea_index], idea_index + 1, id_map=id_map)

    # Step 9: Fill comparative analysis slide
    fill_requests += _fill_comparative_slide(analytics, insights)

    # Step 10: Fill takeaways slide
    fill_requests += _fill_takeaways_slide(analytics, insights)

    # Step 11: Delete original idea template slide
    fill_requests.append({"deleteObject": {"objectId": "tmpl_idea"}})

    # Step 12: Execute all fill requests in a single batch
    if fill_requests:
        _retry_api(
            slides_service.presentations().batchUpdate(
                presentationId=report_id,
                body={"requests": fill_requests},
            ).execute
        )

    # Make the report viewable by anyone with the link
    _retry_api(
        drive_service.permissions().create(
            fileId=report_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        ).execute
    )

    url = f"https://docs.google.com/presentation/d/{report_id}/edit"
    print(f"  Report filled successfully")
    return url


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

    # Check for optional insights
    insights_path = Path(__file__).resolve().parent.parent / ".tmp" / "insights.json"
    insights = None
    if insights_path.exists():
        with open(insights_path, "r", encoding="utf-8") as f:
            insights = json.load(f)

    url = generate_report(analytics, insights)
    print(f"\n  Report URL: {url}")
