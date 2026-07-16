"""
Central theme for Album Studio.

All colors, stylesheets, and style helpers live here.
Import from this module instead of hardcoding colors in widgets.
"""

import os

from ..utils.paths import get_user_data_dir

# =====================================================================
# Color Palette
# =====================================================================

# --- Base surfaces ---
WINDOW_BG = '#ddd8d0'
GRID_BG = '#c8c3bb'
SURFACE = '#f5f3f0'
SURFACE_ALT = '#ece9e4'

# --- Text ---
TEXT = '#2a2520'
TEXT_SECONDARY = '#6a6460'
TEXT_MUTED = '#a09890'
TEXT_DISABLED = '#a09a92'
TEXT_VERSION = '#888888'

# --- Borders ---
BORDER = '#c8c4bc'
BORDER_LIGHT = '#ddd8d0'
TOOLBAR_BORDER = '#c0bbb3'

# --- Retro buttons ---
BTN_BG = '#f7f4ee'
BTN_BORDER = '#fdfbf7'
BTN_HOVER = '#ffffff'
BTN_PRESSED_BG = '#d4d0c8'
BTN_PRESSED_BORDER = '#d8d4cc'
BTN_DISABLED_BG = '#d8d4cc'

# --- Scrollbar ---
SCROLLBAR_TRACK = '#d0cbc3'
SCROLLBAR_HANDLE = '#b0aca4'
SCROLLBAR_HOVER = '#a09c94'

# --- Combobox ---
COMBO_BORDER = '#d4d0c8'
COMBO_DIVIDER = '#b0aca4'
COMBO_ARROW = '#5a554e'
COMBO_SELECTION = '#c5d5e8'

# --- Detail panel header ---
HEADER_BG = '#4a4540'
HEADER_TEXT = '#f0ece6'

# --- Image viewer navigation ---
# The viewer sits on a near-black backdrop, so these are translucent white
# rather than the light `BTN_*` chrome used everywhere else.
VIEWER_NAV_BG = 'rgba(255, 255, 255, 40)'
VIEWER_NAV_HOVER = 'rgba(255, 255, 255, 70)'
VIEWER_NAV_PRESSED = 'rgba(255, 255, 255, 100)'
VIEWER_NAV_TEXT = '#f0ece6'
VIEWER_NAV_SIZE = 48      # square; radius is half this, so the button is a circle
VIEWER_NAV_MARGIN = 12    # gap from the dialog edge

# --- Image cards ---
CARD_RADIUS = 8
CARD_PLACEHOLDER_RGB = (200, 196, 190)

# Card metrics. Cards are a fixed size so a project with four photos lays out
# like one with forty; the grid reflows its column count instead of stretching.
# One shape serves every card in the app — a thumbnail square over a full-size
# text row and a small caption row — so the grid and the similar-images results
# stay visually identical. The two rows are named by their type, not their
# content: the grid puts the filename in the caption and the tag in the text
# row, the results dialog puts the score in the text row and the filename in
# the caption.
CARD_OBJECT_NAME = 'imageCard'
CARD_BORDER = 3       # widest border any card state draws (the selection ring) — always reserved
CARD_PADDING = 10
CARD_SPACING = 6
CARD_CAPTION_HEIGHT = 30   # up to two 11px lines
CARD_TEXT_HEIGHT = 34      # up to two full-size lines

# --- Image grid ---
GRID_SPACING = 16
GRID_MARGIN = 16

CARD_UNTAGGED_BG = '#f5f2ed'
CARD_UNTAGGED_BORDER = '#ddd8d0'

CARD_PARTIAL_BG = '#fdf5e6'
CARD_PARTIAL_BORDER = '#e0c890'
CARD_PARTIAL_TEXT = '#a07020'

# Hover tint for cards that are clickable one-offs (the similar-results
# dialog). Amber-tinted to match the selection lamp below. The main grid's
# selection deliberately does not fill — see the ring constants.
CARD_HOVER_BG = '#f5e6dd'
CARD_HOVER_BORDER = '#dca483'

# Selection is a *ring*, never a fill. The tag's color fills the card
# (identity, persistent); selection draws a CARD_BORDER-wide ring over that
# fill (action, transient), so a selected card keeps showing what it is.
# The rings are the app's "indicator lamps": burnt amber for browsing —
# unmistakably interactive on the beige chassis, and a hue the tag palette
# (models/config.py TAG_COLOR_PALETTE) deliberately never uses — with brick
# and moss reserved for the two batch modes, matching their buttons. Batch
# rings also get a corner badge, since ✕/✓ carry the mode; browse selection
# is the ring alone.
CARD_RING_CURRENT = '#c05a1e'      # amber — right-click browse selection
CARD_RING_DELETE = '#a8402f'       # brick
CARD_RING_DATESTAMP = '#3f7d43'    # moss
CARD_RING_GENERIC = '#5f6b7d'      # slate

