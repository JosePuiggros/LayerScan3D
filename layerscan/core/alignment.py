"""Model alignment using Iterative Closest Point (ICP) algorithm.

RF-12: Align a reconstructed mesh with the original reference model.
Uses scipy.spatial.KDTree for efficient nearest-neighbor queries and
operates primarily in the XY plane (Z is known/fixed from layer data).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.spatial import KDTree
import trimesh

from layerscan.utils.logger import get_logger

logger = get_logger("core.alignment")


@dataclass
class AlignmentResult:
    """Result of an ICP alignment between two meshes.

    Attributes:
        transformation_matrix: 4x4 homogeneous transformation matrix that
            maps source points to target space.
        rotation_angle_deg: Rotation angle around the Z axis (degrees).
        translation_xy: Translation vector in the XY plane [tx, ty] (mm).
        mean_error: Mean point-to-point distance after alignment (mm).
        converged: True if ICP converged within tolerance before reaching
            the maximum number of iterations.
        iterations: Number of iterations performed.
        error_history: List of mean errors at each iteration for diagnostics.
    """

    transformation_matrix: np.ndarray = field(
        default_factory=lambda: np.eye(4)
    )
    rotation_angle_deg: float = 0.0
    translation_xy: np.ndarray = field(
        default_factory=lambda: np.zeros(2)
    )
    mean_error: float = float("inf")
    converged: bool = False
    iterations: int = 0
    error_history: list[float] = field(default_factory=list)


class ModelAligner:
    """Aligns a source mesh to a target mesh using ICP.

    The algorithm operates in the XY plane by default, finding the
    best rigid transformation (rotation + translation) to minimize
    the sum of squared distances between corresponding points.

    Args:
        max_iterations: Maximum number of ICP iterations.
        tolerance: Convergence tolerance on the change in mean error
            between consecutive iterations (mm).
        constrain_z: If True, alignment is constrained to the XY plane
            (no Z rotation or translation). Defaults to True.
        subsample: Maximum number of source points to use per iteration
            for performance. None uses all points.
    """

    def __init__(
        self,
        max_iterations: int = 50,
        tolerance: float = 0.001,
        constrain_z: bool = True,
        subsample: Optional[int] = 5000,
    ) -> None:
        self._max_iter = max_iterations
        self._tolerance = tolerance
        self._constrain_z = constrain_z
        self._subsample = subsample

    def align(
        self,
        source: trimesh.Trimesh,
        target: trimesh.Trimesh,
        initial_transform: Optional[np.ndarray] = None,
    ) -> AlignmentResult:
        """Align source mesh to target mesh using ICP.

        The algorithm first performs centroid alignment, then iteratively
        refines the transformation by finding closest points and computing
        the optimal rigid transform.

        Args:
            source: The mesh to be transformed (e.g., reconstructed model).
            target: The reference mesh to align to (e.g., original STL).
            initial_transform: Optional 4x4 initial transformation matrix.
                If None, centroid alignment is used as the initial guess.

        Returns:
            AlignmentResult with the computed transformation and statistics.
        """
        logger.info(
            "Starting ICP alignment: source=%d verts, target=%d verts",
            len(source.vertices),
            len(target.vertices),
        )

        # Work with copies to avoid modifying originals
        src_pts = np.array(source.vertices, dtype=np.float64)
        tgt_pts = np.array(target.vertices, dtype=np.float64)

        # Determine which dimensions to use for alignment
        if self._constrain_z:
            # Use only XY for ICP, preserve Z
            src_xy = src_pts[:, :2].copy()
            tgt_xy = tgt_pts[:, :2].copy()
        else:
            src_xy = src_pts.copy()
            tgt_xy = tgt_pts.copy()

        # Apply initial transform or centroid alignment
        cumulative_4x4 = np.eye(4)

        if initial_transform is not None:
            cumulative_4x4 = initial_transform.copy()
            src_xy = self._apply_2d_transform(src_xy, initial_transform)
        else:
            # Initial centroid alignment
            src_centroid = np.mean(src_xy, axis=0)
            tgt_centroid = np.mean(tgt_xy, axis=0)
            translation = tgt_centroid - src_centroid

            if self._constrain_z:
                init_t = np.eye(4)
                init_t[0, 3] = translation[0]
                init_t[1, 3] = translation[1]
                cumulative_4x4 = init_t
                src_xy += translation
            else:
                init_t = np.eye(4)
                init_t[:3, 3] = translation
                cumulative_4x4 = init_t
                src_xy += translation

            logger.debug(
                "Initial centroid alignment: translation=%s", translation
            )

        # Build KDTree on target points
        tree = KDTree(tgt_xy)

        # Subsample source points for faster ICP
        if self._subsample and len(src_xy) > self._subsample:
            rng = np.random.default_rng(42)
            sample_idx = rng.choice(
                len(src_xy), size=self._subsample, replace=False
            )
        else:
            sample_idx = np.arange(len(src_xy))

        error_history: list[float] = []
        prev_error = float("inf")
        converged = False

        for iteration in range(self._max_iter):
            # Step 1: Find closest points in target for each source point
            src_sample = src_xy[sample_idx]
            distances, indices = tree.query(src_sample)
            mean_error = float(np.mean(distances))
            error_history.append(mean_error)

            # Check convergence
            error_change = abs(prev_error - mean_error)
            if error_change < self._tolerance:
                converged = True
                logger.debug(
                    "ICP converged at iteration %d: mean_error=%.6f, "
                    "change=%.6f < tol=%.6f",
                    iteration, mean_error, error_change, self._tolerance,
                )
                break

            prev_error = mean_error

            # Step 2: Compute best rigid transformation
            tgt_matched = tgt_xy[indices]

            if self._constrain_z:
                R_2d, t_2d = self._rigid_transform_2d(
                    src_sample, tgt_matched
                )
                # Apply to all source points
                src_xy = (R_2d @ src_xy.T).T + t_2d

                # Accumulate into 4x4
                step_4x4 = np.eye(4)
                step_4x4[:2, :2] = R_2d
                step_4x4[0, 3] = t_2d[0]
                step_4x4[1, 3] = t_2d[1]
            else:
                R_3d, t_3d = self._rigid_transform_3d(
                    src_sample, tgt_matched
                )
                src_xy = (R_3d @ src_xy.T).T + t_3d

                step_4x4 = np.eye(4)
                step_4x4[:3, :3] = R_3d
                step_4x4[:3, 3] = t_3d

            cumulative_4x4 = step_4x4 @ cumulative_4x4

            if (iteration + 1) % 10 == 0:
                logger.debug(
                    "ICP iteration %d: mean_error=%.6f",
                    iteration + 1, mean_error,
                )

        # Final error computation
        distances_final, _ = tree.query(src_xy[sample_idx])
        final_mean_error = float(np.mean(distances_final))
        error_history.append(final_mean_error)

        # Extract rotation angle from the 4x4 matrix
        rotation_angle_rad = np.arctan2(
            cumulative_4x4[1, 0], cumulative_4x4[0, 0]
        )
        rotation_angle_deg = float(np.degrees(rotation_angle_rad))

        translation_xy = cumulative_4x4[:2, 3].copy()

        result = AlignmentResult(
            transformation_matrix=cumulative_4x4,
            rotation_angle_deg=rotation_angle_deg,
            translation_xy=translation_xy,
            mean_error=final_mean_error,
            converged=converged,
            iterations=len(error_history) - 1,
            error_history=error_history,
        )

        logger.info(
            "ICP complete: converged=%s, iterations=%d, "
            "mean_error=%.4f mm, rotation=%.2f°, translation=[%.3f, %.3f]",
            result.converged,
            result.iterations,
            result.mean_error,
            result.rotation_angle_deg,
            result.translation_xy[0],
            result.translation_xy[1],
        )

        return result

    def apply_transform(
        self,
        mesh: trimesh.Trimesh,
        transform: np.ndarray,
    ) -> trimesh.Trimesh:
        """Apply a 4x4 transformation matrix to a mesh.

        Creates a copy of the mesh and applies the transformation
        to its vertices and face normals.

        Args:
            mesh: The mesh to transform.
            transform: 4x4 homogeneous transformation matrix.

        Returns:
            A new trimesh.Trimesh with the transformation applied.
        """
        transformed = mesh.copy()
        transformed.apply_transform(transform)
        logger.debug("Applied 4x4 transform to mesh with %d vertices", len(mesh.vertices))
        return transformed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rigid_transform_2d(
        source: np.ndarray,
        target: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute the optimal 2D rigid transformation (rotation + translation).

        Uses the SVD-based method to find the rotation matrix R and
        translation vector t such that target ≈ R @ source + t.

        Args:
            source: Nx2 array of source points.
            target: Nx2 array of corresponding target points.

        Returns:
            Tuple of (R, t) where R is a 2x2 rotation matrix and t is a
            2-element translation vector.
        """
        src_centroid = np.mean(source, axis=0)
        tgt_centroid = np.mean(target, axis=0)

        src_centered = source - src_centroid
        tgt_centered = target - tgt_centroid

        # Cross-covariance matrix
        H = src_centered.T @ tgt_centered  # 2x2

        U, _, Vt = np.linalg.svd(H)

        # Ensure proper rotation (det = +1)
        d = np.linalg.det(Vt.T @ U.T)
        sign_matrix = np.diag([1.0, np.sign(d)])
        R = Vt.T @ sign_matrix @ U.T

        t = tgt_centroid - R @ src_centroid

        return R, t

    @staticmethod
    def _rigid_transform_3d(
        source: np.ndarray,
        target: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute the optimal 3D rigid transformation using SVD.

        Args:
            source: Nx3 array of source points.
            target: Nx3 array of corresponding target points.

        Returns:
            Tuple of (R, t) where R is a 3x3 rotation matrix and t is a
            3-element translation vector.
        """
        src_centroid = np.mean(source, axis=0)
        tgt_centroid = np.mean(target, axis=0)

        src_centered = source - src_centroid
        tgt_centered = target - tgt_centroid

        H = src_centered.T @ tgt_centered  # 3x3

        U, _, Vt = np.linalg.svd(H)

        d = np.linalg.det(Vt.T @ U.T)
        sign_matrix = np.diag([1.0, 1.0, np.sign(d)])
        R = Vt.T @ sign_matrix @ U.T

        t = tgt_centroid - R @ src_centroid

        return R, t

    @staticmethod
    def _apply_2d_transform(
        points: np.ndarray,
        transform: np.ndarray,
    ) -> np.ndarray:
        """Apply a 4x4 transform to 2D points (XY only).

        Args:
            points: Nx2 array of XY points.
            transform: 4x4 homogeneous transformation matrix.

        Returns:
            Nx2 array of transformed XY points.
        """
        R = transform[:2, :2]
        t = transform[:2, 3]
        return (R @ points.T).T + t
