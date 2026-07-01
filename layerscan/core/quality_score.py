"""Quality score calculation for LayerScan3D.

Calculates a global quality score 0-100 based on dimensional accuracy,
layer accuracy, anomaly penalties, and completeness.
"""

from dataclasses import dataclass, field
from typing import Dict, Any

from layerscan.core.comparison import ComparisonResult
from layerscan.core.anomaly_detection import AnomalyReport
from layerscan.utils.config import Config
from layerscan.utils.logger import get_logger

logger = get_logger("core.quality_score")

@dataclass
class QualityReport:
    """Report containing the final quality score and its components."""
    overall_score: float
    component_scores: Dict[str, float]
    grade: str
    grade_color: str
    details: Dict[str, Any] = field(default_factory=dict)

class QualityScorer:
    """Calculates the overall print quality score based on multiple metrics."""
    
    def __init__(self, config: Config):
        """
        Initialize the scorer with weights and settings from config.
        """
        self.config = config
        
        # Load weights from config
        weights = config.get("quality_score", {})
        self.w_dimensional = weights.get("weight_dimensional_error", 0.35)
        self.w_layer = weights.get("weight_layer_accuracy", 0.25)
        self.w_anomaly = weights.get("weight_anomaly_penalty", 0.25)
        self.w_completeness = weights.get("weight_completeness", 0.15)
        
        # Normalize weights just in case
        total = self.w_dimensional + self.w_layer + self.w_anomaly + self.w_completeness
        if total > 0:
            self.w_dimensional /= total
            self.w_layer /= total
            self.w_anomaly /= total
            self.w_completeness /= total

    def calculate(
        self, 
        comparison: ComparisonResult, 
        anomalies: AnomalyReport,
        total_layers_processed: int,
        total_layers_expected: int
    ) -> QualityReport:
        """
        Calculate the global quality score.
        
        Args:
            comparison: The result from ModelComparator
            anomalies: The report from AnomalyDetector
            total_layers_processed: Number of successfully processed layers
            total_layers_expected: Expected number of layers (from G-code, or equal to processed if no G-code)
            
        Returns:
            QualityReport object.
        """
        component_scores = {}
        
        # 1. Dimensional Accuracy (0-100)
        # Based on percentage of points within user tolerance
        dim_acc = comparison.points_within_tolerance_pct
        component_scores['dimensional_accuracy'] = dim_acc
        
        # 2. Layer Accuracy (0-100)
        # Based on how many layers are within tolerance in Z and XY
        if comparison.per_layer_height_errors:
            height_errors = list(comparison.per_layer_height_errors.values())
            # layers within Z tolerance
            z_ok = sum(1 for err in height_errors if abs(err) <= comparison.tolerance_mm)
            layer_acc = (z_ok / len(height_errors)) * 100.0
        else:
            layer_acc = 100.0  # No G-code reference, assume perfect layer heights
        component_scores['layer_accuracy'] = layer_acc
        
        # 3. Anomaly Penalty (0-100, where 100 is no anomalies)
        penalty = 0.0
        for anom in anomalies.anomalies:
            if anom.severity == 'critical':
                penalty += 15.0
            elif anom.severity == 'warning':
                penalty += 5.0
            elif anom.severity == 'info':
                penalty += 1.0
                
        anomaly_score = max(0.0, 100.0 - penalty)
        component_scores['anomaly_score'] = anomaly_score
        
        # 4. Completeness (0-100)
        if total_layers_expected > 0:
            completeness = min(100.0, (total_layers_processed / total_layers_expected) * 100.0)
        else:
            completeness = 100.0
        component_scores['completeness'] = completeness
        
        # Weighted sum
        overall_score = (
            (dim_acc * self.w_dimensional) +
            (layer_acc * self.w_layer) +
            (anomaly_score * self.w_anomaly) +
            (completeness * self.w_completeness)
        )
        
        # Assign grade
        if overall_score >= 85:
            grade = "A"
            color = "#00FF00"  # Green
        elif overall_score >= 70:
            grade = "B"
            color = "#ADFF2F"  # Yellow-Green
        elif overall_score >= 50:
            grade = "C"
            color = "#FFA500"  # Orange
        elif overall_score >= 30:
            grade = "D"
            color = "#FF4500"  # Orange-Red
        else:
            grade = "F"
            color = "#FF0000"  # Red
            
        logger.info(f"Quality calculation complete. Score: {overall_score:.1f}/100 (Grade {grade})")
            
        return QualityReport(
            overall_score=overall_score,
            component_scores=component_scores,
            grade=grade,
            grade_color=color,
            details={
                "anomalies_count": anomalies.total_anomalies,
                "processed_vs_expected": f"{total_layers_processed}/{total_layers_expected}"
            }
        )
