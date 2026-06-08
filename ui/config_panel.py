import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                              QPushButton, QDoubleSpinBox, QComboBox, QGroupBox,
                              QScrollArea, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt


def _field(label_text):
    lbl = QLabel(label_text.upper())
    lbl.setObjectName('formLabel')
    return lbl


class ConfigPanel(QWidget):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        hdr = QLabel('CONFIGURATION')
        hdr.setObjectName('sectionHeader')
        root.addWidget(hdr)

        broker_group = QGroupBox('BROKER CONNECTION')
        bg = QVBoxLayout(broker_group)
        bg.setSpacing(10)

        row1 = QHBoxLayout()
        lc1 = QVBoxLayout()
        lc1.addWidget(_field('MT5 Login'))
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText('Account number')
        lc1.addWidget(self.login_input)
        row1.addLayout(lc1)

        lc2 = QVBoxLayout()
        lc2.addWidget(_field('MT5 Password'))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText('••••••••')
        lc2.addWidget(self.password_input)
        row1.addLayout(lc2)
        bg.addLayout(row1)

        row2 = QHBoxLayout()
        lc3 = QVBoxLayout()
        lc3.addWidget(_field('FxPro Server Preset'))
        self.server_select = QComboBox()
        self.server_select.addItems(['Custom', 'FxPro-Demo', 'FxPro-Real4', 'FxPro-Real5', 'FxPesa-Demo', 'FxPesa-Live'])
        self.server_select.currentTextChanged.connect(self._on_server_preset)
        lc3.addWidget(self.server_select)
        row2.addLayout(lc3)

        lc4 = QVBoxLayout()
        lc4.addWidget(_field('Server Address'))
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText('e.g. FxPro-Real4')
        lc4.addWidget(self.server_input)
        row2.addLayout(lc4)
        bg.addLayout(row2)

        root.addWidget(broker_group)

        trading_group = QGroupBox('TRADING PARAMETERS')
        tg = QVBoxLayout(trading_group)
        tg.setSpacing(10)

        tg.addWidget(_field('Symbols to Trade (comma separated)'))
        self.symbols_input = QLineEdit()
        self.symbols_input.setPlaceholderText('EURUSD,GBPUSD,USDJPY,USDCHF')
        tg.addWidget(self.symbols_input)

        row3 = QHBoxLayout()
        row3.setSpacing(16)

        lc5 = QVBoxLayout()
        lc5.addWidget(_field('Risk per Trade (%)'))
        self.risk_input = QDoubleSpinBox()
        self.risk_input.setRange(0.1, 10.0)
        self.risk_input.setSingleStep(0.1)
        self.risk_input.setDecimals(1)
        self.risk_input.setSuffix(' %')
        lc5.addWidget(self.risk_input)
        row3.addLayout(lc5)

        lc6 = QVBoxLayout()
        lc6.addWidget(_field('Max Daily Drawdown (%)'))
        self.daily_loss_input = QDoubleSpinBox()
        self.daily_loss_input.setRange(0.5, 50.0)
        self.daily_loss_input.setSingleStep(0.5)
        self.daily_loss_input.setDecimals(1)
        self.daily_loss_input.setSuffix(' %')
        lc6.addWidget(self.daily_loss_input)
        row3.addLayout(lc6)

        lc7 = QVBoxLayout()
        lc7.addWidget(_field('Timeframe'))
        self.tf_select = QComboBox()
        self.tf_select.addItems(['M1', 'M5', 'M15', 'H1', 'H4'])
        self.tf_select.setCurrentText('M5')
        lc7.addWidget(self.tf_select)
        row3.addLayout(lc7)

        lc8 = QVBoxLayout()
        lc8.addWidget(_field('Poll Interval (s)'))
        self.poll_input = QDoubleSpinBox()
        self.poll_input.setRange(0.5, 60.0)
        self.poll_input.setSingleStep(0.5)
        self.poll_input.setDecimals(1)
        self.poll_input.setValue(2.0)
        lc8.addWidget(self.poll_input)
        row3.addLayout(lc8)

        tg.addLayout(row3)
        root.addWidget(trading_group)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_btn = QPushButton('Save Settings')
        self.save_btn.setObjectName('btnSave')
        self.save_btn.setFixedHeight(38)
        self.save_btn.setMinimumWidth(160)
        self.save_btn.clicked.connect(self.save_settings)
        save_row.addWidget(self.save_btn)
        root.addLayout(save_row)

        self.status_lbl = QLabel('')
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.status_lbl.setStyleSheet('color:#3fb950; font-size:12px;')
        root.addWidget(self.status_lbl)

        root.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_server_preset(self, value):
        if value != 'Custom':
            self.server_input.setText(value)

    def load_settings(self):
        cfg = self.orchestrator.config
        self.login_input.setText(str(cfg.get('mt5_login') or ''))
        self.password_input.setText(str(cfg.get('mt5_password') or ''))
        server = str(cfg.get('mt5_server') or '')
        self.server_input.setText(server)
        if server in ['FxPro-Demo', 'FxPro-Real4', 'FxPro-Real5']:
            self.server_select.setCurrentText(server)
        symbols = cfg.get('trade_symbols', [])
        self.symbols_input.setText(','.join(symbols))
        self.risk_input.setValue(float(cfg.get('risk_per_trade', 0.02)) * 100)
        self.daily_loss_input.setValue(float(cfg.get('max_daily_loss', 0.05)) * 100)
        tf_map = {1: 'M1', 5: 'M5', 15: 'M15', 60: 'H1', 240: 'H4'}
        self.tf_select.setCurrentText(tf_map.get(cfg.get('timeframe', 5), 'M5'))
        self.poll_input.setValue(float(cfg.get('poll_interval_seconds', 2.0)))

    def save_settings(self):
        tf_map = {'M1': 1, 'M5': 5, 'M15': 15, 'H1': 60, 'H4': 240}
        symbols = [s.strip() for s in self.symbols_input.text().split(',') if s.strip()]
        values = {
            'broker': 'mt5',
            'mt5_login': self.login_input.text().strip() or None,
            'mt5_password': self.password_input.text() or None,
            'mt5_server': self.server_input.text().strip() or None,
            'trade_symbols': symbols or ['EURUSD', 'GBPUSD'],
            'risk_per_trade': round(self.risk_input.value() / 100, 4),
            'max_daily_loss': round(self.daily_loss_input.value() / 100, 4),
            'timeframe': tf_map.get(self.tf_select.currentText(), 5),
            'poll_interval_seconds': self.poll_input.value(),
            'num_experts': self.orchestrator.config.get('num_experts', 20),
            'esn_hidden': self.orchestrator.config.get('esn_hidden', 120),
            'database_path': self.orchestrator.config.get('database_path', 'db/forex_ai.db')
        }
        try:
            with open(self.orchestrator.config_path, 'w', encoding='utf-8') as f:
                json.dump(values, f, indent=2)
            self.orchestrator.config = values
            self.orchestrator.symbols = values['trade_symbols']
            self.orchestrator.risk_manager.risk_per_trade = values['risk_per_trade']
            self.orchestrator.risk_manager.max_daily_loss = values['max_daily_loss']
            self.orchestrator.update_interval = values['poll_interval_seconds']
            self.status_lbl.setText('✓ Settings saved')
        except Exception as e:
            self.status_lbl.setStyleSheet('color:#f85149; font-size:12px;')
            self.status_lbl.setText(f'✖ Save failed: {e}')
