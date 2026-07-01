"""
Dark premium theme stylesheet for LayerScan3D Qt application.

Provides a complete dark theme with color constants, font settings,
a comprehensive QSS stylesheet, and helper functions for dynamic styling.
"""

from layerscan.utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# Color Constants
# =============================================================================

BG_PRIMARY = '#1a1a2e'
BG_SECONDARY = '#16213e'
BG_CARD = '#1f2940'
BG_INPUT = '#0f1729'

ACCENT = '#00d4aa'
ACCENT_HOVER = '#00e6b8'
ACCENT_SECONDARY = '#0ea5e9'

TEXT_PRIMARY = '#f0f0f0'
TEXT_SECONDARY = '#8892a0'
TEXT_MUTED = '#5a6270'

BORDER = '#2a3550'
BORDER_FOCUS = '#00d4aa'

SUCCESS = '#22c55e'
WARNING = '#f59e0b'
ERROR = '#ef4444'

OVERLAY = 'rgba(10,12,20,180)'

# =============================================================================
# Font Settings
# =============================================================================

FONT_FAMILY = (
    "'Inter', 'Segoe UI', 'San Francisco', 'Helvetica Neue', "
    "'Arial', sans-serif"
)

FONT_SIZE_SM = 11
FONT_SIZE_MD = 13
FONT_SIZE_LG = 15
FONT_SIZE_XL = 18
FONT_SIZE_TITLE = 24

# =============================================================================
# Dark Stylesheet (QSS)
# =============================================================================

