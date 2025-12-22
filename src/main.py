import sys
from PyQt6.QtWidgets import QApplication
from .ui.main_window import MainWindow


def main():
    """Entry point for Album Studio application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Album Studio")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
