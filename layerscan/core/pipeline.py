"""Orchestrator pipeline for LayerScan3D.

Coordinates the end-to-end processing: image loading, calibration, segmentation,
reconstruction, comparison, and reporting.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, List, Any
import traceback

import numpy as np
import trimesh

from layerscan.core.image_loader import load_images, LayerImage
from layerscan.core.calibration import CameraCalibrator
from layerscan.core.segmentation import segment_batch, SegmentationMethod
from layerscan.core.contour_extraction import ContourExtractor, LayerContour
from layerscan.core.occlusion import OcclusionDetector, OcclusionReport
from layerscan.core.reconstruction import MeshReconstructor
from layerscan.core.mesh_io import MeshIO
from layerscan.core.gcode_parser import GCodeParser, GCodeData
from layerscan.core.alignment import ModelAligner, AlignmentResult
from layerscan.core.comparison import ModelComparator, ComparisonResult
from layerscan.core.anomaly_detection import AnomalyDetector, AnomalyReport
from layerscan.core.quality_score import QualityScorer, QualityReport
from layerscan.utils.config import Config, ProjectConfig
from layerscan.utils.logger import get_logger

logger = get_logger("core.pipeline")

@dataclass
class PipelineResult:
    """Container for all artifacts produced during the pipeline execution."""
    images: List[LayerImage] = field(default_factory=list)
    contours: List[LayerContour] = field(default_factory=list)
    reconstructed_mesh: Optional[trimesh.Trimesh] = None
    reference_mesh: Optional[trimesh.Trimesh] = None
    gcode_data: Optional[GCodeData] = None
    alignment: Optional[AlignmentResult] = None
    comparison: Optional[ComparisonResult] = None
    occlusion: Optional[OcclusionReport] = None
    anomalies: Optional[AnomalyReport] = None
    quality: Optional[QualityReport] = None
    error: Optional[str] = None

class ProcessingPipeline:
    """End-to-end processing pipeline orchestrator."""

    def __init__(self, project_config: ProjectConfig, app_config: Config):
        self.project_config = project_config
        self.app_config = app_config
        self.progress_callback: Optional[Callable[[float, str], None]] = None

    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set a function to be called to report progress (0.0 to 100.0, msg)."""
        self.progress_callback = callback

    def _report_progress(self, percent: float, message: str):
        logger.info(f"Pipeline [{percent:.1f}%]: {message}")
        if self.progress_callback:
            self.progress_callback(percent, message)

    def run(self) -> PipelineResult:
        """Execute the full pipeline based on project configuration."""
        result = PipelineResult()
        try:
            p_cfg = self.project_config.data
            
            # Step 1: Parse G-Code (optional)
            self._report_progress(5.0, "Parsing G-code (if provided)...")
            gcode_file = p_cfg.get("gcode_file")
            expected_layers = 0
            if gcode_file and gcode_file.strip():
                parser = GCodeParser()
                result.gcode_data = parser.parse(gcode_file)
                expected_layers = result.gcode_data.layer_count
                
            # Step 2: Load Images
            self._report_progress(10.0, "Loading images...")
            img_dir = p_cfg.get("images_dir")
            if not img_dir:
                raise ValueError("Images directory is required.")
                
            # If G-code layer height is known, use it, else use default manual
            default_layer_h = float(p_cfg.get("layer_height_mm", 0.2))
            result.images = load_images(
                img_dir, 
                expected_count=expected_layers if expected_layers > 0 else None,
                layer_height_mm=default_layer_h
            )
            
            if not result.images:
                raise ValueError("No valid images loaded.")

            # Step 3: Load Calibration
            self._report_progress(20.0, "Applying calibration...")
            # For simplicity in this implementation, we assume calibration scale is applied during contour extraction
            # and images are undistorted here if needed.
            calib_profile_name = p_cfg.get("calibration_profile")
            scale_mm_per_px = float(p_cfg.get("scale_mm_per_px", 1.0))
            if calib_profile_name:
                calibrator = CameraCalibrator()
                try:
                    calibrator.load_profile(calib_profile_name)
                    scale_mm_per_px = calibrator.get_scale()
                except Exception as e:
                    logger.warning(f"Could not load calibration profile '{calib_profile_name}': {e}")
                
            # Step 4: Segment Images
            self._report_progress(30.0, "Segmenting images...")
            # The layer images are already binary (0 and 255 only), so we
            # threshold directly. Using segment_batch with morphological
            # cleanup would fill in fine internal structures (Gyroid pores).
            import cv2
            masks = []
            for img in result.images:
                gray = img.image
                if len(gray.shape) == 3:
                    gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
                mask = (gray > 127).astype(np.uint8) * 255
                masks.append(mask)
            
            # Step 5: Extract Contours
            self._report_progress(45.0, "Extracting contours...")
            extractor = ContourExtractor()
            
            for i, mask in enumerate(masks):
                # Apply z_height from loaded images
                z_h = result.images[i].z_height
                contours_list = extractor.extract_from_mask(mask, scale_override=scale_mm_per_px, z_height=z_h)
                if contours_list:
                    result.contours.extend(contours_list)
                    
            if not result.contours:
                raise ValueError("No contours could be extracted.")

            # Step 6: Occlusion Detection
            self._report_progress(55.0, "Detecting occlusions...")
            occ_detector = OcclusionDetector()
            result.occlusion = occ_detector.detect(result.contours)
            
            # Step 7: 3D Reconstruction
            self._report_progress(60.0, "Reconstructing 3D mesh...")
            reconstructor = MeshReconstructor()
            z_heights = [img.z_height for img in result.images]
            result.reconstructed_mesh = reconstructor.reconstruct(masks, z_heights, scale_mm_per_px)

            # Step 8: Load Reference STL and Compare
            stl_file = p_cfg.get("stl_file")
            if stl_file and stl_file.strip():
                self._report_progress(70.0, "Loading reference model...")
                result.reference_mesh = MeshIO.load_mesh(stl_file)
                
                self._report_progress(75.0, "Aligning models...")
                
                # Pre-align: translate reconstructed mesh so its centroid matches the reference
                src_centroid = result.reconstructed_mesh.centroid
                tgt_centroid = result.reference_mesh.centroid
                pre_translation = tgt_centroid - src_centroid
                pre_transform = np.eye(4)
                pre_transform[:3, 3] = pre_translation
                result.reconstructed_mesh.apply_transform(pre_transform)
                logger.info(
                    "Pre-alignment translation: [%.3f, %.3f, %.3f]",
                    pre_translation[0], pre_translation[1], pre_translation[2],
                )
                
                # Try multiple initial rotations around Z to find the best one.
                # The camera orientation relative to the STL is unknown, so we
                # test every 15° and pick the rotation with the lowest ICP error.
                best_error = float("inf")
                best_transform = np.eye(4)
                best_alignment = None
                center = result.reconstructed_mesh.centroid.copy()
                mesh_backup = result.reconstructed_mesh.copy()
                
                for angle_deg in range(0, 360, 15):
                    candidate = mesh_backup.copy()
                    
                    # Build rotation around centroid
                    angle_rad = np.radians(angle_deg)
                    c, s = np.cos(angle_rad), np.sin(angle_rad)
                    T1 = np.eye(4); T1[:3, 3] = -center
                    R = np.eye(4); R[0,0] = c; R[0,1] = -s; R[1,0] = s; R[1,1] = c
                    T2 = np.eye(4); T2[:3, 3] = center
                    rot_transform = T2 @ R @ T1
                    candidate.apply_transform(rot_transform)
                    
                    aligner = ModelAligner(constrain_z=False, max_iterations=50)
                    alignment = aligner.align(source=candidate, target=result.reference_mesh)
                    
                    if alignment.mean_error < best_error:
                        best_error = alignment.mean_error
                        best_transform = alignment.transformation_matrix @ rot_transform
                        best_alignment = alignment
                        logger.debug(
                            "New best rotation: %d° (error=%.4f mm)",
                            angle_deg, best_error,
                        )
                
                result.alignment = best_alignment
                logger.info(
                    "Best alignment found: rotation=%.1f°, error=%.4f mm",
                    best_alignment.rotation_angle_deg, best_error,
                )
                
                # Apply best combined transform to the original pre-aligned mesh
                result.reconstructed_mesh = mesh_backup
                result.reconstructed_mesh.apply_transform(best_transform)
                
                self._report_progress(85.0, "Calculating comparisons...")
                tolerance = p_cfg.get("tolerance_mm", self.app_config.get("default_tolerance_mm", 0.2))
                comparator = ModelComparator(tolerance_mm=tolerance)
                result.comparison = comparator.compare(result.reconstructed_mesh, result.reference_mesh)
            
            # Step 9: Anomaly Detection
            self._report_progress(90.0, "Detecting anomalies...")
            anomaly_detector = AnomalyDetector()
            result.anomalies = anomaly_detector.detect_all(result.contours)
            
            # Step 10: Quality Score
            self._report_progress(95.0, "Calculating quality score...")
            scorer = QualityScorer(config=self.app_config)
            
            expected_total = expected_layers if expected_layers > 0 else len(result.images)
            if result.comparison and result.anomalies:
                result.quality = scorer.calculate(
                    result.comparison, result.anomalies, 
                    total_layers_processed=len(result.contours), 
                    total_layers_expected=expected_total
                )
                
            self._report_progress(100.0, "Pipeline finished successfully.")
            
        except Exception as e:
            err_msg = f"Pipeline failed: {str(e)}"
            logger.error(f"{err_msg}\n{traceback.format_exc()}")
            result.error = err_msg
            self._report_progress(100.0, err_msg)
            
        return result