DARK_STYLESHEET = f"""
/* =========================================================================
   Global
   ========================================================================= */

QMainWindow {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_MD}px;
}}

QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_MD}px;
}}

QDialog {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

/* =========================================================================
   QPushButton
   ========================================================================= */

QPushButton {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 18px;
    font-size: {FONT_SIZE_MD}px;
    font-weight: 500;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {BG_SECONDARY};
    border-color: {ACCENT};
    color: {ACCENT};
}}

QPushButton:pressed {{
    background-color: {BG_INPUT};
    border-color: {ACCENT_HOVER};
    color: {ACCENT_HOVER};
}}

QPushButton:disabled {{
    background-color: {BG_INPUT};
    color: {TEXT_MUTED};
    border-color: {BG_CARD};
}}

/* Primary button variant via objectName="primaryButton" */
QPushButton#primaryButton {{
    background-color: {ACCENT};
    color: {BG_PRIMARY};
    border: none;
    font-weight: 600;
}}

QPushButton#primaryButton:hover {{
    background-color: {ACCENT_HOVER};
    color: {BG_PRIMARY};
}}

QPushButton#primaryButton:pressed {{
    background-color: {ACCENT};
    color: {BG_PRIMARY};
}}

QPushButton#primaryButton:disabled {{
    background-color: {TEXT_MUTED};
    color: {BG_INPUT};
}}

/* =========================================================================
   QLabel
   ========================================================================= */

QLabel {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    border: none;
    padding: 0px;
}}

/* =========================================================================
   QLineEdit
   ========================================================================= */

QLineEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: {FONT_SIZE_MD}px;
    selection-background-color: {ACCENT};
    selection-color: {BG_PRIMARY};
}}

QLineEdit:focus {{
    border-color: {BORDER_FOCUS};
}}

QLineEdit:disabled {{
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
}}

QLineEdit::placeholder {{
    color: {TEXT_MUTED};
}}

/* =========================================================================
   QSpinBox / QDoubleSpinBox
   ========================================================================= */

QSpinBox, QDoubleSpinBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {FONT_SIZE_MD}px;
    selection-background-color: {ACCENT};
    selection-color: {BG_PRIMARY};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {BORDER_FOCUS};
}}

QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    background-color: {BG_CARD};
    border-left: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    border-top-right-radius: 6px;
    width: 20px;
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: {BG_CARD};
    border-left: 1px solid {BORDER};
    border-bottom-right-radius: 6px;
    width: 20px;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {BG_SECONDARY};
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {TEXT_SECONDARY};
    width: 0px;
    height: 0px;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    width: 0px;
    height: 0px;
}}

/* =========================================================================
   QComboBox
   ========================================================================= */

QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: {FONT_SIZE_MD}px;
    min-width: 80px;
}}

QComboBox:hover {{
    border-color: {ACCENT};
}}

QComboBox:focus {{
    border-color: {BORDER_FOCUS};
}}

QComboBox:disabled {{
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
}}

QComboBox::drop-down {{
    border: none;
    border-left: 1px solid {BORDER};
    width: 28px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background-color: {BG_CARD};
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {TEXT_SECONDARY};
    width: 0px;
    height: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {BG_CARD};
    selection-color: {ACCENT};
    outline: none;
    padding: 4px;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 12px;
    border-radius: 4px;
    min-height: 24px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {BG_CARD};
    color: {ACCENT};
}}

/* =========================================================================
   QSlider (Horizontal)
   ========================================================================= */

QSlider::groove:horizontal {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {ACCENT};
    border: 2px solid {ACCENT};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 9px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QSlider::handle:horizontal:pressed {{
    background-color: {ACCENT_SECONDARY};
    border-color: {ACCENT_SECONDARY};
}}

QSlider::sub-page:horizontal {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

QSlider::add-page:horizontal {{
    background-color: {BG_INPUT};
    border-radius: 3px;
}}

/* =========================================================================
   QProgressBar
   ========================================================================= */

QProgressBar {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE_SM}px;
    font-weight: 600;
    min-height: 20px;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

/* =========================================================================
   QTabWidget / QTabBar
   ========================================================================= */

QTabWidget {{
    background-color: {BG_PRIMARY};
    border: none;
}}

QTabWidget::pane {{
    background-color: {BG_PRIMARY};
    border: 1px solid {BORDER};
    border-top: none;
    border-radius: 0px 0px 8px 8px;
}}

QTabBar {{
    background-color: transparent;
    border: none;
}}

QTabBar::tab {{
    background-color: {BG_CARD};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 10px 20px;
    font-size: {FONT_SIZE_MD}px;
    font-weight: 500;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QTabBar::tab:selected {{
    background-color: {BG_PRIMARY};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

QTabBar::tab:hover:!selected {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
}}

/* =========================================================================
   QTableWidget / QHeaderView
   ========================================================================= */

QTableWidget {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {BG_CARD};
    selection-color: {ACCENT};
    font-size: {FONT_SIZE_MD}px;
    alternate-background-color: {BG_SECONDARY};
}}

QTableWidget::item {{
    padding: 6px 10px;
    border: none;
}}

QTableWidget::item:selected {{
    background-color: {BG_CARD};
    color: {ACCENT};
}}

QHeaderView {{
    background-color: {BG_SECONDARY};
    border: none;
}}

QHeaderView::section {{
    background-color: {BG_SECONDARY};
    color: {TEXT_SECONDARY};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 8px 12px;
    font-size: {FONT_SIZE_SM}px;
    font-weight: 600;
    text-transform: uppercase;
}}

QHeaderView::section:hover {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
}}

/* =========================================================================
   QScrollBar (Thin Modern)
   ========================================================================= */

QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {TEXT_MUTED};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_SECONDARY};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
    border: none;
    background: none;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {TEXT_MUTED};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_SECONDARY};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
    border: none;
    background: none;
}}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* =========================================================================
   QGroupBox
   ========================================================================= */

QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-size: {FONT_SIZE_MD}px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: {ACCENT};
    font-size: {FONT_SIZE_MD}px;
    font-weight: 600;
    background-color: {BG_CARD};
    border-radius: 4px;
    left: 12px;
}}

/* =========================================================================
   QToolBar
   ========================================================================= */

QToolBar {{
    background-color: {BG_SECONDARY};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 4px 8px;
    spacing: 4px;
}}

QToolBar::separator {{
    width: 1px;
    background-color: {BORDER};
    margin: 4px 6px;
}}

QToolBar QToolButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {FONT_SIZE_MD}px;
}}

QToolBar QToolButton:hover {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border-color: {BORDER};
}}

QToolBar QToolButton:pressed {{
    background-color: {BG_INPUT};
    color: {ACCENT};
}}

/* =========================================================================
   QStatusBar
   ========================================================================= */

QStatusBar {{
    background-color: {BG_SECONDARY};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: {FONT_SIZE_SM}px;
    padding: 2px 8px;
}}

QStatusBar::item {{
    border: none;
}}

/* =========================================================================
   QMenuBar / QMenu
   ========================================================================= */

QMenuBar {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    font-size: {FONT_SIZE_MD}px;
    padding: 2px 0px;
}}

QMenuBar::item {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    padding: 6px 14px;
    border-radius: 4px;
    margin: 2px 1px;
}}

QMenuBar::item:selected {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
}}

QMenuBar::item:pressed {{
    background-color: {BG_INPUT};
    color: {ACCENT};
}}

QMenu {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
    font-size: {FONT_SIZE_MD}px;
}}

QMenu::item {{
    padding: 8px 24px 8px 16px;
    border-radius: 4px;
    margin: 1px 4px;
}}

QMenu::item:selected {{
    background-color: {BG_CARD};
    color: {ACCENT};
}}

QMenu::item:disabled {{
    color: {TEXT_MUTED};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 8px;
}}

QMenu::indicator {{
    width: 16px;
    height: 16px;
    margin-left: 6px;
}}

/* =========================================================================
   QCheckBox / QRadioButton
   ========================================================================= */

QCheckBox {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE_MD}px;
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_INPUT};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}

QCheckBox::indicator:disabled {{
    background-color: {BG_CARD};
    border-color: {TEXT_MUTED};
}}

QRadioButton {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE_MD}px;
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: 10px;
    background-color: {BG_INPUT};
}}

QRadioButton::indicator:hover {{
    border-color: {ACCENT};
}}

QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QRadioButton::indicator:disabled {{
    background-color: {BG_CARD};
    border-color: {TEXT_MUTED};
}}

/* =========================================================================
   QToolTip
   ========================================================================= */

QToolTip {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {FONT_SIZE_SM}px;
}}

/* =========================================================================
   QSplitter
   ========================================================================= */

QSplitter {{
    background-color: transparent;
    border: none;
}}

QSplitter::handle {{
    background-color: {BORDER};
    border-radius: 2px;
}}

QSplitter::handle:horizontal {{
    width: 3px;
    margin: 4px 1px;
}}

QSplitter::handle:vertical {{
    height: 3px;
    margin: 1px 4px;
}}

QSplitter::handle:hover {{
    background-color: {ACCENT};
}}

/* =========================================================================
   QListWidget
   ========================================================================= */

QListWidget {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
    font-size: {FONT_SIZE_MD}px;
}}

QListWidget::item {{
    padding: 8px 12px;
    border-radius: 4px;
    margin: 1px 2px;
}}

QListWidget::item:selected {{
    background-color: {BG_CARD};
    color: {ACCENT};
}}

QListWidget::item:hover:!selected {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
}}

/* =========================================================================
   QTextEdit
   ========================================================================= */

QTextEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: {FONT_SIZE_MD}px;
    selection-background-color: {ACCENT};
    selection-color: {BG_PRIMARY};
}}

QTextEdit:focus {{
    border-color: {BORDER_FOCUS};
}}

/* =========================================================================
   QFrame
   ========================================================================= */

QFrame {{
    background-color: transparent;
    border: none;
}}

QFrame[frameShape="4"] {{
    background-color: {BORDER};
    max-height: 1px;
    border: none;
}}

QFrame[frameShape="5"] {{
    background-color: {BORDER};
    max-width: 1px;
    border: none;
}}
"""

