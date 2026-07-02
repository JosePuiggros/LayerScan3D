"""
QThread-based worker classes for LayerScan3D background processing.

Provides thread workers for pipeline execution, calibration, segmentation,
generic callables, and export operations. All workers support cancellation,
progress reporting via Qt signals, and structured error handling.
"""

import traceback
from typing import Any, Callable

try:
    from PySide6.QtCore import QThread, Signal as pyqtSignal
except ImportError:
    pass

from layerscan.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineWorker(QThread):
    """
    Worker thread for running a full processing pipeline.

    Signals
    -------
    progress : float, str
        Emitted with (percentage 0–100, status message).
    finished : object
        Emitted with the pipeline result on success.
    error : str
        Emitted with error message on failure.
    """

    progress = pyqtSignal(float, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, pipeline: Any, parent: Any = None) -> None:
        """
        Initialize the pipeline worker.

        Parameters
        ----------
        pipeline : object
            A pipeline object that exposes a ``run(progress_callback)`` method.
            The callback signature should be ``(float, str) -> None``.
        parent : QObject, optional
            Parent Qt object.
        """
        super().__init__(parent)
        self._pipeline = pipeline
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the pipeline run."""
        self._cancelled = True
        logger.info("PipelineWorker: cancellation requested")

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._cancelled

    def _progress_callback(self, value: float, message: str) -> None:
        """
        Internal progress callback passed to the pipeline.

        Emits the progress signal unless cancelled.

        Parameters
        ----------
        value : float
            Progress percentage (0–100).
        message : str
            Human-readable status message.
        """
        if not self._cancelled:
            self.progress.emit(value, message)

    def run(self) -> None:
        """Execute the pipeline in the background thread."""
        try:
            logger.info("PipelineWorker: starting pipeline execution")
            if hasattr(self._pipeline, 'set_progress_callback'):
                self._pipeline.set_progress_callback(self._progress_callback)
            result = self._pipeline.run()

            if self._cancelled:
                logger.info("PipelineWorker: cancelled during execution")
                self.error.emit("Pipeline execution was cancelled.")
                return

            logger.info("PipelineWorker: pipeline completed successfully")
            self.finished.emit(result)

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("PipelineWorker error: %s\n%s", exc, tb)
            self.error.emit(f"Pipeline error: {exc}")


class CalibrationWorker(QThread):
    """
    Worker thread for running calibration procedures.

    Signals
    -------
    progress : str
        Emitted with a status message during calibration steps.
    finished : object
        Emitted with the calibration result on success.
    error : str
        Emitted with error message on failure.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        calibrator: Any,
        method: str,
        parent: Any = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the calibration worker.

        Parameters
        ----------
        calibrator : object
            A calibrator object that exposes calibration methods by name.
        method : str
            Name of the calibration method to invoke on the calibrator.
        parent : QObject, optional
            Parent Qt object.
        **kwargs
            Additional keyword arguments passed to the calibration method.
        """
        super().__init__(parent)
        self._calibrator = calibrator
        self._method = method
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the calibration."""
        self._cancelled = True
        logger.info("CalibrationWorker: cancellation requested")

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._cancelled

    def run(self) -> None:
        """Execute the calibration method in the background thread."""
        try:
            logger.info(
                "CalibrationWorker: starting calibration method '%s'",
                self._method,
            )
            self.progress.emit(f"Starting calibration: {self._method}")

            calibration_fn = getattr(self._calibrator, self._method)
            result = calibration_fn(**self._kwargs)

            if self._cancelled:
                logger.info("CalibrationWorker: cancelled during execution")
                self.error.emit("Calibration was cancelled.")
                return

            logger.info("CalibrationWorker: calibration completed")
            self.progress.emit("Calibration complete.")
            self.finished.emit(result)

        except AttributeError:
            msg = (
                f"Calibration method '{self._method}' not found "
                f"on calibrator {type(self._calibrator).__name__}"
            )
            logger.error("CalibrationWorker: %s", msg)
            self.error.emit(msg)

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("CalibrationWorker error: %s\n%s", exc, tb)
            self.error.emit(f"Calibration error: {exc}")


