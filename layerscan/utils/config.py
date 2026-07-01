"""Configuration management for LayerScan3D projects.

Handles loading/saving calibration profiles, project settings,
and user preferences using JSON files.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

# Default application data directory
APP_DATA_DIR = Path.home() / ".layerscan3d"
DEFAULT_CALIBRATION_DIR = APP_DATA_DIR / "calibrations"
DEFAULT_PROJECTS_DIR = APP_DATA_DIR / "projects"


def ensure_app_dirs():
    """Create application data directories if they don't exist."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    """Application configuration manager."""

    DEFAULT_CONFIG = {
        "default_layer_height_mm": 0.2,
        "default_tolerance_mm": 0.2,
        "segmentation": {
            "method": "adaptive",  # "adaptive", "otsu", "background_subtraction"
            "adaptive_block_size": 11,
            "adaptive_c": 2,
            "morph_kernel_size": 5,
            "min_contour_area_px": 100,
        },
        "reconstruction": {
            "contour_simplification_epsilon": 1.0,
            "triangulation_method": "loft",
            "generate_caps": True,
        },
        "comparison": {
            "icp_max_iterations": 50,
            "icp_threshold": 1.0,
            "constrain_z_alignment": True,
        },
        "quality_score": {
            "weight_dimensional_error": 0.35,
            "weight_layer_accuracy": 0.25,
            "weight_anomaly_penalty": 0.25,
            "weight_completeness": 0.15,
        },
        "ui": {
            "theme": "dark",
            "viewer_background_color": [0.12, 0.12, 0.15],
            "heatmap_colormap": "jet",
            "show_wireframe": True,
        },
        "export": {
            "pdf_dpi": 150,
            "mesh_format": "stl",
            "data_format": "json",
        },
    }

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = Path(config_path) if config_path else APP_DATA_DIR / "config.json"
        self._config = dict(self.DEFAULT_CONFIG)
        self.load()

    def load(self):
        """Load configuration from file, creating defaults if not found."""
        ensure_app_dirs()
        if self._config_path.exists():
            try:
                with open(self._config_path, "r") as f:
                    saved = json.load(f)
                self._deep_update(self._config, saved)
                logger.info(f"Configuration loaded from {self._config_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config: {e}. Using defaults.")
        else:
            self.save()
            logger.info(f"Default configuration created at {self._config_path}")

    def save(self):
        """Save current configuration to file."""
        ensure_app_dirs()
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(self._config, f, indent=2)
        logger.info(f"Configuration saved to {self._config_path}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation (e.g., 'segmentation.method')."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """Set a config value using dot notation."""
        keys = key.split(".")
        target = self._config
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def _deep_update(self, base: dict, update: dict):
        """Recursively update base dict with update dict."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    @property
    def data(self) -> dict:
        """Return full config dict."""
        return self._config


class CalibrationProfile:
    """Manages camera calibration profiles."""

    def __init__(self, name: str = "default"):
        self.name = name
        self.data = {
            "name": name,
            "scale_mm_per_pixel": 1.0,
            "camera_matrix": None,
            "dist_coeffs": None,
            "image_size": None,
            "origin_offset_px": [0, 0],
            "z_base": 0.0,
            "notes": "",
        }

    def save(self, directory: Optional[Path] = None):
        """Save profile to JSON file."""
        save_dir = directory or DEFAULT_CALIBRATION_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        filepath = save_dir / f"{self.name}.json"

        # Convert numpy arrays to lists for JSON serialization
        serializable = {}
        for key, value in self.data.items():
            if hasattr(value, "tolist"):
                serializable[key] = value.tolist()
            else:
                serializable[key] = value

        with open(filepath, "w") as f:
            json.dump(serializable, f, indent=2)
        logger.info(f"Calibration profile '{self.name}' saved to {filepath}")
        return filepath

    @classmethod
    def load(cls, filepath: str) -> "CalibrationProfile":
        """Load profile from JSON file."""
        import numpy as np

        with open(filepath, "r") as f:
            data = json.load(f)

        profile = cls(data.get("name", "loaded"))
        profile.data = data

        # Convert lists back to numpy arrays where needed
        if profile.data.get("camera_matrix") is not None:
            profile.data["camera_matrix"] = np.array(profile.data["camera_matrix"])
        if profile.data.get("dist_coeffs") is not None:
            profile.data["dist_coeffs"] = np.array(profile.data["dist_coeffs"])

        return profile

    @classmethod
    def list_profiles(cls, directory: Optional[Path] = None) -> list:
        """List available calibration profiles."""
        search_dir = directory or DEFAULT_CALIBRATION_DIR
        if not search_dir.exists():
            return []
        return [f.stem for f in search_dir.glob("*.json")]


class ProjectConfig:
    """Manages per-project configuration and state."""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.config_file = self.project_dir / "layerscan_project.json"
        self.data = {
            "name": self.project_dir.name,
            "images_dir": "",
            "stl_file": "",
            "gcode_file": "",
            "calibration_profile": "",
            "layer_height_mm": 0.2,
            "tolerance_mm": 0.2,
            "processed": False,
            "results": {},
        }
        if self.config_file.exists():
            self.load()

    def load(self):
        """Load project config."""
        try:
            with open(self.config_file, "r") as f:
                saved = json.load(f)
            self.data.update(saved)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load project config: {e}")

    def save(self):
        """Save project config."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self.data, f, indent=2)
