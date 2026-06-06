from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QSizePolicy
from PyQt6.QtCore import Qt

class DashboardWidget(QWidget):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)
        self.summary_label = QLabel()
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.summary_label.setWordWrap(True)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['Pair', 'Direction', 'Entry', 'Size', 'P/L', 'Confidence'])
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.layout.addWidget(self.summary_label)
        self.layout.addWidget(self.table)

    def update_state(self):
        state = self.orchestrator.get_state()
        account = state.get('account', {})
        trade_stats = state.get('trade_stats', {})
        open_positions = account.get('open_positions_count', 0)
        balance = account.get('account_balance', 0)
        equity = account.get('total_equity', 0)
        daily_pnl = account.get('daily_pnl', 0)
        win_rate = trade_stats.get('win_rate', 0)
        profit_factor = trade_stats.get('profit_factor', 0)
        drawdown = trade_stats.get('max_drawdown', 0)

        summary = (
            f"Balance: {balance:.2f}\n"
            f"Equity: {equity:.2f}\n"
            f"Open Positions: {open_positions}\n"
            f"Daily PnL: {daily_pnl:.2f}\n"
            f"Win Rate: {win_rate:.2%}\n"
            f"Profit Factor: {profit_factor:.2f}\n"
            f"Drawdown: {drawdown:.2%}"
        )
        self.summary_label.setText(summary)

        positions = self.orchestrator.risk_manager.get_open_positions()
        self.table.setRowCount(len(positions))
        for row, (pair, position) in enumerate(positions.items()):
            self.table.setItem(row, 0, QTableWidgetItem(pair))
            self.table.setItem(row, 1, QTableWidgetItem(position['direction']))
            self.table.setItem(row, 2, QTableWidgetItem(f"{position['entry_price']:.5f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{position['position_size']:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{position['pnl']:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{position['confidence']:.2f}"))
        self.table.resizeColumnsToContents()
