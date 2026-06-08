from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QTableWidget, QTableWidgetItem, QHeaderView, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class TradeLogWidget(QWidget):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hdr_row = QHBoxLayout()
        hdr = QLabel('TRADE HISTORY')
        hdr.setObjectName('sectionHeader')
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()

        self.lbl_total = QLabel('Total: 0')
        self.lbl_total.setStyleSheet('color:#8b949e; font-size:12px;')
        self.lbl_wins = QLabel('Wins: 0')
        self.lbl_wins.setStyleSheet('color:#3fb950; font-size:12px; font-weight:600;')
        self.lbl_losses = QLabel('Losses: 0')
        self.lbl_losses.setStyleSheet('color:#f85149; font-size:12px; font-weight:600;')
        self.lbl_net = QLabel('Net P&L: 0.00')
        self.lbl_net.setStyleSheet('color:#58a6ff; font-size:12px; font-weight:700;')

        for w in [self.lbl_total, self.lbl_wins, self.lbl_losses, self.lbl_net]:
            hdr_row.addWidget(w)
            hdr_row.addSpacing(14)

        root.addLayout(hdr_row)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ['Time', 'Symbol', 'Direction', 'Entry', 'Exit', 'Size', 'P&L', 'Confidence', 'Reason']
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table)

    def update_state(self):
        trades = self.orchestrator.database.get_recent_trades(limit=100)
        summary = self.orchestrator.database.get_trade_summary()

        self.lbl_total.setText(f'Total: {summary["total"]}')
        self.lbl_wins.setText(f'Wins: {summary["wins"]}')
        self.lbl_losses.setText(f'Losses: {summary["losses"]}')
        net = summary['total_pnl']
        sign = '+' if net >= 0 else ''
        color = '#3fb950' if net >= 0 else '#f85149'
        self.lbl_net.setText(f'Net P&L: {sign}{net:,.2f}')
        self.lbl_net.setStyleSheet(f'color:{color}; font-size:12px; font-weight:700;')

        self.table.setRowCount(len(trades))
        for row, trade in enumerate(trades):
            pnl = float(trade.get('pnl', 0))
            pnl_color = QColor('#3fb950') if pnl >= 0 else QColor('#f85149')
            direction = trade.get('direction', '')
            dir_color = QColor('#58a6ff') if direction == 'BUY' else QColor('#d29922')

            def cell(text, color=None, align=Qt.AlignmentFlag.AlignCenter):
                item = QTableWidgetItem(str(text))
                if color:
                    item.setForeground(color)
                item.setTextAlignment(align)
                return item

            ts = trade.get('timestamp', '')
            if 'T' in ts:
                ts = ts.split('T')[1][:8]

            self.table.setItem(row, 0, cell(ts, QColor('#8b949e')))
            self.table.setItem(row, 1, cell(trade.get('pair', ''), QColor('#e6edf3')))
            self.table.setItem(row, 2, cell(direction, dir_color))
            self.table.setItem(row, 3, cell(f"{float(trade.get('entry_price', 0)):.5f}"))
            self.table.setItem(row, 4, cell(f"{float(trade.get('exit_price', 0)):.5f}"))
            self.table.setItem(row, 5, cell(f"{float(trade.get('size', 0)):.2f}"))
            sign = '+' if pnl >= 0 else ''
            self.table.setItem(row, 6, cell(f'{sign}{pnl:.2f}', pnl_color))
            self.table.setItem(row, 7, cell(f"{float(trade.get('confidence', 0)):.2f}"))
            self.table.setItem(row, 8, cell(trade.get('reason', ''), QColor('#8b949e')))