class SegmentationWorker(QThread):
    """
    Worker thread for batch image segmentation.

    Signals
    -------
    progress : int, int
        Emitted with (current_index, total_count) for each processed image.
    finished : object
        Emitted with the list of segmentation results on success.
    error : str
        Emitted with error message on failure.
    """

    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        segmenter: Any,
        images: list,
        method: str,
        params: dict | None = None,
        parent: Any = None,
    ) -> None:
        """
        Initialize the segmentation worker.

        Parameters
        ----------
        segmenter : object
            A segmenter object exposing a ``segment(image, method, **params)``
            method.
        images : list
            List of images (numpy arrays or paths) to segment.
        method : str
            Segmentation method name to use.
        params : dict, optional
            Additional parameters passed to the segmentation method.
        parent : QObject, optional
            Parent Qt object.
        """
        super().__init__(parent)
        self._segmenter = segmenter
        self._images = images
        self._method = method
        self._params = params or {}
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the segmentation batch."""
        self._cancelled = True
        logger.info("SegmentationWorker: cancellation requested")

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._cancelled

    def run(self) -> None:
        """Execute batch segmentation in the background thread."""
        try:
            total = len(self._images)
            logger.info(
                "SegmentationWorker: starting segmentation of %d images "
                "with method '%s'",
                total,
                self._method,
            )

            results = []

            for idx, image in enumerate(self._images):
                if self._cancelled:
                    logger.info(
                        "SegmentationWorker: cancelled at image %d/%d",
                        idx + 1,
                        total,
                    )
                    self.error.emit(
                        f"Segmentation cancelled at image {idx + 1}/{total}."
                    )
                    return

                result = self._segmenter.segment(
                    image,
                    self._method,
                    **self._params,
                )
                results.append(result)

                self.progress.emit(idx + 1, total)
                logger.debug(
                    "SegmentationWorker: processed image %d/%d",
                    idx + 1,
                    total,
                )

            logger.info(
                "SegmentationWorker: completed %d images", total
            )
            self.finished.emit(results)

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("SegmentationWorker error: %s\n%s", exc, tb)
            self.error.emit(f"Segmentation error: {exc}")


class GenericWorker(QThread):
    """
    Worker thread for executing an arbitrary callable in the background.

    Signals
    -------
    finished : object
        Emitted with the return value of the callable on success.
    error : str
        Emitted with error message on failure.
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(
        self,
        fn: Callable,
        *args: Any,
        parent: Any = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the generic worker.

        Parameters
        ----------
        fn : callable
            The function or callable to execute in the background.
        *args
            Positional arguments to pass to the callable.
        parent : QObject, optional
            Parent Qt object.
        **kwargs
            Keyword arguments to pass to the callable.
        """
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the worker."""
        self._cancelled = True
        logger.info("GenericWorker: cancellation requested")

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._cancelled

    def run(self) -> None:
        """Execute the callable in the background thread."""
        try:
            fn_name = getattr(self._fn, '__name__', repr(self._fn))
            logger.info("GenericWorker: executing '%s'", fn_name)

            result = self._fn(*self._args, **self._kwargs)

            if self._cancelled:
                logger.info("GenericWorker: cancelled during execution")
                self.error.emit("Operation was cancelled.")
                return

            logger.info("GenericWorker: '%s' completed", fn_name)
            self.finished.emit(result)

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("GenericWorker error: %s\n%s", exc, tb)
            self.error.emit(f"Operation error: {exc}")


class ExportWorker(QThread):
    """
    Worker thread for export operations with progress tracking.

    Signals
    -------
    progress : float, str
        Emitted with (percentage 0–100, status message).
    finished : str
        Emitted with the output file path on success.
    error : str
        Emitted with error message on failure.
    """

    progress = pyqtSignal(float, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        export_fn: Callable,
        parent: Any = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the export worker.

        Parameters
        ----------
        export_fn : callable
            An export function that accepts a ``progress_callback`` keyword
            argument with signature ``(float, str) -> None`` and returns
            the output file path as a string.
        parent : QObject, optional
            Parent Qt object.
        **kwargs
            Additional keyword arguments passed to the export function.
        """
        super().__init__(parent)
        self._export_fn = export_fn
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the export."""
        self._cancelled = True
        logger.info("ExportWorker: cancellation requested")

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._cancelled

    def _progress_callback(self, value: float, message: str) -> None:
        """
        Internal progress callback passed to the export function.

        Parameters
        ----------
        value : float
            Progress percentage (0–100).
        message : str
            Human-readable status message.
        """
        if not self._cancelled:
            self.progress.emit(value, message)

    def run(self) -> None:
        """Execute the export function in the background thread."""
        try:
            fn_name = getattr(
                self._export_fn, '__name__', repr(self._export_fn)
            )
            logger.info("ExportWorker: starting export '%s'", fn_name)

            output_path = self._export_fn(
                progress_callback=self._progress_callback,
                **self._kwargs,
            )

            if self._cancelled:
                logger.info("ExportWorker: cancelled during export")
                self.error.emit("Export was cancelled.")
                return

            logger.info(
                "ExportWorker: export completed -> %s", output_path
            )
            self.finished.emit(str(output_path))

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("ExportWorker error: %s\n%s", exc, tb)
            self.error.emit(f"Export error: {exc}")
