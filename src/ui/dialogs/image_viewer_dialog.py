"""Dialog for viewing an image in detail with zoom support."""
from typing import Optional
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QScrollArea,
                             QApplication, QPushButton)
from PyQt6.QtCore import (Qt, QPoint, pyqtSignal, QObject, QRunnable,
                          QThreadPool)
from PyQt6.QtGui import (QPixmap, QImage, QWheelEvent, QMouseEvent, QKeyEvent,
                         QResizeEvent)
from PIL import Image
from src.utils.image_loader import ImageLoader
from src.models.config import Config
from src.ui.theme import (STYLE_VIEWER_NAV_BTN, VIEWER_NAV_SIZE,
                          VIEWER_NAV_MARGIN)

# How many rendered images to keep, and how many neighbours to warm on each
# navigation. The viewer holds full-resolution-ish QImages (a 12MP RGB frame is
# ~36MB), so this is a memory ceiling as much as a hit-rate knob: 5 entries
# covers "arrow left and right a few times" without holding a whole project.
_RENDER_CACHE_MAX = 5
_PREFETCH_RADIUS = 1


def _render_key(image_item, image_path: str):
    """Identify a rendered frame by everything that changes its pixels.

    Crop box and date-stamp state are in here because toggling either must not
    serve a stale frame; the size tag drives the crop ratio.
    """
    if image_item is None:
        return (image_path, None, None, False)
    crop_box = image_item.crop_box
    return (
        image_path,
        image_item.size_tag,
        tuple(sorted(crop_box.items())) if crop_box else None,
        bool(image_item.add_date_stamp),
    )


class _RenderSignals(QObject):
    """Signals for _RenderTask. QRunnable is not a QObject, so they live here."""

    done = pyqtSignal(object, object)  # (render key, QImage or None)


class _RenderTask(QRunnable):
    """Decode/crop/date-stamp one photo off the UI thread.

    Emits a QImage, never a QPixmap: QPixmap is a QPaintDevice and constructing
    one outside the GUI thread is undefined behaviour. The receiver on the main
    thread does the (cheap, ~0ms) QPixmap.fromImage conversion.
    """

    def __init__(self, key, image_path, image_item, config, max_size):
        super().__init__()
        self.signals = _RenderSignals()
        self.key = key
        self.image_path = image_path
        self.image_item = image_item
        self.config = config
        self.max_size = max_size

    def run(self):
        try:
            image = _render_image(self.image_path, self.image_item,
                                  self.config, self.max_size)
        except Exception as e:  # a broken file must not take the pool down
            print(f"Error rendering {self.image_path}: {e}")
            image = None
        self.signals.done.emit(self.key, image)


