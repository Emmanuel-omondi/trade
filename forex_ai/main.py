import sys
import os
from pathlib import Path

os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from ui.main_window import MainWindow
from core.orchestrator import TradingOrchestrator

if __name__ == '__main__':
    config_path = Path('config/settings.json')
    orchestrator = TradingOrchestrator(config_path=config_path)

    app = QApplication(sys.argv)
    app.setFont(QFont('Segoe UI', 10))

    qss_path = Path('ui/style.qss')
    if qss_path.exists():
        with open(qss_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())

    window = MainWindow(orchestrator)
    window.show()
    sys.exit(app.exec())
