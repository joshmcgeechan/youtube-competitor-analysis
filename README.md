# YouTube Competitor Analysis

Analyze any YouTube channel against 4-7 competitors. Fetches video data, scores outliers, generates AI-powered insights, and delivers a polished Google Slides report — all from one terminal command.

## Web App

A Streamlit web UI is available for non-technical users. No terminal or Python needed — just open the link in a browser, enter the password, fill in the channels, and get a Google Slides report.

**Hosted at:** Streamlit Community Cloud (password-protected)

To run locally instead:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

## CLI Quick Start

Open PowerShell and run:

```powershell
cd "C:\Claude Code\YouTube Competitor Analysis"; python execution/main.py --channel "@clienthandle" --competitors "@comp1" "@comp2" "@comp3" "@comp4" --days 60
```

**Important:** In PowerShell, each `@handle` must be wrapped in double quotes — PowerShell treats `@` as a special character.

The pipeline runs automatically and prints a Google Slides link when done.

## What It Does

1. **Fetches** YouTube data for all channels via the YouTube Data API (Shorts are filtered out automatically)
2. **Analyzes** performance — outlier scores (VidIQ-style), cross-channel leaderboard, engagement metrics
3. **Generates AI insights** via Claude API — comparative analysis, 5 video ideas with hooks, key takeaways
4. **Creates a Google Slides report** — a new presentation each run, ready to share with a client

## Requirements

### API Keys

Copy `.env.example` to `.env` and fill in:

```
YOUTUBE_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GOOGLE_SLIDES_TEMPLATE_ID=your_template_id_here
```

- **YouTube Data API key** — from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- **Anthropic API key** — from [Anthropic Console](https://console.anthropic.com/)
- **Google Slides template ID** — created automatically on first run, or set manually

### Google OAuth

A `credentials.json` file is required for Google Slides access. On first run, it will open a browser for OAuth consent and save `token.json` for future runs.

### Python Packages

```powershell
python -m pip install -r requirements.txt
```

## Usage

### Basic Run

```powershell
python execution/main.py --channel "@mkbhd" --competitors "@LinusTechTips" "@JerryRigEverything" "@UnboxTherapy" "@austinevans" --days 60
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--channel` | Your client's @handle (required) | — |
| `--competitors` | 4-7 competitor @handles (required) | — |
| `--days` | Analysis window in days | 60 |
| `--skip-slides` | Skip report generation, output data only | off |

### Data-Only Run (No Slides)

```powershell
python execution/main.py --channel "@handle" --competitors "@c1" "@c2" "@c3" "@c4" --skip-slides
```

Analytics and AI insights are still saved to `.tmp/` — useful for debugging or if Google credentials aren't set up.

## Output

- **Google Slides report** — link printed to terminal, a new presentation each run
- `.tmp/raw_data.json` — raw YouTube API response data
- `.tmp/analytics.json` — computed metrics, outlier scores, leaderboard
- `.tmp/insights.json` — AI-generated comparative analysis, video ideas, takeaways

The `.tmp/` folder is overwritten each run. The Slides report is the deliverable.

## Tips

- **Handle format**: Use the exact @handle from the channel URL (e.g., `@mkbhd`, not `@MKBHD` or `Marques Brownlee`)
- **Ambiguous handles**: Generic handles like `@Austin` may resolve to the wrong channel. Use the full handle (e.g., `@austinevans`)
- **Quota**: Each run uses ~30 of 10,000 daily YouTube API units — you can run this 300+ times per day
- **Niche-agnostic**: Works for any YouTube niche — tech, leadership, fitness, cooking, etc.
- **Shorts filtering**: Only long-form videos are analyzed. Shorts are detected and excluded automatically.

## Folder Structure

```
YouTube Competitor Analysis/
  app.py              Streamlit web UI
  .streamlit/         Streamlit config (dark theme)
  execution/          Python scripts (pipeline stages)
    pipeline.py       Reusable pipeline logic (used by CLI and web)
    main.py           CLI entry point
  directives/         Markdown SOPs (instructions for each stage)
  .tmp/               Intermediate files (overwritten each run)
  .env                API keys (not committed)
  credentials.json    Google OAuth credentials (not committed)
  token.json          Google OAuth token (not committed)
```