CARD_BADGE_OBJECT_NAME = 'cardBadge'
CARD_BADGE_SIZE = 22    # round, so radius is half this
CARD_BADGE_MARGIN = 4   # inset from the card's top-right corner

TAG_DEFAULT_COLOR = '#2f7d6d'      # TAG_COLOR_PALETTE's teal

# --- Action button colors ---
# Tints of the ring lamps above (delete ↔ brick, date stamp ↔ moss) and the
# tag palette's denim, so the chrome and the cards share one register.
DELETE_BTN_BG = '#e0b3a9'
DELETE_BTN_TEXT = '#7d2c1f'
DELETE_BTN_PRESSED = '#c99e92'
DELETE_BTN_HOVER = '#eac2b9'

SELECT_BTN_BG = '#b7c9dc'
SELECT_BTN_PRESSED = '#9fb3c9'
SELECT_BTN_HOVER = '#c7d7e8'

DATESTAMP_BTN_BG = '#b7d2b2'
DATESTAMP_BTN_TEXT = '#2d5c31'
DATESTAMP_BTN_PRESSED = '#a1bd9c'
DATESTAMP_BTN_HOVER = '#c6dfc1'

UPDATE_BTN_BG = '#4f8a55'
UPDATE_BTN_PRESSED = '#427448'
UPDATE_BTN_HOVER = '#579760'

CANCEL_BTN_BG = '#dcc06a'
CANCEL_BTN_PRESSED = '#c3a854'
CANCEL_BTN_HOVER = '#e5cf85'

PULL_BTN_BG = '#b3c4d8'
PULL_BTN_TEXT = '#26415f'
PULL_BTN_PRESSED = '#9cb0c5'
PULL_BTN_HOVER = '#c3d4e7'


# =====================================================================
# Helper Functions
# =====================================================================

def lighten_color(hex_color: str, factor: float = 0.82) -> str:
    """Create a light tint of a color by mixing toward white."""
    hex_color = hex_color.lstrip('#')
    r = int(int(hex_color[0:2], 16) + (255 - int(hex_color[0:2], 16)) * factor)
    g = int(int(hex_color[2:4], 16) + (255 - int(hex_color[2:4], 16)) * factor)
    b = int(int(hex_color[4:6], 16) + (255 - int(hex_color[4:6], 16)) * factor)
    return f'#{r:02x}{g:02x}{b:02x}'


def card_style(bg: str, border_color: str, border_width: int = 1,
               hover_bg: str = '', hover_border: str = '') -> str:
    """Generate the stylesheet for an image card.

    Scoped to the card's object name on purpose: ``QLabel`` derives from
    ``QFrame``, so a bare ``QFrame`` rule would paint the background, border and
    radius onto the card's own thumbnail/filename/tag labels as well, boxing
    each one inside the card.

    Pass ``hover_bg``/``hover_border`` for cards that are clickable in their own
    right; the grid's cards leave them off, since every card there is clickable
    and a hover tint would just be noise.
    """
    style = (
        f"QFrame#{CARD_OBJECT_NAME} {{ background-color: {bg}; "
        f"border: {border_width}px solid {border_color}; "
        f"border-radius: {CARD_RADIUS}px; }}"
    )
    if hover_bg or hover_border:
        style += (
            f"QFrame#{CARD_OBJECT_NAME}:hover {{ "
            f"background-color: {hover_bg or bg}; "
            f"border: {border_width}px solid {hover_border or border_color}; "
            f"border-radius: {CARD_RADIUS}px; }}"
        )
    return style


def card_badge_style(bg: str) -> str:
    """Stylesheet for the round selection badge pinned to a card's corner.

    Scoped to the badge's object name so the rule survives sitting inside a
    card whose own stylesheet is scoped to ``CARD_OBJECT_NAME``, and so it
    overrides the global ``QLabel { background: transparent }``.
    """
    return (
        f"QLabel#{CARD_BADGE_OBJECT_NAME} {{ background-color: {bg}; "
        f"color: {HEADER_TEXT}; border: 2px solid {BTN_BORDER}; "
        f"border-radius: {CARD_BADGE_SIZE // 2}px; "
        f"font-size: 11px; font-weight: bold; }}"
    )


def card_size(thumbnail_size: int) -> tuple[int, int]:
    """Outer pixel size of a card: a ``thumbnail_size`` square, a text row and
    a caption row.

    The border is part of the widget rect and the layout margins sit inside it,
    so both are reserved here. ``CARD_BORDER`` is the widest any state draws —
    reserving it unconditionally keeps a selected card the same size as an
    unselected one.
    """
    inset = 2 * (CARD_BORDER + CARD_PADDING)
    width = thumbnail_size + inset
    height = (thumbnail_size + CARD_TEXT_HEIGHT + CARD_CAPTION_HEIGHT
              + 2 * CARD_SPACING + inset)
    return width, height