def _render_image(image_path: str, image_item, config,
                  max_size: int) -> Optional[QImage]:
    """Produce the QImage the viewer displays: cropped + stamped if tagged.

    Thread-safe — pure PIL and QImage, no widget or QPixmap access.
    """
    should_crop = (image_item is not None and
                   image_item.is_fully_tagged() and
                   config is not None)

    if not should_crop:
        return ImageLoader.load_qimage(image_path, max_size=max_size)

    try:
        from src.services.crop_service import CropService
        from src.utils.image_loader import open_oriented, pil_to_qimage

        crop_service = CropService(config)
        crop_box = crop_service.get_crop_box(
            image_path, image_item.size_tag,
            manual_crop_box=image_item.crop_box)

        if not crop_box:
            return ImageLoader.load_qimage(image_path, max_size=max_size)

        img = open_oriented(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        x, y, width, height = crop_box
        cropped_img = img.crop((x, y, x + width, y + height))

        if image_item.add_date_stamp:
            cropped_img = _apply_date_stamp(cropped_img, image_item, config)

        # Downscale before handing to Qt. The viewer never shows more than
        # ~1500px of this, and a 12MP frame costs ~36MB to hold and ~10ms to
        # rescale on every zoom step.
        if max_size and max(cropped_img.size) > max_size:
            cropped_img.thumbnail((max_size, max_size),
                                  Image.Resampling.LANCZOS)

        return pil_to_qimage(cropped_img)

    except Exception as e:
        print(f"Error loading cropped image: {e}")
        return ImageLoader.load_qimage(image_path, max_size=max_size)


def _apply_date_stamp(img, image_item, config):
    """Stamp ``img`` in place of the old method, callable from a worker thread."""
    if not image_item or not config:
        return img
    try:
        from src.services.date_stamp_service import DateStampService

        display_date = image_item.get_display_date()
        if not display_date:
            return img
        return DateStampService(config).apply_date_stamp(
            img, display_date, image_item.size_tag)
    except Exception as e:
        print(f"Error applying date stamp preview: {e}")
        return img


class ZoomableImageLabel(QLabel):
    """A QLabel that supports zooming and panning for an image."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.original_pixmap = None
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0

        # For panning
        self.panning = False
        self.pan_start = QPoint()
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_image(self, pixmap: QPixmap, initial_zoom: Optional[float] = None):
        """Set the image to display."""
        self.original_pixmap = pixmap
        if initial_zoom is not None:
            self.zoom_factor = initial_zoom
        else:
            self.zoom_factor = 1.0
        self.update_display()

    def update_display(self):
        """Update the displayed image based on current zoom level."""
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled_width = int(self.original_pixmap.width() * self.zoom_factor)
            scaled_height = int(self.original_pixmap.height() * self.zoom_factor)

            scaled_pixmap = self.original_pixmap.scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
            self.adjustSize()

    def wheelEvent(self, event: Optional[QWheelEvent]):
        """Handle mouse wheel for zooming."""
        if event:
            if event.angleDelta().y() > 0:
                # Zoom in
                self.zoom_factor = min(self.zoom_factor * 1.15, self.max_zoom)
            else:
                # Zoom out
                self.zoom_factor = max(self.zoom_factor / 1.15, self.min_zoom)

            self.update_display()
            event.accept()

    def mousePressEvent(self, event: Optional[QMouseEvent]):
        """Start panning on mouse press."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]):
        """Stop panning on mouse release."""
        if event and event.button() == Qt.MouseButton.LeftButton:
            self.panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: Optional[QMouseEvent]):
        """Handle panning when dragging."""
        if event and self.panning:
            delta = event.pos() - self.pan_start
            self.pan_start = event.pos()

            # Get the scroll area parent
            scroll_area = self.parent()
            if scroll_area and isinstance(scroll_area.parent(), QScrollArea):
                scroll_area = scroll_area.parent()
            elif isinstance(scroll_area, QScrollArea):
                pass
            else:
                # Try to find scroll area in ancestors
                widget = self.parent()
                while widget:
                    if isinstance(widget, QScrollArea):
                        scroll_area = widget
                        break
                    widget = widget.parent()

            if isinstance(scroll_area, QScrollArea):
                h_bar = scroll_area.horizontalScrollBar()
                v_bar = scroll_area.verticalScrollBar()
                if h_bar:
                    h_bar.setValue(h_bar.value() - delta.x())
                if v_bar:
                    v_bar.setValue(v_bar.value() - delta.y())

        super().mouseMoveEvent(event)