# =============================================================================
# Helper Functions
# =============================================================================


def get_card_style() -> str:
    """Return a QSS style string for card-like container widgets."""
    return f"""
        background-color: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 16px;
    """


def get_sidebar_style() -> str:
    """Return a QSS style string for sidebar panel widgets."""
    return f"""
        background-color: {BG_SECONDARY};
        border-right: 1px solid {BORDER};
        padding: 8px;
    """


def get_step_button_style(active: bool, completed: bool) -> str:
    """
    Return a QSS style string for a step/wizard button.

    Parameters
    ----------
    active : bool
        Whether the step is the currently active step.
    completed : bool
        Whether the step has been completed.

    Returns
    -------
    str
        QSS stylesheet for the step button.
    """
    if active:
        bg = ACCENT
        text = BG_PRIMARY
        border_color = ACCENT
        font_weight = '700'
    elif completed:
        bg = BG_CARD
        text = SUCCESS
        border_color = SUCCESS
        font_weight = '600'
    else:
        bg = BG_INPUT
        text = TEXT_MUTED
        border_color = BORDER
        font_weight = '500'

    return f"""
        QPushButton {{
            background-color: {bg};
            color: {text};
            border: 2px solid {border_color};
            border-radius: 8px;
            padding: 10px 16px;
            font-size: {FONT_SIZE_MD}px;
            font-weight: {font_weight};
            text-align: left;
        }}
        QPushButton:hover {{
            border-color: {ACCENT_HOVER};
            color: {ACCENT_HOVER if not active else BG_PRIMARY};
        }}
    """


