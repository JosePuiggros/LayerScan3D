"""Anomaly detection for 3D print quality analysis.

RF-15: Detect print anomalies including missing layers, layer shifts,
and width/perimeter variations. Classifies each anomaly by severity
(info, warning, critical).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from layerscan.core.stl_slicer import SliceContour
from layerscan.utils.logger import get_logger

logger = get_logger("core.anomaly_detection")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Anomaly:
    """A single detected print anomaly.

    Attributes:
        anomaly_type: Category of anomaly. One of:
            - 'missing_layer': A layer gap was detected.
            - 'layer_shift': Lateral displacement between consecutive layers.
            - 'width_variation': Sudden change in contour perimeter or area.
        layer_number: Index of the layer where the anomaly was detected.
        severity: Severity classification: 'info', 'warning', or 'critical'.
        description: Human-readable description of the anomaly.
        measured_value: The measured value that triggered detection.
        threshold: The threshold that was exceeded.
    """

    anomaly_type: str = ""
    layer_number: int = 0
    severity: str = "info"
    description: str = ""
    measured_value: float = 0.0
    threshold: float = 0.0


@dataclass
class AnomalyReport:
    """Aggregated anomaly detection report.

    Attributes:
        total_anomalies: Total number of anomalies detected.
        anomalies: List of individual Anomaly objects.
        summary: Summary counts by type and severity, e.g.:
            {
                'by_type': {'missing_layer': 2, 'layer_shift': 1},
                'by_severity': {'warning': 2, 'critical': 1},
            }
    """

    total_anomalies: int = 0
    anomalies: list[Anomaly] = field(default_factory=list)
    summary: dict[str, dict[str, int]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class AnomalyDetector:
    """Detects anomalies in a sequence of layer contours.

    Analyses sequential contour data to identify missing layers, lateral
    shifts, and sudden changes in contour dimensions that may indicate
    print defects.

    Args:
        expected_layer_height: Nominal layer height from the slicer settings
            (mm). Used to detect missing layers. Defaults to 0.2 mm.
        shift_threshold_mm: Maximum acceptable lateral centroid displacement
            between consecutive layers (mm). Defaults to 0.5 mm.
        width_change_pct: Maximum acceptable relative change in contour
            perimeter or area between consecutive layers. Expressed as a
            fraction (e.g., 0.20 = 20%). Defaults to 0.20.
        missing_layer_factor: Factor by which the Z gap must exceed the
            expected layer height to be flagged. A gap > factor * expected
            height triggers a missing layer anomaly. Defaults to 1.5.
    """

    def __init__(
        self,
        expected_layer_height: float = 0.2,
        shift_threshold_mm: float = 0.5,
        width_change_pct: float = 0.20,
        missing_layer_factor: float = 1.5,
    ) -> None:
        self._expected_height = expected_layer_height
        self._shift_threshold = shift_threshold_mm
        self._width_change_pct = width_change_pct
        self._missing_factor = missing_layer_factor

    def detect_all(
        self,
        contours: list[SliceContour],
        planned_z_values: Optional[list[float]] = None,
    ) -> AnomalyReport:
        """Run all anomaly detection checks on a sequence of layer contours.

        Args:
            contours: List of SliceContour objects, one per detected layer,
                ordered by ascending Z height.
            planned_z_values: Optional list of planned Z values from G-code.
                If provided, used for missing layer detection by comparing
                detected vs. planned layer counts and Z gaps.

        Returns:
            AnomalyReport with all detected anomalies and summary statistics.
        """
        if not contours:
            logger.warning("No contours provided for anomaly detection")
            return AnomalyReport(summary={"by_type": {}, "by_severity": {}})

        logger.info(
            "Running anomaly detection on %d layer contours", len(contours)
        )

        anomalies: list[Anomaly] = []

        # Run detection passes
        anomalies.extend(self._detect_missing_layers(contours, planned_z_values))
        anomalies.extend(self._detect_layer_shifts(contours))
        anomalies.extend(self._detect_width_variations(contours))

        # Build summary
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for a in anomalies:
            by_type[a.anomaly_type] = by_type.get(a.anomaly_type, 0) + 1
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1

        report = AnomalyReport(
            total_anomalies=len(anomalies),
            anomalies=anomalies,
            summary={"by_type": by_type, "by_severity": by_severity},
        )

        logger.info(
            "Anomaly detection complete: %d anomalies found. "
            "By severity: %s",
            report.total_anomalies,
            by_severity,
        )

        return report

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _detect_missing_layers(
        self,
        contours: list[SliceContour],
        planned_z_values: Optional[list[float]],
    ) -> list[Anomaly]:
        """Detect missing layers by analysing gaps in Z height sequence.

        A missing layer is detected when the Z gap between consecutive
        contours exceeds the expected layer height by a configurable factor.

        If planned Z values are provided, the comparison is against the
        planned heights. Otherwise, the expected_layer_height is used.

        Args:
            contours: Ordered list of SliceContour.
            planned_z_values: Optional planned Z values from G-code.

        Returns:
            List of Anomaly objects of type 'missing_layer'.
        """
        anomalies: list[Anomaly] = []

        for i in range(1, len(contours)):
            z_gap = contours[i].z_height - contours[i - 1].z_height
            expected_gap = self._expected_height

            # If planned Z values are available, compute expected gap from them
            if planned_z_values and i < len(planned_z_values):
                expected_gap = (
                    planned_z_values[i] - planned_z_values[i - 1]
                    if i > 0
                    else self._expected_height
                )

            threshold = expected_gap * self._missing_factor

            if z_gap > threshold:
                # Estimate how many layers might be missing
                estimated_missing = max(0, round(z_gap / expected_gap) - 1)
                severity = self._classify_missing_severity(estimated_missing)

                anomalies.append(
                    Anomaly(
                        anomaly_type="missing_layer",
                        layer_number=i,
                        severity=severity,
                        description=(
                            f"Z gap of {z_gap:.3f} mm between layers {i - 1} and {i} "
                            f"exceeds expected {expected_gap:.3f} mm by factor "
                            f"{z_gap / expected_gap:.1f}x. "
                            f"~{estimated_missing} layer(s) may be missing."
                        ),
                        measured_value=round(z_gap, 4),
                        threshold=round(threshold, 4),
                    )
                )

        return anomalies

    def _detect_layer_shifts(
        self,
        contours: list[SliceContour],
    ) -> list[Anomaly]:
        """Detect lateral layer shifts by comparing contour centroids.

        A layer shift is detected when the centroid of a layer's contour
        is displaced from the previous layer's centroid by more than the
        shift threshold.

        Args:
            contours: Ordered list of SliceContour.

        Returns:
            List of Anomaly objects of type 'layer_shift'.
        """
        anomalies: list[Anomaly] = []

        prev_centroid: Optional[np.ndarray] = None

        for i, contour in enumerate(contours):
            if contour.contour_points.shape[0] < 3:
                prev_centroid = None
                continue

            centroid = np.mean(contour.contour_points, axis=0)

            if prev_centroid is not None:
                displacement = float(np.linalg.norm(centroid - prev_centroid))

                if displacement > self._shift_threshold:
                    severity = self._classify_shift_severity(displacement)

                    anomalies.append(
                        Anomaly(
                            anomaly_type="layer_shift",
                            layer_number=i,
                            severity=severity,
                            description=(
                                f"Layer {i} centroid shifted {displacement:.3f} mm "
                                f"from layer {i - 1} (threshold: "
                                f"{self._shift_threshold:.2f} mm). "
                                f"Direction: dx={centroid[0] - prev_centroid[0]:.3f}, "
                                f"dy={centroid[1] - prev_centroid[1]:.3f}."
                            ),
                            measured_value=round(displacement, 4),
                            threshold=self._shift_threshold,
                        )
                    )

            prev_centroid = centroid

        return anomalies

    def _detect_width_variations(
        self,
        contours: list[SliceContour],
    ) -> list[Anomaly]:
        """Detect sudden changes in contour perimeter or area.

        A width variation anomaly is flagged when either the perimeter or
        area changes by more than the configured percentage between
        consecutive layers.

        Args:
            contours: Ordered list of SliceContour.

        Returns:
            List of Anomaly objects of type 'width_variation'.
        """
        anomalies: list[Anomaly] = []

        for i in range(1, len(contours)):
            prev = contours[i - 1]
            curr = contours[i]

            # Check perimeter variation
            perimeter_anomaly = self._check_relative_change(
                prev.perimeter, curr.perimeter, "perimeter", i
            )
            if perimeter_anomaly:
                anomalies.append(perimeter_anomaly)

            # Check area variation
            area_anomaly = self._check_relative_change(
                prev.area, curr.area, "area", i
            )
            if area_anomaly:
                anomalies.append(area_anomaly)

        return anomalies

    def _check_relative_change(
        self,
        prev_value: float,
        curr_value: float,
        metric_name: str,
        layer_number: int,
    ) -> Optional[Anomaly]:
        """Check if the relative change between two values exceeds threshold.

        Args:
            prev_value: Previous layer's metric value.
            curr_value: Current layer's metric value.
            metric_name: Name of the metric ('perimeter' or 'area').
            layer_number: Layer index for reporting.

        Returns:
            Anomaly if threshold exceeded, None otherwise.
        """
        # Skip if either value is too small to meaningfully compare
        if prev_value < 1e-6 or curr_value < 1e-6:
            return None

        relative_change = abs(curr_value - prev_value) / prev_value

        if relative_change > self._width_change_pct:
            severity = self._classify_variation_severity(relative_change)
            pct_str = f"{relative_change * 100:.1f}%"
            threshold_pct = f"{self._width_change_pct * 100:.0f}%"

            return Anomaly(
                anomaly_type="width_variation",
                layer_number=layer_number,
                severity=severity,
                description=(
                    f"Layer {layer_number} {metric_name} changed by {pct_str} "
                    f"from layer {layer_number - 1} "
                    f"({prev_value:.2f} → {curr_value:.2f}), "
                    f"exceeding threshold of {threshold_pct}."
                ),
                measured_value=round(relative_change, 4),
                threshold=self._width_change_pct,
            )

        return None

    # ------------------------------------------------------------------
    # Severity classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_missing_severity(estimated_missing: int) -> str:
        """Classify severity of a missing layer anomaly.

        Args:
            estimated_missing: Estimated number of missing layers.

        Returns:
            Severity string: 'info', 'warning', or 'critical'.
        """
        if estimated_missing >= 3:
            return "critical"
        elif estimated_missing >= 1:
            return "warning"
        return "info"

    def _classify_shift_severity(self, displacement: float) -> str:
        """Classify severity of a layer shift anomaly.

        Args:
            displacement: Centroid displacement in mm.

        Returns:
            Severity string: 'info', 'warning', or 'critical'.
        """
        if displacement > self._shift_threshold * 3:
            return "critical"
        elif displacement > self._shift_threshold * 1.5:
            return "warning"
        return "info"

    def _classify_variation_severity(self, relative_change: float) -> str:
        """Classify severity of a width/area variation anomaly.

        Args:
            relative_change: Relative change as a fraction (e.g. 0.25 = 25%).

        Returns:
            Severity string: 'info', 'warning', or 'critical'.
        """
        if relative_change > self._width_change_pct * 3:
            return "critical"
        elif relative_change > self._width_change_pct * 2:
            return "warning"
        return "info"
