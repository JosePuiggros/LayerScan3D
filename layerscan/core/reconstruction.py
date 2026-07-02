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
        1. Compute a global bounding box across all masks and crop to that
           region (with a small padding margin). This dramatically reduces
           the volume size for images where the piece is small relative to
           the full frame.
        2. Stack the cropped masks into a 3D NumPy volume.
        3. Run Marching Cubes at full resolution (step_size=1) to extract
           the isosurface with maximum detail.
        4. Convert voxel coordinates back to physical mm, accounting for
           the crop offset.
        5. Return a watertight trimesh.Trimesh object.

    Args:
        level: The intensity value at which to extract the surface.
            Since masks are 0 (bg) and 255 (fg), a level of 127.5 is standard.
        step_size: Marching cubes step size. 1 = full resolution.
    """

    def __init__(self, level: float = 127.5, step_size: int = 1) -> None:
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

        # 1. Compute global bounding box across all masks
        global_ymin, global_ymax = sorted_masks[0].shape[0], 0
        global_xmin, global_xmax = sorted_masks[0].shape[1], 0
        
        for m in sorted_masks:
            ys, xs = np.where(m > 0)
            if len(xs) > 0:
                global_xmin = min(global_xmin, int(xs.min()))
                global_xmax = max(global_xmax, int(xs.max()))
                global_ymin = min(global_ymin, int(ys.min()))
                global_ymax = max(global_ymax, int(ys.max()))
        
        # Add padding (10 pixels) to ensure marching cubes closes properly
        pad = 10
        h, w = sorted_masks[0].shape[:2]
        global_ymin = max(0, global_ymin - pad)
        global_ymax = min(h - 1, global_ymax + pad)
        global_xmin = max(0, global_xmin - pad)
        global_xmax = min(w - 1, global_xmax + pad)
        
        crop_h = global_ymax - global_ymin + 1
        crop_w = global_xmax - global_xmin + 1
        
        logger.info(
            "Cropping masks to bounding box: X=[%d,%d], Y=[%d,%d] (%dx%d px, "
            "%.1f%% of original %dx%d).",
            global_xmin, global_xmax, global_ymin, global_ymax,
            crop_w, crop_h,
            100.0 * crop_w * crop_h / (w * h),
            w, h,
        )

        # 2. Crop and stack masks into a 3D volume (Z, Y, X)
        cropped_masks = [m[global_ymin:global_ymax+1, global_xmin:global_xmax+1] for m in sorted_masks]
        
        # Pad with empty layers on top and bottom to ensure the mesh closes
        empty_layer = np.zeros((crop_h, crop_w), dtype=np.uint8)
        volume = np.stack([empty_layer] + cropped_masks + [empty_layer])
        
        logger.info(
            "Volume shape: %s (%.1f MB)",
            volume.shape,
            volume.nbytes / 1e6,
        )
        
        # Extend z_heights array to match the padded volume
        avg_thickness = (sorted_z[-1] - sorted_z[0]) / max(1, len(sorted_z) - 1)
        z_array = np.concatenate([
            [sorted_z[0] - avg_thickness], 
            sorted_z, 
            [sorted_z[-1] + avg_thickness]
        ])

        # 3. Run Marching Cubes
        logger.info("Running marching cubes with step_size=%d...", self.step_size)
        verts_voxel, faces, normals, _ = measure.marching_cubes(
            volume, level=self.level, step_size=self.step_size
        )
        
        if len(verts_voxel) == 0:
            raise ValueError("Marching cubes could not extract any surface.")

        # 4. Convert voxel coordinates to physical coordinates
        # verts_voxel columns are (Z_idx, Y_idx, X_idx) in the CROPPED volume.
        # We must add the crop offset back to get original image pixel coords.
        z_idx = verts_voxel[:, 0]
        y_idx = verts_voxel[:, 1] + global_ymin  # add crop offset
        x_idx = verts_voxel[:, 2] + global_xmin  # add crop offset
        
        # X and Y are pixel-to-mm conversions
        x_mm = x_idx * scale_mm_per_px
        y_mm = y_idx * scale_mm_per_px
        
        # Z is interpolated based on the floating-point voxel index
        z_mm = np.interp(z_idx, np.arange(len(z_array)), z_array)
        
        vertices = np.column_stack([x_mm, y_mm, z_mm])

        # 5. Create Trimesh
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
