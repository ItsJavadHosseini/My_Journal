"""Reusable metric card for the Trading Journal dashboard."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from trading_journal.ui import theme


class MetricCard(QFrame):
    """Display a metric label, value, and optional supporting text."""

    def __init__(
        self,
        title: str,
        value: str = "—",
        subtitle: str = "",
        accent: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("metricCard")
        self.setMinimumHeight(118)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 9pt;"
        )

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            f"color: {accent or theme.TEXT_PRIMARY};"
            "font-size: 21pt; font-weight: 700;"
        )
        self.value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 8pt;"
        )
        self.subtitle_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch()

    def set_value(
        self,
        value: str,
        subtitle: str | None = None,
        accent: str | None = None,
    ) -> None:
        """Update the displayed metric."""
        self.value_label.setText(value)

        if subtitle is not None:
            self.subtitle_label.setText(subtitle)

        if accent is not None:
            self.value_label.setStyleSheet(
                f"color: {accent}; font-size: 21pt; font-weight: 700;"
            )
