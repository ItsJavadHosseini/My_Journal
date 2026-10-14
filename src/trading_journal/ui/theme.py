"""Central visual theme for Trading Journal."""

from PySide6.QtGui import QColor, QPalette


# Main palette
BACKGROUND = "#0B0D10"
SURFACE = "#12161C"
SURFACE_ALT = "#191F27"
BORDER = "#29313B"

TEXT_PRIMARY = "#F3F5F7"
TEXT_SECONDARY = "#929CAA"
TEXT_MUTED = "#657080"

GREEN = "#35C98A"
GREEN_HOVER = "#48D99B"
GOLD = "#D8B15A"
RED = "#F06464"
BLUE = "#6C9EFF"

FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10


APP_STYLESHEET = f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT_PRIMARY};
    font-family: "{FONT_FAMILY}";
    font-size: {FONT_SIZE}pt;
}}

QMainWindow {{
    background-color: {BACKGROUND};
}}

QLabel {{
    background-color: transparent;
    border: none;
}}

QPushButton {{
    background-color: {SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: #222B36;
    border-color: {GOLD};
}}

QPushButton:pressed {{
    background-color: {SURFACE};
}}

QPushButton:disabled {{
    color: {TEXT_MUTED};
    background-color: {SURFACE};
}}

QLineEdit,
QComboBox,
QDateEdit,
QDateTimeEdit,
QSpinBox,
QDoubleSpinBox {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 8px 10px;
    selection-background-color: {GOLD};
    selection-color: {BACKGROUND};
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {TEXT_PRIMARY};
    selection-background-color: {SURFACE_ALT};
    selection-color: {GOLD};
    border: 1px solid {BORDER};
    outline: none;
}}

QTableWidget,
QTableView {{
    background-color: {SURFACE};
    alternate-background-color: {SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: #26382F;
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}

QHeaderView::section {{
    background-color: {SURFACE_ALT};
    color: {TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 10px 8px;
    font-weight: 600;
}}

QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background-color: {BACKGROUND};
    width: 9px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {BORDER};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QFrame#panel {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QFrame#metricCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QFrame#sidebar {{
    background-color: #0E1116;
    border-right: 1px solid {BORDER};
}}

QPushButton#navButton {{
    text-align: left;
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    border-radius: 8px;
    padding: 12px 14px;
    font-weight: 500;
}}

QPushButton#navButton:hover {{
    background-color: {SURFACE_ALT};
    color: {TEXT_PRIMARY};
}}

QPushButton#navButton:checked {{
    background-color: #25251F;
    color: {GOLD};
    border-left: 3px solid {GOLD};
    font-weight: 700;
}}

QPushButton#primaryButton {{
    background-color: {GREEN};
    color: #07130D;
    border: none;
    font-weight: 700;
}}

QPushButton#primaryButton:hover {{
    background-color: {GREEN_HOVER};
}}

QPushButton#goldButton {{
    background-color: {GOLD};
    color: #17130A;
    border: none;
    font-weight: 700;
}}

QPushButton#dangerButton {{
    background-color: #351D21;
    color: {RED};
    border: 1px solid #603039;
}}

QToolTip {{
    background-color: {SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 5px;
}}
"""


def configure_application(app) -> None:
    """Apply the application-wide palette and stylesheet."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(GOLD))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BACKGROUND))

    app.setPalette(palette)
    app.setStyleSheet(APP_STYLESHEET)
