# YouTube Data Pipeline — SOP

## What This Pipeline Does

Fetches public channel and video data from the YouTube Data API v3 for a primary channel and 4–7 competitors. Outputs structured JSON for downstream analytics (Feature 2) and AI insights (Feature 4).

## Inputs

| Input | Source | Example |
|-------|--------|---------|
| Primary channel handle | CLI `--channel` | `@mkbhd` |
| Competitor handles | CLI `--competitors` | `@c1 @c2 @c3 @c4` |
| Analysis window | CLI `--days` (default 60) | `60` |
| YouTube API key | `.env` `YOUTUBE_API_KEY` | — |

## Scripts

| Script | Purpose |
|--------|---------|
| `execution/youtube_api.py` | YouTube Data API v3 wrapper — resolve handles, fetch videos, parse details |
| `execution/main.py` | CLI entry point — orchestrates pipeline, saves output |

## How to Run

```bash
python execution/main.py --channel @handle --competitors @c1 @c2 @c3 @c4 --days 60
```

Run from the project root (`YouTube Competitor Analysis/`).

## API Quota Strategy

Uses `playlistItems.list` (uploads playlist) instead of `search.list` to minimize quota usage:

| Endpoint | Cost | Notes |
|----------|------|-------|
| `channels.list(forHandle=...)` | 1 unit | Resolve handle + stats |
| `playlistItems.list` | 1 unit/page | 50 videos per page |
| `videos.list` | 1 unit/batch | 50 video IDs per batch |

**Per channel**: ~4–6 units (resolve + 1-2 playlist pages + 1-2 video batches, x2 for period + baseline)
**Per run (8 channels)**: ~32–48 units out of 10,000 daily quota

## Two Video Fetches Per Channel

1. **Period videos** (`days=60`): Videos published within the analysis window. Used for period metrics.
2. **Baseline videos** (`max_videos=50`): Most recent 50 videos regardless of date. Used for outlier score calculation (median baseline).

## Edge Cases

| Scenario | Handling |
|----------|----------|
| @handle not found | `ValueError` raised, competitor skipped with warning |
| Hidden subscriber count | `subscriber_count` set to `None` |
| Channel has < 5 videos | All available videos returned |
| Duplicate handles | Deduplicated before fetching, warning printed |
| API quota exceeded (403) | Immediate error with reset time info |
| Network error | Retry once with 2s delay, then raise |
| Primary channel fails | Pipeline exits (can't proceed without it) |
| < 4 competitors after failures | Pipeline exits |
| YouTube Shorts | Filtered via HEAD request to `youtube.com/shorts/{id}` (200=Short, 303=not). Videos >3min skip the check. |

## Output Format

Saved to `.tmp/raw_data.json`:

```json
{
  "generated_at": "ISO 8601 timestamp",
  "days": 60,
  "channel": {
    "channel_id": "UC...",
    "channel_name": "Channel Title",
    "subscriber_count": 30700,
    "total_views": 5000000,
    "uploads_playlist_id": "UU...",
    "role": "channel",
    "period_videos": [
      {
        "video_id": "...",
        "title": "Video Title",
        "published_at": "2026-01-15T...",
        "views": 34857,
        "likes": 1200,
        "comments": 85,
        "duration_seconds": 754
      }
    ],
    "baseline_videos": [...]
  },
  "competitors": [
    { "...same structure...", "role": "competitor" }
  ]
}
```

## Lessons Learned

- `playlistItems.list` returns videos in reverse chronological order — stop paginating once past the cutoff date
- Uploads playlist ID: replace `UC` prefix with `UU`
- ISO 8601 duration format: `PT12M34S` = 754 seconds
- `videoPublishedAt` in playlistItems may differ from `publishedAt` in videos.list by a few seconds
- Shorts can be up to 3 minutes (since late 2024) — duration alone is not reliable for detection
- Shorts detection uses HEAD request to `youtube.com/shorts/{id}`: 200 = Short, 303 = regular video
- Videos > 180s skip the HEAD check (can't be Shorts), saving network calls
- Baseline fetch requests 100 videos and keeps the first 50 long-form to compensate for shorts being filtered
- 0.3s delay between HEAD requests to avoid rate limiting
