from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt

class BrainMonitorWidget(QWidget):
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.status_label.setWordWrap(True)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Component', 'Metric', 'Value'])
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.table)

    def update_state(self):
        diagnostics = self.orchestrator.get_light_diagnostics()
        self.status_label.setText('Brain monitor (live)')
        values = []
        values.append(('Experts', 'ensemble_confidence', f"{diagnostics.get('ensemble_confidence',0):.2f}"))
        values.append(('ESN', 'esn_confidence', f"{diagnostics.get('esn_confidence',0):.2f}"))
        values.append(('Bayesian', 'bayesian_confidence', f"{diagnostics.get('bayesian_confidence',0):.2f}"))
        values.append(('Predictive', 'predictive_confidence', f"{diagnostics.get('predictive_confidence',0):.2f}"))
        meta = diagnostics.get('meta_weights', [])
        if meta and len(meta) >= 4:
            values.append(('Meta', 'expert_weight', f"{meta[0]:.2f}"))
            values.append(('Meta', 'esn_weight', f"{meta[1]:.2f}"))
            values.append(('Meta', 'bayesian_weight', f"{meta[2]:.2f}"))
            values.append(('Meta', 'predictive_weight', f"{meta[3]:.2f}"))
        self.table.setRowCount(len(values))
        for row, item in enumerate(values):
            self.table.setItem(row, 0, QTableWidgetItem(item[0]))
            self.table.setItem(row, 1, QTableWidgetItem(item[1]))
            self.table.setItem(row, 2, QTableWidgetItem(item[2]))
        self.table.resizeColumnsToContents()
