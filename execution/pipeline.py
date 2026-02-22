"""Reusable pipeline logic for YouTube Competitor Analysis.

Extracted from main.py so it can be called by both the CLI and web UI.
Yields progress/result/error dicts instead of printing directly.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv

from youtube_api import fetch_channel_data
from analytics import process_all
from ai_insights import generate_insights


def deduplicate_handles(channel: str, competitors: list[str]) -> tuple[list[str], list[str]]:
    """Remove duplicate handles. Returns (unique_competitors, warnings)."""
    warnings = []
    seen = {channel.lstrip("@").lower()}
    unique_competitors = []

    for comp in competitors:
        normalized = comp.lstrip("@").lower()
        if normalized in seen:
            warnings.append(f"Warning: duplicate handle @{normalized} — skipping")
        else:
            seen.add(normalized)
            unique_competitors.append(comp)

    return unique_competitors, warnings


def run_pipeline(
    channel: str,
    competitors: list[str],
    days: int = 60,
    skip_slides: bool = False,
    server_mode: bool = False,
    tmp_dir: str | Path | None = None,
) -> Generator[dict, None, None]:
    """Run the full analysis pipeline as a generator.

    Yields dicts with keys:
        {"type": "progress", "message": "..."}
        {"type": "result", "report_url": "...", "summary": {...}}
        {"type": "error", "message": "..."}
    """
    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        yield {"type": "error", "message": "YOUTUBE_API_KEY not set in .env file"}
        return

    # Validate competitor count
    if len(competitors) < 4:
        yield {"type": "error", "message": f"Need at least 4 competitors, got {len(competitors)}"}
        return
    if len(competitors) > 7:
        yield {"type": "error", "message": f"Max 7 competitors, got {len(competitors)}"}
        return

    # Deduplicate
    competitors, warnings = deduplicate_handles(channel, competitors)
    for w in warnings:
        yield {"type": "progress", "message": f"  {w}"}

    if len(competitors) < 4:
        yield {"type": "error", "message": f"After deduplication, only {len(competitors)} unique competitors remain (need 4)"}
        return

    yield {"type": "progress", "message": f"Channel: {channel}"}
    yield {"type": "progress", "message": f"Competitors: {', '.join(competitors)}"}
    yield {"type": "progress", "message": f"Window: {days} days"}

    total_videos = 0
    failed_channels = []

    # Fetch channel data
    yield {"type": "progress", "message": f"Fetching data for {channel}..."}
    try:
        channel_data = fetch_channel_data(channel, api_key, days=days)
        channel_data["role"] = "channel"
        period_count = len(channel_data["period_videos"])
        baseline_count = len(channel_data["baseline_videos"])
        total_videos += period_count + baseline_count
        yield {"type": "progress", "message": f"  {channel_data['channel_name']}: {period_count} videos in period, {baseline_count} baseline"}
    except Exception as e:
        yield {"type": "error", "message": f"Error fetching {channel}: {e}\nCannot continue without the primary channel."}
        return

    # Fetch competitor data
    competitors_data = []
    for comp in competitors:
        yield {"type": "progress", "message": f"Fetching data for {comp}..."}
        try:
            comp_data = fetch_channel_data(comp, api_key, days=days)
            comp_data["role"] = "competitor"
            period_count = len(comp_data["period_videos"])
            baseline_count = len(comp_data["baseline_videos"])
            total_videos += period_count + baseline_count
            yield {"type": "progress", "message": f"  {comp_data['channel_name']}: {period_count} videos in period, {baseline_count} baseline"}
            competitors_data.append(comp_data)
        except Exception as e:
            yield {"type": "progress", "message": f"  Warning: skipping {comp} — {e}"}
            failed_channels.append(comp)

    if len(competitors_data) < 4:
        yield {"type": "error", "message": f"Only {len(competitors_data)} competitors fetched successfully (need 4)"}
        return

    # Build output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "channel": channel_data,
        "competitors": competitors_data,
    }

    # Save to tmp dir
    if tmp_dir is None:
        tmp_dir = Path(__file__).resolve().parent.parent / ".tmp"
    else:
        tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(exist_ok=True)
    output_path = tmp_dir / "raw_data.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Run analytics
    yield {"type": "progress", "message": "Running analytics..."}
    analytics = process_all(output)

    analytics_path = tmp_dir / "analytics.json"
    with open(analytics_path, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False)

    # Analytics summary
    top_performer = analytics["comparative"]["top_performer"]
    leaderboard = analytics["comparative"]["cross_channel_leaderboard"]
    if leaderboard:
        top_video = leaderboard[0]
        yield {"type": "progress", "message": f"  Top performer: {top_performer}"}
        yield {"type": "progress", "message": f'  Highest outlier: "{top_video["title"]}" by {top_video["channel_name"]}'}
        yield {"type": "progress", "message": f"    {top_video['outlier_score']}x median ({top_video['views']:,} views)"}

    # AI-powered insights
    insights = None
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if anthropic_key:
        yield {"type": "progress", "message": "Generating AI insights..."}
        try:
            insights = generate_insights(analytics)
            insights_path = tmp_dir / "insights.json"
            with open(insights_path, "w", encoding="utf-8") as f:
                json.dump(insights, f, indent=2, ensure_ascii=False)
            yield {"type": "progress", "message": "  AI insights generated"}
        except Exception as e:
            yield {"type": "progress", "message": f"  Warning: AI insights failed — {e}"}
            yield {"type": "progress", "message": "  Continuing with data-driven fallback content."}
            insights = None
    else:
        yield {"type": "progress", "message": "Skipping AI insights (ANTHROPIC_API_KEY not set)"}

    # Google Slides report
    report_url = None
    if not skip_slides:
        yield {"type": "progress", "message": "Generating Google Slides report..."}
        try:
            from slides_report import generate_report
            report_url = generate_report(analytics, insights, server_mode=server_mode)
            yield {"type": "progress", "message": f"  Report URL: {report_url}"}
        except ValueError as e:
            yield {"type": "progress", "message": f"  Skipping report: {e}"}
        except FileNotFoundError as e:
            yield {"type": "progress", "message": f"  Skipping report: {e}"}
        except Exception as e:
            yield {"type": "progress", "message": f"  Warning: report generation failed — {e}"}
    else:
        yield {"type": "progress", "message": "Skipping Google Slides report (skip_slides=True)"}

    # Summary
    all_channels = 1 + len(competitors_data)
    quota_estimate = all_channels * 6

    summary = {
        "channels_fetched": all_channels,
        "failed_channels": failed_channels,
        "total_videos": total_videos,
        "quota_estimate": quota_estimate,
        "output_path": str(output_path),
        "report_url": report_url,
    }

    yield {"type": "result", "report_url": report_url, "summary": summary}
