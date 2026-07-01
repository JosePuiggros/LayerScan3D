"""Image segmentation for LayerScan3D.

RF-05: Automatic segmentation of the printed piece from the background
using adaptive thresholding, Otsu's method, or background subtraction.
Includes morphological cleanup and per-layer parameter overrides.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.ndimage import binary_fill_holes

from layerscan.utils.logger import get_logger

logger = get_logger("core.segmentation")


class SegmentationMethod(str, Enum):
    """Supported segmentation methods."""

    ADAPTIVE = "adaptive"
    OTSU = "otsu"
    BACKGROUND_SUBTRACTION = "background_subtraction"


@dataclass
class SegmentationParams:
    """Parameters controlling segmentation behaviour.

    Attributes:
        method: Segmentation algorithm to use.
        block_size: Block size for adaptive thresholding (must be odd and
            ≥ 3). Ignored for non-adaptive methods.
        c: Constant subtracted from the adaptive threshold mean. Ignored
            for non-adaptive methods.
        kernel_size: Side-length of the square morphological structuring
            element.
        min_contour_area: Minimum contour area in *pixels*; smaller
            regions are removed from the mask.
        invert: If ``True``, the binary mask is inverted after thresholding
            (useful when the piece is darker than the background).
        gaussian_blur_ksize: Kernel size for optional Gaussian blur
            applied before thresholding (0 to disable).
        background_image: Reference background image for background
            subtraction mode. Must be the same size as the input.
        diff_threshold: Pixel intensity difference threshold used in
            background subtraction mode.
    """

    method: SegmentationMethod = SegmentationMethod.ADAPTIVE
    block_size: int = 11
    c: int = 2
    kernel_size: int = 5
    min_contour_area: int = 100
    invert: bool = False
    gaussian_blur_ksize: int = 5
    background_image: Optional[np.ndarray] = field(default=None, repr=False)
    diff_threshold: int = 30


def _ensure_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert to grayscale if the image has more than one channel."""
    if len(image.shape) == 3 and image.shape[2] >= 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def _apply_blur(gray: np.ndarray, ksize: int) -> np.ndarray:
    """Apply Gaussian blur if *ksize* is positive and odd."""
    if ksize > 0:
        ksize = ksize if ksize % 2 == 1 else ksize + 1
        return cv2.GaussianBlur(gray, (ksize, ksize), 0)
    return gray


