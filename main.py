"""Entry point for LayerScan3D application."""

import sys
import logging
from PySide6.QtWidgets import QApplication

from layerscan.utils.logger import setup_logging
from layerscan.ui.main_window import MainWindow
from layerscan.ui.styles import DARK_STYLESHEET

def main():
    # Setup logging
    setup_logging(level=logging.INFO)
    logger = logging.getLogger("layerscan.main")
    logger.info("Starting LayerScan3D...")
    
    # Initialize Qt Application
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