class ImageViewerDialog(QDialog):
    """Dialog for viewing an image in detail with zoom support.

    Pass ``images`` (the project's images, in grid order) to enable Left/Right
    browsing to the neighbouring photo. Omit it and the viewer shows the single
    ``image_item`` with navigation switched off.
    """

    image_changed = pyqtSignal(object)  # Emits the ImageItem navigated to

    def __init__(self, image_path: str, parent=None, image_item=None, config=None,
                 images=None):
        super().__init__(parent)
        self.image_path = image_path
        self.image_item = image_item
        self.config = config

        # Navigation. `index` addresses `images`; both stay valid when the list
        # is empty (no image_item) — navigate() is then a no-op.
        self.images = list(images) if images else ([image_item] if image_item else [])
        self.index = self.images.index(image_item) if image_item in self.images else 0

        # Real-size preview mode
        self.real_size_mode = False
        self.can_use_real_size = self._check_real_size_available()
        self.loaded_pixmap = None  # Store the loaded pixmap for mode switching

        # Rendered-frame cache and the pool that fills it. Renders are dispatched
        # by key; `_pending_key` is the one the user is actually waiting for, so
        # a result that arrives after they have already arrowed on is dropped
        # rather than flashed on screen.
        self._render_cache: dict = {}
        self._pending_key = None
        self._loading = False
        self._pool = QThreadPool(self)
        # Cap the pool: the point is to keep the UI thread free and warm one or
        # two neighbours, not to decode a whole project at once.
        self._pool.setMaxThreadCount(2)

        self.setWindowTitle("Image Viewer")
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Semi-transparent dark background
        self.setStyleSheet("QDialog { background-color: rgba(0, 0, 0, 200); }")

        self.init_ui()
        self.load_image()

        # Size to 90% of screen
        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            screen = primary_screen.geometry()
            self.resize(int(screen.width() * 0.9), int(screen.height() * 0.9))

            # Center on screen
            self.move(
                (screen.width() - self.width()) // 2,
                (screen.height() - self.height()) // 2
            )

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        # Scroll area for the image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # CRITICAL: QAbstractScrollArea consumes arrow keys to scroll itself, and
        # it takes focus by default — which would swallow Left/Right before
        # keyPressEvent ever sees them. Nothing here needs key focus: wheel-zoom
        # and drag-pan are mouse-driven. See tests/test_image_viewer_nav.py.
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)

        # Zoomable image label
        self.image_label = ZoomableImageLabel()
        self.image_label.setStyleSheet("background-color: transparent;")
        self.scroll_area.setWidget(self.image_label)

        layout.addWidget(self.scroll_area)

        # Hint label (will be updated based on mode)
        self.hint_label = QLabel()
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setStyleSheet("color: white; font-size: 12px; padding: 10px;")
        self._update_hint_label()
        layout.addWidget(self.hint_label)

        self.setLayout(layout)

        # Navigation chevrons. Children of the dialog rather than layout members,
        # so they float over the photo; resizeEvent keeps them centred. Being real
        # children, they take their own clicks — mousePressEvent's click-outside-
        # to-close never fires for them, even though they sit outside scroll_area.
        self.prev_btn = self._make_nav_button("‹", -1)
        self.next_btn = self._make_nav_button("›", +1)
        self._update_nav_buttons()

    def _make_nav_button(self, glyph: str, delta: int) -> QPushButton:
        """Build one floating chevron that steps the viewer by ``delta``."""
        button = QPushButton(glyph, self)
        button.setFixedSize(VIEWER_NAV_SIZE, VIEWER_NAV_SIZE)
        button.setStyleSheet(STYLE_VIEWER_NAV_BTN)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # else it eats the arrow keys
        button.clicked.connect(lambda: self.navigate(delta))
        return button

    def _update_nav_buttons(self):
        """Show each chevron only where it leads somewhere."""
        self.prev_btn.setVisible(self._target_index(-1) is not None)
        self.next_btn.setVisible(self._target_index(+1) is not None)

    def resizeEvent(self, a0: Optional[QResizeEvent]):
        """Keep the chevrons pinned to the vertical centre of each edge."""
        super().resizeEvent(a0)
        y = (self.height() - VIEWER_NAV_SIZE) // 2
        self.prev_btn.move(VIEWER_NAV_MARGIN, y)
        self.next_btn.move(
            self.width() - VIEWER_NAV_SIZE - VIEWER_NAV_MARGIN, y)

    def _target_index(self, delta: int) -> Optional[int]:
        """The neighbour ``delta`` steps away, or None at the ends of the list."""
        if not self.images:
            return None
        target = self.index + delta
        return target if 0 <= target < len(self.images) else None

    def navigate(self, delta: int):
        """Step to a neighbouring image. Silently does nothing at the ends."""
        target = self._target_index(delta)
        if target is not None:
            self._show_index(target)

    def _show_index(self, index: int):
        """Point the viewer at ``images[index]`` and reload all that depends on it."""
        self.index = index
        self.image_item = self.images[index]
        self.image_path = self.image_item.file_path

        self.can_use_real_size = self._check_real_size_available()
        # Real-size is sticky across navigation, but only survives onto images
        # that can actually honour it (i.e. are fully tagged).
        if self.real_size_mode and not self.can_use_real_size:
            self.real_size_mode = False

        # Resets zoom to fit-to-window, and re-applies real-size itself once the
        # frame is actually in hand — which may be after this returns.
        self.load_image()

        self._update_hint_label()
        self._update_nav_buttons()
        self.image_changed.emit(self.image_item)

    def _render_max_size(self) -> int:
        """Longest edge worth decoding: what fit-to-window can actually show.

        Rendering beyond this only costs memory and makes every zoom step
        rescale more pixels. Generous enough that zooming in stays sharp.
        """
        primary_screen = QApplication.primaryScreen()
        if not primary_screen:
            return 2000
        screen = primary_screen.geometry()
        return int(max(screen.width(), screen.height()) * 0.9 * 2)

    def load_image(self):
        """Show the current image, rendering off-thread unless already cached."""
        key = _render_key(self.image_item, self.image_path)

        cached = self._render_cache.get(key)
        if cached is not None:
            self._pending_key = None
            # Clear the flag even though nothing was awaited here: arrowing off a
            # still-rendering photo onto a cached one would otherwise strand the
            # hint on "Loading…" until some unrelated render happened to finish.
            self._set_loading(False)
            self._display_image(cached)
            self._prefetch_neighbours()
            return

        # Nothing to show yet. Keep the previous frame on screen rather than
        # blanking — an empty viewer reads as a crash — and say why it is waiting.
        self._pending_key = key
        self._set_loading(True)

        task = _RenderTask(key, self.image_path, self.image_item, self.config,
                           self._render_max_size())
        task.signals.done.connect(self._on_render_done)
        self._pool.start(task)

    def _on_render_done(self, key, image):
        """Receive a rendered frame. Runs on the UI thread (queued connection)."""
        if image is not None and not image.isNull():
            self._cache_put(key, image)

        # Only paint it if it is still what the user is looking at; a prefetched
        # or superseded frame just lands in the cache.
        if key == self._pending_key:
            self._pending_key = None
            self._set_loading(False)
            if image is not None and not image.isNull():
                self._display_image(image)
            # Warm neighbours only now, so the photo being waited on never
            # queues behind a prefetch for one nobody asked for.
            self._prefetch_neighbours()

    def _cache_put(self, key, image):
        """Insert into the render cache, evicting oldest first."""
        if key in self._render_cache:
            return
        if len(self._render_cache) >= _RENDER_CACHE_MAX:
            self._render_cache.pop(next(iter(self._render_cache)))
        self._render_cache[key] = image

    def _display_image(self, image: QImage):
        """Convert to a pixmap and show it fit-to-window (or at real size)."""
        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            return

        self.loaded_pixmap = pixmap
        self.image_label.set_image(pixmap, self._fit_zoom(pixmap))
        if self.real_size_mode:
            self._apply_real_size_zoom()

    def _fit_zoom(self, pixmap: QPixmap) -> float:
        """Zoom factor that fits ``pixmap`` in the window, never upscaling."""
        primary_screen = QApplication.primaryScreen()
        if not primary_screen or pixmap.width() == 0 or pixmap.height() == 0:
            return 1.0
        screen = primary_screen.geometry()
        # Account for margins (20px each side) and hint label (~40px)
        max_width = int(screen.width() * 0.9) - 40
        max_height = int(screen.height() * 0.9) - 80
        return min(max_width / pixmap.width(),
                   max_height / pixmap.height(),
                   1.0)

    def _set_loading(self, loading: bool):
        """Reflect render-in-flight state in the hint line."""
        self._loading = loading
        self._update_hint_label()

    def _prefetch_neighbours(self):
        """Warm the frames the user is one arrow-press away from needing."""
        for delta in range(-_PREFETCH_RADIUS, _PREFETCH_RADIUS + 1):
            if delta == 0:
                continue
            target = self._target_index(delta)
            if target is None:
                continue
            item = self.images[target]
            key = _render_key(item, item.file_path)
            if key in self._render_cache:
                continue
            task = _RenderTask(key, item.file_path, item, self.config,
                               self._render_max_size())
            task.signals.done.connect(self._on_render_done)
            self._pool.start(task)

    def _check_real_size_available(self) -> bool:
        """Check if real-size preview is available for this image."""
        # Must have image_item, config, and a valid size tag
        if self.image_item is None or self.config is None:
            return False
        if not self.image_item.is_fully_tagged():
            return False
        # Verify size_tag can be parsed
        try:
            Config.parse_size_dimensions(self.image_item.size_tag)
            return True
        except ValueError:
            return False

    def _update_hint_label(self):
        """Update the hint label based on current mode."""
        base_hint = "Scroll to zoom | Drag to pan | Click outside or ESC to close"

        # Position counter — the only discoverability the arrow keys get.
        if len(self.images) > 1:
            base_hint = (f"{self.index + 1} / {len(self.images)} | "
                         f"← → to browse | {base_hint}")

        # Check if date stamp preview is shown
        date_stamp_indicator = ""
        if self.image_item and self.image_item.add_date_stamp:
            date_stamp_indicator = "[DATE STAMP PREVIEW] | "

        # The previous photo stays on screen while the next one renders, so
        # without this there is no sign anything is happening.
        if getattr(self, "_loading", False):
            date_stamp_indicator = f"[Loading…] | {date_stamp_indicator}"

        if self.can_use_real_size:
            if self.real_size_mode:
                # Get dimensions for display
                try:
                    width, height = Config.parse_size_dimensions(self.image_item.size_tag)
                    ppu = self.config.get_setting("pixels_per_unit", 100)
                    real_width = width * ppu
                    real_height = height * ppu
                    mode_info = f"[REAL SIZE: {width}x{height} units = {real_width}x{real_height}px]"
                except ValueError:
                    mode_info = "[REAL SIZE MODE]"
                self.hint_label.setText(f"{date_stamp_indicator}{mode_info} | Press R for normal view | {base_hint}")
            else:
                self.hint_label.setText(
                    f"{date_stamp_indicator}[Normal View] | Press R for real-size preview | {base_hint}")
        else:
            self.hint_label.setText(f"{date_stamp_indicator}{base_hint}")

    def toggle_real_size_mode(self):
        """Toggle between normal and real-size preview modes."""
        if not self.can_use_real_size:
            return

        self.real_size_mode = not self.real_size_mode
        self._update_hint_label()

        if self.loaded_pixmap and not self.loaded_pixmap.isNull():
            if self.real_size_mode:
                self._apply_real_size_zoom()
            else:
                self.image_label.set_image(self.loaded_pixmap,
                                           self._fit_zoom(self.loaded_pixmap))

    def _apply_real_size_zoom(self):
        """Apply zoom level for real-size preview."""
        if not self.loaded_pixmap or self.loaded_pixmap.isNull():
            return
        if not self.image_item or not self.config:
            return

        try:
            # Get size dimensions from tag (e.g., "9x6" -> (9, 6))
            width_units, _height_units = Config.parse_size_dimensions(self.image_item.size_tag)

            # Get pixels per unit from config
            ppu = self.config.get_setting("pixels_per_unit", 100)

            # Calculate target display size in pixels
            target_width = width_units * ppu

            # Calculate zoom factor based on the loaded pixmap dimensions
            # The pixmap is already cropped to the correct aspect ratio
            zoom_factor = target_width / self.loaded_pixmap.width()

            # Apply the zoom
            self.image_label.set_image(self.loaded_pixmap, zoom_factor)

        except (ValueError, ZeroDivisionError) as e:
            print(f"Error applying real-size zoom: {e}")
            # Fall back to normal view
            self.real_size_mode = False
            self._update_hint_label()

    def keyPressEvent(self, event: Optional[QKeyEvent]):
        """ESC closes, R toggles real-size, Left/Right browse the project."""
        if event:
            if event.key() == Qt.Key.Key_Escape:
                self.close()
            elif event.key() == Qt.Key.Key_R:
                self.toggle_real_size_mode()
            elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                # Each step is a full-resolution load, plus a crop and date-stamp
                # render for tagged images. Held-down auto-repeat would queue up
                # seconds of work for frames nobody sees.
                if not event.isAutoRepeat():
                    self.navigate(-1 if event.key() == Qt.Key.Key_Left else +1)
            else:
                super().keyPressEvent(event)

    def closeEvent(self, a0):
        """Let in-flight renders finish before the dialog can be torn down.

        Each _RenderTask emits into this dialog. If Python collected it while a
        worker was still running, that signal would fire at freed memory and take
        the app down — so stop accepting results, then wait the pool out. Waiting
        is bounded by one render (a few hundred ms) and only bites if you close
        the viewer the instant you opened it.
        """
        self._pending_key = None
        self._pool.clear()  # drop tasks that have not started
        self._pool.waitForDone()
        self._render_cache.clear()
        super().closeEvent(a0)

    def mousePressEvent(self, event: Optional[QMouseEvent]):
        """Close dialog when clicking outside the image area."""
        # Check if click is on the dialog background (not on the scroll area content)
        if event and event.button() == Qt.MouseButton.LeftButton:
            # Get the scroll area geometry in dialog coordinates
            scroll_rect = self.scroll_area.geometry()
            click_pos = event.pos()

            # If click is outside scroll area, close
            if not scroll_rect.contains(click_pos):
                self.close()
                return

        super().mousePressEvent(event)
