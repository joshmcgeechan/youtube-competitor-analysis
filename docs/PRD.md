# YouTube Competitor Analysis Tool — PRD

## Overview

A CLI-driven automation that analyzes a YouTube channel's performance over the last 60 days alongside 4–7 competitor channels. It pulls public data via the YouTube Data API v3, calculates outlier scores (VidIQ-style), generates AI-powered insights using the Claude API, and outputs a polished Google Slides presentation with channel breakdowns, comparative analysis, data-backed video ideas, and strategic takeaways.

The tool is **niche-agnostic** — it works for any channel category, driven entirely by the @handles provided at runtime.

---

## Architecture

Follows the 3-layer pattern defined in `CLAUDE.md`:

| Layer | Role | Location |
|-------|------|----------|
| **Directive** | SOPs for each feature | `directives/` |
| **Orchestration** | CLI entry point, pipeline coordination | `execution/main.py` |
| **Execution** | Deterministic Python scripts | `execution/` |

### Directory Structure

```
YouTube Competitor Analysis/
├── CLAUDE.md                    # Agent instructions
├── docs/
│   └── PRD.md                   # This file
├── directives/                  # Markdown SOPs per feature
├── execution/                   # Python scripts
│   ├── main.py                  # CLI entry point & pipeline
│   ├── youtube_api.py           # YouTube Data API v3 wrapper
│   ├── analytics.py             # Outlier scoring & metrics
│   ├── slides_template.py       # One-time template builder
│   ├── slides_report.py         # Report generation (fill template)
│   ├── ai_insights.py           # Claude API for analysis & ideas
│   └── auth.py                  # OAuth 2.0 helper
├── .tmp/                        # Intermediate data (gitignored)
├── .env                         # API keys (gitignored)
├── credentials.json             # Google OAuth credentials (gitignored)
├── token.json                   # OAuth token cache (gitignored)
└── requirements.txt
```

---

## Configuration & Auth

### Environment Variables (`.env`)

```
YOUTUBE_API_KEY=<YouTube Data API v3 key>
ANTHROPIC_API_KEY=<Claude API key>
GOOGLE_SLIDES_TEMPLATE_ID=<ID of the template presentation>
```

### Google OAuth 2.0

- Required for Google Slides API (read/write presentations)
- `credentials.json` — OAuth client ID downloaded from Google Cloud Console
- `token.json` — auto-generated after first auth flow, cached for reuse
- Scopes: `https://www.googleapis.com/auth/presentations`, `https://www.googleapis.com/auth/drive`

### YouTube Data API v3

- API key only (no OAuth) — all data is public
- Default quota: 10,000 units/day
- Estimated usage per run: ~50 units for 8 channels (well within limits)

---

## CLI Interface

```bash
python execution/main.py \
  --channel @mychannel \
  --competitors @competitor1 @competitor2 @competitor3 @competitor4 \
  --days 60
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--channel` | Yes | — | Your channel's @handle |
| `--competitors` | Yes | — | 4–7 competitor @handles (space-separated) |
| `--days` | No | 60 | Analysis window in days |

### Output

- Google Slides presentation (shareable link printed to console)
- Intermediate data saved to `.tmp/` for debugging

---

## Outlier Score Calculation

Based on VidIQ's methodology:

```
outlier_score = video_views / channel_average_views
```

### Baseline Calculation

