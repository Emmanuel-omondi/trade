from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt

class TradeLogWidget(QWidget):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(['Time', 'Pair', 'Direction', 'Entry', 'Exit', 'Size', 'PnL', 'Confidence', 'Reason'])
        self.layout.addWidget(self.table)

    def update_state(self):
        trades = self.orchestrator.database.get_recent_trades(limit=50)
        self.table.setRowCount(len(trades))
        for row, trade in enumerate(trades):
            self.table.setItem(row, 0, QTableWidgetItem(trade['timestamp']))
            self.table.setItem(row, 1, QTableWidgetItem(trade['pair']))
            self.table.setItem(row, 2, QTableWidgetItem(trade['direction']))
            self.table.setItem(row, 3, QTableWidgetItem(f"{trade['entry_price']:.5f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{trade['exit_price']:.5f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{trade['size']:.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{trade['pnl']:.2f}"))
            self.table.setItem(row, 7, QTableWidgetItem(f"{trade['confidence']:.2f}"))
            self.table.setItem(row, 8, QTableWidgetItem(trade['reason']))
        self.table.resizeColumnsToContents()
