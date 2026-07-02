"""3D mesh reconstruction from stacked layer contours for LayerScan3D.

RF-07: Build a watertight 3D mesh by lofting between consecutive layer
masks using voxel-based Marching Cubes, which perfectly handles complex
topologies (like Gyroids) with multiple disconnected islands and holes.
"""

from typing import List

import numpy as np
import trimesh
from skimage import measure

from layerscan.utils.logger import get_logger

logger = get_logger("core.reconstruction")


class MeshReconstructor:
    """Build a 3D triangle mesh from a stack of 2D binary masks.

    The reconstruction workflow:
        1. Stack all 2D binary masks into a 3D NumPy volume.
        2. Run Marching Cubes to extract the isosurface.
        3. Convert the voxel coordinates to physical mm coordinates using
           the calibration scale for X/Y and the actual z_heights for Z.
        4. Return a watertight trimesh.Trimesh object.

    Args:
        level: The intensity value at which to extract the surface.
            Since masks are 0 (bg) and 255 (fg), a level of 127 is standard.
    """

    def __init__(self, level: float = 127.5, step_size: int = 4) -> None:
        self.level: float = level
        self.step_size: int = step_size

    def reconstruct(
        self,
        masks: List[np.ndarray],
        z_heights: List[float],
        scale_mm_per_px: float,
    ) -> trimesh.Trimesh:
        """Build a 3D mesh from a sequence of binary masks.

        Args:
            masks: List of 2D binary masks (uint8).
            z_heights: List of Z heights (mm) corresponding to each mask.
            scale_mm_per_px: Calibration scale to convert X,Y pixels to mm.

        Returns:
            A watertight :class:`trimesh.Trimesh` object.

        Raises:
            ValueError: If fewer than 2 masks are provided.
        """
        if len(masks) < 2:
            raise ValueError(
                "At least 2 layers are required for reconstruction."
            )
            
        if len(masks) != len(z_heights):
            raise ValueError(
                "Number of masks must equal number of z_heights."
            )

        # Sort masks and z_heights by z_height ascending
        sorted_pairs = sorted(zip(z_heights, masks), key=lambda x: x[0])
        sorted_z = np.array([p[0] for p in sorted_pairs])
        sorted_masks = [p[1] for p in sorted_pairs]
        
        logger.info(
            "Reconstructing mesh from %d layers (z: %.3f – %.3f mm).",
            len(sorted_masks),
            sorted_z[0],
            sorted_z[-1],
        )

        # 1. Stack masks into a 3D volume (Z, Y, X)
        # Pad with empty layers on top and bottom to ensure the mesh closes natively
        empty_layer = np.zeros_like(sorted_masks[0])
        volume = np.stack([empty_layer] + sorted_masks + [empty_layer])
        
        # Extend z_heights array to match the padded volume
        # We extrapolate the top and bottom Z by the average layer thickness
        avg_thickness = (sorted_z[-1] - sorted_z[0]) / max(1, len(sorted_z) - 1)
        z_array = np.concatenate([
            [sorted_z[0] - avg_thickness], 
            sorted_z, 
            [sorted_z[-1] + avg_thickness]
        ])

        # 2. Run Marching Cubes
        # step_size downsamples the volume to save memory. 
        # step_size=4 reduces resolution by 64x and prevents OOM on large images.
        logger.debug("Running marching cubes on volume of shape %s with step_size %d", volume.shape, self.step_size)
        verts_voxel, faces, normals, _ = measure.marching_cubes(
            volume, level=self.level, step_size=self.step_size
        )
        
        if len(verts_voxel) == 0:
            raise ValueError("Marching cubes could not extract any surface.")

        # 3. Convert voxel coordinates to physical coordinates
        # verts_voxel is returned as (Z, Y, X)
        z_idx = verts_voxel[:, 0]
        y_idx = verts_voxel[:, 1]
        x_idx = verts_voxel[:, 2]
        
        # X and Y are straight pixel-to-mm conversions
        x_mm = x_idx * scale_mm_per_px
        y_mm = y_idx * scale_mm_per_px
        
        # Z is interpolated based on the floating-point voxel index
        # np.interp expects strictly increasing x coordinates
        z_mm = np.interp(z_idx, np.arange(len(z_array)), z_array)
        
        vertices = np.column_stack([x_mm, y_mm, z_mm])

        # 4. Create Trimesh
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, vertex_normals=normals, process=True)
        
        # Ensure normals point outward
        mesh.fix_normals()

        logger.info(
            "Mesh reconstructed: %d vertices, %d faces, "
            "watertight=%s, volume=%.2f mm³.",
            len(mesh.vertices),
            len(mesh.faces),
            mesh.is_watertight,
            mesh.volume if mesh.is_watertight else float("nan"),
        )

        return mesh
