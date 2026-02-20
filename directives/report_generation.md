# Report Generation Directive

## Objective
Generate a filled Google Slides report from analytics data by copying the template, duplicating multi-instance slides, and replacing placeholder text with real data.

## Script
`execution/slides_report.py`

## Entry Point
```python
from slides_report import generate_report
url = generate_report(analytics, insights=None)
```

Also runnable standalone: `python execution/slides_report.py` (loads `.tmp/analytics.json`)

## Prerequisites
- `GOOGLE_SLIDES_TEMPLATE_ID` set in `.env`
- `credentials.json` and valid `token.json` in project root
- `.tmp/analytics.json` populated by the analytics pipeline

## Report Generation Flow

### Step 1: Copy Template
- Uses Drive API `files.copy` to create a new presentation
- Title format: "YouTube Analytics Report — {Month Year}"

### Step 2: Fill Title Slide
- Inserts current month/year and analysis window

### Step 3: Fill Channel Slide
- Single instance, uses original template objectIds directly
- Fills name, 4 metrics, and top 5 videos

### Step 4: Duplicate Competitor Slides
- **Reverse-order duplication**: last competitor first → produces correct final ordering
- Each `duplicateObject` is its own `batchUpdate` call to capture the `objectIdMapping`
- The mapping translates template IDs → new IDs for the duplicate

### Step 5: Fill Competitor Slides
- Uses `id_map` from each duplication to target the correct elements

### Step 6: Delete Original Competitor Template Slide
- Removes `tmpl_competitor` after all duplicates are created

### Step 7-8: Duplicate and Fill Idea Slides
- Same reverse-order pattern as competitors
- 5 idea slides created from single template

### Step 9-10: Fill Comparative and Takeaways Slides
- Uses original objectIds (single-instance slides)

### Step 11: Delete Original Idea Template Slide
- Removes `tmpl_idea` after all duplicates are created

### Step 12: Execute All Fills
- All text replacements accumulated into a single `batchUpdate` for efficiency

## Text Replacement Strategy

**Why not `replaceAllText`?**
`replaceAllText` is presentation-wide — it can't scope to a single slide. With duplicated slides (multiple competitors, multiple ideas), all copies share the same placeholder text. Using `replaceAllText` would replace text in ALL copies simultaneously.

**Instead: deleteText → insertText → updateTextStyle**
```python
_replace_shape_text(object_id, text, font_size, color, bold, id_map)
```
This targets a specific shape by objectId, which is unique per duplicate thanks to the `objectIdMapping`.

## Reverse-Order Duplication

`duplicateObject` inserts the new slide immediately after the source slide. To get competitors in order [1, 2, 3, 4]:
1. Duplicate for competitor 4 → appears after template
2. Duplicate for competitor 3 → appears after template (before 4)
3. Duplicate for competitor 2 → appears after template (before 3)
4. Duplicate for competitor 1 → appears after template (before 2)

Result after deleting template: slides are in order [1, 2, 3, 4].

## Fallback Behavior (insights=None)

When Feature 4 AI insights aren't available, the report still generates with data-driven content:

| Section | Fallback |
|---------|----------|
| Comparative Overview | Auto-generated from rankings data |
| Key Trends | Derived from views/engagement/outlier rankings |
| Content Gaps | Based on upload frequency, engagement, and views comparisons |
| Video Ideas | Based on cross-channel leaderboard top videos |
| Takeaways | Channel ranking stats + "Enable AI insights" prompt |

## Retry Strategy
`_retry_api()` with exponential backoff:
- Retries on HTTP 429 (rate limit), 500, 503
- Max 3 retries with delays: 2s, 4s, 8s
- All other errors raised immediately

## Error Handling in main.py
- Missing `GOOGLE_SLIDES_TEMPLATE_ID` → `ValueError`, prints helpful message
- Missing `credentials.json` → `FileNotFoundError`
- API failures → caught with generic `Exception`, analytics data preserved
- `--skip-slides` flag bypasses report entirely

## Expected Slide Count
For N competitors: 1 (title) + 1 (channel) + N (competitors) + 1 (comparative) + 5 (ideas) + 1 (takeaways) = N + 9

## Lessons Learned
- (Updated as issues are discovered)
