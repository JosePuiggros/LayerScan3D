"""3D Viewer widget using PyVista and PySide6."""

import os
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QToolBar, QSpacerItem, QSizePolicy
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal

try:
    import pyvista as pv
    from pyvistaqt import QtInteractor
except ImportError:
    pv = None
    QtInteractor = None

class Viewer3D(QWidget):
    """Interactive 3D viewer for comparing reconstructed and original meshes."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.reconstructed_mesh_actor = None
        self.reference_mesh_actor = None
        self.heatmap_actor = None
        
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        self.toolbar = QHBoxLayout()
        
        self.btn_reset = QPushButton("Reset Camera")
        self.btn_reset.clicked.connect(self.reset_camera)
        
        self.btn_toggle_recon = QPushButton("Toggle Reconstructed")
        self.btn_toggle_recon.setCheckable(True)
        self.btn_toggle_recon.setChecked(True)
        self.btn_toggle_recon.toggled.connect(self.toggle_reconstructed)
        
        self.btn_toggle_ref = QPushButton("Toggle Original STL")
        self.btn_toggle_ref.setCheckable(True)
        self.btn_toggle_ref.setChecked(True)
        self.btn_toggle_ref.toggled.connect(self.toggle_reference)
        
        self.toolbar.addWidget(self.btn_reset)
        self.toolbar.addWidget(self.btn_toggle_recon)
        self.toolbar.addWidget(self.btn_toggle_ref)
        self.toolbar.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        self.layout.addLayout(self.toolbar)
        
        # 3D Plotter
        if QtInteractor is not None:
            self.plotter = QtInteractor(self)
            self.plotter.set_background("#16213e")  # Dark theme background
            self.layout.addWidget(self.plotter.interactor)
        else:
            from PySide6.QtWidgets import QLabel
            lbl = QLabel("PyVista or PyVistaQt not installed.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(lbl)
            
    def load_meshes(self, reconstructed_trimesh, reference_trimesh=None):
        if self.plotter is None:
            return
            
        self.plotter.clear()
        self.reconstructed_mesh_actor = None
        self.reference_mesh_actor = None
        self.heatmap_actor = None
        
        if reconstructed_trimesh:
            # Convert trimesh to pyvista
            faces = np.column_stack((np.full(len(reconstructed_trimesh.faces), 3), reconstructed_trimesh.faces)).flatten()
            pv_mesh = pv.PolyData(reconstructed_trimesh.vertices, faces)
            self.reconstructed_mesh_actor = self.plotter.add_mesh(pv_mesh, color="#00d4aa", opacity=1.0, show_edges=False, name="reconstructed")
            
        if reference_trimesh:
            faces_ref = np.column_stack((np.full(len(reference_trimesh.faces), 3), reference_trimesh.faces)).flatten()
            pv_ref = pv.PolyData(reference_trimesh.vertices, faces_ref)
            self.reference_mesh_actor = self.plotter.add_mesh(pv_ref, color="#888888", style="wireframe", opacity=0.3, name="reference")
            
        self.plotter.reset_camera()
        
    def show_heatmap(self, reconstructed_trimesh, per_vertex_distances, cmap="jet"):
        if self.plotter is None or not reconstructed_trimesh:
            return
            
        self.plotter.clear()
        faces = np.column_stack((np.full(len(reconstructed_trimesh.faces), 3), reconstructed_trimesh.faces)).flatten()
        pv_mesh = pv.PolyData(reconstructed_trimesh.vertices, faces)
        
        # Add scalar data
        pv_mesh.point_data["Distance Error (mm)"] = per_vertex_distances
        
        self.heatmap_actor = self.plotter.add_mesh(
            pv_mesh, 
            scalars="Distance Error (mm)", 
            cmap=cmap, 
            show_scalar_bar=True,
            name="heatmap"
        )
        self.plotter.reset_camera()
        
    def reset_camera(self):
        if hasattr(self, 'plotter') and self.plotter:
            self.plotter.reset_camera()
            
    def toggle_reconstructed(self, checked):
        if self.reconstructed_mesh_actor and hasattr(self, 'plotter'):
            self.reconstructed_mesh_actor.SetVisibility(checked)
            self.plotter.update()
            
    def toggle_reference(self, checked):
        if self.reference_mesh_actor and hasattr(self, 'plotter'):
            self.reference_mesh_actor.SetVisibility(checked)
            self.plotter.update()