- Pull the channel's most recent **50 videos** (regardless of date)
- Calculate the **median** views across those 50 videos (median is more robust than mean — a single viral video won't skew the baseline)
- If the channel has fewer than 50 videos, use all available videos

### Interpretation

| Score | Meaning |
|-------|---------|
| < 1x | Underperforming relative to channel average |
| 1x–2x | Normal performance |
| 2x–5x | Above average |
| 5x–10x | Strong outlier |
| 10x+ | Viral outlier |

### Application

- Outlier scores are calculated for **all channels** (yours + competitors)
- Top 5 videos per channel are ranked by outlier score
- The comparative analysis highlights cross-channel outlier trends

---

## Google Slides Output

### Design Spec

- **Theme**: Dark background (#1A1A24), dark card backgrounds (#2D2D3D)
- **Headers**: Blue gradient accent bar (matching example screenshots)
- **Text**: White (#FFFFFF) primary, light gray (#B0B0B0) secondary
- **Accent colors**: Green (#4CAF50) for numbered circles/badges, red for alerts
- **Font**: Clean sans-serif (Roboto or similar)
- **Layout**: Minimal text, scannable, data-forward

### Slide Sequence

For a run with 1 channel + N competitors, the deck contains:

```
1. Title Slide
2. Your Channel Data
3. Competitor 1 Data
4. Competitor 2 Data
... (one slide per competitor)
N+2. Comparative Analysis
N+3. Video Idea 1
N+4. Video Idea 2
N+5. Video Idea 3
N+6. Video Idea 4
N+7. Video Idea 5
N+8. Key Takeaways & Next Steps
```

---

### Slide 1: Title Slide

```
┌─────────────────────────────────────────────┐
│                                             │
│     YOUTUBE ANALYTICS                       │
│     MONTHLY PERFORMANCE REPORT              │
│                                             │
│     February 2026                           │
│                                             │
└─────────────────────────────────────────────┘
```

- Current month and year, auto-generated from run date

---

### Slide 2: Your Channel Data

```
┌─────────────────────────────────────────────┐
│  YOUR CHANNEL                               │
│  Channel Name                               │
│  ┌──────────┬──────────┬────────┬─────────┐ │
│  │SUBSCRIBERS│VIEWS(60D)│ VIDEOS │ENGAGEMENT│ │
│  │  30,700  │  92,757  │   19   │  3.83%  │ │
│  └──────────┴──────────┴────────┴─────────┘ │
│                                             │
│  TOP PERFORMING VIDEOS                      │
│  ┌──┬─────────────────────┬───────┬────┬───┐│
│  │1.│ Video Title Here... │34,857 │3.7%│12x││
│  │2.│ Another Video Ti... │19,080 │3.5%│ 8x││
│  │3.│ Third Video Titl... │13,698 │3.4%│ 5x││
│  │4.│ Fourth Video Tit... │ 3,052 │2.1%│ 2x││
│  │5.│ Fifth Video Titl... │ 2,463 │1.8%│ 1x││
│  └──┴─────────────────────┴───────┴────┴───┘│
└─────────────────────────────────────────────┘
```

**Label**: "YOUR CHANNEL" (distinguishes from competitors)

**Metric boxes** (4 across):
- **Subscribers**: Current subscriber count
- **Views (60D)**: Total views across all videos published in the last 60 days
- **Videos**: Number of videos published in the last 60 days
- **Engagement**: Average engagement % across videos in period
  - `engagement = (likes + comments) / views * 100`

**Top Performing Videos** (5 rows):
- Rank, title (truncated), views, engagement %, outlier score

---

### Slide 3–N+1: Competitor Channel Data

Identical layout to "Your Channel" slide, but labeled **"COMPETITOR"** instead of "YOUR CHANNEL". One slide per competitor.

---

### Slide N+2: Comparative Analysis

```
┌─────────────────────────────────────────────┐
│  COMPARATIVE ANALYSIS                       │
│                                             │
│  ┌─────────────────────────────────────────┐│
│  │ Overview paragraph summarizing the      ││
│  │ competitive landscape...                ││
│  └─────────────────────────────────────────┘│
│                                             │
│  ┌───────────────────┬─────────────────────┐│
│  │ KEY TRENDS        │ CONTENT GAPS        ││
│  │ • Trend 1...      │ • Gap 1...          ││
│  │ • Trend 2...      │ • Gap 2...          ││
│  │ • Trend 3...      │ • Gap 3...          ││
│  └───────────────────┴─────────────────────┘│
│                                             │
│  TOP PERFORMER   Channel Name               │
└─────────────────────────────────────────────┘
```

**Content** (AI-generated via Claude API):
- **Overview**: 2–3 sentence summary of the competitive landscape
- **Key Trends**: 3 bullet points on what's working across competitors
- **Content Gaps**: 3 bullet points on topics/formats competitors cover that you don't
- **Top Performer**: The channel with the best performance in the period (by total views or highest outlier video)

---

### Slides N+3 to N+7: Video Ideas (5 slides)

```
┌─────────────────────────────────────────────┐
│  ① VIDEO IDEA                               │
│                                             │
│  ClawdBot vs Claude Code: I Tested Both     │
│  for 50 Hours (Honest Results)              │
│                                             │
│  ┌───────────────────┬─────────────────────┐│
│  │ TITLE VARIATIONS  │ HOOK OPTIONS        ││
│  │ 1. Variation A... │                     ││
│  │ 2. Variation B... │ Hook 1:             ││
│  │ 3. Variation C... │ "Opening line..."   ││
│  │ 4. Variation D... │                     ││
│  │ 5. Variation E... │ Hook 2:             ││
│  │                   │ "Opening line..."   ││
│  └───────────────────┴─────────────────────┘│
│                                             │
│  🟢 HIGH POTENTIAL                          │
└─────────────────────────────────────────────┘
```

**Content** (AI-generated via Claude API):
- **Main title**: The primary video idea title
- **Title Variations**: 5 alternative ways to title the video
- **Hook Options**: 2 written-out opening hooks (first 15 seconds of the video)
- **Potential Badge**: "HIGH POTENTIAL" — all ideas are data-backed from outlier analysis

**Generation Logic**:
- Claude receives: all outlier videos across channels, content gaps, trending topics, engagement patterns
- Claude outputs: 5 video ideas that capitalize on proven formats/topics from competitors, adapted for your channel

---

### Slide N+8: Key Takeaways & Next Steps

```
┌─────────────────────────────────────────────┐
│  KEY TAKEAWAYS & NEXT STEPS                 │
│                                             │
│  ① Takeaway 1: Actionable insight based    │
│     on the competitive analysis...          │
│                                             │
│  ② Takeaway 2: Another strategic           │
│     recommendation...                       │
│                                             │
│  ③ Takeaway 3: Third data-backed           │
│     recommendation...                       │
│                                             │
│  Review monthly to track progress and       │
│  adjust strategy                            │
└─────────────────────────────────────────────┘
```

**Content** (AI-generated via Claude API):
- **3 takeaways**: Specific, actionable recommendations based on the full analysis
- **Footer**: Reminder to review regularly

---

## Features

### Feature 1: Project Setup & YouTube Data Pipeline

**Objective**: Set up the project structure, configure the YouTube Data API, and build a CLI that fetches and stores channel + video data for all provided handles.

**Scope**:
1. Initialize project directories (`directives/`, `execution/`, `.tmp/`)
2. Create `requirements.txt` with dependencies
3. Create `.env` template and `.gitignore`
4. Implement `execution/youtube_api.py`:
   - `resolve_handle(handle: str) -> str` — resolve @handle to channel ID via `channels.list(forHandle=...)`
   - `get_channel_stats(channel_id: str) -> dict` — subscriber count, total views, video count
   - `get_recent_videos(channel_id: str, days: int) -> list[dict]` — fetch videos from last N days via `playlistItems.list` (uploads playlist, `UC` → `UU` prefix swap), then `videos.list` for stats/details. Returns list of `{title, video_id, published_at, views, likes, comments, duration_seconds}`
   - Efficient batching: up to 50 video IDs per `videos.list` call
5. Implement `execution/main.py`:
   - CLI argument parsing (`--channel`, `--competitors`, `--days`)
   - Call YouTube API functions for each handle
   - Save raw data to `.tmp/raw_data.json`
6. Write directive: `directives/youtube_data_pipeline.md`

**Test criteria**:
- Run CLI with real @handles, verify JSON output in `.tmp/`
- Verify correct subscriber counts, view counts against YouTube
- Verify all videos from last 60 days are captured
- Quota usage is within expected range (~50 units for 8 channels)

**API Quota Budget** (per channel):
| Call | Units |
|------|-------|
| `channels.list` (resolve handle + stats) | 1 |
| `playlistItems.list` (1–2 pages) | 1–2 |
| `videos.list` (1–2 batches of 50) | 1–2 |
| **Total per channel** | **~4** |
| **Total for 8 channels** | **~32** |

---

### Feature 2: Analytics Engine (Outlier Scoring & Metrics)

**Objective**: Process raw YouTube data into analytics: outlier scores, engagement rates, channel aggregates, and ranked video lists.

**Scope**:
1. Implement `execution/analytics.py`:
   - `calculate_outlier_scores(videos: list[dict], baseline_videos: list[dict]) -> list[dict]` — for each video, compute `outlier_score = views / median(baseline_views)`. Baseline = most recent 50 videos from the channel.
   - `calculate_engagement(video: dict) -> float` — `(likes + comments) / views * 100`
   - `build_channel_summary(channel_stats: dict, period_videos: list[dict]) -> dict` — aggregate metrics:
     - Subscriber count
     - Total views in period
     - Number of videos published in period
     - Average engagement %
     - Average video duration
     - Upload frequency (videos per week)
   - `rank_top_videos(videos: list[dict], n: int = 5) -> list[dict]` — top N videos by outlier score, with views, engagement %, and outlier score
   - `build_comparative_data(my_channel: dict, competitors: list[dict]) -> dict` — structure for comparative analysis:
     - Rankings by total views, engagement, outlier max
     - Top performer identification
     - Cross-channel outlier leaderboard
2. Pipeline integration in `main.py`:
   - After data fetch, run analytics on each channel
   - Save processed analytics to `.tmp/analytics.json`
3. Write directive: `directives/analytics_engine.md`

**Baseline Video Fetching**:
- The 50 baseline videos may extend beyond the 60-day window
- `get_recent_videos()` from Feature 1 should support a `max_videos` parameter in addition to `days`
- For outlier baseline: call with `max_videos=50, days=None`
- For period analysis: call with `days=60`

**Test criteria**:
- Manually verify outlier scores for known channels
- Engagement % matches `(likes + comments) / views * 100`
- Top 5 videos are correctly ranked by outlier score
- Channel summaries contain all required fields
- Comparative data correctly identifies top performer

---

### Feature 3: Google Slides Template & Report Generation

**Objective**: Create a dark-themed Google Slides template programmatically, then build a report generator that duplicates template slides and fills them with analytics data.

**Scope**:

#### Part A: Template Creation (one-time setup)
1. Implement `execution/auth.py`:
   - OAuth 2.0 flow for Google Slides + Drive APIs
   - Token caching in `token.json`
   - Scope: `presentations`, `drive`
2. Implement `execution/slides_template.py`:
   - Create a new Google Slides presentation
   - Build template slides matching the design spec:
     - **Title slide**: "YOUTUBE ANALYTICS MONTHLY PERFORMANCE REPORT" + month placeholder
     - **Channel data slide**: "YOUR CHANNEL" label, 4 metric boxes, top 5 videos table
     - **Competitor data slide**: "COMPETITOR" label, same layout
     - **Comparative analysis slide**: Overview box, key trends, content gaps, top performer
     - **Video idea slide**: Number circle, title, title variations, hook options, badge
     - **Key takeaways slide**: 3 numbered takeaways, footer
   - Dark theme: background #1A1A24, cards #2D2D3D, white text, blue accents, green circles
   - Store template ID in `.env` as `GOOGLE_SLIDES_TEMPLATE_ID`
3. Write directive: `directives/slides_template.md`

#### Part B: Report Generation
4. Implement `execution/slides_report.py`:
   - `generate_report(analytics: dict, insights: dict) -> str` — returns Google Slides URL
   - Copy the template presentation (via Drive API `files.copy`)
   - For each channel: duplicate the appropriate template slide, fill with data
   - Remove unused template slides after population
   - Fill all placeholders with real data:
     - Channel names, metrics, video titles, scores
     - AI-generated text (from Feature 4) for comparative analysis, video ideas, takeaways
   - Return the shareable link
5. Pipeline integration in `main.py`:
   - After analytics + AI insights, generate the report
   - Print shareable Google Slides URL to console
6. Write directive: `directives/report_generation.md`

**Template Approach Details**:
- Each template slide contains placeholder text (e.g., `{{channel_name}}`, `{{subscribers}}`, `{{video_1_title}}`)
- Report generator uses `replaceAllText` requests to swap placeholders with real values
- `duplicateObject` creates copies of template slides for each channel/idea
- After populating, delete the original template slides from the copy

**Test criteria**:
- Template creation script produces a properly styled presentation
- Report generation creates a new presentation with correct data
- All placeholder text is replaced — no `{{...}}` remaining
- Slide count matches expected: 1 + 1 + N competitors + 1 + 5 + 1
- Shareable link works and opens correctly

---

### Feature 4: AI-Powered Insights & Video Ideas

**Objective**: Use the Claude API to generate the comparative analysis, 5 video ideas with hooks, and strategic takeaways based on the analytics data.

**Scope**:
1. Implement `execution/ai_insights.py`:
   - `generate_comparative_analysis(my_channel: dict, competitors: list[dict]) -> dict`:
     - Input: channel summaries, top videos, outlier data for all channels
     - Output: `{overview: str, key_trends: [str, str, str], content_gaps: [str, str, str], top_performer: str}`
   - `generate_video_ideas(my_channel: dict, competitors: list[dict], comparative: dict) -> list[dict]`:
     - Input: all analytics data + comparative analysis
     - Output: 5 ideas, each with `{title: str, title_variations: [str x5], hook_1: str, hook_2: str}`
     - Ideas should be data-backed: reference specific outlier videos, trending formats, or content gaps
   - `generate_takeaways(my_channel: dict, competitors: list[dict], comparative: dict) -> list[str]`:
     - Input: full analysis
     - Output: 3 actionable takeaway strings
2. Prompt engineering:
   - System prompt establishes the role: YouTube strategist analyzing competitive data
   - User prompt includes structured analytics data (JSON)
   - Output format strictly defined for reliable parsing
   - Temperature set low for consistency
3. Pipeline integration in `main.py`:
   - After analytics, call AI insights
   - Pass results to report generator (Feature 3)
   - Save AI outputs to `.tmp/insights.json`
4. Write directive: `directives/ai_insights.md`

**Claude API Details**:
- Model: `claude-sonnet-4-5-20250929` (fast, capable, cost-effective for structured analysis)
- Structured output via tool use or JSON mode for reliable parsing
- Estimated tokens per run: ~4,000 input + ~2,000 output
- Cost per run: ~$0.02–0.04

**Prompt Strategy**:
- Provide all channel data as structured JSON
- Explicitly reference outlier videos and their scores
- Ask for specificity: "Reference specific competitor videos and their performance"
- Constrain output format to match slide placeholders exactly

**Implementation Notes**:
- Only `directives/sops/hooks.md` is loaded as context (not all SOPs)
- Video idea titles are data-driven from outlier analysis, not SOP-constrained
- User writes `directives/sops/hooks.md` during Feature 4 implementation

**Test criteria**:
- AI outputs parse correctly into expected data structures
- Comparative analysis references actual data (not hallucinated metrics)
- Video ideas are distinct and actionable
- Hooks are written as spoken word (first 15 seconds of video)
- Takeaways are specific to the channels analyzed, not generic advice

---

## Full Pipeline Flow

```
CLI Input (@handles, --days)
        │
        ▼
┌─────────────────────┐
│  Feature 1          │
│  YouTube Data API   │──► .tmp/raw_data.json
│  Fetch all channels │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Feature 2          │
│  Analytics Engine   │──► .tmp/analytics.json
│  Outlier scores     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Feature 4          │
│  Claude API         │──► .tmp/insights.json
│  AI Insights        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Feature 3          │
│  Google Slides      │──► Shareable Google Slides URL
│  Report Generation  │
└─────────────────────┘
```

---

## Dependencies

```
# requirements.txt
google-api-python-client>=2.100.0
google-auth>=2.20.0
google-auth-oauthlib>=1.1.0
google-auth-httplib2>=0.2.0
anthropic>=0.40.0
python-dotenv>=1.0.0
```

---

## API Reference

### YouTube Data API v3

| Endpoint | Purpose | Quota Cost |
|----------|---------|------------|
| `channels.list(forHandle=...)` | Resolve @handle → channel ID + stats | 1 unit |
| `playlistItems.list(playlistId=UU...)` | List recent uploads (50/page) | 1 unit/page |
| `videos.list(id=..., part=snippet,statistics,contentDetails)` | Video details + stats (50/call) | 1 unit/call |

### Google Slides API

| Method | Purpose |
|--------|---------|
| `presentations.create` | Create template (one-time) |
| `presentations.batchUpdate` | Build template elements, fill data |
| `drive.files.copy` | Copy template for each report |

### Claude API (Anthropic)

| Endpoint | Purpose |
|----------|---------|
| `messages.create` | Generate comparative analysis, video ideas, takeaways |

---

## Edge Cases & Error Handling

| Scenario | Handling |
|----------|----------|
| @handle not found | Print error, skip channel, continue with remaining |
| Channel has < 5 videos in 60 days | Show all available videos, note low activity |
| Channel has hidden subscriber count | Display "Hidden" instead of number |
| YouTube API quota exceeded | Print clear error with quota reset time (midnight PT) |
| Google Slides API rate limit (429) | Exponential backoff, max 3 retries |
| Claude API error | Retry once, then generate report without AI sections (data-only fallback) |
| Video has 0 views | Outlier score = 0, engagement = 0% |
| Duplicate @handles in input | Deduplicate, warn user |

---

## Future Enhancements (Out of Scope)

- Historical data storage and cross-run comparisons
- Scheduled/automated runs (cron, GitHub Actions)
- Web UI for input and report viewing
- YouTube Shorts-specific analysis
- Thumbnail analysis
- Private analytics (YouTube Analytics API) for own channel
- Export to PDF
- Multi-language support
