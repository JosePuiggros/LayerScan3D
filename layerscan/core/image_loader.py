"""Image loading and ordering for LayerScan3D.

RF-01, RF-04: Load layer images from a directory, extract layer numbers
from filenames, sort by layer order, and validate against expected counts.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from layerscan.utils.logger import get_logger

logger = get_logger("core.image_loader")

# Supported image file extensions (case-insensitive)
SUPPORTED_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}

# Regex patterns for extracting layer numbers from filenames, ordered by
# specificity. Each pattern must contain exactly one capturing group for the
# layer number.
_LAYER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"layer[_\-]?(\d+)", re.IGNORECASE),  # layer_001, layer-1, layer01
    re.compile(r"img[_\-]?(\d+)", re.IGNORECASE),     # img001, img_001, img-1
    re.compile(r"capa[_\-]?(\d+)", re.IGNORECASE),    # capa_001 (Spanish)
    re.compile(r"slice[_\-]?(\d+)", re.IGNORECASE),   # slice_001
    re.compile(r"^(\d+)$"),                            # bare number: "001" (stem only)
]


@dataclass
class LayerImage:
    """Container for a single layer image with its metadata.

    Attributes:
        image: The loaded image as a NumPy array (BGR color space from OpenCV).
        layer_number: Integer layer index extracted from the filename.
        filepath: Absolute path to the source image file.
        z_height: Computed Z height in mm for this layer, derived from
            ``layer_number * layer_height_mm``.
    """

    image: np.ndarray
    layer_number: int
    filepath: str
    z_height: float

    def __repr__(self) -> str:
        h, w = self.image.shape[:2]
        return (
            f"LayerImage(layer={self.layer_number}, "
            f"z={self.z_height:.3f}mm, "
            f"size={w}x{h}, "
            f"file='{Path(self.filepath).name}')"
        )


def extract_layer_number(filename: str) -> Optional[int]:
    """Extract a layer number from a filename using a set of regex patterns.

    The function tries several common naming conventions in order:
    ``layer_001.png``, ``img001.jpg``, ``capa_01.tiff``, ``slice_05.bmp``,
    and finally a bare numeric stem like ``001.png``.

    Args:
        filename: The filename (not full path) to parse.

    Returns:
        The extracted layer number as an integer, or ``None`` if no pattern
        matched.
    """
    stem = Path(filename).stem

    for pattern in _LAYER_PATTERNS:
        match = pattern.search(stem)
        if match:
            return int(match.group(1))

    return None


def _is_supported_image(path: Path) -> bool:
    """Check whether *path* has a supported image extension."""
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def load_images(
    directory: str,
    layer_height_mm: float = 0.2,
    expected_count: Optional[int] = None,
    grayscale: bool = False,
) -> List[LayerImage]:
    """Load all supported images from *directory*, sorted by layer number.

    For every image whose filename matches a known naming pattern, the layer
    number is extracted and used to compute ``z_height = layer_number *
    layer_height_mm``.  Images that cannot be parsed are skipped with a
    warning.

    Args:
        directory: Path to the folder containing layer images.
        layer_height_mm: The physical height of each printed layer in
            millimetres. Defaults to ``0.2`` mm.
        expected_count: If provided, the function validates that exactly this
            many images were loaded and raises ``ValueError`` on mismatch.
        grayscale: If ``True``, images are loaded as single-channel grayscale.

    Returns:
        A list of :class:`LayerImage` objects sorted in ascending layer order.

    Raises:
        FileNotFoundError: If *directory* does not exist or is not a directory.
        ValueError: If *expected_count* is given and the actual number of
            loaded images does not match.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileNotFoundError(
            f"Image directory does not exist or is not a directory: {directory}"
        )

    # Discover candidate image files
    candidates = sorted(
        [p for p in dir_path.iterdir() if p.is_file() and _is_supported_image(p)]
    )

    if not candidates:
        logger.warning("No supported image files found in '%s'.", directory)
        return []

    logger.info(
        "Found %d candidate image file(s) in '%s'.", len(candidates), directory
    )

    # Extract layer numbers and build (layer_number, path) pairs
    parsed: list[Tuple[int, Path]] = []
    for path in candidates:
        layer_num = extract_layer_number(path.name)
        if layer_num is None:
            logger.warning(
                "Could not extract layer number from '%s'; skipping.", path.name
            )
            continue
        parsed.append((layer_num, path))

    if not parsed:
        logger.error(
            "No image filenames matched any known layer-naming pattern."
        )
        return []

    # Sort by layer number
    parsed.sort(key=lambda pair: pair[0])

    # Check for duplicate layer numbers
    seen_layers: dict[int, str] = {}
    for layer_num, path in parsed:
        if layer_num in seen_layers:
            logger.warning(
                "Duplicate layer number %d: '%s' conflicts with '%s'. "
                "Keeping the first occurrence.",
                layer_num,
                path.name,
                seen_layers[layer_num],
            )
        else:
            seen_layers[layer_num] = path.name

    # Deduplicate – keep first occurrence per layer number
    unique_parsed: list[Tuple[int, Path]] = []
    added: set[int] = set()
    for layer_num, path in parsed:
        if layer_num not in added:
            unique_parsed.append((layer_num, path))
            added.add(layer_num)
    parsed = unique_parsed

    # Load images
    imread_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR
    layer_images: list[LayerImage] = []

    for layer_num, path in parsed:
        img = cv2.imread(str(path), imread_flag)
        if img is None:
            logger.error("Failed to read image '%s'; skipping.", path)
            continue

        z = layer_num * layer_height_mm
        layer_images.append(
            LayerImage(
                image=img,
                layer_number=layer_num,
                filepath=str(path),
                z_height=z,
            )
        )

    logger.info(
        "Successfully loaded %d layer image(s) (z range: %.2f–%.2f mm).",
        len(layer_images),
        layer_images[0].z_height if layer_images else 0.0,
        layer_images[-1].z_height if layer_images else 0.0,
    )

    # Validate count
    if expected_count is not None and len(layer_images) != expected_count:
        raise ValueError(
            f"Expected {expected_count} layer images but loaded "
            f"{len(layer_images)}."
        )

    return layer_images


def validate_image_sequence(
    layer_images: List[LayerImage],
) -> List[int]:
    """Check for gaps in the layer number sequence.

    Args:
        layer_images: A sorted list of :class:`LayerImage` objects.

    Returns:
        A list of missing layer numbers (empty if the sequence is contiguous).
    """
    if len(layer_images) < 2:
        return []

    numbers = [li.layer_number for li in layer_images]
    full_range = set(range(numbers[0], numbers[-1] + 1))
    present = set(numbers)
    missing = sorted(full_range - present)

    if missing:
        logger.warning(
            "Layer sequence has %d gap(s): missing layers %s.",
            len(missing),
            missing,
        )
    else:
        logger.info("Layer sequence is contiguous (%d–%d).", numbers[0], numbers[-1])

    return missing
