"""One-time template builder for YouTube Analytics Google Slides report.

Design system: Luminous Signal
Fonts: Outfit (headings), Instrument Sans (body), Roboto Mono (numbers)
Palette: Deep dark (#12121E), Emerald/Electric/Amber/Coral accents

Run once to create the 6-slide template, then store the presentation ID
in .env as GOOGLE_SLIDES_TEMPLATE_ID.

Usage:
    python execution/slides_template.py
"""

from auth import build_slides_service

# ---------------------------------------------------------------------------
# Design constants (EMU = English Metric Units, 1 inch = 914400 EMU)
# ---------------------------------------------------------------------------
SLIDE_W = 9144000   # 10 inches
SLIDE_H = 6858000   # 7.5 inches
EMU_INCH = 914400
EMU_PT = 12700      # 1 point = 12700 EMU

# ---------------------------------------------------------------------------
# Color palette — Luminous Signal (RGB floats 0-1)
# ---------------------------------------------------------------------------
BG_COLOR   = {"red": 0.071, "green": 0.071, "blue": 0.118}       # #12121E
CARD_COLOR = {"red": 0.118, "green": 0.122, "blue": 0.188}       # #1E1F30

# Text hierarchy
WHITE      = {"red": 0.941, "green": 0.949, "blue": 0.980}       # #F0F2FA
LIGHT_GRAY = {"red": 0.627, "green": 0.647, "blue": 0.745}       # #A0A5BE
TERTIARY   = {"red": 0.392, "green": 0.412, "blue": 0.510}       # #646982

# Accent colors — semantic
GREEN        = {"red": 0.282, "green": 0.780, "blue": 0.557}     # #48C78E (emerald)
BLUE_LIGHT   = {"red": 0.373, "green": 0.490, "blue": 0.912}     # #5F7DE9 (gradient mid)
RED_ACCENT   = {"red": 0.937, "green": 0.424, "blue": 0.424}     # #EF6C6C (coral)
ORANGE_ACCENT = {"red": 1.0, "green": 0.718, "blue": 0.302}      # #FFB74D (amber)

# Header band color (dark navy, near-background tone)
HEADER_DARK = {"red": 0.114, "green": 0.118, "blue": 0.173}      # #1D1E2C

# Pure white for on-gradient text
PURE_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}

# Font families
FONT_DISPLAY = "Outfit"
FONT_BODY = "Instrument Sans"
FONT_MONO = "Roboto Mono"
FONT_LABEL = "Work Sans"
FONT_FAMILY = "Instrument Sans"  # default for report generator

# Slide page IDs
PAGE_TITLE = "tmpl_title"
PAGE_CHANNEL = "tmpl_channel"
PAGE_COMPETITOR = "tmpl_competitor"
PAGE_COMPARATIVE = "tmpl_comparative"
PAGE_IDEA = "tmpl_idea"
PAGE_TAKEAWAYS = "tmpl_takeaways"


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _create_slide(page_id: str) -> dict:
    return {
        "createSlide": {
            "objectId": page_id,
            "slideLayoutReference": {"predefinedLayout": "BLANK"},
        }
    }


def _set_bg(page_id: str, color: dict) -> dict:
    return {
        "updatePageProperties": {
            "objectId": page_id,
            "pageProperties": {
                "pageBackgroundFill": {
                    "solidFill": {"color": {"rgbColor": color}}
                }
            },
            "fields": "pageBackgroundFill.solidFill.color",
        }
    }


def _shape(oid: str, page_id: str, x: int, y: int, w: int, h: int,
           shape_type: str = "RECTANGLE") -> dict:
    return {
        "createShape": {
            "objectId": oid,
            "shapeType": shape_type,
            "elementProperties": {
                "pageObjectId": page_id,
                "size": {
                    "width": {"magnitude": w, "unit": "EMU"},
                    "height": {"magnitude": h, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1, "scaleY": 1,
                    "translateX": x, "translateY": y, "unit": "EMU",
                },
            },
        }
    }


def _rect(oid: str, page_id: str, x: int, y: int, w: int, h: int,
          fill: dict) -> list[dict]:
    """Filled rectangle, no outline."""
    return [
        _shape(oid, page_id, x, y, w, h),
        {"updateShapeProperties": {
            "objectId": oid,
            "shapeProperties": {
                "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": fill}}},
                "outline": {"propertyState": "NOT_RENDERED"},
            },
            "fields": "shapeBackgroundFill.solidFill.color,outline",
        }},
    ]


