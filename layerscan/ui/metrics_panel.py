"""Metrics panel displaying quality scores and anomaly reports."""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QFrame)
from PySide6.QtCore import Qt

class MetricsPanel(QWidget):
    """Panel to display comparison metrics and anomalies."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # Top Row: Score Cards
        self.cards_layout = QHBoxLayout()
        
        self.lbl_score = self._create_card("Quality Score", "N/A", "#00d4aa")
        self.lbl_mean_err = self._create_card("Mean Error", "N/A mm", "#ffffff")
        self.lbl_max_err = self._create_card("Max Error", "N/A mm", "#ffffff")
        self.lbl_tolerance = self._create_card("In Tolerance", "N/A %", "#0ea5e9")
        
        self.cards_layout.addWidget(self.lbl_score)
        self.cards_layout.addWidget(self.lbl_mean_err)
        self.cards_layout.addWidget(self.lbl_max_err)
        self.cards_layout.addWidget(self.lbl_tolerance)
        
        self.layout.addLayout(self.cards_layout)
        
        # Anomalies Table
        self.layout.addWidget(QLabel("<b>Detected Anomalies</b>"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Layer", "Type", "Severity", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.table)
        
        # Limitations note
        note = QLabel("<i>Note: Variations detected via a single zenith camera setup are approximations of volumetric defects.</i>")
        note.setStyleSheet("color: #888888;")
        self.layout.addWidget(note)
        
    def _create_card(self, title, initial_value, color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #16213e;
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        layout = QVBoxLayout(frame)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #aaaaaa; font-weight: bold;")
        
        val_lbl = QLabel(initial_value)
        val_lbl.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title_lbl)
        layout.addWidget(val_lbl)
        
        # We store the value label reference as a dynamic property to update it later
        frame.val_lbl = val_lbl
        return frame
        
    def update_metrics(self, pipeline_result):
        """Update UI with results from PipelineResult."""
        if pipeline_result.quality:
            q = pipeline_result.quality
            self.lbl_score.val_lbl.setText(f"{q.overall_score:.1f}")
            self.lbl_score.val_lbl.setStyleSheet(f"color: {q.grade_color}; font-size: 24px; font-weight: bold;")
            
        if pipeline_result.comparison:
            comp = pipeline_result.comparison
            stats = comp.global_stats
            if stats:
                self.lbl_mean_err.val_lbl.setText(f"{stats.get('mean_error', 0):.3f} mm")
                self.lbl_max_err.val_lbl.setText(f"{stats.get('max_error', 0):.3f} mm")
            self.lbl_tolerance.val_lbl.setText(f"{comp.points_within_tolerance_pct:.1f} %")
            
        if pipeline_result.anomalies:
            anoms = pipeline_result.anomalies.anomalies
            self.table.setRowCount(len(anoms))
            for i, a in enumerate(anoms):
                self.table.setItem(i, 0, QTableWidgetItem(str(a.layer_number)))
                self.table.setItem(i, 1, QTableWidgetItem(a.anomaly_type))
                
                sev_item = QTableWidgetItem(a.severity.upper())
                if a.severity == 'critical':
                    sev_item.setForeground(Qt.GlobalColor.red)
                elif a.severity == 'warning':
                    sev_item.setForeground(Qt.GlobalColor.yellow)
                self.table.setItem(i, 2, sev_item)
                
                self.table.setItem(i, 3, QTableWidgetItem(a.description))
