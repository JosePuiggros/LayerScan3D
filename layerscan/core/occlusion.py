"""Occlusion detection for LayerScan3D.

RF-07b: Detect layers with possible occlusion. Compare area between consecutive layers,
flag sudden drops, generate confidence scores per layer.
"""

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from layerscan.core.contour_extraction import LayerContour
from layerscan.utils.logger import get_logger

logger = get_logger("core.occlusion")

@dataclass
class OcclusionReport:
    """Report containing occlusion confidence scores for layers."""
    per_layer_confidence: Dict[int, float] = field(default_factory=dict)
    flagged_layers: List[int] = field(default_factory=list)

class OcclusionDetector:
    """Detects likely occlusions by analyzing contour variation between layers."""
    
    def __init__(self, area_drop_threshold: float = 0.3, confidence_threshold: float = 0.7):
        """
        Initialize the detector.
        
        Args:
            area_drop_threshold: Fraction (0 to 1) representing the maximum allowable
                                 drop in area from one layer to the next before flagging.
            confidence_threshold: Minimum confidence score to not flag a layer.
        """
        self.area_drop_threshold = area_drop_threshold
        self.confidence_threshold = confidence_threshold

    def detect(self, contours: List[LayerContour]) -> OcclusionReport:
        """
        Analyze a sequence of layer contours and generate an occlusion report.
        
        Args:
            contours: List of extracted layer contours sorted by Z height.
            
        Returns:
            OcclusionReport containing confidence scores and flagged layer indices.
        """
        report = OcclusionReport()
        if not contours:
            return report

        # Assuming contours are ordered. If only one contour, confidence is 1.0.
        report.per_layer_confidence[0] = 1.0
        
        for i in range(1, len(contours)):
            prev = contours[i-1]
            curr = contours[i]
            
            confidence = 1.0
            
            # 1. Area Drop Check
            # If the current area is significantly smaller than the previous area,
            # it might be because the print head or an overhang occluded the view.
            if prev.area_mm2 > 0:
                area_ratio = curr.area_mm2 / prev.area_mm2
                if area_ratio < (1.0 - self.area_drop_threshold):
                    # Reduce confidence proportionally to the drop beyond the threshold
                    drop_severity = (1.0 - area_ratio) - self.area_drop_threshold
                    confidence -= drop_severity * 2.0  # arbitrary penalty scaling
                    logger.warning(f"Sudden area drop at layer {i} (Z={curr.z_height:.2f}). "
                                   f"Ratio: {area_ratio:.2f}")

            # Note: Hu moments could be added here for more complex shape similarity checking
            
            # Bound confidence between 0 and 1
            confidence = max(0.0, min(1.0, confidence))
            report.per_layer_confidence[i] = confidence
            
            # If confidence is below threshold, flag the layer
            if confidence < self.confidence_threshold:
                report.flagged_layers.append(i)
                
        logger.info(f"Occlusion detection complete. Flagged {len(report.flagged_layers)} layers.")
        return report
