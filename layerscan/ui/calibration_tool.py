"""Interactive visual calibration tool."""

import math
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                             QGraphicsLineItem, QInputDialog, QMessageBox)
from PySide6.QtGui import QPixmap, QPen, QColor, QPainter
from PySide6.QtCore import Qt, QPointF

class ImageGraphicsView(QGraphicsView):
    """Custom GraphicsView to handle mouse events for drawing a calibration line."""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        self.drawing = False
        self.start_point = None
        self.current_line = None
        
        # Pen for drawing the line
        self.pen = QPen(QColor(0, 255, 255)) # Cyan
        self.pen.setWidth(3)
        self.pen.setCosmetic(True) # Keeps line width constant when zooming
        
        self.parent_dialog = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.start_point = self.mapToScene(event.position().toPoint())
            
            if self.current_line:
                self.scene().removeItem(self.current_line)
                
            self.current_line = QGraphicsLineItem(
                self.start_point.x(), self.start_point.y(),
                self.start_point.x(), self.start_point.y()
            )
            self.current_line.setPen(self.pen)
            self.scene().addItem(self.current_line)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing and self.current_line:
            end_point = self.mapToScene(event.position().toPoint())
            self.current_line.setLine(
                self.start_point.x(), self.start_point.y(),
                end_point.x(), end_point.y()
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            end_point = self.mapToScene(event.position().toPoint())
            
            if self.current_line:
                self.current_line.setLine(
                    self.start_point.x(), self.start_point.y(),
                    end_point.x(), end_point.y()
                )
                
                # Calculate pixel distance
                dx = end_point.x() - self.start_point.x()
                dy = end_point.y() - self.start_point.y()
                distance_px = math.sqrt(dx*dx + dy*dy)
                
                if distance_px < 5:
                    self.scene().removeItem(self.current_line)
                    self.current_line = None
                    return
                
                if self.parent_dialog:
                    self.parent_dialog.on_line_drawn(distance_px)
                    
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """Enable zooming with mouse wheel."""
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
            
        self.scale(zoom_factor, zoom_factor)


class ManualCalibrationDialog(QDialog):
    """Dialog to allow the user to draw a line on an image to calibrate scale."""
    
    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Calibration Tool")
        self.setMinimumSize(1000, 700)
        
        self.calculated_scale = None
        self.image_path = image_path
        
        self.setup_ui()
        self.load_image()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        lbl_inst = QLabel(
            "<b>Instructions:</b><br>"
            "1. Use the mouse wheel to zoom in/out if needed.<br>"
            "2. Click and drag on the image to draw a line over a known physical feature (like a printed scale or piece width).<br>"
            "3. Release the mouse and enter the physical length in mm to compute the scale."
        )
        lbl_inst.setStyleSheet("font-size: 14px; padding: 10px; background-color: #16213e; border-radius: 5px;")
        lbl_inst.setWordWrap(True)
        layout.addWidget(lbl_inst)
        
        # Graphics View
        self.scene = QGraphicsScene(self)
        self.view = ImageGraphicsView(self.scene, parent=self)
        self.view.setStyleSheet("background-color: #0f172a;")
        layout.addWidget(self.view)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
    def load_image(self):
        pixmap = QPixmap(self.image_path)
        if pixmap.isNull():
            QMessageBox.critical(self, "Error", f"Failed to load image: {self.image_path}")
            self.reject()
            return
            
        self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(pixmap.rect())
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        
    def on_line_drawn(self, distance_px: float):
        """Called by ImageGraphicsView when the user finishes drawing a line."""
        val, ok = QInputDialog.getDouble(
            self, 
            "Enter Physical Length", 
            f"Line is {distance_px:.1f} pixels long.\nWhat is this length in millimeters (mm)?", 
            10.0, 0.01, 10000.0, 3
        )
        
        if ok and val > 0:
            self.calculated_scale = val / distance_px
            QMessageBox.information(
                self, 
                "Calibration Success", 
                f"Calculated scale: <b>{self.calculated_scale:.5f} mm/px</b>"
            )
            self.accept()
        else:
            # If user cancelled, remove the line
            if self.view.current_line:
                self.scene.removeItem(self.view.current_line)
                self.view.current_line = None