def _clear_shape(oid: str) -> dict:
    """Remove fill and outline from a text shape."""
    return {
        "updateShapeProperties": {
            "objectId": oid,
            "shapeProperties": {
                "shapeBackgroundFill": {"propertyState": "NOT_RENDERED"},
                "outline": {"propertyState": "NOT_RENDERED"},
            },
            "fields": "shapeBackgroundFill,outline",
        }
    }


def _text(oid: str, text: str) -> dict:
    return {"insertText": {"objectId": oid, "text": text, "insertionIndex": 0}}


def _style(oid: str, color: dict, size: int, bold: bool = False,
           font: str = FONT_BODY) -> dict:
    return {
        "updateTextStyle": {
            "objectId": oid,
            "style": {
                "foregroundColor": {"opaqueColor": {"rgbColor": color}},
                "fontSize": {"magnitude": size, "unit": "PT"},
                "bold": bold,
                "fontFamily": font,
            },
            "textRange": {"type": "ALL"},
            "fields": "foregroundColor,fontSize,bold,fontFamily",
        }
    }


def _align(oid: str, alignment: str = "CENTER") -> dict:
    return {
        "updateParagraphStyle": {
            "objectId": oid,
            "style": {"alignment": alignment},
            "textRange": {"type": "ALL"},
            "fields": "alignment",
        }
    }


def _text_box(oid: str, page_id: str, x: int, y: int, w: int, h: int,
              text: str, color: dict, size: int, bold: bool = False,
              font: str = FONT_BODY, alignment: str = "START") -> list[dict]:
    """Create a transparent text box with styled text."""
    return [
        _shape(oid, page_id, x, y, w, h),
        _clear_shape(oid),
        _text(oid, text),
        _style(oid, color, size, bold, font),
        _align(oid, alignment),
    ]


# Shorthand for inches to EMU
def _in(inches: float) -> int:
    return int(EMU_INCH * inches)


# ---------------------------------------------------------------------------
# Slide 1: Title — centered, full-gradient background
# ---------------------------------------------------------------------------

def _build_title_slide() -> list[dict]:
    reqs = [_create_slide(PAGE_TITLE), _set_bg(PAGE_TITLE, BG_COLOR)]

    # Gradient band (solid fill approximation) — covers top 60%
    reqs += _rect("tmpl_title_gradient", PAGE_TITLE,
                  0, 0, SLIDE_W, _in(4.5), HEADER_DARK)

    # "YOUTUBE" — centered, massive
    reqs += _text_box("tmpl_title_line1", PAGE_TITLE,
                      0, _in(1.4), SLIDE_W, _in(1.0),
                      "YOUTUBE", PURE_WHITE, 60, bold=True,
                      font=FONT_DISPLAY, alignment="CENTER")

    # "ANALYTICS" — centered, massive
    reqs += _text_box("tmpl_title_line2", PAGE_TITLE,
                      0, _in(2.3), SLIDE_W, _in(1.0),
                      "ANALYTICS", PURE_WHITE, 60, bold=True,
                      font=FONT_DISPLAY, alignment="CENTER")

    # Emerald accent bar — centered, thin
    bar_w = _in(1.2)
    bar_x = (SLIDE_W - bar_w) // 2
    reqs += _rect("tmpl_title_accent", PAGE_TITLE,
                  bar_x, _in(3.45), bar_w, _in(0.05), GREEN)

    # "MONTHLY PERFORMANCE REPORT" — centered
    reqs += _text_box("tmpl_title_subtitle", PAGE_TITLE,
                      0, _in(3.65), SLIDE_W, _in(0.5),
                      "MONTHLY PERFORMANCE REPORT", PURE_WHITE, 20, bold=False,
                      font=FONT_DISPLAY, alignment="CENTER")

    # Date placeholder — centered
    reqs += _text_box("tmpl_title_date", PAGE_TITLE,
                      0, _in(4.2), SLIDE_W, _in(0.4),
                      "{{DATE}}", LIGHT_GRAY, 14, font=FONT_BODY,
                      alignment="CENTER")

    # Channel name — centered, below date
    reqs += _text_box("tmpl_title_channel", PAGE_TITLE,
                      0, _in(4.8), SLIDE_W, _in(0.5),
                      "{{CHANNEL_NAME}}", WHITE, 24, bold=True,
                      font=FONT_DISPLAY, alignment="CENTER")

    # Footer — bottom left
    reqs += _text_box("tmpl_title_footer", PAGE_TITLE,
                      _in(0.5), _in(6.8), _in(5.0), _in(0.4),
                      "GENERATED BY  YouTube Analytics Engine",
                      TERTIARY, 9, font=FONT_LABEL)

    return reqs


