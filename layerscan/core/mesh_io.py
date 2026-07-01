"""Mesh Import/Export operations for LayerScan3D.

RF-08, RF-10: Import/export meshes (STL/OBJ/PLY) using trimesh.
Validate meshes and compute basic metadata.
"""

import os
from dataclasses import dataclass
from typing import Tuple

import numpy as np
import trimesh

from layerscan.utils.logger import get_logger

logger = get_logger("core.mesh_io")

@dataclass
class MeshInfo:
    """Metadata about a loaded 3D mesh."""
    bounds: Tuple[np.ndarray, np.ndarray]
    volume: float
    surface_area: float
    center_of_mass: np.ndarray
    vertex_count: int
    face_count: int
    is_watertight: bool

class MeshIO:
    """Utility class for loading, saving, and analyzing 3D meshes."""

    @staticmethod
    def load_mesh(filepath: str) -> trimesh.Trimesh:
        """
        Load a mesh from a file (STL, OBJ, PLY).
        
        Args:
            filepath: Path to the mesh file.
            
        Returns:
            A trimesh.Trimesh object.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Mesh file not found: {filepath}")
            
        logger.info(f"Loading mesh from {filepath}")
        # load can sometimes return a Scene, force it to return a Trimesh
        mesh = trimesh.load(filepath, force='mesh')
        
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError(f"Failed to load a valid Trimesh from {filepath}")
            
        logger.info(f"Loaded mesh with {len(mesh.vertices)} vertices and {len(mesh.faces)} faces.")
        return mesh

    @staticmethod
    def save_mesh(mesh: trimesh.Trimesh, filepath: str) -> None:
        """
        Export a mesh to a file. Format is inferred from the extension.
        
        Args:
            mesh: The trimesh.Trimesh object to save.
            filepath: Destination path (e.g., output.stl, output.obj).
        """
        logger.info(f"Saving mesh to {filepath}")
        mesh.export(filepath)
        logger.info("Mesh saved successfully.")

    @staticmethod
    def get_mesh_info(mesh: trimesh.Trimesh) -> MeshInfo:
        """
        Compute and return metadata for a mesh.
        
        Args:
            mesh: The trimesh.Trimesh object to analyze.
            
        Returns:
            MeshInfo dataclass with the computed metadata.
        """
        # Ensure properties are computed
        return MeshInfo(
            bounds=mesh.bounds,
            volume=mesh.volume if mesh.is_volume else 0.0,
            surface_area=mesh.area,
            center_of_mass=mesh.center_mass,
            vertex_count=len(mesh.vertices),
            face_count=len(mesh.faces),
            is_watertight=mesh.is_watertight
        )
