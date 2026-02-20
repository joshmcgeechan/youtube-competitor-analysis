# Slides Template Directive

## Objective
Create a one-time Google Slides template with 6 dark-themed slides that serves as the base for all generated reports. The template uses deterministic objectIds so the report generator can reliably target elements for text replacement.

## Script
`execution/slides_template.py`

## When to Run
- Once during initial setup
- Again only if the template design changes or the template is deleted
- After running, store the presentation ID in `.env` as `GOOGLE_SLIDES_TEMPLATE_ID`

## Template Structure (6 Slides)

### Slide 1: Title
- Page ID: `tmpl_title`
- Blue gradient accent bar at top (~35% of slide height)
- "YOUTUBE ANALYTICS" main title (40pt bold white)
- "MONTHLY PERFORMANCE REPORT" subtitle (24pt white)
- Date placeholder `tmpl_title_date` (16pt light gray)

### Slide 2: Your Channel
- Page ID: `tmpl_channel`
- "YOUR CHANNEL" green label + channel name
- 4 metric boxes (Subscribers/Views/Videos/Engagement) with colored accent lines (green/blue/orange/red)
- Top 5 videos table with rank, title, views (green), engagement (gray)

### Slide 3: Competitor (Template)
- Page ID: `tmpl_competitor`
- Identical layout to channel slide, labeled "COMPETITOR"
- Duplicated N times in report via `duplicateObject`

### Slide 4: Comparative Analysis
- Page ID: `tmpl_comparative`
- Overview text box in card
- Two-column layout: Key Trends | Content Gaps
- Bottom row: Top Performer name

### Slide 5: Video Idea (Template)
- Page ID: `tmpl_idea`
- Green number circle + "VIDEO IDEA" label
- Idea title (18pt bold)
- Two-column: Title Variations (5 lines) | Hook Options (2 hooks)
- "HIGH POTENTIAL" badge + topic line
- Duplicated 5 times in report

### Slide 6: Key Takeaways
- Page ID: `tmpl_takeaways`
- Blue header bar with "KEY TAKEAWAYS & NEXT STEPS"
- 3 numbered items with green circles and card backgrounds
- Footer: "Review monthly to track progress and adjust strategy"

## ObjectId Convention
Pattern: `tmpl_{slide_type}_{element}`

Examples:
- `tmpl_channel_name` — channel name text on the channel slide
- `tmpl_comp_v3_title` — 3rd video title on the competitor slide
- `tmpl_idea_hook1_text` — first hook text on the idea slide
- `tmpl_take_2_text` — second takeaway text

Deterministic IDs are critical — they enable the `objectIdMapping` strategy when `duplicateObject` creates copies in the report.

## Design Spec
- Background: `#1A1A24` (dark navy)
- Cards: `#2D2D3D` (dark gray)
- Text: White (`#FFFFFF`) and Light Gray (`#B3B3B3`)
- Green accent: `#4CAF50` (section headers, metrics, number circles)
- Blue accent: `#879BE8` (gradient bars)
- Red accent: `#E53935` (title variations/hooks headers)
- Orange accent: `#FF9800` (videos metric box)
- Font: Roboto throughout
- Slide size: 10" x 7.5" (9144000 x 6858000 EMU)

## Edge Cases
- If `credentials.json` is missing, the script raises `FileNotFoundError` with instructions
- If the Google API is unavailable, standard `HttpError` propagates
- Running the script multiple times creates multiple templates — only the latest should be stored in `.env`

## Lessons Learned
- (Updated as issues are discovered)
