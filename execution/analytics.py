"""Analytics engine — outlier scoring, engagement rates, and channel summaries.

Pure computation module. Takes raw data dicts from youtube_api, returns
analytics dicts. No API calls, no file I/O.
"""

from statistics import median


def calculate_engagement(video: dict) -> float:
    """Calculate engagement rate for a single video.

    Formula: (likes + comments) / views * 100
    Returns 0.0 if views == 0.
    """
    views = video.get("views", 0)
    if views == 0:
        return 0.0
    likes = video.get("likes", 0)
    comments = video.get("comments", 0)
    return (likes + comments) / views * 100


def calculate_outlier_scores(
    period_videos: list[dict], baseline_videos: list[dict]
) -> list[dict]:
    """Add outlier_score and engagement fields to each period video.

    Outlier score = views / median(baseline views).
    If median is 0 (no baseline), outlier_score = 0.
    """
    baseline_views = [v.get("views", 0) for v in baseline_videos]
    median_views = median(baseline_views) if baseline_views else 0

    scored = []
    for video in period_videos:
        enriched = dict(video)
        enriched["engagement"] = calculate_engagement(video)
        if median_views > 0:
            enriched["outlier_score"] = round(video.get("views", 0) / median_views, 2)
        else:
            enriched["outlier_score"] = 0
        scored.append(enriched)

    return scored


def rank_top_videos(videos: list[dict], n: int = 5) -> list[dict]:
    """Return top N videos by outlier_score descending."""
    sorted_videos = sorted(videos, key=lambda v: v.get("outlier_score", 0), reverse=True)
    return [
        {
            "title": v["title"],
            "video_id": v["video_id"],
            "views": v["views"],
            "engagement": round(v.get("engagement", 0), 2),
            "outlier_score": v.get("outlier_score", 0),
        }
        for v in sorted_videos[:n]
    ]


def build_channel_summary(channel_data: dict, days: int) -> dict:
    """Build a summary dict for one channel.

    Args:
        channel_data: Full channel dict from raw_data (has subscriber_count,
                      period_videos, baseline_videos, role, etc.)
        days: Analysis window in days (for upload frequency calculation)

    Returns:
        Summary dict with all computed metrics.
    """
    period_videos = calculate_outlier_scores(
        channel_data["period_videos"], channel_data["baseline_videos"]
    )

    total_period_views = sum(v.get("views", 0) for v in period_videos)
    video_count = len(period_videos)

    engagements = [v.get("engagement", 0) for v in period_videos]
    avg_engagement = round(sum(engagements) / len(engagements), 2) if engagements else 0.0

    durations = [v.get("duration_seconds", 0) for v in period_videos]
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0.0

    weeks = max(days / 7, 1)
    upload_frequency = round(video_count / weeks, 2)

    top_videos = rank_top_videos(period_videos)

    return {
        "channel_id": channel_data["channel_id"],
        "channel_name": channel_data["channel_name"],
        "role": channel_data.get("role", "competitor"),
        "subscriber_count": channel_data.get("subscriber_count"),
        "total_period_views": total_period_views,
        "video_count": video_count,
        "avg_engagement": avg_engagement,
        "avg_duration": avg_duration,
        "upload_frequency": upload_frequency,
        "top_videos": top_videos,
        "period_videos": period_videos,
    }


def build_comparative_data(
    channel_summary: dict, competitor_summaries: list[dict]
) -> dict:
    """Build cross-channel comparative analytics.

    Args:
        channel_summary: The primary channel's summary
        competitor_summaries: List of competitor summaries

    Returns:
        Dict with rankings, top performer, and cross-channel outlier leaderboard.
    """
    all_summaries = [channel_summary] + competitor_summaries

    # Rankings by total period views
    by_views = sorted(all_summaries, key=lambda s: s["total_period_views"], reverse=True)
    views_ranking = [
        {"channel_name": s["channel_name"], "total_period_views": s["total_period_views"]}
        for s in by_views
    ]

    # Rankings by avg engagement
    by_engagement = sorted(all_summaries, key=lambda s: s["avg_engagement"], reverse=True)
    engagement_ranking = [
        {"channel_name": s["channel_name"], "avg_engagement": s["avg_engagement"]}
        for s in by_engagement
    ]

    # Rankings by highest single outlier score
    def best_outlier(summary):
        if summary["top_videos"]:
            return summary["top_videos"][0]["outlier_score"]
        return 0

    by_outlier = sorted(all_summaries, key=best_outlier, reverse=True)
    outlier_ranking = [
        {
            "channel_name": s["channel_name"],
            "highest_outlier_score": best_outlier(s),
        }
        for s in by_outlier
    ]

    # Top performer: highest total period views
    top_performer = by_views[0]["channel_name"] if by_views else None

    # Cross-channel outlier leaderboard: top 10 videos across all channels
    all_videos = []
    for s in all_summaries:
        for v in s.get("period_videos", []):
            all_videos.append({
                "channel_name": s["channel_name"],
                "title": v["title"],
                "video_id": v["video_id"],
                "views": v["views"],
                "outlier_score": v.get("outlier_score", 0),
                "engagement": round(v.get("engagement", 0), 2),
            })

    all_videos.sort(key=lambda v: v["outlier_score"], reverse=True)
    cross_channel_leaderboard = all_videos[:10]

    return {
        "views_ranking": views_ranking,
        "engagement_ranking": engagement_ranking,
        "outlier_ranking": outlier_ranking,
        "top_performer": top_performer,
        "cross_channel_leaderboard": cross_channel_leaderboard,
    }


def process_all(raw_data: dict) -> dict:
    """Process raw_data into complete analytics.

    Args:
        raw_data: Full raw_data dict (has 'channel', 'competitors', 'days')

    Returns:
        Analytics dict with channel summary, competitor summaries, and
        comparative data.
    """
    days = raw_data.get("days", 60)

    channel_summary = build_channel_summary(raw_data["channel"], days)

    competitor_summaries = [
        build_channel_summary(comp, days) for comp in raw_data["competitors"]
    ]

    comparative = build_comparative_data(channel_summary, competitor_summaries)

    return {
        "channel": channel_summary,
        "competitors": competitor_summaries,
        "comparative": comparative,
    }