def grid_columns_for_width(viewport_width: int, thumbnail_size: int) -> int:
    """How many fixed-size cards fit across a viewport, at least one."""
    card_width, _ = card_size(thumbnail_size)
    available = viewport_width - 2 * GRID_MARGIN
    return max(1, (available + GRID_SPACING) // (card_width + GRID_SPACING))


def retro_button_style(bg: str, text: str = '', pressed: str = '',
                       hover: str = '', extra: str = '') -> str:
    """Generate a retro-styled button stylesheet with outset/inset 3D borders."""
    pressed = pressed or bg
    hover = hover or bg
    color = f" color: {text}; font-weight: bold;" if text else ""
    return (
        f"QPushButton {{ background-color: {bg};{color} "
        f"border: 2px outset {bg}; border-radius: 4px; }}"
        f"QPushButton:pressed {{ border: 2px inset {pressed}; background-color: {pressed}; }}"
        f"QPushButton:hover:!pressed {{ background-color: {hover}; }}"
        f"{extra}"
    )


# =====================================================================
# Pre-built Widget Styles
# =====================================================================

STYLE_DELETE_BTN = retro_button_style(
    DELETE_BTN_BG, DELETE_BTN_TEXT, DELETE_BTN_PRESSED, DELETE_BTN_HOVER)

STYLE_SELECT_ALL_BTN = retro_button_style(
    SELECT_BTN_BG, pressed=SELECT_BTN_PRESSED, hover=SELECT_BTN_HOVER,
    extra=f"QPushButton:checked {{ border: 2px inset {SELECT_BTN_PRESSED}; "
          f"background-color: {SELECT_BTN_PRESSED}; }}")

STYLE_DATESTAMP_BTN = retro_button_style(
    DATESTAMP_BTN_BG, DATESTAMP_BTN_TEXT, DATESTAMP_BTN_PRESSED, DATESTAMP_BTN_HOVER)

STYLE_UPDATE_BTN = retro_button_style(
    UPDATE_BTN_BG, 'white', UPDATE_BTN_PRESSED, UPDATE_BTN_HOVER)

STYLE_CANCEL_BTN = retro_button_style(
    CANCEL_BTN_BG, pressed=CANCEL_BTN_PRESSED, hover=CANCEL_BTN_HOVER,
    extra="QPushButton { font-weight: bold; }")

STYLE_PULL_BTN = retro_button_style(
    PULL_BTN_BG, PULL_BTN_TEXT, PULL_BTN_PRESSED, PULL_BTN_HOVER)

# Shown while a pull is in flight. The button is disabled then, so the tint has
# to come from :disabled — plain QPushButton rules do not apply to it.
PULL_BTN_BUSY_BG = lighten_color(PULL_BTN_BG, 0.45)

STYLE_PULL_BTN_BUSY = retro_button_style(
    PULL_BTN_BUSY_BG, PULL_BTN_TEXT,
    extra=f"QPushButton:disabled {{ background-color: {PULL_BTN_BUSY_BG}; "
          f"color: {PULL_BTN_TEXT}; border: 2px inset {PULL_BTN_BUSY_BG}; }}")

STYLE_TOTAL_COST = "font-weight: bold; padding: 0 10px;"
STYLE_VERSION_LABEL = f"color: {TEXT_VERSION}; font-size: 11px; padding: 0 5px;"
STYLE_FILENAME_LABEL = f"color: {TEXT_SECONDARY}; font-size: 11px;"
STYLE_STATUS_LABEL = f"color: {TEXT_SECONDARY}; font-style: italic;"
STYLE_READONLY_FIELD = (
    f"padding: 5px; background: {SURFACE}; border: 1px solid {BORDER};")
STYLE_DETAIL_HEADER = (
    f"font-weight: bold; padding: 10px; "
    f"background-color: {HEADER_BG}; color: {HEADER_TEXT};")

# Deliberately not retro_button_style(): its outset 3D border is for the light
# toolbar chrome and reads as a scuff mark on the viewer's dark backdrop.
STYLE_VIEWER_NAV_BTN = (
    f"QPushButton {{ background-color: {VIEWER_NAV_BG}; color: {VIEWER_NAV_TEXT}; "
    f"border: none; border-radius: {VIEWER_NAV_SIZE // 2}px; "
    f"font-size: 26px; font-weight: bold; }}"
    f"QPushButton:hover {{ background-color: {VIEWER_NAV_HOVER}; }}"
    f"QPushButton:pressed {{ background-color: {VIEWER_NAV_PRESSED}; }}")


# =====================================================================
# Generated Stylesheet Assets
# =====================================================================

def _write_arrow_svg(name: str, color: str) -> str:
    """
    Write a downward triangle SVG tinted `color` and return a QSS-safe url() path.

    Qt's stylesheet engine has no triangle primitive and does not honour the CSS
    transparent-border trick -- it fills the whole border box, so a bordered
    ::down-arrow renders as a solid rectangle. An image is the only way to draw
    the arrow, and generating it here keeps the colour in this file rather than
    baking it into a checked-in asset.
    """
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="9" height="6" '
        'viewBox="0 0 9 6">'
        f'<path d="M0 0 H9 L4.5 6 Z" fill="{color}"/>'
        '</svg>'
    )
    cache_dir = os.path.join(get_user_data_dir(), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, name)

    # Rewrite only on change: the path is baked into the stylesheet string, so a
    # stale file from an older palette would otherwise survive forever.
    try:
        with open(path, "r", encoding="utf-8") as f:
            if f.read() == svg:
                return path.replace(os.sep, "/")
    except OSError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return path.replace(os.sep, "/")


