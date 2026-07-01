"""Camera calibration for LayerScan3D.

RF-02, RF-03: Chessboard-based camera calibration, manual scale input,
lens distortion correction, and calibration profile persistence.
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from layerscan.utils.config import CalibrationProfile
from layerscan.utils.logger import get_logger

logger = get_logger("core.calibration")


class CameraCalibrator:
    """Camera calibration utility for computing mm/pixel scale and
    correcting lens distortion.

    The calibrator supports two workflows:

    1. **Chessboard calibration** – uses a set of images containing a
       printed chessboard pattern of known physical dimensions to compute
       the full camera intrinsic matrix and distortion coefficients.
    2. **Manual scale** – the user provides a known physical distance and
       the corresponding pixel distance to derive a simple mm/pixel ratio.

    Calibration results can be saved to and loaded from JSON files via
    :class:`~layerscan.utils.config.CalibrationProfile`.

    Attributes:
        camera_matrix: 3×3 intrinsic camera matrix (``None`` until
            :meth:`calibrate_from_chessboard` succeeds).
        dist_coeffs: Distortion coefficient vector (``None`` until
            :meth:`calibrate_from_chessboard` succeeds).
        scale_mm_per_pixel: Spatial resolution in mm per pixel.
        image_size: ``(width, height)`` of the calibration images.
    """

    def __init__(self) -> None:
        self.camera_matrix: Optional[np.ndarray] = None
        self.dist_coeffs: Optional[np.ndarray] = None
        self.scale_mm_per_pixel: float = 1.0
        self.image_size: Optional[Tuple[int, int]] = None
        self._optimal_camera_matrix: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Chessboard calibration
    # ------------------------------------------------------------------

    def calibrate_from_chessboard(
        self,
        image_paths: List[str],
        board_size: Tuple[int, int] = (9, 6),
        square_size_mm: float = 25.0,
        show_corners: bool = False,
    ) -> float:
        """Calibrate the camera from a set of chessboard images.

        The method uses OpenCV's ``findChessboardCorners`` and
        ``calibrateCamera`` to compute the intrinsic matrix and
        distortion coefficients. The mm/pixel scale is derived from the
        mean reprojection of the known square size.

        Args:
            image_paths: List of filesystem paths to calibration images.
            board_size: Number of *inner corners* per row and column of
                the chessboard (e.g. ``(9, 6)`` for a 10×7 square board).
            square_size_mm: Physical side-length of one chessboard square
                in millimetres.
            show_corners: If ``True``, each image with detected corners is
                displayed via ``cv2.imshow`` (useful for debugging).

        Returns:
            The mean reprojection error in pixels.

        Raises:
            ValueError: If fewer than 3 images with valid corners are
                available (OpenCV requires a minimum of 3).
        """
        obj_point = np.zeros((board_size[0] * board_size[1], 3), np.float32)
        obj_point[:, :2] = (
            np.mgrid[0 : board_size[0], 0 : board_size[1]]
            .T.reshape(-1, 2)
            .astype(np.float32)
            * square_size_mm
        )

        obj_points: list[np.ndarray] = []
        img_points: list[np.ndarray] = []
        image_size: Optional[Tuple[int, int]] = None

        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            30,
            0.001,
        )

        for path_str in image_paths:
            img = cv2.imread(path_str)
            if img is None:
                logger.warning("Could not read calibration image '%s'; skipping.", path_str)
                continue

            gray = (
                cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if len(img.shape) == 3
                else img
            )
            if image_size is None:
                image_size = (gray.shape[1], gray.shape[0])

            found, corners = cv2.findChessboardCorners(gray, board_size, None)
            if not found:
                logger.warning(
                    "Chessboard corners not found in '%s'; skipping.",
                    path_str,
                )
                continue

            # Sub-pixel refinement
            corners_refined = cv2.cornerSubPix(
                gray, corners, (11, 11), (-1, -1), criteria
            )

            obj_points.append(obj_point)
            img_points.append(corners_refined)

            if show_corners:
                vis = img.copy()
                cv2.drawChessboardCorners(vis, board_size, corners_refined, found)
                cv2.imshow("Chessboard Corners", vis)
                cv2.waitKey(500)

        if show_corners:
            cv2.destroyAllWindows()

        if len(obj_points) < 3:
            raise ValueError(
                f"Only {len(obj_points)} valid chessboard image(s) found; "
                "at least 3 are required for calibration."
            )

        logger.info(
            "Running calibration with %d valid images...", len(obj_points)
        )

        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            obj_points, img_points, image_size, None, None
        )

        self.camera_matrix = mtx
        self.dist_coeffs = dist
        self.image_size = image_size

        # Compute optimal new camera matrix
        w, h = image_size
        new_mtx, _roi = cv2.getOptimalNewCameraMatrix(
            mtx, dist, (w, h), 1, (w, h)
        )
        self._optimal_camera_matrix = new_mtx

        # Derive mm/pixel scale from the focal length and the mean distance
        # to the chessboard plane.  A simpler approach: use the mean
        # reprojected distance between adjacent corners versus the known
        # square_size_mm.
        self.scale_mm_per_pixel = self._compute_scale_from_corners(
            obj_points, img_points, rvecs, tvecs, mtx, dist, square_size_mm, board_size
        )

        logger.info(
            "Calibration complete. RMS error: %.4f px, scale: %.6f mm/px.",
            ret,
            self.scale_mm_per_pixel,
        )

        return float(ret)

    @staticmethod
    def _compute_scale_from_corners(
        obj_points: list[np.ndarray],
        img_points: list[np.ndarray],
        rvecs: list[np.ndarray],
        tvecs: list[np.ndarray],
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        square_size_mm: float,
        board_size: Tuple[int, int],
    ) -> float:
        """Compute the average mm/pixel scale from calibrated corner data.

        For each image the reprojected pixel positions of adjacent corners
        are compared against the known physical square size.

        Returns:
            Mean mm/pixel scale across all images and corner pairs.
        """
        pixel_distances: list[float] = []
        cols = board_size[0]

        for obj_pts, img_pts in zip(obj_points, img_points):
            projected, _ = cv2.projectPoints(
                obj_pts, np.zeros(3), np.zeros(3),
                camera_matrix, dist_coeffs,
            )
            projected = projected.reshape(-1, 2)

            # Horizontal neighbours
            for i in range(len(projected)):
                if (i + 1) % cols != 0 and (i + 1) < len(projected):
                    d = float(np.linalg.norm(projected[i + 1] - projected[i]))
                    pixel_distances.append(d)

        if not pixel_distances:
            return 1.0

        mean_px = float(np.mean(pixel_distances))
        return square_size_mm / mean_px if mean_px > 0 else 1.0

    # ------------------------------------------------------------------
    # Manual scale
    # ------------------------------------------------------------------

    def calibrate_manual_scale(
        self,
        known_distance_mm: float,
        pixel_distance: float,
    ) -> float:
        """Set the mm/pixel scale from a user-provided measurement.

        This is the simplest calibration method: the user measures a known
        physical distance in the image (e.g. a ruler) and reports both the
        real-world distance and the corresponding pixel distance.

        Args:
            known_distance_mm: The known physical distance in millimetres.
            pixel_distance: The measured distance in pixels.

        Returns:
            The resulting mm/pixel scale.

        Raises:
            ValueError: If either distance is not positive.
        """
        if known_distance_mm <= 0 or pixel_distance <= 0:
            raise ValueError(
                "Both known_distance_mm and pixel_distance must be positive."
            )

        self.scale_mm_per_pixel = known_distance_mm / pixel_distance
        logger.info(
            "Manual scale set: %.2f mm / %.1f px = %.6f mm/px.",
            known_distance_mm,
            pixel_distance,
            self.scale_mm_per_pixel,
        )
        return self.scale_mm_per_pixel

    # ------------------------------------------------------------------
    # Distortion correction
    # ------------------------------------------------------------------

    def undistort_image(self, image: np.ndarray) -> np.ndarray:
        """Remove lens distortion from *image*.

        If chessboard calibration has not been performed (i.e. the camera
        matrix and distortion coefficients are unavailable), the image is
        returned unchanged with a warning.

        Args:
            image: Input image (BGR or grayscale).

        Returns:
            The undistorted image as a NumPy array with the same shape
            and dtype as the input.
        """
        if self.camera_matrix is None or self.dist_coeffs is None:
            logger.warning(
                "No calibration data available; returning image unchanged."
            )
            return image

        if self._optimal_camera_matrix is not None:
            undistorted = cv2.undistort(
                image,
                self.camera_matrix,
                self.dist_coeffs,
                None,
                self._optimal_camera_matrix,
            )
        else:
            undistorted = cv2.undistort(
                image, self.camera_matrix, self.dist_coeffs
            )

        return undistorted

    # ------------------------------------------------------------------
    # Convenience: apply calibration
    # ------------------------------------------------------------------

    def get_scale(self) -> float:
        """Return the current mm/pixel scale.

        Returns:
            mm/pixel scale as a float.
        """
        return self.scale_mm_per_pixel

    def apply_calibration(
        self, image: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """Undistort *image* and return it together with the mm/pixel scale.

        This is a convenience wrapper combining :meth:`undistort_image` and
        :meth:`get_scale`.

        Args:
            image: Input image.

        Returns:
            A tuple ``(undistorted_image, scale_mm_per_pixel)``.
        """
        undistorted = self.undistort_image(image)
        return undistorted, self.scale_mm_per_pixel

    # ------------------------------------------------------------------
    # Persistence via CalibrationProfile
    # ------------------------------------------------------------------

    def save_profile(
        self,
        name: str = "default",
        directory: Optional[Path] = None,
        notes: str = "",
    ) -> Path:
        """Persist the current calibration state to a JSON profile.

        Args:
            name: Human-readable profile name (also used as the filename
                stem).
            directory: Directory in which to store the profile. Defaults to
                the application calibration directory.
            notes: Optional free-text notes.

        Returns:
            The :class:`pathlib.Path` to the saved JSON file.
        """
        profile = CalibrationProfile(name=name)
        profile.data["scale_mm_per_pixel"] = self.scale_mm_per_pixel
        profile.data["camera_matrix"] = (
            self.camera_matrix.tolist() if self.camera_matrix is not None else None
        )
        profile.data["dist_coeffs"] = (
            self.dist_coeffs.tolist() if self.dist_coeffs is not None else None
        )
        profile.data["image_size"] = (
            list(self.image_size) if self.image_size is not None else None
        )
        profile.data["notes"] = notes

        save_dir = Path(directory) if directory else None
        filepath = profile.save(directory=save_dir)
        logger.info("Calibration profile saved as '%s'.", name)
        return Path(filepath)

    def load_profile(self, filepath: str) -> None:
        """Restore calibration state from a previously saved JSON profile.

        Args:
            filepath: Path to the JSON profile file.

        Raises:
            FileNotFoundError: If *filepath* does not exist.
        """
        if not Path(filepath).exists():
            raise FileNotFoundError(
                f"Calibration profile not found: {filepath}"
            )

        profile = CalibrationProfile.load(filepath)
        self.scale_mm_per_pixel = float(
            profile.data.get("scale_mm_per_pixel", 1.0)
        )

        cam = profile.data.get("camera_matrix")
        self.camera_matrix = np.array(cam, dtype=np.float64) if cam is not None else None

        dist = profile.data.get("dist_coeffs")
        self.dist_coeffs = np.array(dist, dtype=np.float64) if dist is not None else None

        img_size = profile.data.get("image_size")
        self.image_size = tuple(img_size) if img_size is not None else None

        # Recompute optimal matrix if possible
        if (
            self.camera_matrix is not None
            and self.dist_coeffs is not None
            and self.image_size is not None
        ):
            w, h = self.image_size
            new_mtx, _ = cv2.getOptimalNewCameraMatrix(
                self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h)
            )
            self._optimal_camera_matrix = new_mtx
        else:
            self._optimal_camera_matrix = None

        logger.info(
            "Loaded calibration profile '%s' (scale=%.6f mm/px).",
            profile.name,
            self.scale_mm_per_pixel,
        )
