"""STL model slicer for extracting 2D contours at specific Z heights.

RF-12b: Slice an STL mesh at given Z heights using trimesh to produce
2D contour representations compatible with the LayerContour format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh

from layerscan.utils.logger import get_logger

logger = get_logger("core.stl_slicer")


@dataclass
class SliceContour:
    """2D contour extracted from slicing an STL model at a specific Z height.

    Attributes:
        contour_points: Nx2 numpy array of (x, y) coordinates forming the
            contour polygon. Empty array if the slice produced no geometry.
        z_height: The Z height (mm) at which this slice was taken.
        area: Area enclosed by the contour polygon (mm²). 0.0 if empty.
        perimeter: Total perimeter length of the contour (mm). 0.0 if empty.
    """

    contour_points: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))
    z_height: float = 0.0
    area: float = 0.0
    perimeter: float = 0.0


class STLSlicer:
    """Slices an STL mesh at specified Z heights to extract 2D contours.

    Uses trimesh's section method to compute cross-sections of a triangular
    mesh with horizontal planes (normal = Z-up). Each cross-section is
    converted into contour points, with area and perimeter computed.

    Args:
        mesh: A trimesh.Trimesh object representing the STL model.
            If None, a mesh must be loaded via load_mesh() before slicing.
    """

    def __init__(self, mesh: Optional[trimesh.Trimesh] = None) -> None:
        self._mesh = mesh

    def load_mesh(self, stl_path: str | Path) -> trimesh.Trimesh:
        """Load an STL file and store the mesh internally.

        Args:
            stl_path: Path to the STL file.

        Returns:
            The loaded trimesh.Trimesh object.

        Raises:
            FileNotFoundError: If the STL file does not exist.
            ValueError: If the file cannot be parsed as a valid mesh.
        """
        stl_path = Path(stl_path)
        if not stl_path.exists():
            raise FileNotFoundError(f"STL file not found: {stl_path}")

        logger.info("Loading STL mesh: %s", stl_path.name)
        loaded = trimesh.load(str(stl_path), force="mesh")

        if not isinstance(loaded, trimesh.Trimesh):
            raise ValueError(
                f"File did not load as a single mesh: {stl_path.name}. "
                f"Got {type(loaded).__name__} instead."
            )

        self._mesh = loaded
        logger.info(
            "STL loaded: %d vertices, %d faces, bounds Z=[%.3f, %.3f]",
            len(self._mesh.vertices),
            len(self._mesh.faces),
            self._mesh.bounds[0, 2],
            self._mesh.bounds[1, 2],
        )
        return self._mesh

    @property
    def mesh(self) -> trimesh.Trimesh:
        """Access the currently loaded mesh.

        Raises:
            RuntimeError: If no mesh has been loaded or set.
        """
        if self._mesh is None:
            raise RuntimeError(
                "No mesh loaded. Call load_mesh() or pass a mesh to the constructor."
            )
        return self._mesh

    def slice_at_heights(
        self,
        z_heights: list[float] | np.ndarray,
    ) -> list[SliceContour]:
        """Slice the mesh at each specified Z height and extract contours.

        For each Z height, a horizontal cross-section is computed. The
        resulting 2D path is converted to contour points. If the Z height
        is outside the mesh bounds or the cross-section is empty, an empty
        SliceContour is returned for that height.

        Args:
            z_heights: Iterable of Z heights (mm) at which to slice.

        Returns:
            List of SliceContour objects, one per input Z height,
            in the same order as the input heights.

        Raises:
            RuntimeError: If no mesh has been loaded.
        """
        mesh = self.mesh
        z_min, z_max = mesh.bounds[0, 2], mesh.bounds[1, 2]
        plane_normal = [0.0, 0.0, 1.0]
        results: list[SliceContour] = []

        logger.info(
            "Slicing mesh at %d Z heights (mesh Z range: [%.3f, %.3f])",
            len(z_heights),
            z_min,
            z_max,
        )

        for i, z in enumerate(z_heights):
            # Skip Z values clearly outside the mesh bounds (with small margin)
            margin = 0.001
            if z < z_min - margin or z > z_max + margin:
                logger.debug(
                    "Z=%.4f outside mesh bounds [%.3f, %.3f], returning empty contour",
                    z, z_min, z_max,
                )
                results.append(SliceContour(z_height=z))
                continue

            try:
                section = mesh.section(
                    plane_origin=[0.0, 0.0, z],
                    plane_normal=plane_normal,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to section mesh at Z=%.4f: %s", z, exc
                )
                results.append(SliceContour(z_height=z))
                continue

            if section is None:
                logger.debug("Empty section at Z=%.4f", z)
                results.append(SliceContour(z_height=z))
                continue

            contour = self._section_to_contour(section, z)
            results.append(contour)

            if (i + 1) % 50 == 0:
                logger.debug("Sliced %d / %d heights", i + 1, len(z_heights))

        non_empty = sum(1 for c in results if c.contour_points.shape[0] > 0)
        logger.info(
            "Slicing complete: %d / %d slices produced contours",
            non_empty,
            len(results),
        )
        return results

    def slice_at_height(self, z_height: float) -> SliceContour:
        """Slice the mesh at a single Z height.

        Convenience wrapper around slice_at_heights for a single height.

        Args:
            z_height: The Z height (mm) at which to slice.

        Returns:
            SliceContour for the specified Z height.
        """
        return self.slice_at_heights([z_height])[0]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _section_to_contour(
        section: trimesh.path.Path3D,
        z_height: float,
    ) -> SliceContour:
        """Convert a trimesh Path3D cross-section to a SliceContour.

        Attempts to project the 3D section to 2D and extract the largest
        contour polygon (by vertex count). Computes area and perimeter
        from the resulting polygon.

        Args:
            section: The 3D cross-section path from trimesh.
            z_height: The Z height this section was taken at.

        Returns:
            SliceContour with contour points, area, and perimeter.
        """
        try:
            # Project the 3D section down to a 2D path
            path_2d, _to_3d = section.to_planar()
        except Exception as exc:
            logger.debug(
                "Could not convert section to planar at Z=%.4f: %s",
                z_height, exc,
            )
            return SliceContour(z_height=z_height)

        if not path_2d.entities or len(path_2d.vertices) == 0:
            return SliceContour(z_height=z_height)

        # Collect all contour points from all discrete paths (polygons)
        all_points: list[np.ndarray] = []
        total_area: float = 0.0
        total_perimeter: float = 0.0

        try:
            polygons = path_2d.polygons_full
        except Exception:
            polygons = []

        if polygons:
            # Use the polygon representations for accurate area/perimeter
            for poly in polygons:
                coords = np.array(poly.exterior.coords, dtype=np.float64)
                all_points.append(coords)
                total_area += poly.area
                total_perimeter += poly.length
        else:
            # Fallback: use raw vertices from each discrete path
            for entity in path_2d.entities:
                try:
                    pts = path_2d.vertices[entity.points]
                    if len(pts) >= 3:
                        all_points.append(pts[:, :2].astype(np.float64))
                except (IndexError, AttributeError):
                    continue

            # Estimate area and perimeter from the points
            if all_points:
                for pts in all_points:
                    total_area += _shoelace_area(pts)
                    total_perimeter += _polyline_length(pts)

        if not all_points:
            return SliceContour(z_height=z_height)

        # Concatenate all contour points into a single Nx2 array.
        # The largest polygon is used as the primary contour.
        largest = max(all_points, key=len)

        return SliceContour(
            contour_points=largest,
            z_height=z_height,
            area=round(total_area, 6),
            perimeter=round(total_perimeter, 4),
        )


def _shoelace_area(points: np.ndarray) -> float:
    """Compute the area of a 2D polygon using the shoelace formula.

    Args:
        points: Nx2 array of polygon vertices.

    Returns:
        Absolute area of the polygon.
    """
    if len(points) < 3:
        return 0.0
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _polyline_length(points: np.ndarray) -> float:
    """Compute the total length of a polyline.

    Args:
        points: Nx2 array of vertices.

    Returns:
        Sum of segment lengths.
    """
    if len(points) < 2:
        return 0.0
    diffs = np.diff(points, axis=0)
    return float(np.sum(np.sqrt(np.sum(diffs ** 2, axis=1))))
