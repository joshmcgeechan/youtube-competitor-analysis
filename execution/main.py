"""CLI entry point for YouTube Competitor Analysis pipeline."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from youtube_api import fetch_channel_data
from analytics import process_all
from ai_insights import generate_insights


def parse_args():
    parser = argparse.ArgumentParser(
        description="YouTube Competitor Analysis — fetch channel and video data"
    )
    parser.add_argument(
        "--channel",
        required=True,
        help="Your channel's @handle (e.g., @mkbhd)",
    )
    parser.add_argument(
        "--competitors",
        required=True,
        nargs="+",
        help="4-7 competitor @handles (e.g., @c1 @c2 @c3 @c4)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=60,
        help="Analysis window in days (default: 60)",
    )
    parser.add_argument(
        "--skip-slides",
        action="store_true",
        help="Skip Google Slides report generation",
    )
    return parser.parse_args()


def deduplicate_handles(channel: str, competitors: list[str]) -> list[str]:
    """Remove duplicate handles and warn if any found."""
    all_handles = [channel.lstrip("@").lower()] + [
        c.lstrip("@").lower() for c in competitors
    ]
    seen = set()
    unique_competitors = []

    # Channel handle is always first
    seen.add(all_handles[0])

    for comp in competitors:
        normalized = comp.lstrip("@").lower()
        if normalized in seen:
            print(f"  Warning: duplicate handle @{normalized} — skipping")
        else:
            seen.add(normalized)
            unique_competitors.append(comp)

    return unique_competitors


def main():
    args = parse_args()

    # Load environment
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("Error: YOUTUBE_API_KEY not set in .env file")
        print(f"  Copy .env.example to .env and add your key: {env_path}")
        sys.exit(1)

    # Validate competitor count
    if len(args.competitors) < 4:
        print(f"Error: need at least 4 competitors, got {len(args.competitors)}")
        sys.exit(1)
    if len(args.competitors) > 7:
        print(f"Error: max 7 competitors, got {len(args.competitors)}")
        sys.exit(1)

    # Deduplicate
    competitors = deduplicate_handles(args.channel, args.competitors)
    if len(competitors) < 4:
        print(f"Error: after deduplication, only {len(competitors)} unique competitors remain (need 4)")
        sys.exit(1)

    print(f"\n=== YouTube Competitor Analysis ===")
    print(f"Channel:     {args.channel}")
    print(f"Competitors: {', '.join(competitors)}")
    print(f"Window:      {args.days} days\n")

    total_videos = 0
    failed_channels = []

    # Fetch channel data
    print(f"Fetching data for {args.channel}...")
    try:
        channel_data = fetch_channel_data(args.channel, api_key, days=args.days)
        channel_data["role"] = "channel"
        period_count = len(channel_data["period_videos"])
        baseline_count = len(channel_data["baseline_videos"])
        total_videos += period_count + baseline_count
        print(f"  {channel_data['channel_name']}: {period_count} videos in period, {baseline_count} baseline")
    except Exception as e:
        print(f"  Error fetching {args.channel}: {e}")
        print("  Cannot continue without the primary channel.")
        sys.exit(1)

    # Fetch competitor data
    competitors_data = []
    for comp in competitors:
        print(f"Fetching data for {comp}...")
        try:
            comp_data = fetch_channel_data(comp, api_key, days=args.days)
            comp_data["role"] = "competitor"
            period_count = len(comp_data["period_videos"])
            baseline_count = len(comp_data["baseline_videos"])
            total_videos += period_count + baseline_count
            print(f"  {comp_data['channel_name']}: {period_count} videos in period, {baseline_count} baseline")
            competitors_data.append(comp_data)
        except Exception as e:
            print(f"  Warning: skipping {comp} — {e}")
            failed_channels.append(comp)

    if len(competitors_data) < 4:
        print(f"\nError: only {len(competitors_data)} competitors fetched successfully (need 4)")
        sys.exit(1)

    # Build output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": args.days,
        "channel": channel_data,
        "competitors": competitors_data,
    }

    # Save to .tmp/raw_data.json
    tmp_dir = Path(__file__).resolve().parent.parent / ".tmp"
    tmp_dir.mkdir(exist_ok=True)
    output_path = tmp_dir / "raw_data.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Run analytics
    print(f"\nRunning analytics...")
    analytics = process_all(output)

    analytics_path = tmp_dir / "analytics.json"
    with open(analytics_path, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False)

    # Analytics summary
    top_performer = analytics["comparative"]["top_performer"]
    leaderboard = analytics["comparative"]["cross_channel_leaderboard"]
    if leaderboard:
        top_video = leaderboard[0]
        print(f"  Top performer:    {top_performer}")
        print(f"  Highest outlier:  \"{top_video['title']}\" by {top_video['channel_name']}")
        print(f"                    {top_video['outlier_score']}x median ({top_video['views']:,} views)")
    print(f"  Analytics saved:  {analytics_path}")

    # AI-powered insights (Claude API)
    insights = None
    insights_path = tmp_dir / "insights.json"
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if anthropic_key:
        print(f"\nGenerating AI insights...")
        try:
            insights = generate_insights(analytics)
            with open(insights_path, "w", encoding="utf-8") as f:
                json.dump(insights, f, indent=2, ensure_ascii=False)
            print(f"  AI insights saved: {insights_path}")
        except Exception as e:
            print(f"  Warning: AI insights failed — {e}")
            print(f"  Continuing with data-driven fallback content.")
            insights = None
    else:
        print(f"\n  Skipping AI insights (ANTHROPIC_API_KEY not set in .env)")

    # Google Slides report generation
    if not args.skip_slides:
        print(f"\nGenerating Google Slides report...")
        try:
            from slides_report import generate_report
            report_url = generate_report(analytics, insights)
            print(f"  Report URL: {report_url}")
        except ValueError as e:
            print(f"  Skipping report: {e}")
        except FileNotFoundError as e:
            print(f"  Skipping report: {e}")
        except Exception as e:
            print(f"  Warning: report generation failed — {e}")
            print(f"  Analytics data is still available at {analytics_path}")
    else:
        print(f"\n  Skipping Google Slides report (--skip-slides)")

    # Summary
    all_channels = 1 + len(competitors_data)
    # Rough quota estimate: ~4 units per channel (1 resolve + 1-2 playlist pages + 1-2 video batches)
    # Baseline fetch adds ~2 more (1 playlist page + 1 video batch)
    quota_estimate = all_channels * 6

    print(f"\n=== Summary ===")
    print(f"Channels fetched: {all_channels}")
    if failed_channels:
        print(f"Channels failed:  {len(failed_channels)} ({', '.join(failed_channels)})")
    print(f"Total videos:     {total_videos}")
    print(f"Est. quota used:  ~{quota_estimate} units (of 10,000 daily)")
    print(f"Output saved to:  {output_path}")


if __name__ == "__main__":
    main()
