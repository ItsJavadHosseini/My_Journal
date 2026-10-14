"""Trade Explorer page for filtering and inspecting individual trades."""

from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trading_journal.domain.models import Trade
from trading_journal.ui import theme


class TradeExplorerPage(QWidget):
    """Filter, browse, and inspect trades from the selected account."""

    COLUMNS = (
        "Symbol",
        "Direction",
        "Volume",
        "Entry Time",
        "Entry Price",
        "Exit Time",
        "Exit Price",
        "Reported P&L",
        "Status",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._trades: list[Trade] = []
        self._visible_trades: list[Trade] = []
        self._currency = "USD"

        self._build_ui()
        self._connect_signals()
        self.set_trades([])

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(18)

        title = QLabel("Trade Explorer")
        title.setStyleSheet("font-size: 24pt; font-weight: 700;")

        subtitle = QLabel(
            "Search, filter, and inspect individual trading records"
        )
        subtitle.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 10pt;"
        )

        root.addWidget(title)
        root.addWidget(subtitle)

        filters = QFrame()
        filters.setObjectName("panel")
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(14, 14, 14, 14)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search symbol or position ID..."
        )

        self.symbol_filter = QComboBox()
        self.symbol_filter.addItem("All symbols")

        self.direction_filter = QComboBox()
        self.direction_filter.addItems(
            ["All directions", "BUY", "SELL"]
        )

        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["All statuses", "Closed", "Open"]
        )

        filter_layout.addWidget(QLabel("Search"), 0, 0)
        filter_layout.addWidget(QLabel("Symbol"), 0, 1)
        filter_layout.addWidget(QLabel("Direction"), 0, 2)
        filter_layout.addWidget(QLabel("Status"), 0, 3)

        filter_layout.addWidget(self.search_input, 1, 0)
        filter_layout.addWidget(self.symbol_filter, 1, 1)
        filter_layout.addWidget(self.direction_filter, 1, 2)
        filter_layout.addWidget(self.status_filter, 1, 3)

        root.addWidget(filters)

        self.result_count = QLabel("0 trades")
        self.result_count.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-weight: 600;"
        )
        root.addWidget(self.result_count)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header.setStretchLastSection(True)

        root.addWidget(self.table, 3)

        details_panel = QFrame()
        details_panel.setObjectName("panel")
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(16, 14, 16, 14)
        details_layout.setSpacing(12)

        details_title = QLabel("Trade Details")
        details_title.setStyleSheet(
            "font-size: 12pt; font-weight: 700;"
        )
        details_layout.addWidget(details_title)

        self.details_grid = QGridLayout()
        self.details_grid.setHorizontalSpacing(24)
        self.details_grid.setVerticalSpacing(12)

        self.detail_labels: dict[str, QLabel] = {}

        detail_fields = [
            ("Position ID", "position_id"),
            ("Trade ID", "trade_id"),
            ("Stop Loss", "stop_loss"),
            ("Take Profit", "take_profit"),
            ("Commission", "commission"),
            ("Swap", "swap"),
            ("Source Profit", "reported_profit"),
            ("Entry Time", "entry_time"),
            ("Exit Time", "exit_time"),
            ("Duration", "duration"),
        ]

        for index, (label_text, key) in enumerate(detail_fields):
            row = index // 2
            col = (index % 2) * 2

            field_label = QLabel(label_text)
            field_label.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY};"
            )

            value_label = QLabel("—")
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            value_label.setWordWrap(True)

            self.details_grid.addWidget(field_label, row, col)
            self.details_grid.addWidget(value_label, row, col + 1)
            self.detail_labels[key] = value_label

        details_layout.addLayout(self.details_grid)
        root.addWidget(details_panel, 2)

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(self._apply_filters)
        self.symbol_filter.currentIndexChanged.connect(
            self._apply_filters
        )
        self.direction_filter.currentIndexChanged.connect(
            self._apply_filters
        )
        self.status_filter.currentIndexChanged.connect(
            self._apply_filters
        )
        self.table.itemSelectionChanged.connect(
            self._show_selected_trade
        )

    def set_trades(
        self,
        trades: list[Trade],
        currency: str = "USD",
    ) -> None:
        """Replace the displayed dataset and refresh available filters."""
        self._trades = list(trades)
        self._currency = currency or "USD"

        current_symbol = self.symbol_filter.currentText()

        self.symbol_filter.blockSignals(True)
        self.symbol_filter.clear()
        self.symbol_filter.addItem("All symbols")

        symbols = sorted({trade.symbol for trade in self._trades})
        self.symbol_filter.addItems(symbols)

        symbol_index = self.symbol_filter.findText(current_symbol)
        if symbol_index >= 0:
            self.symbol_filter.setCurrentIndex(symbol_index)

        self.symbol_filter.blockSignals(False)

        self._apply_filters()

    def _apply_filters(self, *_args) -> None:
        query = self.search_input.text().strip().casefold()
        selected_symbol = self.symbol_filter.currentText()
        selected_direction = self.direction_filter.currentText()
        selected_status = self.status_filter.currentText()

        filtered: list[Trade] = []

        for trade in self._trades:
            if (
                selected_symbol != "All symbols"
                and trade.symbol != selected_symbol
            ):
                continue

            if (
                selected_direction != "All directions"
                and trade.direction.value != selected_direction
            ):
                continue

            if selected_status == "Closed" and not trade.is_closed:
                continue

            if selected_status == "Open" and trade.is_closed:
                continue

            if query:
                searchable = (
                    f"{trade.symbol} "
                    f"{trade.position_id or ''} "
                    f"{trade.trade_id}"
                ).casefold()

                if query not in searchable:
                    continue

            filtered.append(trade)

        self._visible_trades = filtered
        self._populate_table()
        self.result_count.setText(
            f"{len(filtered):,} of {len(self._trades):,} trades"
        )
        self._clear_details()

    def _populate_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(self._visible_trades))

        for row, trade in enumerate(self._visible_trades):
            values = [
                trade.symbol,
                trade.direction.value,
                self._number(trade.volume),
                self._datetime(trade.entry_time),
                self._number(trade.entry_price),
                self._datetime(trade.exit_time),
                self._number(trade.exit_price),
                self._money(trade.reported_profit),
                "Closed" if trade.is_closed else "Open",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column in (2, 4, 6, 7):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )

                if column == 7 and trade.reported_profit is not None:
                    if trade.reported_profit > 0:
                        item.setForeground(QColor(theme.GREEN))
                    elif trade.reported_profit < 0:
                        item.setForeground(QColor(theme.RED))

                if column == 8:
                    color = (
                        theme.GREEN if trade.is_closed
                        else theme.GOLD
                    )
                    item.setForeground(QColor(color))

                self.table.setItem(row, column, item)

        self.table.setSortingEnabled(True)

        if self._visible_trades:
            self.table.selectRow(0)
        else:
            self._clear_details()

    def _show_selected_trade(self) -> None:
        selected = self.table.selectionModel().selectedRows()

        if not selected:
            self._clear_details()
            return

        row = selected[0].row()

        if not 0 <= row < len(self._visible_trades):
            self._clear_details()
            return

        # Use the selected symbol and position ID to locate the trade,
        # because table sorting can change the visible row order.
        symbol_item = self.table.item(row, 0)
        direction_item = self.table.item(row, 1)
        entry_time_item = self.table.item(row, 3)

        if symbol_item is None or direction_item is None:
            self._clear_details()
            return

        symbol = symbol_item.text()
        direction = direction_item.text()
        entry_time = entry_time_item.text() if entry_time_item else ""

        trade = next(
            (
                item
                for item in self._visible_trades
                if item.symbol == symbol
                and item.direction.value == direction
                and self._datetime(item.entry_time) == entry_time
            ),
            None,
        )

        if trade is None:
            return

        values = {
            "position_id": trade.position_id or "—",
            "trade_id": str(trade.trade_id),
            "stop_loss": self._number(trade.stop_loss),
            "take_profit": self._number(trade.take_profit),
            "commission": self._money(trade.commission),
            "swap": self._money(trade.swap),
            "reported_profit": self._money(trade.reported_profit),
            "entry_time": self._datetime(trade.entry_time),
            "exit_time": self._datetime(trade.exit_time),
            "duration": self._duration(trade),
        }

        for key, value in values.items():
            self.detail_labels[key].setText(value)

        profit = trade.reported_profit
        color = (
            theme.GREEN if profit is not None and profit > 0
            else theme.RED if profit is not None and profit < 0
            else theme.TEXT_PRIMARY
        )
        self.detail_labels["reported_profit"].setStyleSheet(
            f"color: {color}; font-weight: 700;"
        )

    def _clear_details(self) -> None:
        for label in self.detail_labels.values():
            label.setText("—")
            label.setStyleSheet("")

    def _money(self, value: Decimal | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:,.2f} {self._currency}"

    @staticmethod
    def _number(value: Decimal | None) -> str:
        if value is None:
            return "—"
        return f"{value:,.5f}".rstrip("0").rstrip(".")

    @staticmethod
    def _datetime(value: datetime | None) -> str:
        if value is None:
            return "—"
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _duration(trade: Trade) -> str:
        if trade.exit_time is None:
            return "Open"

        delta = trade.exit_time - trade.entry_time
        seconds = int(delta.total_seconds())

        if seconds < 0:
            return "Invalid timestamps"

        days, remainder = divmod(seconds, 86_400)
        hours, remainder = divmod(remainder, 3_600)
        minutes, _ = divmod(remainder, 60)

        parts = []

        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes or not parts:
            parts.append(f"{minutes}m")

        return " ".join(parts)
