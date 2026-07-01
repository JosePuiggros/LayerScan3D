"""Import panel for selecting input files and images."""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QFileDialog, QDoubleSpinBox, QGroupBox)
from PySide6.QtCore import Signal
from pathlib import Path

class ImportPanel(QWidget):
    """Panel for configuring project inputs."""
    
    start_processing = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # Images section
        group_img = QGroupBox("1. Input Images (Z-Stack)")
        l_img = QHBoxLayout()
        self.txt_images = QLineEdit()
        self.txt_images.setReadOnly(True)
        self.btn_images = QPushButton("Browse...")
        self.btn_images.clicked.connect(self.browse_images)
        l_img.addWidget(self.txt_images)
        l_img.addWidget(self.btn_images)
        group_img.setLayout(l_img)
        self.layout.addWidget(group_img)
        
        # STL section
        group_stl = QGroupBox("2. Reference Model (STL/OBJ)")
        l_stl = QHBoxLayout()
        self.txt_stl = QLineEdit()
        self.txt_stl.setReadOnly(True)
        self.btn_stl = QPushButton("Browse...")
        self.btn_stl.clicked.connect(self.browse_stl)
        l_stl.addWidget(self.txt_stl)
        l_stl.addWidget(self.btn_stl)
        group_stl.setLayout(l_stl)
        self.layout.addWidget(group_stl)
        
        # GCode section
        group_gcode = QGroupBox("3. G-Code File (Optional)")
        l_gcode = QHBoxLayout()
        self.txt_gcode = QLineEdit()
        self.txt_gcode.setReadOnly(True)
        self.btn_gcode = QPushButton("Browse...")
        self.btn_gcode.clicked.connect(self.browse_gcode)
        l_gcode.addWidget(self.txt_gcode)
        l_gcode.addWidget(self.btn_gcode)
        group_gcode.setLayout(l_gcode)
        self.layout.addWidget(group_gcode)
        
        # Settings section
        group_set = QGroupBox("4. Print Settings")
        l_set = QHBoxLayout()
        l_set.addWidget(QLabel("Default Layer Height:"))
        self.spin_layer = QDoubleSpinBox()
        self.spin_layer.setDecimals(3)
        self.spin_layer.setSingleStep(0.04)
        self.spin_layer.setValue(0.2)
        self.spin_layer.setSuffix(" mm")
        l_set.addWidget(self.spin_layer)
        l_set.addStretch()
        group_set.setLayout(l_set)
        self.layout.addWidget(group_set)
        
        self.layout.addStretch()
        
        # Action button
        self.btn_start = QPushButton("Start Processing")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.setStyleSheet("background-color: #00d4aa; color: black; font-weight: bold; border-radius: 5px;")
        self.btn_start.clicked.connect(self.emit_start)
        self.layout.addWidget(self.btn_start)
        
    def browse_images(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with Layer Images")
        if folder:
            self.txt_images.setText(folder)
            
    def browse_stl(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select STL File", "", "3D Meshes (*.stl *.obj *.ply)")
        if file:
            self.txt_stl.setText(file)
            
    def browse_gcode(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select G-Code File", "", "G-Code (*.gcode *.gco)")
        if file:
            self.txt_gcode.setText(file)
            
    def emit_start(self):
        config_data = {
            "images_dir": self.txt_images.text(),
            "stl_file": self.txt_stl.text(),
            "gcode_file": self.txt_gcode.text(),
            "layer_height_mm": self.spin_layer.value()
        }
        self.start_processing.emit(config_data)
