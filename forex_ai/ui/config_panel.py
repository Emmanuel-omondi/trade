from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox, QListWidget, QComboBox
from PyQt6.QtCore import Qt
import json
from pathlib import Path

class ConfigPanel(QWidget):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)
        self.login_input = QLineEdit()
        self.password_input = QLineEdit()
        self.server_select = QComboBox()
        self.server_select.addItems(['Custom', 'FxPro-Demo', 'FxPro-Real4', 'FxPro-Real5'])
        self.server_input = QLineEdit()
        self.symbols_edit = QLineEdit()
        self.balance_input = QDoubleSpinBox()
        self.balance_input.setMaximum(100000000)
        self.balance_input.setValue(self.orchestrator.risk_manager.current_balance)
        self.risk_input = QDoubleSpinBox()
        self.risk_input.setDecimals(4)
        self.risk_input.setSingleStep(0.005)
        self.risk_input.setMaximum(1)
        self.risk_input.setValue(self.orchestrator.risk_manager.risk_per_trade)
        self.daily_loss_input = QDoubleSpinBox()
        self.daily_loss_input.setDecimals(4)
        self.daily_loss_input.setSingleStep(0.005)
        self.daily_loss_input.setMaximum(1)
        self.daily_loss_input.setValue(self.orchestrator.risk_manager.max_daily_loss)
        self.save_button = QPushButton('Save Settings')
        self.save_button.clicked.connect(self.save_settings)
        self.layout.addWidget(QLabel('MT5 Login'))
        self.layout.addWidget(self.login_input)
        self.layout.addWidget(QLabel('MT5 Password'))
        self.layout.addWidget(self.password_input)
        self.layout.addWidget(QLabel('Common FxPro Server'))
        self.layout.addWidget(self.server_select)
        self.layout.addWidget(QLabel('MT5 Server'))
        self.layout.addWidget(self.server_input)
        self.layout.addWidget(QLabel('Symbols (comma separated)'))
        self.layout.addWidget(self.symbols_edit)
        self.layout.addWidget(QLabel('Starting Balance'))
        self.layout.addWidget(self.balance_input)
        self.layout.addWidget(QLabel('Risk per Trade'))
        self.layout.addWidget(self.risk_input)
        self.layout.addWidget(QLabel('Max Daily Loss'))
        self.layout.addWidget(self.daily_loss_input)
        self.layout.addWidget(self.save_button)
        self.server_select.currentTextChanged.connect(self._on_server_selection_changed)
        self.load_settings()

    def _on_server_selection_changed(self, value):
        if value == 'Custom':
            return
        self.server_input.setText(value)

    def load_settings(self):
        config = self.orchestrator.config
        self.login_input.setText(str(config.get('mt5_login') or ''))
        self.password_input.setText(str(config.get('mt5_password') or ''))
        self.server_input.setText(str(config.get('mt5_server') or ''))
        server_value = config.get('mt5_server', '')
        if server_value in ['FxPro-Demo', 'FxPro-Real4', 'FxPro-Real5']:
            self.server_select.setCurrentText(server_value)
        else:
            self.server_select.setCurrentText('Custom')
        self.symbols_edit.setText(','.join(config.get('trade_symbols', [])))
        self.balance_input.setValue(config.get('account_balance', self.orchestrator.risk_manager.current_balance))
        self.risk_input.setValue(config.get('risk_per_trade', self.orchestrator.risk_manager.risk_per_trade))
        self.daily_loss_input.setValue(config.get('max_daily_loss', self.orchestrator.risk_manager.max_daily_loss))

    def save_settings(self):
        values = {
            'mt5_login': self.login_input.text() or None,
            'mt5_password': self.password_input.text() or None,
            'mt5_server': self.server_input.text() or None,
            'trade_symbols': [s.strip() for s in self.symbols_edit.text().split(',') if s.strip()],
            'account_balance': float(self.balance_input.value()),
            'risk_per_trade': float(self.risk_input.value()),
            'max_daily_loss': float(self.daily_loss_input.value()),
            'timeframe': self.orchestrator.config.get('timeframe', 5),
            'poll_interval_seconds': self.orchestrator.config.get('poll_interval_seconds', 2),
            'num_experts': self.orchestrator.config.get('num_experts', 20),
            'esn_hidden': self.orchestrator.config.get('esn_hidden', 120),
            'database_path': self.orchestrator.config.get('database_path', 'db/forex_ai.db')
        }
        with open(self.orchestrator.config_path, 'w', encoding='utf-8') as f:
            json.dump(values, f, indent=2)
        self.orchestrator.config = values
        self.orchestrator.symbols = values['trade_symbols']
        self.orchestrator.risk_manager.current_balance = values['account_balance']
        self.orchestrator.risk_manager.risk_per_trade = values['risk_per_trade']
        self.orchestrator.risk_manager.max_daily_loss = values['max_daily_loss']
