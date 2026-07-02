"""Main Application Window for LayerScan3D."""

import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QStackedWidget, QListWidget, QLabel, QProgressBar)
from PySide6.QtCore import Qt

from layerscan.ui.import_panel import ImportPanel
from layerscan.ui.viewer_3d import Viewer3D
from layerscan.ui.metrics_panel import MetricsPanel
from layerscan.ui.worker_threads import PipelineWorker
from layerscan.utils.config import Config, ProjectConfig

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LayerScan 3D — Verificación Dimensional")
        self.setMinimumSize(1200, 800)
        
        self.app_config = Config()
        self.project_config = ProjectConfig(os.path.join(os.path.expanduser("~"), ".layerscan3d", "projects", "default"))
        
        self.setup_ui()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("background-color: #1a1a2e; border-right: 1px solid #333;")
        sidebar_layout = QVBoxLayout(sidebar)
        
        title = QLabel("LayerScan 3D")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #00d4aa; padding: 20px 10px;")
        sidebar_layout.addWidget(title)
        
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { padding: 15px; color: #aaaaaa; font-size: 16px; border-radius: 5px; margin: 5px; }
            QListWidget::item:selected { background: #16213e; color: #00d4aa; font-weight: bold; }
        """)
        self.nav_list.addItems(["1. Configuración", "2. Procesamiento", "3. Visor 3D", "4. Métricas"])
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self.change_page)
        sidebar_layout.addWidget(self.nav_list)
        
        main_layout.addWidget(sidebar)
        
        # Main Content Area
        content_area = QWidget()
        content_area.setStyleSheet("background-color: #0f172a;")
        content_layout = QVBoxLayout(content_area)
        
        self.stack = QStackedWidget()
        
        # Page 1: Import
        self.import_panel = ImportPanel()
        self.import_panel.start_processing.connect(self.start_processing)
        self.stack.addWidget(self.import_panel)
        
        # Page 2: Processing
        self.page_proc = QWidget()
        l_proc = QVBoxLayout(self.page_proc)
        self.lbl_proc_status = QLabel("Ready to process...")
        self.lbl_proc_status.setStyleSheet("font-size: 18px; color: white;")
        self.lbl_proc_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("QProgressBar { border: 1px solid #333; border-radius: 5px; text-align: center; } QProgressBar::chunk { background-color: #00d4aa; }")
        l_proc.addStretch()
        l_proc.addWidget(self.lbl_proc_status)
        l_proc.addWidget(self.progress_bar)
        l_proc.addStretch()
        self.stack.addWidget(self.page_proc)
        
        # Page 3: 3D Viewer
        self.viewer_3d = Viewer3D()
        self.stack.addWidget(self.viewer_3d)
        
        # Page 4: Metrics
        self.metrics_panel = MetricsPanel()
        self.stack.addWidget(self.metrics_panel)
        
        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_area)
        
    def change_page(self, index):
        self.stack.setCurrentIndex(index)
        
    def start_processing(self, config_data):
        self.project_config.data.update(config_data)
        
        self.nav_list.setCurrentRow(1)
        self.lbl_proc_status.setText("Initializing pipeline...")
        self.progress_bar.setValue(0)
        
        from layerscan.core.pipeline import ProcessingPipeline
        pipeline = ProcessingPipeline(self.project_config, self.app_config)
        self.worker = PipelineWorker(pipeline, self)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.processing_finished)
        self.worker.start()
        
    def update_progress(self, val, msg):
        self.progress_bar.setValue(int(val))
        self.lbl_proc_status.setText(msg)
        
    def processing_finished(self, result):
        if result.error:
            self.lbl_proc_status.setText(f"Error: {result.error}")
            self.lbl_proc_status.setStyleSheet("font-size: 18px; color: #ff4444;")
        else:
            self.lbl_proc_status.setText("Processing complete!")
            
            # Update Viewer
            self.viewer_3d.load_meshes(result.reconstructed_mesh, result.reference_mesh)
            if result.comparison and result.comparison.per_vertex_distances is not None:
                self.viewer_3d.show_heatmap(result.reconstructed_mesh, result.comparison.per_vertex_distances)
                
            # Update Metrics
            self.metrics_panel.update_metrics(result)
            
            # Switch to Viewer
            self.nav_list.setCurrentRow(2)