# ---------------------------------------------------------------------------
# Slide 2/3: Channel / Competitor data
# ---------------------------------------------------------------------------

def _build_channel_slide() -> list[dict]:
    return _build_data_slide(PAGE_CHANNEL, "channel", "YOUR CHANNEL")


def _build_competitor_slide() -> list[dict]:
    return _build_data_slide(PAGE_COMPETITOR, "comp", "COMPETITOR")


def _build_data_slide(page_id: str, prefix: str, label: str) -> list[dict]:
    reqs = [_create_slide(page_id), _set_bg(page_id, BG_COLOR)]

    is_comp = prefix == "comp"
    accent = BLUE_LIGHT if is_comp else GREEN

    # Compact gradient header band
    reqs += _rect(f"tmpl_{prefix}_gradient", page_id,
                  0, 0, SLIDE_W, _in(0.5), HEADER_DARK)

    # Label
    reqs += _text_box(f"tmpl_{prefix}_label", page_id,
                      _in(0.5), _in(0.6), _in(3.0), _in(0.3),
                      label, accent, 11, bold=True, font=FONT_LABEL)

    # Channel name — large
    reqs += _text_box(f"tmpl_{prefix}_name", page_id,
                      _in(0.5), _in(0.85), _in(8.0), _in(0.6),
                      "{{CHANNEL_NAME}}", WHITE, 32, bold=True, font=FONT_DISPLAY)

    # Accent line under name
    reqs += _rect(f"tmpl_{prefix}_line", page_id,
                  _in(0.5), _in(1.45), _in(9.0), _in(0.03), accent)

    # 4 metric cards
    card_w = int((_in(9.0) - 3 * _in(0.12)) / 4)
    card_h = _in(0.82)
    card_y = _in(1.6)

    metrics = [
        ("subscribers", "SUBSCRIBERS", "{{SUBSCRIBERS}}", GREEN),
        ("views", "VIEWS (60D)", "{{VIEWS}}", BLUE_LIGHT),
        ("videos", "VIDEOS", "{{VIDEOS}}", ORANGE_ACCENT),
        ("engagement", "ENGAGEMENT", "{{ENGAGEMENT}}", RED_ACCENT),
    ]

    for i, (key, m_label, placeholder, m_color) in enumerate(metrics):
        cx = _in(0.5) + i * (card_w + _in(0.12))

        # Card background
        reqs += _rect(f"tmpl_{prefix}_{key}_bg", page_id,
                      cx, card_y, card_w, card_h, CARD_COLOR)
        # Accent line on card
        reqs += _rect(f"tmpl_{prefix}_{key}_accent", page_id,
                      cx, card_y, card_w, _in(0.03), m_color)
        # Label
        reqs += _text_box(f"tmpl_{prefix}_{key}_label", page_id,
                          cx + _in(0.15), card_y + _in(0.08),
                          card_w - _in(0.3), _in(0.2),
                          m_label, TERTIARY, 9, bold=True, font=FONT_LABEL)
        # Value — mono numbers (14pt fits 10+ char numbers like 20,800,000)
        reqs += _text_box(f"tmpl_{prefix}_{key}_value", page_id,
                          cx + _in(0.15), card_y + _in(0.3),
                          card_w - _in(0.3), _in(0.45),
                          placeholder, WHITE, 14, bold=True, font=FONT_MONO)

    # "TOP PERFORMING VIDEOS" header
    tph_y = card_y + card_h + _in(0.22)
    reqs += _text_box(f"tmpl_{prefix}_top_header", page_id,
                      _in(0.5), tph_y, _in(4.0), _in(0.3),
                      "TOP PERFORMING VIDEOS", accent, 11, bold=True, font=FONT_LABEL)

    # 5 video rows
    row_h = _in(0.44)
    row_y_start = tph_y + _in(0.4)
    row_gap = _in(0.05)

    for v in range(1, 6):
        ry = row_y_start + (v - 1) * (row_h + row_gap)

        # Row background (subtle alternating)
        row_fill = CARD_COLOR if v % 2 == 1 else BG_COLOR
        reqs += _rect(f"tmpl_{prefix}_v{v}_bg", page_id,
                      _in(0.5), ry, _in(9.0), row_h, row_fill)

        # Rank
        reqs += _text_box(f"tmpl_{prefix}_v{v}_rank", page_id,
                          _in(0.6), ry + _in(0.08),
                          _in(0.35), row_h - _in(0.16),
                          f"{v}.", TERTIARY, 11, bold=True, font=FONT_BODY)

        # Title
        reqs += _text_box(f"tmpl_{prefix}_v{v}_title", page_id,
                          _in(1.0), ry + _in(0.08),
                          _in(5.5), row_h - _in(0.16),
                          f"{{{{V{v}_TITLE}}}}", WHITE, 11, font=FONT_BODY)

        # Views
        reqs += _text_box(f"tmpl_{prefix}_v{v}_views", page_id,
                          _in(6.7), ry + _in(0.08),
                          _in(1.4), row_h - _in(0.16),
                          f"{{{{V{v}_VIEWS}}}}", GREEN, 11, bold=True, font=FONT_MONO)

        # Engagement
        reqs += _text_box(f"tmpl_{prefix}_v{v}_engagement", page_id,
                          _in(8.2), ry + _in(0.08),
                          _in(1.1), row_h - _in(0.16),
                          f"{{{{V{v}_ENG}}}}", LIGHT_GRAY, 11, font=FONT_MONO)

    return reqs


