"""Behavior analytics page for Trading Journal."""

from collections import defaultdict
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QBarSeries,
    QChart,
    QChartView,
    QValueAxis,
)

from trading_journal.domain.models import Trade
from trading_journal.ui import theme
from trading_journal.ui.components.metric_card import MetricCard


class BehaviorPage(QWidget):
    """Analyze reported results across symbols, weekdays, directions, and holding time."""

    GROUPINGS = {
        "Symbol": "symbol",
        "Weekday": "weekday",
        "Direction": "direction",
        "Holding duration": "duration",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._trades: list[Trade] = []
        self._currency = "USD"

        self._build_ui()
        self._connect_signals()
        self.set_trades([])

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(18)

        title = QLabel("Behavior")
        title.setStyleSheet("font-size: 24pt; font-weight: 700;")

        subtitle = QLabel(
            "Find patterns in your trading decisions and outcomes"
        )
        subtitle.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 10pt;"
        )

        root.addWidget(title)
        root.addWidget(subtitle)

        self.closed_card = MetricCard(
            "ANALYZABLE TRADES", "—",
            "Closed trades with reported profit",
        )
        self.best_group_card = MetricCard("STRONGEST GROUP", "—")
        self.weakest_group_card = MetricCard("WEAKEST GROUP", "—")
        self.groups_card = MetricCard("GROUPS ANALYZED", "—")

        cards_layout = QGridLayout()
        cards_layout.setSpacing(14)

        for index, card in enumerate(
            [
                self.closed_card,
                self.best_group_card,
                self.weakest_group_card,
                self.groups_card,
            ]
        ):
            cards_layout.addWidget(card, 0, index)

        root.addLayout(cards_layout)

        filter_panel = QFrame()
        filter_panel.setObjectName("panel")
        filter_layout = QHBoxLayout(filter_panel)
        filter_layout.setContentsMargins(14, 12, 14, 12)

        grouping_label = QLabel("Analyze by")
        grouping_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY};"
        )

        self.grouping_filter = QComboBox()
        self.grouping_filter.addItems(list(self.GROUPINGS.keys()))

        filter_layout.addWidget(grouping_label)
        filter_layout.addWidget(self.grouping_filter)
        filter_layout.addStretch()

        self.grouping_description = QLabel(
            "Compare the reported results for each group."
        )
        self.grouping_description.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY};"
        )
        filter_layout.addWidget(self.grouping_description)

        root.addWidget(filter_panel)

        content_layout = QGridLayout()
        content_layout.setSpacing(16)

        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setMinimumHeight(330)
        self.chart_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.chart_view.setStyleSheet(
            "background: transparent; border: none;"
        )

        chart_panel = QFrame()
        chart_panel.setObjectName("panel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(16, 14, 16, 14)
        chart_layout.addWidget(self.chart_view)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Group", "Trades", "Wins", "Win Rate", "Reported P&L"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        table_panel = QFrame()
        table_panel.setObjectName("panel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(16, 14, 16, 14)

        table_title = QLabel("Group Breakdown")
        table_title.setStyleSheet(
            "font-size: 12pt; font-weight: 700;"
        )

        table_layout.addWidget(table_title)
        table_layout.addWidget(self.table)

        content_layout.addWidget(chart_panel, 0, 0)
        content_layout.addWidget(table_panel, 1, 0)

        root.addLayout(content_layout)
        root.addStretch()

    def _connect_signals(self) -> None:
        self.grouping_filter.currentTextChanged.connect(
            self._refresh_analysis
        )

    def set_trades(
        self,
        trades: list[Trade],
        currency: str = "USD",
    ) -> None:
        """Set the selected account's trades and recompute behavior analysis."""
        self._trades = list(trades)
        self._currency = currency or "USD"
        self._refresh_analysis()

    def _refresh_analysis(self, *_args) -> None:
        eligible = [
            trade
            for trade in self._trades
            if trade.is_closed
            and trade.exit_time is not None
            and trade.reported_profit is not None
        ]

        self.closed_card.set_value(str(len(eligible)))

        if not eligible:
            self.best_group_card.set_value("—", "No analyzable data")
            self.weakest_group_card.set_value("—", "No analyzable data")
            self.groups_card.set_value("0")
            self.table.setRowCount(0)
            self.chart_view.setChart(
                self._empty_chart("No behavior data available")
            )
            return

        grouping_label = self.grouping_filter.currentText()
        grouping = self.GROUPINGS[grouping_label]

        grouped: dict[str, list[Trade]] = defaultdict(list)

        for trade in eligible:
            key = self._group_key(trade, grouping)
            grouped[key].append(trade)

        summaries = []

        for key, group_trades in grouped.items():
            pnl = sum(
                (
                    trade.reported_profit
                    for trade in group_trades
                    if trade.reported_profit is not None
                ),
                Decimal("0"),
            )

            wins = sum(
                1
                for trade in group_trades
                if trade.reported_profit is not None
                and trade.reported_profit > 0
            )

            win_rate = wins / len(group_trades) * 100

            summaries.append(
                {
                    "group": key,
                    "count": len(group_trades),
                    "wins": wins,
                    "win_rate": win_rate,
                    "pnl": pnl,
                }
            )

        # Best and weakest groups are ranked by total reported P&L.
        # These labels are descriptive, not evidence of a causal edge.
        summaries.sort(key=lambda item: item["pnl"], reverse=True)

        best = summaries[0]
        weakest = summaries[-1]

        self.best_group_card.set_value(
            best["group"],
            self._money(best["pnl"]),
            theme.GREEN if best["pnl"] >= 0 else theme.RED,
        )
        self.weakest_group_card.set_value(
            weakest["group"],
            self._money(weakest["pnl"]),
            theme.RED if weakest["pnl"] < 0 else theme.TEXT_PRIMARY,
        )
        self.groups_card.set_value(str(len(summaries)))

        descriptions = {
            "Symbol": "Compare total results for each traded symbol.",
            "Weekday": "Group trades by the weekday of their exit.",
            "Direction": "Compare BUY and SELL trade outcomes.",
            "Holding duration": (
                "Compare outcomes by elapsed time between entry and exit."
            ),
        }
        self.grouping_description.setText(
            descriptions[grouping_label]
        )

        self._populate_table(summaries)
        self._build_chart(summaries, grouping_label)

    @staticmethod
    def _group_key(trade: Trade, grouping: str) -> str:
        if grouping == "symbol":
            return trade.symbol

        if grouping == "weekday":
            assert trade.exit_time is not None
            return trade.exit_time.strftime("%A")

        if grouping == "direction":
            return trade.direction.value

        if trade.exit_time is None:
            return "Unknown"

        seconds = (trade.exit_time - trade.entry_time).total_seconds()

        if seconds < 0:
            return "Invalid duration"
        if seconds < 5 * 60:
            return "Under 5 min"
        if seconds < 15 * 60:
            return "5–15 min"
        if seconds < 60 * 60:
            return "15–60 min"
        if seconds < 4 * 60 * 60:
            return "1–4 hours"
        if seconds < 24 * 60 * 60:
            return "4–24 hours"
        return "1+ days"

    def _populate_table(self, summaries: list[dict]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(summaries))

        for row, item in enumerate(summaries):
            values = [
                item["group"],
                str(item["count"]),
                str(item["wins"]),
                f'{item["win_rate"]:.1f}%',
                self._money(item["pnl"]),
            ]

            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)

                if column in (1, 2, 3, 4):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )

                if column == 4:
                    if item["pnl"] > 0:
                        cell.setForeground(QColor(theme.GREEN))
                    elif item["pnl"] < 0:
                        cell.setForeground(QColor(theme.RED))

                self.table.setItem(row, column, cell)

        self.table.setSortingEnabled(True)

    def _build_chart(
        self,
        summaries: list[dict],
        grouping_label: str,
    ) -> None:
        chart = QChart()
        chart.setBackgroundBrush(QColor(theme.SURFACE))
        chart.setTitle(f"Reported P&L by {grouping_label}")
        chart.setTitleBrush(QColor(theme.TEXT_SECONDARY))
        chart.legend().setVisible(False)

        series = QBarSeries()
        series.setBarWidth(0.72)

        values = QBarSet("Reported P&L")
        labels = []

        for item in summaries:
            labels.append(item["group"])
            values.append(float(item["pnl"]))

        values.setColor(QColor(theme.GREEN))
        series.append(values)
        chart.addSeries(series)

        if labels:
            axis_x = QBarCategoryAxis()
            axis_x.append(labels)
            axis_x.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis_x.setLinePenColor(QColor(theme.BORDER))

            axis_y = QValueAxis()
            axis_y.setTitleText(self._currency)
            axis_y.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis_y.setLinePenColor(QColor(theme.BORDER))
            axis_y.setLabelFormat("%.2f")

            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)

            low = min([float(item["pnl"]) for item in summaries] + [0.0])
            high = max([float(item["pnl"]) for item in summaries] + [0.0])

            if low == high:
                low, high = -1.0, 1.0
            else:
                padding = (high - low) * 0.12
                low -= padding
                high += padding

            axis_y.setRange(low, high)

        self.chart_view.setChart(chart)

    @staticmethod
    def _empty_chart(message: str) -> QChart:
        chart = QChart()
        chart.setBackgroundBrush(QColor(theme.SURFACE))
        chart.setTitle(message)
        chart.setTitleBrush(QColor(theme.TEXT_SECONDARY))
        chart.legend().hide()
        return chart

    def _money(self, value: Decimal) -> str:
        return f"{value:,.2f} {self._currency}"
