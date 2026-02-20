"""YouTube Data API v3 wrapper for channel and video data fetching."""

import re
import time
from datetime import datetime, timezone, timedelta

import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def _build_service(api_key: str):
    """Build a YouTube Data API v3 service object."""
    return build("youtube", "v3", developerKey=api_key)


def _parse_iso8601_duration(duration: str) -> int:
    """Parse ISO 8601 duration (e.g., PT12M34S) to total seconds."""
    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration
    )
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def _is_short(video_id: str) -> bool:
    """Check if a video is a YouTube Short via HEAD request.

    Returns True if youtube.com/shorts/{id} responds 200 (is a Short),
    False if it responds 303 (redirects to regular watch page).
    """
    url = f"https://www.youtube.com/shorts/{video_id}"
    try:
        resp = requests.head(url, allow_redirects=False, timeout=10)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def _filter_shorts(videos: list[dict]) -> list[dict]:
    """Remove YouTube Shorts from a list of videos.

    Two-step filter:
    1. Videos > 180s are definitely long-form (Shorts max is 3 min)
    2. Videos <= 180s get a HEAD request to youtube.com/shorts/{id}
    """
    long_form = []
    to_check = []

    for v in videos:
        if v["duration_seconds"] > 180:
            long_form.append(v)
        else:
            to_check.append(v)

    if to_check:
        checked_count = len(to_check)
        shorts_count = 0
        for v in to_check:
            if _is_short(v["video_id"]):
                shorts_count += 1
            else:
                long_form.append(v)
            time.sleep(0.3)
        if shorts_count:
            print(f"    Filtered {shorts_count} Shorts (checked {checked_count} videos <= 3min)")

    return long_form


def resolve_handle(handle: str, api_key: str) -> dict:
    """Resolve a YouTube @handle to channel info.

    Args:
        handle: YouTube handle (with or without leading @)
        api_key: YouTube Data API key

    Returns:
        Dict with channel_id, title, subscriber_count, total_views,
        uploads_playlist_id

    Raises:
        ValueError: If handle not found
    """
    handle = handle.lstrip("@")
    service = _build_service(api_key)

    response = service.channels().list(
        part="id,snippet,statistics,contentDetails",
        forHandle=handle,
    ).execute()

    items = response.get("items", [])
    if not items:
        raise ValueError(f"Channel not found for handle: @{handle}")

    channel = items[0]
    channel_id = channel["id"]

    # Subscriber count may be hidden
    sub_count = channel["statistics"].get("subscriberCount")
    subscriber_count = int(sub_count) if sub_count else None

    total_views = int(channel["statistics"].get("viewCount", 0))

    # Uploads playlist: swap UC prefix to UU
    uploads_playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    if uploads_playlist_id.startswith("UC"):
        uploads_playlist_id = "UU" + uploads_playlist_id[2:]

    return {
        "channel_id": channel_id,
        "title": channel["snippet"]["title"],
        "subscriber_count": subscriber_count,
        "total_views": total_views,
        "uploads_playlist_id": uploads_playlist_id,
    }


def get_recent_videos(
    uploads_playlist_id: str,
    api_key: str,
    days: int = None,
    max_videos: int = None,
) -> list[str]:
    """Fetch recent video IDs from an uploads playlist.

    Args:
        uploads_playlist_id: The UU-prefixed uploads playlist ID
        api_key: YouTube Data API key
        days: Only include videos published within this many days (optional)
        max_videos: Stop after collecting this many video IDs (optional)

    Returns:
        List of video IDs
    """
    service = _build_service(api_key)
    video_ids = []
    next_page_token = None
    cutoff = None

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    while True:
        response = service.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        for item in response.get("items", []):
            published = item["contentDetails"].get("videoPublishedAt")
            if published and cutoff:
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if pub_dt < cutoff:
                    # Videos are in reverse chronological order; stop here
                    return video_ids

            video_ids.append(item["contentDetails"]["videoId"])

            if max_videos and len(video_ids) >= max_videos:
                return video_ids

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return video_ids


def get_video_details(video_ids: list[str], api_key: str) -> list[dict]:
    """Fetch detailed info for a list of video IDs.

    Args:
        video_ids: List of YouTube video IDs
        api_key: YouTube Data API key

    Returns:
        List of dicts with video_id, title, published_at, views, likes,
        comments, duration_seconds
    """
    if not video_ids:
        return []

    service = _build_service(api_key)
    results = []

    # Batch into chunks of 50
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        response = service.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(batch),
        ).execute()

        for item in response.get("items", []):
            stats = item.get("statistics", {})
            results.append({
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "duration_seconds": _parse_iso8601_duration(
                    item["contentDetails"]["duration"]
                ),
            })

    return results


def fetch_channel_data(handle: str, api_key: str, days: int = 60) -> dict:
    """Fetch complete channel data for analysis.

    Orchestrates resolve_handle, get_recent_videos, and get_video_details
    to produce a full data structure for one channel.

    Args:
        handle: YouTube @handle
        api_key: YouTube Data API key
        days: Analysis window in days

    Returns:
        Dict with channel_id, channel_name, subscriber_count,
        uploads_playlist_id, period_videos, baseline_videos
    """
    channel_info = _retry(resolve_handle, handle, api_key)

    # Period videos: within the analysis window
    period_ids = _retry(
        get_recent_videos,
        channel_info["uploads_playlist_id"],
        api_key,
        days=days,
    )
    period_videos = _retry(get_video_details, period_ids, api_key) if period_ids else []
    period_videos = _filter_shorts(period_videos)

    # Baseline videos: most recent 50 long-form (for outlier calculation in Feature 2)
    # Fetch extra to compensate for shorts that get filtered out
    baseline_ids = _retry(
        get_recent_videos,
        channel_info["uploads_playlist_id"],
        api_key,
        max_videos=100,
    )
    baseline_videos = (
        _retry(get_video_details, baseline_ids, api_key) if baseline_ids else []
    )
    baseline_videos = _filter_shorts(baseline_videos)[:50]

    return {
        "channel_id": channel_info["channel_id"],
        "channel_name": channel_info["title"],
        "subscriber_count": channel_info["subscriber_count"],
        "total_views": channel_info["total_views"],
        "uploads_playlist_id": channel_info["uploads_playlist_id"],
        "period_videos": period_videos,
        "baseline_videos": baseline_videos,
    }


def _retry(func, *args, max_retries: int = 1, delay: float = 2.0, **kwargs):
    """Retry a function once on network/API errors.

    Quota errors (403) are raised immediately without retry.
    """
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                raise RuntimeError(
                    "YouTube API quota exceeded. Quota resets at midnight Pacific Time. "
                    "Check your usage at https://console.cloud.google.com/apis/dashboard"
                ) from e
            if attempt < max_retries:
                print(f"  API error (attempt {attempt + 1}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise
        except Exception:
            if attempt < max_retries:
                print(f"  Error (attempt {attempt + 1}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise
