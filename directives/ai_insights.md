# AI Insights Directive

## Objective

Generate AI-powered comparative analysis, video ideas, and strategic takeaways using the Claude API. Transforms raw analytics data into actionable content for the Google Slides report.

## Script

`execution/ai_insights.py`

## Inputs

- `.tmp/analytics.json` — processed analytics data from the analytics engine
- `ANTHROPIC_API_KEY` — set in `.env`

## Outputs

- `.tmp/insights.json` — structured AI insights dict with three keys:
  - `comparative_analysis`: `{overview, key_trends, content_gaps}`
  - `video_ideas`: list of 5 `{title, title_variations, hooks, topic}`
  - `takeaways`: list of 3 strings

## Pipeline Position

```
analytics.json → ai_insights.py → insights.json → slides_report.py
```

Called after analytics, before report generation. If AI insights fail, the pipeline continues with data-driven fallback content.

## API Details

- **Model**: `claude-sonnet-4-5-20250929`
- **Temperature**: 0.3 for analysis/takeaways, 0.5 for video ideas
- **Estimated tokens**: ~4,000 input + ~2,000 output per run
- **Cost**: ~$0.02–0.04 per run
- **Calls**: 3 sequential API calls (comparative → ideas → takeaways)

## Prompt Strategy

- System prompt establishes YouTube strategist role
- User prompt includes structured analytics summary (channel stats, top videos, rankings, leaderboard)
- Output forced to JSON via assistant prefill technique (`{` or `[`)
- Each prompt explicitly prohibits generic advice — must reference actual data

## Error Handling

- Missing API key: raises `ValueError` with setup instructions
- API errors: caught in `main.py`, falls back to data-driven content (no AI sections)
- JSON parse errors: will propagate — prompts are designed to produce valid JSON

## Edge Cases

| Scenario | Handling |
|----------|----------|
| ANTHROPIC_API_KEY not set | Pipeline skips AI insights, uses fallback |
| Claude API error (rate limit, timeout) | Caught in main.py, falls back to data-only |
| Malformed JSON response | Error propagates, falls back to data-only |
| Fewer than 5 video ideas returned | `generate_video_ideas()` slices to first 5; `slides_report.py` pads to 5 |
| Fewer than 3 takeaways returned | `generate_takeaways()` slices to first 3; `slides_report.py` handles short lists |

## Standalone Usage

```bash
python execution/ai_insights.py
```

Reads `.tmp/analytics.json`, generates insights, saves to `.tmp/insights.json`.
