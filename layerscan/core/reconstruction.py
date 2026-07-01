"""3D mesh reconstruction from stacked layer contours for LayerScan3D.

RF-07: Build a watertight 3D mesh by lofting between consecutive layer
contours, resampling point counts, and generating top/bottom caps.
Uses trimesh (not Open3D) for all mesh operations.
"""

from typing import List, Optional, Tuple

import numpy as np
import trimesh
from scipy.interpolate import interp1d
from scipy.spatial import Delaunay

from layerscan.core.contour_extraction import LayerContour
from layerscan.utils.logger import get_logger

logger = get_logger("core.reconstruction")


class MeshReconstructor:
    """Build a 3D triangle mesh from a stack of 2D layer contours.

    The reconstruction workflow:
        1. Sort contours by ascending Z height.
        2. Resample each contour to a uniform point count so that
           consecutive layers have matching vertex indices.
        3. Triangulate between consecutive layers using a triangle-strip
           pattern.
        4. Generate bottom and top cap faces via polygon triangulation.
        5. Combine everything into a single :class:`trimesh.Trimesh`.

    Args:
        target_points: Number of evenly-spaced points to resample each
            contour to.  Higher values give smoother meshes at the cost
            of more geometry.
        generate_caps: Whether to close the top and bottom of the mesh.
    """

    def __init__(
        self,
        target_points: int = 128,
        generate_caps: bool = True,
    ) -> None:
        if target_points < 4:
            raise ValueError("target_points must be at least 4.")
        self.target_points: int = target_points
        self.generate_caps: bool = generate_caps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reconstruct(
        self,
        layer_contours: List[LayerContour],
    ) -> trimesh.Trimesh:
        """Build a 3D mesh from a list of layer contours.

        Only the **outer contour** of each :class:`LayerContour` is used
        for the side-wall lofting.  Inner contours (holes) are not
        currently subtracted from the caps; full boolean-hole support
        would require CSG operations.

        Args:
            layer_contours: One :class:`LayerContour` per layer. If a
                layer produced multiple contours (disjoint pieces), pass
                the primary (largest-area) contour.

        Returns:
            A :class:`trimesh.Trimesh` object.

        Raises:
            ValueError: If fewer than 2 contours are provided.
        """
        if len(layer_contours) < 2:
            raise ValueError(
                "At least 2 layer contours are required for reconstruction."
            )

        # Sort by Z height
        sorted_contours = sorted(layer_contours, key=lambda c: c.z_height)
        logger.info(
            "Reconstructing mesh from %d layers (z: %.3f – %.3f mm).",
            len(sorted_contours),
            sorted_contours[0].z_height,
            sorted_contours[-1].z_height,
        )

        # Resample all contours to uniform point count
        resampled: list[np.ndarray] = []
        z_values: list[float] = []

        for lc in sorted_contours:
            pts_2d = lc.outer_contour  # Nx2
            if pts_2d.shape[0] < 3:
                logger.warning(
                    "Contour at z=%.3f has fewer than 3 points; skipping.",
                    lc.z_height,
                )
                continue
            resampled_2d = self._resample_contour(pts_2d, self.target_points)
            resampled.append(resampled_2d)
            z_values.append(lc.z_height)

        if len(resampled) < 2:
            raise ValueError(
                "Fewer than 2 valid contours remain after filtering."
            )

        # Build 3D vertex array: each resampled contour gets its Z
        all_vertices: list[np.ndarray] = []
        for pts_2d, z in zip(resampled, z_values):
            z_col = np.full((pts_2d.shape[0], 1), z)
            pts_3d = np.hstack([pts_2d, z_col])
            all_vertices.append(pts_3d)

        vertices = np.vstack(all_vertices)  # (N_layers * target_points, 3)
        n = self.target_points
        n_layers = len(resampled)

        # Triangulate side walls between consecutive layers
        faces = self._triangulate_sides(n_layers, n)

        # Generate caps
        if self.generate_caps:
            bottom_faces = self._triangulate_cap(resampled[0], offset=0, flip=True)
            top_offset = (n_layers - 1) * n
            top_faces = self._triangulate_cap(
                resampled[-1], offset=top_offset, flip=False
            )
            faces = np.vstack([faces, bottom_faces, top_faces])

        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)

        # Fix normals so they point outward
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

    # ------------------------------------------------------------------
    # Contour resampling
    # ------------------------------------------------------------------

    @staticmethod
    def _resample_contour(
        contour: np.ndarray,
        num_points: int,
    ) -> np.ndarray:
        """Resample a 2D contour to exactly *num_points* evenly-spaced
        vertices along its perimeter.

        The contour is treated as a closed polygon: the last point is
        connected back to the first.

        Args:
            contour: Nx2 array of 2D points.
            num_points: Desired output vertex count.

        Returns:
            ``num_points × 2`` array of resampled coordinates.
        """
        # Close the contour by appending the first point
        pts = np.vstack([contour, contour[0:1]])

        # Cumulative arc-length parameter
        diffs = np.diff(pts, axis=0)
        segment_lengths = np.sqrt((diffs ** 2).sum(axis=1))
        cum_len = np.concatenate([[0.0], np.cumsum(segment_lengths)])
        total_len = cum_len[-1]

        if total_len == 0:
            # Degenerate contour – all points coincide
            return np.tile(contour[0], (num_points, 1))

        # Normalise to [0, 1]
        t = cum_len / total_len

        # Interpolate X and Y independently
        fx = interp1d(t, pts[:, 0], kind="linear")
        fy = interp1d(t, pts[:, 1], kind="linear")

        # Evenly spaced parameter (exclude endpoint == start for closed)
        t_new = np.linspace(0.0, 1.0, num_points, endpoint=False)
        x_new = fx(t_new)
        y_new = fy(t_new)

        return np.column_stack([x_new, y_new])

    # ------------------------------------------------------------------
    # Side-wall triangulation
    # ------------------------------------------------------------------

    @staticmethod
    def _triangulate_sides(
        n_layers: int,
        n_points: int,
    ) -> np.ndarray:
        """Create triangle-strip faces connecting consecutive contour
        rings.

        For two adjacent layers with vertex indices ``[base …
        base+n-1]`` and ``[base+n … base+2n-1]``, a quad strip is
        decomposed into two triangles per quad.

        Args:
            n_layers: Number of contour layers.
            n_points: Number of vertices per contour ring.

        Returns:
            ``(F, 3)`` integer array of face indices.
        """
        faces: list[list[int]] = []

        for layer_idx in range(n_layers - 1):
            base_lo = layer_idx * n_points
            base_hi = (layer_idx + 1) * n_points

            for i in range(n_points):
                i_next = (i + 1) % n_points

                v0 = base_lo + i
                v1 = base_lo + i_next
                v2 = base_hi + i_next
                v3 = base_hi + i

                # Two triangles per quad
                faces.append([v0, v1, v2])
                faces.append([v0, v2, v3])

        return np.array(faces, dtype=np.int64)

    # ------------------------------------------------------------------
    # Cap triangulation
    # ------------------------------------------------------------------

    @staticmethod
    def _triangulate_cap(
        contour_2d: np.ndarray,
        offset: int,
        flip: bool = False,
    ) -> np.ndarray:
        """Triangulate a flat polygon (cap) using Delaunay triangulation
        and filter to keep only interior triangles.

        Args:
            contour_2d: Nx2 array of the cap polygon vertices.
            offset: Vertex index offset in the global vertex array.
            flip: If ``True``, reverse the triangle winding order (used
                for the bottom cap so normals face downward/outward).

        Returns:
            ``(F, 3)`` integer array of face indices (with *offset*
            applied).
        """
        n = contour_2d.shape[0]
        if n < 3:
            return np.empty((0, 3), dtype=np.int64)

        try:
            # Ear-clipping via trimesh is the most reliable for
            # arbitrary simple polygons.  Fall back to Delaunay if it
            # fails.
            from trimesh.creation import triangulate_polygon
            from shapely.geometry import Polygon as ShapelyPolygon

            poly = ShapelyPolygon(contour_2d)
            if poly.is_valid:
                verts, faces = trimesh.creation.triangulate_polygon(
                    poly, engine=None
                )
                # Map the returned vertex indices back to the global
                # vertex buffer.  trimesh.creation.triangulate_polygon
                # may return new vertices; we need to map to the
                # closest original index.
                if len(faces) > 0:
                    from scipy.spatial import cKDTree

                    tree = cKDTree(contour_2d)
                    _, idx_map = tree.query(verts)
                    mapped_faces = idx_map[faces] + offset
                    if flip:
                        mapped_faces = mapped_faces[:, ::-1]
                    return mapped_faces.astype(np.int64)
        except Exception:
            pass

        # Fallback: Delaunay triangulation filtered to polygon interior
        return MeshReconstructor._delaunay_cap(contour_2d, offset, flip)

    @staticmethod
    def _delaunay_cap(
        contour_2d: np.ndarray,
        offset: int,
        flip: bool,
    ) -> np.ndarray:
        """Delaunay-based cap triangulation with interior filtering.

        All Delaunay triangles whose centroid lies inside the polygon
        (tested via OpenCV ``pointPolygonTest``) are kept.

        Args:
            contour_2d: Nx2 polygon vertices.
            offset: Global vertex index offset.
            flip: Reverse winding if True.

        Returns:
            Face index array ``(F, 3)``.
        """
        import cv2

        n = contour_2d.shape[0]
        if n < 3:
            return np.empty((0, 3), dtype=np.int64)

        try:
            tri = Delaunay(contour_2d)
        except Exception as exc:
            logger.warning("Delaunay triangulation failed: %s", exc)
            return np.empty((0, 3), dtype=np.int64)

        # Build an OpenCV-compatible contour for point-in-polygon test
        cv_contour = contour_2d.reshape(-1, 1, 2).astype(np.float32)

        valid_faces: list[list[int]] = []
        for simplex in tri.simplices:
            centroid = contour_2d[simplex].mean(axis=0)
            dist = cv2.pointPolygonTest(
                cv_contour, (float(centroid[0]), float(centroid[1])), False
            )
            if dist >= 0:
                face = [s + offset for s in simplex]
                if flip:
                    face = face[::-1]
                valid_faces.append(face)

        if not valid_faces:
            return np.empty((0, 3), dtype=np.int64)

        return np.array(valid_faces, dtype=np.int64)
