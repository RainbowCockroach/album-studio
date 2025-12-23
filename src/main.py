import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from .ui.main_window import MainWindow


def main():
    """Entry point for Album Studio application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Album Studio")

    # Set the application icon
    app.setWindowIcon(QIcon("assets/app_icon.png"))  # Replace with your icon path

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
