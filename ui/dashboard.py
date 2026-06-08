from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QTableWidget, QTableWidgetItem, QPlainTextEdit,
                              QSizePolicy, QFrame, QHeaderView, QSplitter)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from datetime import datetime


def _stat_card(title, value_id, sub=''):
    card = QWidget()
    card.setObjectName('statCard')
    card.setMinimumWidth(140)
    vl = QVBoxLayout(card)
    vl.setContentsMargins(14, 12, 14, 12)
    vl.setSpacing(2)
    t = QLabel(title.upper())
    t.setObjectName('cardTitle')
    v = QLabel('---')
    v.setObjectName('cardValue')
    v.setObjectName(value_id)
    s = QLabel(sub)
    s.setObjectName('cardSub')
    vl.addWidget(t)
    vl.addWidget(v)
    if sub:
        vl.addWidget(s)
    return card, v


class DashboardWidget(QWidget):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)

        c1, self.lbl_balance = _stat_card('Balance', 'lbl_balance')
        c2, self.lbl_equity = _stat_card('Equity', 'lbl_equity')
        c3, self.lbl_daily_pnl = _stat_card('Daily P&L', 'lbl_daily_pnl')
        c4, self.lbl_win_rate = _stat_card('Win Rate', 'lbl_win_rate')
        c5, self.lbl_pf = _stat_card('Profit Factor', 'lbl_pf')
        c6, self.lbl_drawdown = _stat_card('Drawdown', 'lbl_drawdown')
        c7, self.lbl_trades = _stat_card('Total Trades', 'lbl_trades')
        c8, self.lbl_open = _stat_card('Open Positions', 'lbl_open')

        for c in [c1, c2, c3, c4, c5, c6, c7, c8]:
            cards_row.addWidget(c)
        root.addLayout(cards_row)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet('QSplitter::handle { background: #21262d; height: 1px; }')

        positions_widget = QWidget()
        pv = QVBoxLayout(positions_widget)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(8)
        pos_hdr = QLabel('OPEN POSITIONS')
        pos_hdr.setObjectName('sectionHeader')
        pv.addWidget(pos_hdr)
        self.positions_table = QTableWidget(0, 8)
        self.positions_table.setHorizontalHeaderLabels(
            ['Symbol', 'Direction', 'Entry Price', 'Current', 'Size', 'P&L', 'SL', 'TP']
        )
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.positions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.positions_table.verticalHeader().setVisible(False)
        pv.addWidget(self.positions_table)
        splitter.addWidget(positions_widget)

        log_widget = QWidget()
        lv = QVBoxLayout(log_widget)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)
        log_hdr = QLabel('SYSTEM LOG')
        log_hdr.setObjectName('sectionHeader')
        lv.addWidget(log_hdr)
        self.log_panel = QPlainTextEdit()
        self.log_panel.setObjectName('logPanel')
        self.log_panel.setReadOnly(True)
        self.log_panel.setMaximumBlockCount(500)
        lv.addWidget(self.log_panel)
        splitter.addWidget(log_widget)

        splitter.setSizes([280, 220])
        root.addWidget(splitter)

    def update_state(self, state=None):
        if state is None:
            state = self.orchestrator.get_state()

        account = state.get('account', {})
        trade_stats = state.get('trade_stats', {})

        live_bal = self.orchestrator.risk_manager.live_balance
        live_eq  = self.orchestrator.risk_manager.live_equity
        balance  = live_bal if live_bal > 0 else 0.0
        equity   = live_eq  if live_eq  > 0 else 0.0
        daily_pnl = account.get('daily_pnl', 0.0)
        n_open = account.get('open_positions_count', 0)
        win_rate = trade_stats.get('win_rate', 0.0)
        pf = trade_stats.get('profit_factor', 0.0)
        dd = trade_stats.get('max_drawdown', 0.0)
        total_trades = trade_stats.get('total_trades', 0)

        self.lbl_balance.setText(f'{balance:,.2f}')
        self.lbl_equity.setText(f'{equity:,.2f}')

        dpnl_color = '#3fb950' if daily_pnl >= 0 else '#f85149'
        sign = '+' if daily_pnl >= 0 else ''
        self.lbl_daily_pnl.setText(f'{sign}{daily_pnl:,.2f}')
        self.lbl_daily_pnl.setStyleSheet(f'color: {dpnl_color}; font-size: 22px; font-weight: 700;')

        wr_color = '#3fb950' if win_rate >= 0.5 else '#f85149'
        self.lbl_win_rate.setText(f'{win_rate:.1%}')
        self.lbl_win_rate.setStyleSheet(f'color: {wr_color}; font-size: 22px; font-weight: 700;')

        self.lbl_pf.setText(f'{pf:.2f}')
        self.lbl_drawdown.setText(f'{dd:.1%}')
        self.lbl_trades.setText(str(total_trades))
        self.lbl_open.setText(str(n_open))

        positions = self.orchestrator.risk_manager.get_open_positions()
        self.positions_table.setRowCount(len(positions))
        for row, (pair, pos) in enumerate(positions.items()):
            pnl = pos.get('pnl', 0.0)
            pnl_color = QColor('#3fb950') if pnl >= 0 else QColor('#f85149')
            direction = pos.get('direction', '')
            dir_color = QColor('#58a6ff') if direction == 'BUY' else QColor('#d29922')

            items = [
                (pair, QColor('#e6edf3')),
                (direction, dir_color),
                (f"{pos.get('entry_price', 0):.5f}", QColor('#e6edf3')),
                (f"{pos.get('current_price', pos.get('entry_price', 0)):.5f}", QColor('#e6edf3')),
                (f"{pos.get('position_size', 0):.2f}", QColor('#e6edf3')),
                (f"{'+' if pnl >= 0 else ''}{pnl:.2f}", pnl_color),
                (f"{pos.get('stop_loss', 0):.5f}", QColor('#f85149')),
                (f"{pos.get('take_profit', 0):.5f}", QColor('#3fb950')),
            ]
            for col, (text, color) in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(color)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.positions_table.setItem(row, col, item)

    def append_log(self, level, message):
        ts = datetime.now().strftime('%H:%M:%S')
        colors = {
            'INFO': '#8b949e',
            'TRADE': '#3fb950',
            'WARNING': '#d29922',
            'ERROR': '#f85149',
            'DEBUG': '#6e7681'
        }
        color = colors.get(level.upper(), '#8b949e')
        icons = {'INFO': 'ℹ', 'TRADE': '◆', 'WARNING': '⚠', 'ERROR': '✖', 'DEBUG': '·'}
        icon = icons.get(level.upper(), '·')
        html = f'<span style="color:#30363d">{ts}</span> <span style="color:{color}">{icon} [{level.upper()}]</span> <span style="color:#c9d1d9">{message}</span>'
        self.log_panel.appendHtml(html)
        sb = self.log_panel.verticalScrollBar()
        sb.setValue(sb.maximum())