def _morphological_cleanup(
    mask: np.ndarray,
    kernel_size: int,
    min_contour_area: int,
) -> np.ndarray:
    """Clean a binary mask with morphological operations and small-object
    removal.

    Steps:
        1. Morphological *opening* (erosion then dilation) to remove small
           noise blobs.
        2. Morphological *closing* (dilation then erosion) to fill small
           gaps.
        3. Hole filling using :func:`scipy.ndimage.binary_fill_holes`.
        4. Removal of connected components whose area is below
           *min_contour_area*.

    Args:
        mask: Binary mask (dtype ``uint8``, values 0 or 255).
        kernel_size: Structuring element side-length.
        min_contour_area: Minimum area in pixels.

    Returns:
        Cleaned binary mask (``uint8``, values 0/255).
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
    )

    # Opening: remove small noise
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Closing: fill small gaps
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Fill interior holes (scipy operates on bool arrays)
    filled = binary_fill_holes(cleaned > 0)
    cleaned = (filled.astype(np.uint8)) * 255

    # Remove small connected components
    if min_contour_area > 0:
        contours, _ = cv2.findContours(
            cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        filtered_mask = np.zeros_like(cleaned)
        for cnt in contours:
            if cv2.contourArea(cnt) >= min_contour_area:
                cv2.drawContours(filtered_mask, [cnt], -1, 255, cv2.FILLED)
        cleaned = filtered_mask

    return cleaned


# ------------------------------------------------------------------
# Core segmentation algorithms
# ------------------------------------------------------------------


def _segment_adaptive(
    gray: np.ndarray,
    block_size: int,
    c: int,
) -> np.ndarray:
    """Adaptive Gaussian thresholding."""
    block = block_size if block_size % 2 == 1 and block_size >= 3 else 11
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block,
        c,
    )
    return binary


def _segment_otsu(gray: np.ndarray) -> np.ndarray:
    """Otsu's automatic thresholding."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _segment_background_subtraction(
    gray: np.ndarray,
    background: np.ndarray,
    diff_threshold: int,
) -> np.ndarray:
    """Subtract a reference background and threshold the absolute
    difference.

    Args:
        gray: Grayscale image of the current layer.
        background: Grayscale reference background (no printed piece).
        diff_threshold: Minimum pixel-difference to consider foreground.

    Returns:
        Binary mask (``uint8``, 0/255).
    """
    bg_gray = _ensure_grayscale(background)

    # Ensure same size
    if bg_gray.shape != gray.shape:
        bg_gray = cv2.resize(bg_gray, (gray.shape[1], gray.shape[0]))

    diff = cv2.absdiff(gray, bg_gray)
    _, binary = cv2.threshold(diff, diff_threshold, 255, cv2.THRESH_BINARY)
    return binary


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def segment_image(
    image: np.ndarray,
    method: SegmentationMethod = SegmentationMethod.ADAPTIVE,
    params: Optional[SegmentationParams] = None,
) -> np.ndarray:
    """Segment the printed piece from the background in a single image.

    Args:
        image: Input image (BGR or grayscale).
        method: Segmentation algorithm. Overridden by ``params.method``
            if *params* is supplied.
        params: Full parameter set. If ``None``, defaults are used.

    Returns:
        Binary mask as a ``uint8`` NumPy array (0 = background,
        255 = foreground).

    Raises:
        ValueError: If ``method`` is ``BACKGROUND_SUBTRACTION`` but no
            ``background_image`` has been provided in *params*.
    """
    if params is None:
        params = SegmentationParams(method=method)

    effective_method = params.method

    gray = _ensure_grayscale(image)
    gray = _apply_blur(gray, params.gaussian_blur_ksize)

    if effective_method == SegmentationMethod.ADAPTIVE:
        binary = _segment_adaptive(gray, params.block_size, params.c)
    elif effective_method == SegmentationMethod.OTSU:
        binary = _segment_otsu(gray)
    elif effective_method == SegmentationMethod.BACKGROUND_SUBTRACTION:
        if params.background_image is None:
            raise ValueError(
                "Background subtraction requires a reference background_image "
                "in SegmentationParams."
            )
        binary = _segment_background_subtraction(
            gray, params.background_image, params.diff_threshold
        )
    else:
        logger.warning(
            "Unknown segmentation method '%s'; falling back to adaptive.",
            effective_method,
        )
        binary = _segment_adaptive(gray, params.block_size, params.c)

    # Invert if requested (e.g. dark piece on light background)
    if params.invert:
        binary = cv2.bitwise_not(binary)

    # Morphological cleanup
    mask = _morphological_cleanup(
        binary, params.kernel_size, params.min_contour_area
    )

    return mask


def segment_batch(
    images: List[np.ndarray],
    method: SegmentationMethod = SegmentationMethod.ADAPTIVE,
    params: Optional[SegmentationParams] = None,
    per_layer_overrides: Optional[Dict[int, SegmentationParams]] = None,
) -> List[np.ndarray]:
    """Segment a batch of images, with optional per-layer parameter
    overrides.

    Args:
        images: List of input images (BGR or grayscale).
        method: Default segmentation method.
        params: Default parameter set applied to all layers unless
            overridden.
        per_layer_overrides: A dictionary mapping *layer index* (0-based
            position in *images*) to a :class:`SegmentationParams` object
            that overrides the defaults for that specific layer.

    Returns:
        A list of binary masks (same length as *images*).
    """
    if params is None:
        params = SegmentationParams(method=method)
    if per_layer_overrides is None:
        per_layer_overrides = {}

    masks: list[np.ndarray] = []
    total = len(images)

    for idx, img in enumerate(images):
        layer_params = per_layer_overrides.get(idx, params)
        mask = segment_image(img, params=layer_params)
        masks.append(mask)

        if (idx + 1) % max(1, total // 10) == 0 or idx == total - 1:
            logger.info("Segmented %d / %d layers.", idx + 1, total)

    return masks