COMBO_ARROW_SVG = _write_arrow_svg("combo_arrow.svg", COMBO_ARROW)
COMBO_ARROW_DISABLED_SVG = _write_arrow_svg(
    "combo_arrow_disabled.svg", TEXT_DISABLED)


# =====================================================================
# Global Stylesheet
# =====================================================================

GLOBAL_STYLESHEET = f"""
/* ===== Base Window ===== */
QMainWindow, QDialog {{
    background-color: {WINDOW_BG};
}}

/* ===== Retro Push Buttons ===== */
QPushButton {{
    background-color: {BTN_BG};
    border: 2px outset {BTN_BORDER};
    border-radius: 4px;
    padding: 5px 14px;
    min-height: 20px;
    color: {TEXT};
    font-size: 12px;
}}
QPushButton:pressed {{
    border: 2px inset {BTN_PRESSED_BORDER};
    background-color: {BTN_PRESSED_BG};
}}
QPushButton:hover:!pressed {{
    background-color: {BTN_HOVER};
}}
QPushButton:disabled {{
    color: {TEXT_DISABLED};
    background-color: {BTN_DISABLED_BG};
    border: 2px outset {BTN_DISABLED_BG};
}}
QPushButton:checked {{
    border: 2px inset {BTN_PRESSED_BORDER};
    background-color: {BTN_PRESSED_BG};
}}

/* ===== ComboBoxes ===== */
QComboBox {{
    background-color: {SURFACE};
    border: 2px inset {COMBO_BORDER};
    padding: 4px 8px;
    min-height: 20px;
    color: {TEXT};
    font-size: 12px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border-left: 1px solid {COMBO_DIVIDER};
    width: 20px;
}}
QComboBox::down-arrow {{
    image: url("{COMBO_ARROW_SVG}");
    width: 9px;
    height: 6px;
}}
QComboBox::down-arrow:disabled {{
    image: url("{COMBO_ARROW_DISABLED_SVG}");
}}
QComboBox::down-arrow:on {{
    /* nudge down while the popup is open, so the arrow reads as pressed */
    top: 1px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {COMBO_DIVIDER};
    selection-background-color: {COMBO_SELECTION};
    selection-color: {TEXT};
}}

/* ===== Labels ===== */
QLabel {{
    color: {TEXT};
    background: transparent;
}}

/* ===== ScrollArea & Grid Background ===== */
QScrollArea {{
    border: none;
    background-color: {GRID_BG};
}}
#imageGridContainer {{
    background-color: {GRID_BG};
}}

/* ===== Scrollbars ===== */
QScrollBar:vertical {{
    background-color: {SCROLLBAR_TRACK};
    width: 12px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {SCROLLBAR_HANDLE};
    min-height: 30px;
    border-radius: 3px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {SCROLLBAR_HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}
QScrollBar:horizontal {{
    background-color: {SCROLLBAR_TRACK};
    height: 12px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: {SCROLLBAR_HANDLE};
    min-width: 30px;
    border-radius: 3px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {SCROLLBAR_HOVER};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ===== Toolbar Areas ===== */
#topToolbar {{
    background-color: {WINDOW_BG};
    border-bottom: 1px solid {TOOLBAR_BORDER};
}}
#bottomToolbar {{
    background-color: {WINDOW_BG};
    border-top: 1px solid {TOOLBAR_BORDER};
}}

/* ===== Tree Widget (Detail Panel) ===== */
QTreeWidget {{
    background-color: {SURFACE};
    alternate-background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
}}
QTreeWidget::item {{
    padding: 2px;
}}

/* ===== Line Edits ===== */
QLineEdit {{
    background-color: {SURFACE};
    border: 2px inset {COMBO_BORDER};
    padding: 4px 8px;
    color: {TEXT};
}}
"""
