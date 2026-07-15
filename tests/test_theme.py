"""Tests for the card/grid geometry in ``src/ui/theme.py``.

``theme.py`` imports no Qt, so the sizing math behind the image grid is
testable without a QApplication. It is worth pinning: cards used to be sized by
whatever space QGridLayout had left over, which made a four-photo project
render as four ~490px-wide cards stretched across the window.
"""

import os

from src.ui.theme import (
    CARD_OBJECT_NAME, COMBO_ARROW, COMBO_ARROW_DISABLED_SVG, COMBO_ARROW_SVG,
    GLOBAL_STYLESHEET, GRID_MARGIN, GRID_SPACING,
    _write_arrow_svg, card_size, card_style, grid_columns_for_width)


class TestComboArrow:
    """The dropdown arrow is an image because Qt's stylesheet engine has no
    triangle primitive: it ignores the CSS transparent-border trick and fills
    the whole border box, which drew the arrow as a solid dark rectangle."""

    def test_stylesheet_draws_the_arrow_from_an_image(self):
        assert f'image: url("{COMBO_ARROW_SVG}")' in GLOBAL_STYLESHEET
        assert f'image: url("{COMBO_ARROW_DISABLED_SVG}")' in GLOBAL_STYLESHEET

    def test_stylesheet_never_builds_the_arrow_out_of_borders(self):
        """Guards the regression itself -- borders here render as a rectangle."""
        assert 'solid transparent' not in GLOBAL_STYLESHEET

    def test_referenced_arrow_files_exist(self):
        """A url() pointing nowhere fails silently: no arrow, no error."""
        assert os.path.isfile(COMBO_ARROW_SVG)
        assert os.path.isfile(COMBO_ARROW_DISABLED_SVG)

    def test_arrow_uses_forward_slashes(self):
        """QSS url() reads a backslash as an escape, so Windows paths must not
        reach the stylesheet with os.sep in them."""
        assert '\\' not in COMBO_ARROW_SVG

    def test_arrow_is_tinted_with_the_theme_color(self):
        with open(COMBO_ARROW_SVG, encoding='utf-8') as f:
            assert f'fill="{COMBO_ARROW}"' in f.read()

    def test_rewrites_a_file_left_over_from_an_older_palette(self):
        """The path is baked into the stylesheet, so a stale file would be
        served forever rather than picking up a changed colour."""
        path = _write_arrow_svg('test_stale_arrow.svg', '#ff0000')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('<svg>stale</svg>')

        _write_arrow_svg('test_stale_arrow.svg', '#00ff00')

        with open(path, encoding='utf-8') as f:
            contents = f.read()
        os.remove(path)
        assert 'stale' not in contents
        assert 'fill="#00ff00"' in contents


class TestCardStyle:
    def test_style_is_scoped_to_the_card_object_name(self):
        """QLabel derives from QFrame, so a bare ``QFrame`` rule would paint the
        card's background and border onto its own thumbnail/filename/tag labels."""
        style = card_style('#ffffff', '#000000')

        assert style.startswith(f"QFrame#{CARD_OBJECT_NAME} ")

    def test_style_carries_the_requested_colors_and_border(self):
        style = card_style('#f5f2ed', '#ddd8d0', 2)

        assert 'background-color: #f5f2ed' in style
        assert 'border: 2px solid #ddd8d0' in style


class TestCardSize:
    def test_card_is_wider_and_taller_than_its_thumbnail(self):
        width, height = card_size(200)

        assert width > 200          # padding + border
        assert height > width       # plus the filename and tag rows

    def test_size_scales_with_thumbnail_size(self):
        small_w, small_h = card_size(100)
        large_w, large_h = card_size(200)

        assert large_w - small_w == 100
        assert large_h - small_h == 100


class TestGridColumnsForWidth:
    def test_columns_fit_within_the_viewport(self):
        """The whole point: cards keep their size and the count adapts."""
        card_width, _ = card_size(200)
        viewport = 2000

        columns = grid_columns_for_width(viewport, 200)
        used = (2 * GRID_MARGIN + columns * card_width
                + (columns - 1) * GRID_SPACING)

        assert used <= viewport

    def test_one_more_column_would_overflow(self):
        card_width, _ = card_size(200)
        viewport = 2000

        columns = grid_columns_for_width(viewport, 200) + 1
        used = (2 * GRID_MARGIN + columns * card_width
                + (columns - 1) * GRID_SPACING)

        assert used > viewport

    def test_exact_fit_is_not_rounded_down(self):
        card_width, _ = card_size(200)
        viewport = 2 * GRID_MARGIN + 4 * card_width + 3 * GRID_SPACING

        assert grid_columns_for_width(viewport, 200) == 4

    def test_wider_viewport_never_yields_fewer_columns(self):
        columns = [grid_columns_for_width(w, 200) for w in range(200, 3000, 37)]

        assert columns == sorted(columns)

    def test_never_returns_zero_columns(self):
        """A viewport too narrow for one card gets a single (clipped) column
        rather than a division-by-zero layout or an empty grid."""
        assert grid_columns_for_width(10, 200) == 1
        assert grid_columns_for_width(0, 200) == 1
