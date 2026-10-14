"""Navigation sidebar for the Trading Journal application."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from trading_journal.ui import theme


class Sidebar(QFrame):
    """Sidebar that emits the selected page identifier."""

    page_changed = Signal(str)

    PAGES = [
        ("overview", "Overview"),
        ("performance", "Performance"),
        ("trade_explorer", "Trade Explorer"),
        ("behavior", "Behavior"),
        ("accounts", "Accounts & Data"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("sidebar")
        self.setFixedWidth(224)

        self._buttons: dict[str, QPushButton] = {}
        self._active_page: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 18)
        layout.setSpacing(8)

        brand = QLabel("TRADING")
        brand.setStyleSheet(
            f"""
            color: {theme.TEXT_PRIMARY};
            font-size: 17pt;
            font-weight: 800;
            letter-spacing: 2px;
            """
        )

        brand_subtitle = QLabel("JOURNAL")
        brand_subtitle.setStyleSheet(
            f"""
            color: {theme.GOLD};
            font-size: 9pt;
            font-weight: 700;
            letter-spacing: 4px;
            """
        )

        layout.addWidget(brand)
        layout.addWidget(brand_subtitle)
        layout.addSpacing(28)

        section_label = QLabel("WORKSPACE")
        section_label.setStyleSheet(
            f"""
            color: {theme.TEXT_MUTED};
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: 1px;
            padding-left: 10px;
            """
        )
        layout.addWidget(section_label)
        layout.addSpacing(8)

        for page_id, page_title in self.PAGES:
            button = QPushButton(page_title)
            button.setCheckable(True)
            button.setMinimumHeight(42)
            button.setCursor(__import__(
                "PySide6.QtCore", fromlist=["Qt"]
            ).Qt.CursorShape.PointingHandCursor)

            button.setStyleSheet(
                f"""
                QPushButton {{
                    color: {theme.TEXT_SECONDARY};
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 7px;
                    text-align: left;
                    padding: 0 12px;
                    font-size: 10pt;
                }}

                QPushButton:hover {{
                    color: {theme.TEXT_PRIMARY};
                    background: {theme.SURFACE_ALT};
                }}

                QPushButton:checked {{
                    color: {theme.GREEN};
                    background: {theme.SURFACE_ALT};
                    border: 1px solid {theme.BORDER};
                    font-weight: 700;
                }}
                """
            )

            button.clicked.connect(
                lambda checked=False, key=page_id: self.set_active_page(key)
            )

            self._buttons[page_id] = button
            layout.addWidget(button)

        layout.addStretch()

        footer = QLabel("TRADING JOURNAL")
        footer.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 8pt;"
        )
        layout.addWidget(footer)

        self.setStyleSheet(
            f"""
            QFrame#sidebar {{
                background-color: {theme.SURFACE};
                border-right: 1px solid {theme.BORDER};
            }}
            """
        )

        self.set_active_page("overview", emit_signal=False)

    def set_active_page(
        self,
        page_id: str,
        emit_signal: bool = True,
    ) -> None:
        """Highlight a page and optionally notify the main window."""
        if page_id not in self._buttons:
            raise ValueError(f"Unknown page identifier: {page_id}")

        self._active_page = page_id

        for key, button in self._buttons.items():
            button.blockSignals(True)
            button.setChecked(key == page_id)
            button.blockSignals(False)

        if emit_signal:
            self.page_changed.emit(page_id)

    @property
    def active_page(self) -> str | None:
        return self._active_page
