"""CLI entry point for YouTube Competitor Analysis pipeline."""

import argparse
import sys

from pipeline import run_pipeline


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


def main():
    args = parse_args()

    print(f"\n=== YouTube Competitor Analysis ===")

    for event in run_pipeline(
        channel=args.channel,
        competitors=args.competitors,
        days=args.days,
        skip_slides=args.skip_slides,
    ):
        if event["type"] == "progress":
            print(event["message"])
        elif event["type"] == "error":
            print(f"Error: {event['message']}")
            sys.exit(1)
        elif event["type"] == "result":
            summary = event["summary"]
            print(f"\n=== Summary ===")
            print(f"Channels fetched: {summary['channels_fetched']}")
            if summary["failed_channels"]:
                print(f"Channels failed:  {len(summary['failed_channels'])} ({', '.join(summary['failed_channels'])})")
            print(f"Total videos:     {summary['total_videos']}")
            print(f"Est. quota used:  ~{summary['quota_estimate']} units (of 10,000 daily)")
            print(f"Output saved to:  {summary['output_path']}")


if __name__ == "__main__":
    main()