# ---------------------------------------------------------------------------
# Slide 4: Comparative Analysis
# ---------------------------------------------------------------------------

def _build_comparative_slide() -> list[dict]:
    page_id = PAGE_COMPARATIVE
    reqs = [_create_slide(page_id), _set_bg(page_id, BG_COLOR)]

    # Header — single line
    reqs += _text_box("tmpl_comp_header", page_id,
                      _in(0.5), _in(0.2), _in(9.0), _in(0.55),
                      "COMPARATIVE ANALYSIS", WHITE, 32, bold=True, font=FONT_DISPLAY)

    # Blue accent line
    reqs += _rect("tmpl_comp_accent_line", page_id,
                  _in(0.5), _in(0.8), _in(1.8), _in(0.04), BLUE_LIGHT)

    # Overview card
    ov_y = _in(1.0)
    ov_h = _in(1.0)
    reqs += _rect("tmpl_comp_overview_bg", page_id,
                  _in(0.5), ov_y, _in(9.0), ov_h, CARD_COLOR)
    reqs += _rect("tmpl_comp_overview_accent", page_id,
                  _in(0.5), ov_y, _in(9.0), _in(0.03), BLUE_LIGHT)
    reqs += _text_box("tmpl_comp_overview_text", page_id,
                      _in(0.7), ov_y + _in(0.15),
                      _in(8.6), ov_h - _in(0.3),
                      "{{OVERVIEW}}", LIGHT_GRAY, 10, font=FONT_BODY)

    # Two columns: Key Trends | Content Gaps
    col_gap = _in(0.15)
    col_w = int((_in(9.0) - col_gap) / 2)
    col_y = ov_y + ov_h + _in(0.15)
    col_h = _in(3.55)
    left_x = _in(0.5)
    right_x = _in(0.5) + col_w + col_gap

    # Key Trends
    reqs += _rect("tmpl_comp_trends_bg", page_id,
                  left_x, col_y, col_w, col_h, CARD_COLOR)
    reqs += _rect("tmpl_comp_trends_accent", page_id,
                  left_x, col_y, col_w, _in(0.03), GREEN)
    reqs += _text_box("tmpl_comp_trends_header", page_id,
                      left_x + _in(0.2), col_y + _in(0.12),
                      _in(3.0), _in(0.3),
                      "KEY TRENDS", GREEN, 11, bold=True, font=FONT_LABEL)
    reqs += _text_box("tmpl_comp_trends_text", page_id,
                      left_x + _in(0.2), col_y + _in(0.38),
                      col_w - _in(0.4), col_h - _in(0.5),
                      "{{KEY_TRENDS}}", LIGHT_GRAY, 10, font=FONT_BODY)

    # Content Gaps
    reqs += _rect("tmpl_comp_gaps_bg", page_id,
                  right_x, col_y, col_w, col_h, CARD_COLOR)
    reqs += _rect("tmpl_comp_gaps_accent", page_id,
                  right_x, col_y, col_w, _in(0.03), ORANGE_ACCENT)
    reqs += _text_box("tmpl_comp_gaps_header", page_id,
                      right_x + _in(0.2), col_y + _in(0.12),
                      _in(3.0), _in(0.3),
                      "CONTENT GAPS", ORANGE_ACCENT, 11, bold=True, font=FONT_LABEL)
    reqs += _text_box("tmpl_comp_gaps_text", page_id,
                      right_x + _in(0.2), col_y + _in(0.38),
                      col_w - _in(0.4), col_h - _in(0.5),
                      "{{CONTENT_GAPS}}", LIGHT_GRAY, 10, font=FONT_BODY)

    # Top performer row
    tp_y = col_y + col_h + _in(0.15)
    tp_h = _in(0.5)
    reqs += _rect("tmpl_comp_top_bg", page_id,
                  _in(0.5), tp_y, _in(9.0), tp_h, CARD_COLOR)
    reqs += _text_box("tmpl_comp_top_label", page_id,
                      _in(0.7), tp_y + _in(0.1),
                      _in(2.0), _in(0.3),
                      "TOP PERFORMER", GREEN, 11, bold=True, font=FONT_LABEL)
    reqs += _text_box("tmpl_comp_top_name", page_id,
                      _in(2.8), tp_y + _in(0.08),
                      _in(5.0), _in(0.35),
                      "{{TOP_PERFORMER}}", WHITE, 18, bold=True, font=FONT_DISPLAY)

    return reqs


