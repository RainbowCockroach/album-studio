import os
import sys
from PyQt6.QtWidgets import QApplication
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
