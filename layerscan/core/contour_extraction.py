"""Contour extraction from segmented masks for LayerScan3D.

RF-06: Extract XY contours from binary segmentation masks, convert pixel
coordinates to millimetres, simplify contours, and assign Z heights for
downstream 3D reconstruction.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from layerscan.utils.logger import get_logger

logger = get_logger("core.contour_extraction")


@dataclass
class LayerContour:
    """Geometric representation of one layer's contour(s) in physical
    coordinates.

    Attributes:
        outer_contour: Nx2 NumPy array of the outer boundary in mm
            (ordered clockwise).
        inner_contours: List of Mx2 arrays representing holes (ordered
            counter-clockwise).
        z_height: Z coordinate of this layer in mm.
        area_mm2: Area enclosed by the outer contour minus holes, in mm².
        perimeter_mm: Perimeter of the outer contour in mm.
        confidence: Extraction confidence score in [0, 1]. Heuristic
            based on contour regularity.
    """

    outer_contour: np.ndarray
    inner_contours: List[np.ndarray] = field(default_factory=list)
    z_height: float = 0.0
    area_mm2: float = 0.0
    perimeter_mm: float = 0.0
    confidence: float = 1.0

    def __repr__(self) -> str:
        n_outer = len(self.outer_contour) if self.outer_contour is not None else 0
        n_holes = len(self.inner_contours)
        return (
            f"LayerContour(z={self.z_height:.3f}mm, "
            f"pts={n_outer}, holes={n_holes}, "
            f"area={self.area_mm2:.2f}mm², "
            f"confidence={self.confidence:.2f})"
        )


class ContourExtractor:
    """Extract and post-process contours from binary segmentation masks.

    The extractor converts pixel-level masks into physical-coordinate
    contour objects suitable for 3D reconstruction.

    Args:
        scale_mm_per_pixel: Spatial resolution used for pixel-to-mm
            conversion.
        simplification_epsilon: Tolerance parameter for Douglas-Peucker
            contour simplification, expressed as a *fraction* of the
            contour perimeter (e.g. ``0.001`` keeps very fine detail,
            ``0.01`` is a moderate simplification).
        min_area_mm2: Minimum contour area in mm². Contours smaller
            than this are discarded.
    """

    def __init__(
        self,
        scale_mm_per_pixel: float = 1.0,
        simplification_epsilon: float = 0.002,
        min_area_mm2: float = 1.0,
    ) -> None:
        if scale_mm_per_pixel <= 0:
            raise ValueError("scale_mm_per_pixel must be positive.")
        self.scale: float = scale_mm_per_pixel
        self.simplification_epsilon: float = simplification_epsilon
        self.min_area_mm2: float = min_area_mm2

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def extract_from_mask(
        self,
        mask: np.ndarray,
        z_height: float = 0.0,
        scale_override: Optional[float] = None,
    ) -> List[LayerContour]:
        """Extract all contours from a binary *mask*.

        The method supports multiple disjoint pieces per layer as well as
        pieces with interior holes.

        Args:
            mask: Binary image (``uint8``, values 0 or 255).
            z_height: Z height in mm to assign to the resulting contours.
            scale_override: If given, overrides the instance-level
                ``scale_mm_per_pixel`` for this call only.

        Returns:
            A list of :class:`LayerContour` objects, one per outer contour
            found in the mask. Empty list if no valid contours are
            detected.
        """
        scale = scale_override if scale_override is not None else self.scale

        # Find contours with full hierarchy (RETR_CCOMP gives 2-level
        # hierarchy: outer boundaries and their immediate children = holes).
        contours, hierarchy = cv2.findContours(
            mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours or hierarchy is None:
            logger.debug("No contours found in mask at z=%.3f mm.", z_height)
            return []

        hierarchy = hierarchy[0]  # shape (N, 4): [next, prev, child, parent]

        results: list[LayerContour] = []

        # Iterate over top-level (outer) contours (those with parent == -1)
        idx = 0
        while idx >= 0:
            if hierarchy[idx][3] != -1:
                # Not a top-level contour; skip
                idx = hierarchy[idx][0]
                continue

            outer_px = contours[idx]
            area_px = cv2.contourArea(outer_px)
            area_mm2 = area_px * (scale ** 2)

            if area_mm2 < self.min_area_mm2:
                idx = hierarchy[idx][0]
                continue

            # Simplify outer contour
            outer_simplified = self._simplify(outer_px)
            outer_mm = self._pixels_to_mm(outer_simplified, scale)

            perimeter_px = cv2.arcLength(outer_px, closed=True)
            perimeter_mm = perimeter_px * scale

            # Collect child (hole) contours
            inner_contours_mm: list[np.ndarray] = []
            hole_area_mm2 = 0.0
            child_idx = hierarchy[idx][2]
            while child_idx >= 0:
                hole_px = contours[child_idx]
                hole_area_px = cv2.contourArea(hole_px)
                hole_area_mm2 += hole_area_px * (scale ** 2)

                hole_simplified = self._simplify(hole_px)
                hole_mm = self._pixels_to_mm(hole_simplified, scale)
                inner_contours_mm.append(hole_mm)

                child_idx = hierarchy[child_idx][0]

            net_area_mm2 = area_mm2 - hole_area_mm2

            confidence = self._compute_confidence(
                outer_simplified, area_px, perimeter_px
            )

            results.append(
                LayerContour(
                    outer_contour=outer_mm,
                    inner_contours=inner_contours_mm,
                    z_height=z_height,
                    area_mm2=net_area_mm2,
                    perimeter_mm=perimeter_mm,
                    confidence=confidence,
                )
            )

            idx = hierarchy[idx][0]

        logger.debug(
            "Extracted %d contour(s) at z=%.3f mm.", len(results), z_height
        )
        return results

    # ------------------------------------------------------------------
    # Batch extraction
    # ------------------------------------------------------------------

    def extract_batch(
        self,
        masks: List[np.ndarray],
        z_heights: List[float],
        scale_override: Optional[float] = None,
    ) -> List[List[LayerContour]]:
        """Extract contours from a batch of masks.

        Args:
            masks: List of binary masks.
            z_heights: Corresponding Z heights for each mask.
            scale_override: Optional per-batch scale override.

        Returns:
            A list of lists; each inner list contains the
            :class:`LayerContour` objects for one layer.

        Raises:
            ValueError: If *masks* and *z_heights* have different lengths.
        """
        if len(masks) != len(z_heights):
            raise ValueError(
                f"masks ({len(masks)}) and z_heights ({len(z_heights)}) "
                "must have the same length."
            )

        all_contours: list[list[LayerContour]] = []
        total = len(masks)

        for i, (mask, z) in enumerate(zip(masks, z_heights)):
            layer_contours = self.extract_from_mask(
                mask, z_height=z, scale_override=scale_override
            )
            all_contours.append(layer_contours)

            if (i + 1) % max(1, total // 10) == 0 or i == total - 1:
                logger.info("Extracted contours for %d / %d layers.", i + 1, total)

        return all_contours

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _simplify(self, contour_px: np.ndarray) -> np.ndarray:
        """Apply Douglas-Peucker simplification to a pixel contour.

        Args:
            contour_px: Contour as returned by ``cv2.findContours``
                (shape ``(N, 1, 2)``).

        Returns:
            Simplified contour with shape ``(M, 1, 2)`` where ``M ≤ N``.
        """
        perimeter = cv2.arcLength(contour_px, closed=True)
        epsilon = self.simplification_epsilon * perimeter
        return cv2.approxPolyDP(contour_px, epsilon, closed=True)

    @staticmethod
    def _pixels_to_mm(
        contour_px: np.ndarray,
        scale: float,
    ) -> np.ndarray:
        """Convert a pixel contour to millimetre coordinates.

        Args:
            contour_px: Contour with shape ``(N, 1, 2)`` (OpenCV format).
            scale: mm/pixel conversion factor.

        Returns:
            Nx2 NumPy array of coordinates in mm.
        """
        pts = contour_px.reshape(-1, 2).astype(np.float64)
        return pts * scale

    @staticmethod
    def _compute_confidence(
        contour_px: np.ndarray,
        area_px: float,
        perimeter_px: float,
    ) -> float:
        """Compute a heuristic confidence score for a contour.

        The score is based on **circularity** (a.k.a. isoperimetric
        quotient) which measures how close the shape is to a circle.
        Highly irregular or very noisy contours yield lower scores.
        The value is clamped to [0, 1].

        A perfect circle has circularity = 1.0. Realistic printed
        contours score 0.3–0.9.

        Args:
            contour_px: Simplified pixel contour.
            area_px: Area in pixels.
            perimeter_px: Perimeter in pixels.

        Returns:
            Confidence score in [0.0, 1.0].
        """
        if perimeter_px <= 0 or area_px <= 0:
            return 0.0

        circularity = (4.0 * np.pi * area_px) / (perimeter_px ** 2)

        # Also penalise very low point counts (under-sampled contour)
        n_points = contour_px.reshape(-1, 2).shape[0]
        point_factor = min(1.0, n_points / 10.0)

        confidence = float(np.clip(circularity * point_factor, 0.0, 1.0))
        return confidence