# ---------------------------------------------------------------------------
# Slide 5: Video Idea
# ---------------------------------------------------------------------------

def _build_idea_slide() -> list[dict]:
    page_id = PAGE_IDEA
    reqs = [_create_slide(page_id), _set_bg(page_id, BG_COLOR)]

    # Green circle + number
    reqs += _rect("tmpl_idea_circle", page_id,
                  _in(0.5), _in(0.2), _in(0.5), _in(0.5), GREEN)
    reqs += _text_box("tmpl_idea_number", page_id,
                      _in(0.5), _in(0.2), _in(0.5), _in(0.5),
                      "{{IDEA_NUM}}", PURE_WHITE, 18, bold=True,
                      font=FONT_DISPLAY, alignment="CENTER")

    # "VIDEO IDEA" label
    reqs += _text_box("tmpl_idea_label", page_id,
                      _in(1.15), _in(0.3), _in(2.0), _in(0.3),
                      "VIDEO IDEA", TERTIARY, 11, bold=True, font=FONT_LABEL)

    # Idea title — large
    reqs += _text_box("tmpl_idea_title", page_id,
                      _in(0.5), _in(0.85), _in(9.0), _in(0.8),
                      "{{IDEA_TITLE}}", WHITE, 24, bold=True, font=FONT_DISPLAY)

    # Emerald accent line
    reqs += _rect("tmpl_idea_accent", page_id,
                  _in(0.5), _in(1.75), _in(0.8), _in(0.04), GREEN)

    # Two columns: Title Variations | Hook Options
    col_gap = _in(0.15)
    col_w = int((_in(9.0) - col_gap) / 2)
    col_y = _in(1.95)
    col_h = _in(3.7)
    left_x = _in(0.5)
    right_x = _in(0.5) + col_w + col_gap

    # Title Variations card
    reqs += _rect("tmpl_idea_titles_bg", page_id,
                  left_x, col_y, col_w, col_h, CARD_COLOR)
    reqs += _rect("tmpl_idea_titles_accent", page_id,
                  left_x, col_y, col_w, _in(0.03), RED_ACCENT)
    reqs += _text_box("tmpl_idea_titles_header", page_id,
                      left_x + _in(0.2), col_y + _in(0.12),
                      _in(3.0), _in(0.3),
                      "TITLE VARIATIONS", RED_ACCENT, 11, bold=True, font=FONT_LABEL)

    # 5 title variation lines
    for i in range(1, 6):
        ty = col_y + _in(0.5) + (i - 1) * _in(0.6)
        reqs += _text_box(f"tmpl_idea_tv{i}_text", page_id,
                          left_x + _in(0.2), ty,
                          col_w - _in(0.4), _in(0.5),
                          f"{{{{TV{i}}}}}", LIGHT_GRAY, 10, font=FONT_BODY)

    # Hook Options card
    reqs += _rect("tmpl_idea_hooks_bg", page_id,
                  right_x, col_y, col_w, col_h, CARD_COLOR)
    reqs += _rect("tmpl_idea_hooks_accent", page_id,
                  right_x, col_y, col_w, _in(0.03), BLUE_LIGHT)
    reqs += _text_box("tmpl_idea_hooks_header", page_id,
                      right_x + _in(0.2), col_y + _in(0.12),
                      _in(3.0), _in(0.3),
                      "HOOK OPTIONS", BLUE_LIGHT, 11, bold=True, font=FONT_LABEL)

    # 2 hook text boxes (label nudged up to avoid overlap with body)
    for i in range(1, 3):
        hy = col_y + _in(0.5) + (i - 1) * _in(1.6)
        reqs += _text_box(f"tmpl_idea_hook{i}_label", page_id,
                          right_x + _in(0.2), hy - _in(0.08),
                          _in(1.5), _in(0.25),
                          f"Hook {i}", GREEN, 11, bold=True, font=FONT_BODY)
        reqs += _text_box(f"tmpl_idea_hook{i}_text", page_id,
                          right_x + _in(0.2), hy + _in(0.22),
                          col_w - _in(0.4), _in(1.3),
                          f"{{{{HOOK{i}}}}}", LIGHT_GRAY, 10, font=FONT_BODY)

    # Full-width bottom card behind badge + topic
    reqs += _rect("tmpl_idea_bottom_bg", page_id,
                  _in(0.5), _in(5.75), _in(9.0), _in(1.15), CARD_COLOR)

    # "HIGH POTENTIAL" badge
    reqs += _rect("tmpl_idea_badge_bg", page_id,
                  _in(0.5), _in(5.85), _in(2.2), _in(0.35), CARD_COLOR)
    reqs += _text_box("tmpl_idea_badge", page_id,
                      _in(0.5), _in(5.85), _in(2.2), _in(0.35),
                      "HIGH POTENTIAL", GREEN, 11, bold=True,
                      font=FONT_LABEL, alignment="CENTER")

    # Topic line
    reqs += _text_box("tmpl_idea_topic", page_id,
                      _in(0.7), _in(6.25), _in(8.6), _in(0.55),
                      "{{IDEA_TOPIC}}", LIGHT_GRAY, 10, font=FONT_BODY)

    return reqs


