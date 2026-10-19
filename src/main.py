import os
import sys


def ensure_std_streams():
    """Give a console-less app somewhere to write.

    A windowed PyInstaller build has no console, so sys.stdout and sys.stderr
    are None and any write raises AttributeError. torch's model download
    writes a progress bar to stderr, which broke the first "Find similar" on
    Windows with "'NoneType' object has no attribute 'write'".
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


ensure_std_streams()

# Before any PyQt6 import, or Qt's old C++ runtime breaks torch on Windows.
from .utils.msvc_runtime import preload_msvc_runtime
preload_msvc_runtime()

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtGui import QIcon
from .ui.main_window import MainWindow
from .ui.theme import GLOBAL_STYLESHEET
from .utils.paths import get_assets_dir


def main():
    """Entry point for Album Studio application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Album Studio")

    # Set the application icon. Must be an absolute path: a relative one
    # resolves against the working directory, which is '/' when launched from
    # Finder, and QIcon reports no error for a file it cannot find.
    app.setWindowIcon(QIcon(os.path.join(get_assets_dir(), "app_icon.png")))

    # Apply global retro theme
    app.setStyleSheet(GLOBAL_STYLESHEET)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
