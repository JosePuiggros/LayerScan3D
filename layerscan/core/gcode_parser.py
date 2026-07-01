"""G-code parser for extracting layer information from 3D print files.

RF-11: Parse G-code files to extract layer heights, Z values, layer counts,
and optionally XY toolpath contours per layer. Supports both absolute (G90)
and relative (G91) positioning modes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from layerscan.utils.logger import get_logger

logger = get_logger("core.gcode_parser")

# Pre-compiled regex patterns for G-code parsing
_RE_COMMENT = re.compile(r";.*$")
_RE_GCODE = re.compile(
    r"^[Gg]\s*(\d+)"  # G command number
)
_RE_PARAM = re.compile(
    r"([XYZEFxyzef])\s*([-+]?\d*\.?\d+)"  # Parameter letter + value
)


@dataclass
class GCodeData:
    """Parsed G-code data containing layer geometry information.

    Attributes:
        layer_heights: List of individual layer heights (mm), computed as
            the difference between consecutive Z values.
        layer_z_values: List of absolute Z positions (mm) where each layer
            starts. Sorted in ascending order.
        layer_count: Total number of detected layers.
        total_height: Maximum Z height reached during the print (mm).
        xy_paths_per_layer: Optional mapping from layer index to a list of
            Nx2 numpy arrays, each representing a contiguous XY toolpath
            segment within that layer.
    """

    layer_heights: list[float] = field(default_factory=list)
    layer_z_values: list[float] = field(default_factory=list)
    layer_count: int = 0
    total_height: float = 0.0
    xy_paths_per_layer: Optional[dict[int, list[np.ndarray]]] = None


class GCodeParser:
    """Parser for G-code files used in FDM 3D printing.

    Extracts layer structure information by tracking Z-height changes across
    G0/G1 movement commands. Supports both absolute (G90) and relative (G91)
    positioning modes.

    Args:
        extract_xy_paths: If True, collect XY toolpath coordinates per layer.
            This increases memory usage but is needed for contour comparison.
            Defaults to False.
        z_epsilon: Minimum Z change (mm) to be considered a new layer.
            Avoids detecting tiny Z adjustments as layer changes.
            Defaults to 0.005 mm.
    """

    def __init__(
        self,
        extract_xy_paths: bool = False,
        z_epsilon: float = 0.005,
    ) -> None:
        self._extract_xy = extract_xy_paths
        self._z_epsilon = z_epsilon

    def parse(self, gcode_path: str | Path) -> GCodeData:
        """Parse a G-code file and extract layer information.

        Args:
            gcode_path: Path to the G-code file.

        Returns:
            GCodeData containing layer heights, Z values, layer count,
            total height, and optionally XY paths per layer.

        Raises:
            FileNotFoundError: If the G-code file does not exist.
            ValueError: If no layers are detected in the file.
        """
        gcode_path = Path(gcode_path)
        if not gcode_path.exists():
            raise FileNotFoundError(f"G-code file not found: {gcode_path}")

        logger.info("Parsing G-code file: %s", gcode_path.name)

        # State variables for tracking position and mode
        absolute_mode = True  # G90 is default
        current_x: float = 0.0
        current_y: float = 0.0
        current_z: float = 0.0

        z_values_seen: list[float] = []
        current_layer_idx: int = -1  # Not yet on any layer

        # XY path tracking
        xy_paths: dict[int, list[np.ndarray]] = {} if self._extract_xy else None
        current_segment: list[list[float]] = []

        with open(gcode_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, raw_line in enumerate(f, start=1):
                line = self._strip_comment(raw_line).strip()
                if not line:
                    continue

                # Check for positioning mode changes
                if line.upper().startswith("G90"):
                    absolute_mode = True
                    continue
                elif line.upper().startswith("G91"):
                    absolute_mode = False
                    continue

                # Match G0 or G1 movement commands
                g_match = _RE_GCODE.match(line)
                if not g_match:
                    continue

                g_number = int(g_match.group(1))
                if g_number not in (0, 1):
                    continue

                # Extract axis parameters from the line
                params = self._extract_params(line)

                # Compute new positions
                new_x = self._resolve_axis(
                    params.get("X"), current_x, absolute_mode
                )
                new_y = self._resolve_axis(
                    params.get("Y"), current_y, absolute_mode
                )
                new_z = self._resolve_axis(
                    params.get("Z"), current_z, absolute_mode
                )

                # Detect layer change when Z changes
                if "Z" in params and abs(new_z - current_z) > self._z_epsilon:
                    # Flush current XY segment to the previous layer
                    if self._extract_xy and current_segment and current_layer_idx >= 0:
                        self._flush_segment(
                            xy_paths, current_layer_idx, current_segment
                        )
                        current_segment = []

                    # Check if this Z value is new
                    z_rounded = round(new_z, 4)
                    if not z_values_seen or abs(z_rounded - z_values_seen[-1]) > self._z_epsilon:
                        z_values_seen.append(z_rounded)
                        current_layer_idx = len(z_values_seen) - 1
                        logger.debug(
                            "Layer %d detected at Z=%.4f (line %d)",
                            current_layer_idx,
                            z_rounded,
                            line_num,
                        )

                # Track XY movement for toolpath extraction
                if self._extract_xy and current_layer_idx >= 0:
                    if "X" in params or "Y" in params:
                        current_segment.append([new_x, new_y])

                # Update current position
                current_x = new_x
                current_y = new_y
                current_z = new_z

        # Flush any remaining segment
        if self._extract_xy and current_segment and current_layer_idx >= 0:
            self._flush_segment(xy_paths, current_layer_idx, current_segment)

        if not z_values_seen:
            raise ValueError(
                f"No layers detected in G-code file: {gcode_path.name}. "
                "Ensure the file contains G0/G1 commands with Z movements."
            )

        # Compute layer heights as differences between consecutive Z values
        layer_heights: list[float] = []
        for i in range(1, len(z_values_seen)):
            height = round(z_values_seen[i] - z_values_seen[i - 1], 4)
            layer_heights.append(height)

        result = GCodeData(
            layer_heights=layer_heights,
            layer_z_values=z_values_seen,
            layer_count=len(z_values_seen),
            total_height=round(max(z_values_seen), 4),
            xy_paths_per_layer=xy_paths,
        )

        logger.info(
            "G-code parsed: %d layers, total height=%.2f mm, "
            "layer heights range=[%.3f, %.3f]",
            result.layer_count,
            result.total_height,
            min(layer_heights) if layer_heights else 0.0,
            max(layer_heights) if layer_heights else 0.0,
        )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_comment(line: str) -> str:
        """Remove inline comments (everything after semicolon).

        Args:
            line: Raw G-code line.

        Returns:
            Line with comments stripped.
        """
        idx = line.find(";")
        if idx >= 0:
            return line[:idx]
        return line

    @staticmethod
    def _extract_params(line: str) -> dict[str, float]:
        """Extract axis parameters from a G-code line.

        Args:
            line: G-code line (comments already stripped).

        Returns:
            Dictionary mapping axis letters (upper-case) to float values.
        """
        params: dict[str, float] = {}
        for match in _RE_PARAM.finditer(line):
            letter = match.group(1).upper()
            value = float(match.group(2))
            params[letter] = value
        return params

    @staticmethod
    def _resolve_axis(
        param_value: Optional[float],
        current: float,
        absolute: bool,
    ) -> float:
        """Resolve a new axis position given a parameter value and mode.

        Args:
            param_value: Value from the G-code parameter, or None if absent.
            current: Current position on this axis.
            absolute: True for absolute mode (G90), False for relative (G91).

        Returns:
            New axis position.
        """
        if param_value is None:
            return current
        if absolute:
            return param_value
        return current + param_value

    @staticmethod
    def _flush_segment(
        xy_paths: dict[int, list[np.ndarray]],
        layer_idx: int,
        segment: list[list[float]],
    ) -> None:
        """Convert a segment of XY points to a numpy array and store it.

        Args:
            xy_paths: Dictionary mapping layer index to list of path arrays.
            layer_idx: Current layer index.
            segment: List of [x, y] coordinate pairs.
        """
        if len(segment) < 2:
            return
        arr = np.array(segment, dtype=np.float64)
        if layer_idx not in xy_paths:
            xy_paths[layer_idx] = []
        xy_paths[layer_idx].append(arr)