# ---------------------------------------------------------------------------
# Slide 6: Key Takeaways & Next Steps
# ---------------------------------------------------------------------------

def _build_takeaways_slide() -> list[dict]:
    page_id = PAGE_TAKEAWAYS
    reqs = [_create_slide(page_id), _set_bg(page_id, BG_COLOR)]

    # Gradient header band
    reqs += _rect("tmpl_take_gradient", page_id,
                  0, 0, SLIDE_W, _in(1.3), HEADER_DARK)

    # Header — two-line treatment
    reqs += _text_box("tmpl_take_header", page_id,
                      _in(0.5), _in(0.2), _in(8.0), _in(0.55),
                      "KEY TAKEAWAYS", PURE_WHITE, 32, bold=True, font=FONT_DISPLAY)
    reqs += _text_box("tmpl_take_header2", page_id,
                      _in(0.5), _in(0.7), _in(8.0), _in(0.45),
                      "& NEXT STEPS", PURE_WHITE, 18, font=FONT_DISPLAY)

    # 3 takeaway items (tighter spacing to fit within slide)
    for i in range(1, 4):
        item_y = _in(1.5) + (i - 1) * _in(1.4)

        # Card background
        reqs += _rect(f"tmpl_take_{i}_bg", page_id,
                      _in(1.3), item_y - _in(0.05),
                      _in(8.2), _in(1.15), CARD_COLOR)

        # Green circle with number
        reqs += _rect(f"tmpl_take_{i}_circle", page_id,
                      _in(0.5), item_y + _in(0.15),
                      _in(0.55), _in(0.55), GREEN)
        reqs += _text_box(f"tmpl_take_{i}_num", page_id,
                          _in(0.5), item_y + _in(0.15),
                          _in(0.55), _in(0.55),
                          str(i), PURE_WHITE, 18, bold=True,
                          font=FONT_DISPLAY, alignment="CENTER")

        # Takeaway text
        reqs += _text_box(f"tmpl_take_{i}_text", page_id,
                          _in(1.5), item_y + _in(0.15),
                          _in(7.8), _in(0.8),
                          f"{{{{TAKEAWAY_{i}}}}}", WHITE, 13, font=FONT_BODY)

    # Footer
    reqs += _text_box("tmpl_take_footer", page_id,
                      0, _in(6.7), SLIDE_W, _in(0.4),
                      "Review monthly to track progress and adjust strategy",
                      TERTIARY, 10, font=FONT_BODY, alignment="CENTER")

    return reqs


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def create_template() -> str:
    """Create the 6-slide template and return the presentation ID."""
    service = build_slides_service()

    presentation = service.presentations().create(
        body={"title": "YouTube Analytics — Template v2"}
    ).execute()
    pres_id = presentation["presentationId"]

    requests = []
    requests += _build_title_slide()
    requests += _build_channel_slide()
    requests += _build_competitor_slide()
    requests += _build_comparative_slide()
    requests += _build_idea_slide()
    requests += _build_takeaways_slide()

    # Delete the default blank slide
    default_slide_id = presentation["slides"][0]["objectId"]
    requests.append({"deleteObject": {"objectId": default_slide_id}})

    service.presentations().batchUpdate(
        presentationId=pres_id,
        body={"requests": requests},
    ).execute()

    return pres_id


if __name__ == "__main__":
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    pres_id = create_template()
    url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
    print(f"\nTemplate created successfully!")
    print(f"  Presentation ID: {pres_id}")
    print(f"  URL: {url}")

    # Auto-update .env
    env_content = env_path.read_text() if env_path.exists() else ""
    if "GOOGLE_SLIDES_TEMPLATE_ID=" in env_content:
        lines = env_content.splitlines()
        new_lines = []
        for line in lines:
            if line.startswith("GOOGLE_SLIDES_TEMPLATE_ID="):
                new_lines.append(f"GOOGLE_SLIDES_TEMPLATE_ID={pres_id}")
            else:
                new_lines.append(line)
        env_path.write_text("\n".join(new_lines) + "\n")
    else:
        with open(env_path, "a") as f:
            f.write(f"\nGOOGLE_SLIDES_TEMPLATE_ID={pres_id}\n")
    print(f"  .env updated with new template ID")
