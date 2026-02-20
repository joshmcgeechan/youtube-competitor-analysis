# Analytics Engine — SOP

## What This Engine Does

Processes raw channel/video data from `.tmp/raw_data.json` into scored, summarized, and compared analytics. Output (`.tmp/analytics.json`) feeds into Feature 3 (Google Slides report) and Feature 4 (Claude AI insights).

## Scripts

| Script | Purpose |
|--------|---------|
| `execution/analytics.py` | Pure computation — outlier scores, engagement rates, channel summaries, comparative data |
| `execution/main.py` | Calls `process_all()` after data fetch, saves `.tmp/analytics.json` |

## Formulas

### Outlier Score

```
outlier_score = video_views / median(baseline_views)
```

- **Baseline**: Most recent 50 videos for the channel (fetched in Feature 1)
- **Interpretation**: 1.0 = median performance, 2.0 = double typical views, 0.5 = half typical
- **Edge case**: If median is 0 (no baseline videos), outlier_score = 0

### Engagement Rate

```
engagement = (likes + comments) / views * 100
```

- Returns 0.0 if views == 0
- Expressed as a percentage

### Upload Frequency

```
upload_frequency = video_count / (days / 7)
```

- Videos per week within the analysis window
- Minimum denominator of 1 week to avoid division by zero

## Output Structure

`.tmp/analytics.json`:

```json
{
  "channel": {
    "channel_id": "UC...",
    "channel_name": "Channel Title",
    "role": "channel",
    "subscriber_count": 30700,
    "total_period_views": 500000,
    "video_count": 8,
    "avg_engagement": 3.45,
    "avg_duration": 612.5,
    "upload_frequency": 0.93,
    "top_videos": [
      {
        "title": "Video Title",
        "video_id": "abc123",
        "views": 150000,
        "engagement": 4.2,
        "outlier_score": 3.5
      }
    ],
    "period_videos": [ "...scored videos with outlier_score and engagement fields..." ]
  },
  "competitors": [ "...same structure per competitor..." ],
  "comparative": {
    "views_ranking": [
      { "channel_name": "...", "total_period_views": 500000 }
    ],
    "engagement_ranking": [
      { "channel_name": "...", "avg_engagement": 3.45 }
    ],
    "outlier_ranking": [
      { "channel_name": "...", "highest_outlier_score": 5.2 }
    ],
    "top_performer": "Channel Name",
    "cross_channel_leaderboard": [
      {
        "channel_name": "...",
        "title": "Video Title",
        "video_id": "abc123",
        "views": 150000,
        "outlier_score": 5.2,
        "engagement": 4.2
      }
    ]
  }
}
```

## Edge Cases

| Scenario | Handling |
|----------|----------|
| 0 views on a video | engagement = 0.0, outlier_score depends on median |
| No baseline videos | median = 0, all outlier_scores = 0 |
| Hidden subscriber count | `subscriber_count` = `null` (passed through from raw data) |
| Channel has 0 period videos | video_count = 0, avg_engagement = 0, upload_frequency = 0 |
| All baseline videos have 0 views | median = 0, all outlier_scores = 0 |

## Lessons Learned

- (None yet — update as edge cases are discovered)
