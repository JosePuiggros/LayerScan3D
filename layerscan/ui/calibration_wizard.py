"""Wizard for camera calibration."""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWizard, QWizardPage, QLineEdit, 
                             QFileDialog, QRadioButton, QDoubleSpinBox)

class CalibrationWizard(QWizard):
    """Wizard to guide user through camera calibration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camera Calibration Wizard")
        self.setMinimumSize(600, 400)
        
        self.addPage(self.create_intro_page())
        self.addPage(self.create_method_page())
        self.addPage(self.create_save_page())
        
    def create_intro_page(self):
        page = QWizardPage()
        page.setTitle("Welcome to Calibration")
        layout = QVBoxLayout(page)
        lbl = QLabel("This wizard will help you calibrate your camera scale (mm per pixel).")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        return page
        
    def create_method_page(self):
        page = QWizardPage()
        page.setTitle("Calibration Method")
        layout = QVBoxLayout(page)
        
        self.radio_manual = QRadioButton("Manual Scale (Enter mm/px directly)")
        self.radio_manual.setChecked(True)
        
        self.input_scale = QDoubleSpinBox()
        self.input_scale.setDecimals(4)
        self.input_scale.setSingleStep(0.01)
        self.input_scale.setValue(0.1)
        self.input_scale.setSuffix(" mm/px")
        
        layout.addWidget(self.radio_manual)
        layout.addWidget(self.input_scale)
        return page
        
    def create_save_page(self):
        page = QWizardPage()
        page.setTitle("Save Profile")
        layout = QVBoxLayout(page)
        
        layout.addWidget(QLabel("Profile Name:"))
        self.input_name = QLineEdit("My_Printer_Profile")
        layout.addWidget(self.input_name)
        
        return page
        
    def get_profile_data(self):
        """Returns the data gathered from the wizard to create a CalibrationProfile."""
        return {
            "name": self.input_name.text(),
            "scale": self.input_scale.value()
        }
