from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QProgressBar, QGridLayout, QFrame, QSizePolicy, QGroupBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


def _make_bar(label, bar_id):
    row = QWidget()
    hl = QHBoxLayout(row)
    hl.setContentsMargins(0, 2, 0, 2)
    lbl = QLabel(label)
    lbl.setFixedWidth(130)
    lbl.setStyleSheet('color:#8b949e; font-size:12px;')
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setFixedHeight(6)
    bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    val_lbl = QLabel('0.00')
    val_lbl.setFixedWidth(40)
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    val_lbl.setStyleSheet('color:#e6edf3; font-size:12px; font-weight:600;')
    hl.addWidget(lbl)
    hl.addWidget(bar)
    hl.addWidget(val_lbl)
    return row, bar, val_lbl


class BrainMonitorWidget(QWidget):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        hdr = QLabel('AI BRAIN MONITOR')
        hdr.setObjectName('sectionHeader')
        root.addWidget(hdr)

        grid = QHBoxLayout()
        grid.setSpacing(16)

        conf_group = QGroupBox('COMPONENT CONFIDENCE')
        conf_vl = QVBoxLayout(conf_group)
        conf_vl.setSpacing(6)
        _, self.bar_expert, self.val_expert = _make_bar('Expert Ensemble', 'expert')
        _, self.bar_esn, self.val_esn = _make_bar('Echo State Net', 'esn')
        _, self.bar_bayesian, self.val_bayesian = _make_bar('Bayesian Belief', 'bayesian')
        _, self.bar_predictive, self.val_predictive = _make_bar('Predictive Coding', 'predictive')
        for w in [_, self.bar_expert, self.val_expert,
                  _, self.bar_esn, self.val_esn,
                  _, self.bar_bayesian, self.val_bayesian,
                  _, self.bar_predictive, self.val_predictive]:
            pass
        r1, self.bar_expert, self.val_expert = _make_bar('Expert Ensemble', 'e')
        r2, self.bar_esn, self.val_esn = _make_bar('Echo State Net', 'esn')
        r3, self.bar_bayesian, self.val_bayesian = _make_bar('Bayesian Belief', 'bay')
        r4, self.bar_predictive, self.val_predictive = _make_bar('Predictive Coding', 'pred')
        for r in [r1, r2, r3, r4]:
            conf_vl.addWidget(r)
        conf_vl.addStretch()
        grid.addWidget(conf_group)

        weight_group = QGroupBox('META-LEARNER WEIGHTS')
        weight_vl = QVBoxLayout(weight_group)
        weight_vl.setSpacing(6)
        rw1, self.bar_w_expert, self.val_w_expert = _make_bar('Expert Weight', 'we')
        rw2, self.bar_w_esn, self.val_w_esn = _make_bar('ESN Weight', 'wesn')
        rw3, self.bar_w_bayesian, self.val_w_bayesian = _make_bar('Bayesian Weight', 'wbay')
        rw4, self.bar_w_predictive, self.val_w_predictive = _make_bar('Predictive Weight', 'wpred')
        for r in [rw1, rw2, rw3, rw4]:
            weight_vl.addWidget(r)
        weight_vl.addStretch()
        grid.addWidget(weight_group)

        root.addLayout(grid)

        status_group = QGroupBox('SYSTEM SIGNALS')
        sv = QVBoxLayout(status_group)
        sv.setSpacing(8)
        self.signal_labels = {}
        for key in ['Active Symbols', 'Current Regime', 'Signal Strength', 'Learning Rate', 'Open Trades']:
            hl = QHBoxLayout()
            lk = QLabel(key)
            lk.setStyleSheet('color:#8b949e; font-size:12px;')
            lv = QLabel('---')
            lv.setStyleSheet('color:#e6edf3; font-size:12px; font-weight:600;')
            lv.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            hl.addWidget(lk)
            hl.addStretch()
            hl.addWidget(lv)
            sv.addLayout(hl)
            self.signal_labels[key] = lv
        root.addWidget(status_group)
        root.addStretch()

    def _set_bar(self, bar, val_lbl, value):
        pct = int(min(max(float(value) * 100, 0), 100))
        bar.setValue(pct)
        val_lbl.setText(f'{float(value):.2f}')
        if pct >= 70:
            bar.setStyleSheet('QProgressBar::chunk { background-color: #3fb950; border-radius: 3px; }')
        elif pct >= 40:
            bar.setStyleSheet('QProgressBar::chunk { background-color: #58a6ff; border-radius: 3px; }')
        else:
            bar.setStyleSheet('QProgressBar::chunk { background-color: #d29922; border-radius: 3px; }')

    def update_state(self):
        d = self.orchestrator.get_light_diagnostics()
        state = self.orchestrator.get_state()

        self._set_bar(self.bar_expert, self.val_expert, d.get('ensemble_confidence', 0))
        self._set_bar(self.bar_esn, self.val_esn, d.get('esn_confidence', 0))
        self._set_bar(self.bar_bayesian, self.val_bayesian, d.get('bayesian_confidence', 0))
        self._set_bar(self.bar_predictive, self.val_predictive, d.get('predictive_confidence', 0))

        weights = d.get('meta_weights', [0, 0, 0, 0])
        if len(weights) >= 4:
            self._set_bar(self.bar_w_expert, self.val_w_expert, weights[0])
            self._set_bar(self.bar_w_esn, self.val_w_esn, weights[1])
            self._set_bar(self.bar_w_bayesian, self.val_w_bayesian, weights[2])
            self._set_bar(self.bar_w_predictive, self.val_w_predictive, weights[3])

        symbols = state.get('symbols', [])
        account = state.get('account', {})
        trade_stats = state.get('trade_stats', {})

        self.signal_labels['Active Symbols'].setText(', '.join(symbols) if symbols else '---')
        self.signal_labels['Current Regime'].setText('Analyzing...' if state.get('status') == 'running' else 'Idle')
        avg_conf = d.get('ensemble_confidence', 0)
        sig_color = '#3fb950' if avg_conf > 0.6 else '#d29922' if avg_conf > 0.3 else '#f85149'
        self.signal_labels['Signal Strength'].setText(f'<span style="color:{sig_color}">{avg_conf:.2%}</span>')
        self.signal_labels['Learning Rate'].setText(f"{self.orchestrator.config.get('risk_per_trade', 0.02):.2%}")
        self.signal_labels['Open Trades'].setText(str(account.get('open_positions_count', 0)))
