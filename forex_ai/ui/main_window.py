from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QTabWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QToolBar, QStyle
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer, pyqtSignal
import threading
from ui.dashboard import DashboardWidget
from ui.config_panel import ConfigPanel
from ui.brain_monitor import BrainMonitorWidget
from ui.trade_log import TradeLogWidget

class MainWindow(QMainWindow):
    connectResult = pyqtSignal(bool)

    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.setWindowTitle('Skelter Trader Agent')
        self.setMinimumSize(900, 700)
        self.container = QWidget()
        self.container.setObjectName('containerWidget')
        self.layout = QVBoxLayout(self.container)
        self.setCentralWidget(self.container)
        toolbar = QToolBar()
        icon_folder = 'assets/'
        style = QApplication.style()
        start_icon = style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        stop_icon = style.standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self.start_action = QAction(start_icon, 'Start', self)
        self.stop_action = QAction(stop_icon, 'Stop', self)
        self.stop_action.setEnabled(False)
        toolbar.addAction(self.start_action)
        toolbar.addAction(self.stop_action)
        # assign object names to the generated toolbuttons for styling
        self.start_btn_widget = toolbar.widgetForAction(self.start_action)
        if self.start_btn_widget is not None:
            self.start_btn_widget.setObjectName('startButton')
        self.stop_btn_widget = toolbar.widgetForAction(self.stop_action)
        if self.stop_btn_widget is not None:
            self.stop_btn_widget.setObjectName('stopButton')

        # connection indicator and status
        self.conn_indicator = QLabel('\u25CF')
        self.conn_indicator.setObjectName('connIndicator')
        self.status_label = QLabel('Status: stopped')
        self.status_label.setObjectName('statusLabel')
        self.balance_label = QLabel('Balance: 0.00')
        self.balance_label.setObjectName('balanceLabel')
        # ensure readable defaults regardless of stylesheet
        self.conn_indicator.setStyleSheet('color: #e74c3c; font-weight:700;')
        self.status_label.setStyleSheet('color: #ffffff; background: transparent; font-weight:700;')
        self.balance_label.setStyleSheet('color: #111111; background: #ffffff; padding:4px; border-radius:6px; font-weight:700;')
        toolbar.addWidget(self.conn_indicator)
        toolbar.addWidget(self.status_label)
        toolbar.addWidget(self.balance_label)
        self.layout.addWidget(toolbar)
        self.tabs = QTabWidget()
        self.dashboard = DashboardWidget(orchestrator)
        self.brain_monitor = BrainMonitorWidget(orchestrator)
        self.config_panel = ConfigPanel(orchestrator)
        self.trade_log = TradeLogWidget(orchestrator)
        self.tabs.addTab(self.dashboard, 'Dashboard')
        self.tabs.addTab(self.brain_monitor, 'Brain Monitor')
        self.tabs.addTab(self.trade_log, 'Trade Log')
        self.tabs.addTab(self.config_panel, 'Config')
        self.layout.addWidget(self.tabs)
        self.start_action.triggered.connect(self.start_system)
        self.stop_action.triggered.connect(self.stop_system)
        self.connectResult.connect(self._on_connect_result)
        self.timer = QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def start_system(self):
        # run connect on a background thread to avoid blocking the UI
        self.status_label.setText('Status: connecting...')
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(False)
        self.conn_indicator.setStyleSheet('color: #f1c40f;')  # yellow during connect

        def worker():
            ok = False
            try:
                print('[UI worker] Starting connect...', flush=True)
                import sys
                sys.stdout.flush()
                ok = self.orchestrator.connect()
                print(f'[UI worker] Connect returned {ok}', flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f'[UI worker] Connect exception: {e}', flush=True)
                import sys
                sys.stdout.flush()
                ok = False
            # schedule UI update back on the main thread
            print('[UI worker] Scheduling callback...', flush=True)
            import sys
            sys.stdout.flush()
            self.connectResult.emit(ok)
            print('[UI worker] Callback scheduled, thread exiting...', flush=True)
            sys.stdout.flush()

        # start thread with daemon mode
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        # schedule a watchdog UI update if connection takes long
        QTimer.singleShot(30000, lambda: self._on_connect_watchdog())

    def stop_system(self):
        self.orchestrator.stop()
        self.orchestrator.disconnect()
        self.config_panel.setEnabled(True)
        self.start_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        self.status_label.setText('Status: stopped')

    def _on_connect_result(self, success: bool):
        import sys
        print(f'[UI] _on_connect_result called with success={success}', flush=True)
        sys.stdout.flush()
        if not success:
            err = getattr(self.orchestrator, 'last_error', None)
            msg = 'connection failed' if not err else f'connection failed: {err}'
            self.status_label.setText(f'Status: {msg}')
            self.status_label.setToolTip(str(err or ''))
            self.start_action.setEnabled(True)
            self.stop_action.setEnabled(False)
            self.conn_indicator.setStyleSheet('color: #e74c3c;')
            print(f'[UI] Connect failed: {err}', flush=True)
            sys.stdout.flush()
            return

        # connected successfully
        print('[UI] Connected successfully', flush=True)
        sys.stdout.flush()
        self.config_panel.setEnabled(False)
        self.orchestrator.start()
        self.status_label.setText('Status: running')
        self.status_label.setToolTip('')
        self.start_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        self.conn_indicator.setStyleSheet('color: #2ecc71;')
        # schedule state update on main thread after UI updates settle
        QTimer.singleShot(100, self._refresh_ui_state_after_connect)

    def _refresh_ui_state_after_connect(self):
        """Refresh UI state after a successful connect, without blocking the main thread."""
        import sys
        print('[UI] _refresh_ui_state_after_connect starting...', flush=True)
        sys.stdout.flush()
        try:
            self.orchestrator._update_status()
            print('[UI] _update_status() completed', flush=True)
            sys.stdout.flush()
            state = self.orchestrator.get_state()
            print(f'[UI] State after update: {state}', flush=True)
            sys.stdout.flush()
            self.tick()
            print('[UI] tick() completed', flush=True)
            sys.stdout.flush()
        except Exception as e:
            import traceback
            print(f'[UI] _refresh_ui_state_after_connect failed: {e}', flush=True)
            traceback.print_exc()
            sys.stdout.flush()

    def _on_connect_watchdog(self):
        # if still not connected after a delay, show a warning and set indicator to yellow
        if getattr(self.orchestrator, 'is_connected', False):
            return
        st = self.status_label.text()
        if 'connecting' in st.lower():
            self.status_label.setText('Status: connecting (taking longer than expected)')
            self.status_label.setToolTip('Connection is taking longer than expected; please check the MT5 terminal')
            self.conn_indicator.setStyleSheet('color: #f1c40f;')

    def tick(self):
        import sys
        state = self.orchestrator.get_state()
        if not state and getattr(self.orchestrator, 'is_connected', False):
            try:
                self.orchestrator._update_status()
                state = self.orchestrator.get_state()
                print('[UI tick] Refreshed state after finding it empty', flush=True)
                sys.stdout.flush()
            except Exception:
                state = {}

        account = state.get('account', {})
        balance = account.get('account_balance', 0)
        print(f'[UI tick] balance={balance}, account={account}', flush=True)
        sys.stdout.flush()
        self.balance_label.setText(f'Balance: {balance:.2f}')
        st = state.get('status', 'stopped')
        self.status_label.setText(f"Status: {st}")
        # update connection indicator color
        if getattr(self.orchestrator, 'is_connected', False):
            self.conn_indicator.setStyleSheet('color: #2ecc71;')
        elif st == 'reconnecting':
            self.conn_indicator.setStyleSheet('color: #f1c40f;')
        else:
            self.conn_indicator.setStyleSheet('color: #e74c3c;')
        self.dashboard.update_state()
        self.brain_monitor.update_state()
        self.trade_log.update_state()
