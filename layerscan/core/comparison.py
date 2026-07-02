"""Model comparison between reconstructed and original reference meshes.

RF-13, RF-14: Compute per-vertex distance metrics, per-layer height errors,
per-layer contour Hausdorff distances, and aggregate statistics for quality
assessment of 3D printed parts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.spatial.distance import directed_hausdorff
import trimesh

from layerscan.core.stl_slicer import SliceContour
from layerscan.utils.logger import get_logger

logger = get_logger("core.comparison")


@dataclass
class ComparisonResult:
    """Result of comparing a reconstructed mesh against a reference mesh.

    Attributes:
        per_vertex_distances: 1D array of signed/unsigned distances from each
            vertex of the reconstructed mesh to the closest point on the
            reference surface (mm).
        global_stats: Dictionary of aggregate statistics including:
            - mean_error: Mean absolute distance (mm).
            - max_error: Maximum distance (mm).
            - std_dev: Standard deviation of distances (mm).
            - median: Median distance (mm).
            - p95: 95th percentile distance (mm).
            - p99: 99th percentile distance (mm).
        per_layer_height_errors: Mapping from layer index to the height error
            (detected_z - planned_z) in mm. Empty if no G-code data provided.
        per_layer_contour_hausdorff: Mapping from layer index to the
            symmetric Hausdorff distance (mm) between reconstructed and
            reference contours at that layer.
        points_within_tolerance_pct: Percentage of reconstructed vertices
            that fall within the specified tolerance distance.
        tolerance_mm: The tolerance threshold used (mm).
    """

    per_vertex_distances: np.ndarray = field(
        default_factory=lambda: np.empty(0)
    )
    global_stats: dict[str, float] = field(default_factory=dict)
    per_layer_height_errors: dict[int, float] = field(default_factory=dict)
    per_layer_contour_hausdorff: dict[int, float] = field(default_factory=dict)
    points_within_tolerance_pct: float = 0.0
    tolerance_mm: float = 0.2


class ModelComparator:
    """Compare a reconstructed mesh against a reference (original STL).

    Computes point-to-surface distances using trimesh's proximity queries,
    per-layer height comparisons, and per-layer contour Hausdorff distances.

    Args:
        tolerance_mm: Distance threshold for determining whether a point
            is "within tolerance". Defaults to 0.2 mm.
    """

    def __init__(self, tolerance_mm: float = 0.2) -> None:
        self._tolerance = tolerance_mm

    def compare(
        self,
        reconstructed: trimesh.Trimesh,
        reference: trimesh.Trimesh,
        planned_z_values: Optional[list[float]] = None,
        detected_z_values: Optional[list[float]] = None,
        reconstructed_contours: Optional[list[SliceContour]] = None,
        reference_contours: Optional[list[SliceContour]] = None,
    ) -> ComparisonResult:
        """Perform full comparison between reconstructed and reference meshes.

        Args:
            reconstructed: The mesh produced from 3D scan reconstruction.
            reference: The original reference STL mesh.
            planned_z_values: Z heights from G-code (planned layers).
                If provided along with detected_z_values, per-layer
                height errors are computed.
            detected_z_values: Z heights detected from the reconstructed model
                or scan data.
            reconstructed_contours: List of SliceContour from the
                reconstructed mesh, for Hausdorff distance computation.
            reference_contours: List of SliceContour from the reference mesh,
                for Hausdorff distance computation.

        Returns:
            ComparisonResult with all computed metrics.
        """
        logger.info(
            "Comparing meshes: reconstructed=%d verts, reference=%d verts",
            len(reconstructed.vertices),
            len(reference.vertices),
        )

        # Step 1: Point-to-surface distances
        per_vertex_distances = self._compute_vertex_distances(
            reconstructed, reference
        )

        # Step 2: Global statistics
        global_stats = self._compute_statistics(per_vertex_distances)

        # Step 3: Percentage within tolerance
        within_tol = self._compute_tolerance_percentage(
            per_vertex_distances, self._tolerance
        )

        # Step 4: Per-layer height errors
        height_errors = self._compute_layer_height_errors(
            planned_z_values, detected_z_values
        )

        # Step 5: Per-layer contour Hausdorff distances
        contour_hausdorff = self._compute_contour_hausdorff(
            reconstructed_contours, reference_contours
        )

        result = ComparisonResult(
            per_vertex_distances=per_vertex_distances,
            global_stats=global_stats,
            per_layer_height_errors=height_errors,
            per_layer_contour_hausdorff=contour_hausdorff,
            points_within_tolerance_pct=within_tol,
            tolerance_mm=self._tolerance,
        )

        logger.info(
            "Comparison complete: mean=%.4f mm, max=%.4f mm, "
            "within_tol=%.1f%% (tol=%.2f mm)",
            global_stats.get("mean_error", 0),
            global_stats.get("max_error", 0),
            within_tol,
            self._tolerance,
        )

        return result

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_vertex_distances(
        reconstructed: trimesh.Trimesh,
        reference: trimesh.Trimesh,
    ) -> np.ndarray:
        """Compute per-vertex distances from reconstructed to reference surface.

        Uses scipy's cKDTree for memory-efficient point-to-point distance 
        approximation instead of full point-to-surface to avoid OOM on large meshes.
        """
        from scipy.spatial import cKDTree
        
        logger.debug(
            "Computing point-to-point distances for %d vertices against %d reference vertices",
            len(reconstructed.vertices), len(reference.vertices)
        )

        tree = cKDTree(reference.vertices)
        distances, _ = tree.query(reconstructed.vertices)

        return np.abs(distances).astype(np.float64)

    @staticmethod
    def _compute_statistics(distances: np.ndarray) -> dict[str, float]:
        """Compute aggregate statistics from a distance array.

        Args:
            distances: 1D array of distances (mm).

        Returns:
            Dictionary with keys: mean_error, max_error, std_dev,
            median, p95, p99.
        """
        if len(distances) == 0:
            return {
                "mean_error": 0.0,
                "max_error": 0.0,
                "std_dev": 0.0,
                "median": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        return {
            "mean_error": round(float(np.mean(distances)), 6),
            "max_error": round(float(np.max(distances)), 6),
            "std_dev": round(float(np.std(distances)), 6),
            "median": round(float(np.median(distances)), 6),
            "p95": round(float(np.percentile(distances, 95)), 6),
            "p99": round(float(np.percentile(distances, 99)), 6),
        }

    @staticmethod
    def _compute_tolerance_percentage(
        distances: np.ndarray,
        tolerance: float,
    ) -> float:
        """Compute the percentage of points within a given tolerance.

        Args:
            distances: 1D array of distances (mm).
            tolerance: Distance threshold (mm).

        Returns:
            Percentage (0-100) of points within tolerance.
        """
        if len(distances) == 0:
            return 100.0
        count_within = int(np.sum(distances <= tolerance))
        return round(100.0 * count_within / len(distances), 2)

    @staticmethod
    def _compute_layer_height_errors(
        planned_z: Optional[list[float]],
        detected_z: Optional[list[float]],
    ) -> dict[int, float]:
        """Compute per-layer height errors between planned and detected Z values.

        For each layer, the error is computed as (detected - planned).
        Only layers where both planned and detected values exist are included.

        Args:
            planned_z: Z heights from G-code (planned).
            detected_z: Z heights from the reconstructed model (detected).

        Returns:
            Dictionary mapping layer index to height error (mm).
        """
        if not planned_z or not detected_z:
            return {}

        errors: dict[int, float] = {}
        n = min(len(planned_z), len(detected_z))

        for i in range(n):
            error = round(detected_z[i] - planned_z[i], 6)
            errors[i] = error

        if errors:
            abs_errors = [abs(e) for e in errors.values()]
            logger.debug(
                "Layer height errors: n=%d, mean_abs=%.4f, max_abs=%.4f",
                len(errors),
                sum(abs_errors) / len(abs_errors),
                max(abs_errors),
            )

        return errors

    @staticmethod
    def _compute_contour_hausdorff(
        reconstructed_contours: Optional[list[SliceContour]],
        reference_contours: Optional[list[SliceContour]],
    ) -> dict[int, float]:
        """Compute per-layer symmetric Hausdorff distance between contours.

        For each layer where both reconstructed and reference contours have
        valid data, the symmetric Hausdorff distance is computed.

        Args:
            reconstructed_contours: Contours from the reconstructed mesh.
            reference_contours: Contours from the reference mesh.

        Returns:
            Dictionary mapping layer index to symmetric Hausdorff distance (mm).
        """
        if not reconstructed_contours or not reference_contours:
            return {}

        hausdorff_map: dict[int, float] = {}
        n = min(len(reconstructed_contours), len(reference_contours))

        for i in range(n):
            rc = reconstructed_contours[i]
            ref = reference_contours[i]

            # Skip if either contour is empty
            if rc.contour_points.shape[0] < 2 or ref.contour_points.shape[0] < 2:
                continue

            # Compute symmetric Hausdorff distance
            d_forward = directed_hausdorff(rc.contour_points, ref.contour_points)[0]
            d_backward = directed_hausdorff(ref.contour_points, rc.contour_points)[0]
            symmetric = max(d_forward, d_backward)

            hausdorff_map[i] = round(float(symmetric), 6)

        if hausdorff_map:
            values = list(hausdorff_map.values())
            logger.debug(
                "Contour Hausdorff: n=%d, mean=%.4f, max=%.4f",
                len(values),
                sum(values) / len(values),
                max(values),
            )

        return hausdorff_map
