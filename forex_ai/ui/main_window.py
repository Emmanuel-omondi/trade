import threading
from PyQt6.QtWidgets import (QMainWindow, QWidget, QTabWidget, QPushButton,
                              QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QFrame)
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from ui.dashboard import DashboardWidget
from ui.config_panel import ConfigPanel
from ui.brain_monitor import BrainMonitorWidget
from ui.trade_log import TradeLogWidget


class MainWindow(QMainWindow):
    connectResult = pyqtSignal(bool)
    logSignal = pyqtSignal(str, str)

    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.orchestrator.add_log_callback(self._on_log)
        self.setWindowTitle('Skelter Forex AI')
        self.setMinimumSize(1100, 720)
        self.resize(1280, 820)

        root = QWidget()
        root.setObjectName('rootWidget')
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        top_bar = self._build_top_bar()
        root_layout.addWidget(top_bar)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.dashboard = DashboardWidget(orchestrator)
        self.brain_monitor = BrainMonitorWidget(orchestrator)
        self.config_panel = ConfigPanel(orchestrator)
        self.trade_log = TradeLogWidget(orchestrator)
        self.tabs.addTab(self.dashboard, '  Dashboard  ')
        self.tabs.addTab(self.brain_monitor, '  AI Brain  ')
        self.tabs.addTab(self.trade_log, '  Trade Log  ')
        self.tabs.addTab(self.config_panel, '  Config  ')
        root_layout.addWidget(self.tabs)

        self.connectResult.connect(self._on_connect_result)
        self.logSignal.connect(self._dispatch_log)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _build_top_bar(self):
        bar = QWidget()
        bar.setObjectName('topBar')
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        title = QLabel('⬡ SKELTER AI')
        title.setObjectName('appTitle')
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet('color: #21262d;')
        layout.addWidget(sep)

        self.conn_dot = QLabel('●')
        self.conn_dot.setObjectName('connDot')
        self.conn_dot.setStyleSheet('color: #da3633;')
        self.conn_dot.setToolTip('Disconnected')
        layout.addWidget(self.conn_dot)

        self.status_chip = QLabel('STOPPED')
        self.status_chip.setObjectName('statusChip')
        layout.addWidget(self.status_chip)

        layout.addStretch()

        self.balance_chip = QLabel('Balance: ---')
        self.balance_chip.setObjectName('balanceChip')
        layout.addWidget(self.balance_chip)

        self.equity_chip = QLabel('Equity: ---')
        self.equity_chip.setObjectName('equityChip')
        layout.addWidget(self.equity_chip)

        self.pnl_chip = QLabel('P&L: ---')
        self.pnl_chip.setObjectName('pnlChip')
        self.pnl_chip.setStyleSheet('background:#21262d; color:#8b949e; border-radius:10px; padding:3px 12px; font-size:13px; font-weight:700;')
        layout.addWidget(self.pnl_chip)

        layout.addStretch()

        self.btn_start = QPushButton('▶  START')
        self.btn_start.setObjectName('btnStart')
        self.btn_start.setFixedHeight(34)
        self.btn_start.clicked.connect(self._start_system)
        layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton('■  STOP')
        self.btn_stop.setObjectName('btnStop')
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_system)
        layout.addWidget(self.btn_stop)

        return bar

    def _start_system(self):
        self.status_chip.setText('CONNECTING...')
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.conn_dot.setStyleSheet('color: #d29922;')

        def worker():
            ok = False
            try:
                ok = self.orchestrator.connect()
            except Exception as e:
                pass
            self.connectResult.emit(ok)

        threading.Thread(target=worker, daemon=True).start()

    def _stop_system(self):
        self.orchestrator.stop()
        self.orchestrator.disconnect()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_chip.setText('STOPPED')
        self.status_chip.setStyleSheet('')
        self.conn_dot.setStyleSheet('color: #da3633;')
        self.config_panel.setEnabled(True)

    def _on_connect_result(self, success: bool):
        if not success:
            err = getattr(self.orchestrator, 'last_error', 'Unknown error')
            self.status_chip.setText('FAILED')
            self.status_chip.setStyleSheet('background:#3d1a1a; color:#f85149;')
            self.conn_dot.setStyleSheet('color: #da3633;')
            self.btn_start.setEnabled(True)
            return

        self.config_panel.setEnabled(False)
        self.orchestrator.start()
        self.status_chip.setText('RUNNING')
        self.status_chip.setStyleSheet('background:#1a3d28; color:#3fb950;')
        self.conn_dot.setStyleSheet('color: #3fb950;')
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _on_log(self, level, message):
        self.logSignal.emit(level, message)

    def _dispatch_log(self, level, message):
        self.dashboard.append_log(level, message)

    def _tick(self):
        state = self.orchestrator.get_state()
        account = state.get('account', {})

        balance = account.get('account_balance', 0.0)
        equity = account.get('total_equity', 0.0)
        open_pnl = account.get('open_pnl', 0.0)

        self.balance_chip.setText(f'Balance: {balance:,.2f}')
        self.equity_chip.setText(f'Equity: {equity:,.2f}')

        pnl_color = '#3fb950' if open_pnl >= 0 else '#f85149'
        sign = '+' if open_pnl >= 0 else ''
        self.pnl_chip.setText(f'P&L: {sign}{open_pnl:,.2f}')
        self.pnl_chip.setStyleSheet(f'background:#21262d; color:{pnl_color}; border-radius:10px; padding:3px 12px; font-size:13px; font-weight:700;')

        is_conn = getattr(self.orchestrator, 'is_connected', False)
        st = state.get('status', 'stopped')
        if is_conn and st == 'running':
            self.conn_dot.setStyleSheet('color: #3fb950;')
            self.status_chip.setText('RUNNING')
            self.status_chip.setStyleSheet('background:#1a3d28; color:#3fb950; border-radius:10px; padding:3px 10px; font-size:12px; font-weight:600;')
        elif st == 'reconnecting':
            self.conn_dot.setStyleSheet('color: #d29922;')
            self.status_chip.setText('RECONNECTING')
            self.status_chip.setStyleSheet('background:#3d2f0a; color:#d29922; border-radius:10px; padding:3px 10px; font-size:12px; font-weight:600;')

        self.dashboard.update_state(state)
        self.brain_monitor.update_state()
        self.trade_log.update_state()