def get_gauge_colors(value: float) -> tuple[str, str]:
    """
    Return (fill_color, text_color) for a gauge based on a 0–100 value.

    Parameters
    ----------
    value : float
        A value between 0 and 100 representing the gauge percentage.

    Returns
    -------
    tuple[str, str]
        A tuple of (fill_color, text_color) hex strings.
    """
    if value >= 80:
        return SUCCESS, SUCCESS
    elif value >= 60:
        return ACCENT, ACCENT
    elif value >= 40:
        return WARNING, WARNING
    else:
        return ERROR, ERROR


def get_severity_color(severity: str) -> str:
    """
    Return a color hex string corresponding to a severity level.

    Parameters
    ----------
    severity : str
        Severity level: 'critical', 'high', 'medium', 'low', or 'info'.

    Returns
    -------
    str
        Hex color string for the given severity.
    """
    severity_map = {
        'critical': ERROR,
        'high': '#f97316',      # orange
        'medium': WARNING,
        'low': ACCENT,
        'info': ACCENT_SECONDARY,
    }
    return severity_map.get(severity.lower(), TEXT_SECONDARY)


def apply_theme(app) -> None:
    """
    Apply the dark theme stylesheet and QPalette to a QApplication.

    Parameters
    ----------
    app : QApplication
        The Qt application instance to theme.
    """
    try:
        from PyQt6.QtGui import QColor, QPalette
        from PyQt6.QtCore import Qt
    except ImportError:
        try:
            from PyQt5.QtGui import QColor, QPalette
            from PyQt5.QtCore import Qt
        except ImportError:
            logger.warning(
                "Neither PyQt6 nor PyQt5 found. "
                "Applying stylesheet only without QPalette."
            )
            app.setStyleSheet(DARK_STYLESHEET)
            return

    logger.info("Applying LayerScan3D dark theme")

    # Apply QSS stylesheet
    app.setStyleSheet(DARK_STYLESHEET)

    # Build and apply QPalette for native widgets and fallback rendering
    palette = QPalette()

    palette.setColor(QPalette.ColorRole.Window, QColor(BG_PRIMARY))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_SECONDARY))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_INPUT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT_SECONDARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BG_PRIMARY))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_MUTED))
    palette.setColor(QPalette.ColorRole.Light, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.Midlight, QColor(BG_SECONDARY))
    palette.setColor(QPalette.ColorRole.Dark, QColor(BG_INPUT))
    palette.setColor(QPalette.ColorRole.Mid, QColor(BORDER))
    palette.setColor(QPalette.ColorRole.Shadow, QColor('#000000'))

    # Disabled state
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor(TEXT_MUTED),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(TEXT_MUTED),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(TEXT_MUTED),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Highlight,
        QColor(BORDER),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.HighlightedText,
        QColor(TEXT_MUTED),
    )

    app.setPalette(palette)

    logger.info("Dark theme applied successfully")
