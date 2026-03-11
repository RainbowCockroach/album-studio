"""
Central theme for Album Studio.

All colors, stylesheets, and style helpers live here.
Import from this module instead of hardcoding colors in widgets.
"""

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

# --- Image cards ---
CARD_RADIUS = 8
CARD_PLACEHOLDER_RGB = (200, 196, 190)

CARD_UNTAGGED_BG = '#f5f2ed'
CARD_UNTAGGED_BORDER = '#ddd8d0'

CARD_PARTIAL_BG = '#fdf5e6'
CARD_PARTIAL_BORDER = '#e0c890'
CARD_PARTIAL_TEXT = '#a07020'

CARD_SELECTED_BG = '#e3edf8'
CARD_SELECTED_BORDER = '#90b0d8'

CARD_DELETE_BG = '#f8e0e0'
CARD_DELETE_BORDER = '#d08080'
CARD_DELETE_TEXT = '#b03030'

CARD_DATESTAMP_BG = '#e0f0e0'
CARD_DATESTAMP_BORDER = '#80b080'
CARD_DATESTAMP_TEXT = '#308030'

CARD_GENERIC_BG = '#e0e8f0'
CARD_GENERIC_BORDER = '#8098b8'
CARD_GENERIC_TEXT = '#305080'

TAG_DEFAULT_COLOR = '#4CAF50'

# --- Action button colors ---
DELETE_BTN_BG = '#e8b0b0'
DELETE_BTN_TEXT = '#8b0000'
DELETE_BTN_PRESSED = '#d09898'
DELETE_BTN_HOVER = '#f0bebe'

SELECT_BTN_BG = '#b8d0e8'
SELECT_BTN_PRESSED = '#a0b8d0'
SELECT_BTN_HOVER = '#c8daf0'

DATESTAMP_BTN_BG = '#b0d8b0'
DATESTAMP_BTN_TEXT = '#1a6b1a'
DATESTAMP_BTN_PRESSED = '#98c098'
DATESTAMP_BTN_HOVER = '#c0e8c0'

UPDATE_BTN_BG = '#4CAF50'
UPDATE_BTN_PRESSED = '#3d9142'
UPDATE_BTN_HOVER = '#45a049'

CANCEL_BTN_BG = '#e0c860'
CANCEL_BTN_PRESSED = '#c8b050'
CANCEL_BTN_HOVER = '#e8d070'


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


def card_style(bg: str, border_color: str, border_width: int = 1) -> str:
    """Generate QFrame stylesheet for an image card."""
    return (
        f"QFrame {{ background-color: {bg}; border: {border_width}px solid {border_color}; "
        f"border-radius: {CARD_RADIUS}px; }}"
    )


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

STYLE_TOTAL_COST = "font-weight: bold; padding: 0 10px;"
STYLE_VERSION_LABEL = f"color: {TEXT_VERSION}; font-size: 11px; padding: 0 5px;"
STYLE_FILENAME_LABEL = f"color: {TEXT_SECONDARY}; font-size: 11px;"
STYLE_DETAIL_HEADER = (
    f"font-weight: bold; padding: 10px; "
    f"background-color: {HEADER_BG}; color: {HEADER_TEXT};")


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
    border-left: 1px solid {COMBO_DIVIDER};
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COMBO_ARROW};
    width: 0px;
    height: 0px;
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
