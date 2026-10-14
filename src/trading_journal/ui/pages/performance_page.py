"""Performance analytics page."""

from collections import defaultdict
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
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

from trading_journal.analytics.metrics import calculate_metrics
from trading_journal.domain.models import Trade
from trading_journal.ui import theme
from trading_journal.ui.components.metric_card import MetricCard


class PerformancePage(QWidget):
    """Detailed performance analytics for one trading account."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._trades: list[Trade] = []
        self._currency = "USD"

        self._build_ui()
        self.set_trades([])

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(20)

        title = QLabel("Performance")
        title.setStyleSheet("font-size: 24pt; font-weight: 700;")

        subtitle = QLabel(
            "Understand profitability, consistency, and trade outcomes"
        )
        subtitle.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 10pt;"
        )

        root.addWidget(title)
        root.addWidget(subtitle)

        self.empty_label = QLabel(
            "No closed trades with reported profit are available."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setMinimumHeight(90)
        self.empty_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY};"
            f"background-color: {theme.SURFACE};"
            f"border: 1px solid {theme.BORDER};"
            "border-radius: 12px; padding: 20px;"
        )
        root.addWidget(self.empty_label)

        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(14)

        self.average_win_card = MetricCard("AVERAGE WIN")
        self.average_loss_card = MetricCard("AVERAGE LOSS")
        self.largest_win_card = MetricCard("LARGEST WIN")
        self.largest_loss_card = MetricCard("LARGEST LOSS")
        self.expectancy_card = MetricCard("AVERAGE P&L / TRADE")
        self.closed_card = MetricCard("CLOSED TRADES")
        self.wins_card = MetricCard("WINNING TRADES")
        self.losses_card = MetricCard("LOSING TRADES")

        cards = [
            self.average_win_card,
            self.average_loss_card,
            self.largest_win_card,
            self.largest_loss_card,
            self.expectancy_card,
            self.closed_card,
            self.wins_card,
            self.losses_card,
        ]

        for index, card in enumerate(cards):
            metrics_grid.addWidget(card, index // 4, index % 4)

        root.addLayout(metrics_grid)

        charts_grid = QGridLayout()
        charts_grid.setSpacing(16)

        self.monthly_chart = self._make_chart_view()
        self.distribution_chart = self._make_chart_view()

        charts_grid.addWidget(
            self._chart_panel("Monthly Reported P&L", self.monthly_chart),
            0, 0,
        )
        charts_grid.addWidget(
            self._chart_panel(
                "Trade Outcome Distribution",
                self.distribution_chart,
            ),
            0, 1,
        )

        root.addLayout(charts_grid)

        note = QLabel(
            "Metrics use reported profit from closed trades. "
            "Commission and swap are not added or subtracted separately "
            "because source-file profit semantics may vary."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 9pt;"
            f"background-color: {theme.SURFACE};"
            "border-radius: 8px; padding: 12px;"
        )
        root.addWidget(note)
        root.addStretch()

    @staticmethod
    def _make_chart_view() -> QChartView:
        view = QChartView()
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(330)
        view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        view.setStyleSheet("background: transparent; border: none;")
        return view

    @staticmethod
    def _chart_panel(title: str, chart_view: QChartView) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 12pt; font-weight: 600;")

        layout.addWidget(heading)
        layout.addWidget(chart_view)

        return panel

    def set_trades(
        self,
        trades: list[Trade],
        currency: str = "USD",
    ) -> None:
        """Recalculate all metrics and charts for the supplied trades."""
        self._trades = list(trades)
        self._currency = currency or "USD"

        metrics = calculate_metrics(self._trades)

        eligible = [
            trade
            for trade in self._trades
            if trade.is_closed and trade.reported_profit is not None
        ]

        if not eligible:
            self.empty_label.show()
            self._reset_cards()
            self.monthly_chart.setChart(
                self._empty_chart("No monthly results")
            )
            self.distribution_chart.setChart(
                self._empty_chart("No trade outcomes")
            )
            return

        self.empty_label.hide()

        wins = [
            trade.reported_profit
            for trade in eligible
            if trade.reported_profit is not None
            and trade.reported_profit > 0
        ]
        losses = [
            trade.reported_profit
            for trade in eligible
            if trade.reported_profit is not None
            and trade.reported_profit < 0
        ]

        self.average_win_card.set_value(
            self._money(metrics.average_win),
            f"{len(wins)} profitable trades",
            theme.GREEN,
        )
        self.average_loss_card.set_value(
            self._money(metrics.average_loss),
            f"{len(losses)} losing trades",
            theme.RED if losses else theme.TEXT_SECONDARY,
        )

        self.largest_win_card.set_value(
            self._money(max(wins) if wins else None),
            "Largest positive reported result",
            theme.GREEN if wins else theme.TEXT_SECONDARY,
        )
        self.largest_loss_card.set_value(
            self._money(min(losses) if losses else None),
            "Largest negative reported result",
            theme.RED if losses else theme.TEXT_SECONDARY,
        )

        total_pnl = sum(
            (trade.reported_profit for trade in eligible),
            Decimal("0"),
        )
        expectancy = total_pnl / len(eligible)

        expectancy_color = (
            theme.GREEN if expectancy > 0
            else theme.RED if expectancy < 0
            else theme.TEXT_PRIMARY
        )

        self.expectancy_card.set_value(
            self._money(expectancy),
            "Mean reported P&L per eligible trade",
            expectancy_color,
        )
        self.closed_card.set_value(
            str(metrics.closed_trades),
            "All closed trades",
        )
        self.wins_card.set_value(
            str(metrics.winning_trades),
            "Reported profit above zero",
            theme.GREEN,
        )
        self.losses_card.set_value(
            str(metrics.losing_trades),
            "Reported profit below zero",
            theme.RED,
        )

        self._build_monthly_chart(eligible)
        self._build_distribution_chart(wins, losses, eligible)

    def _reset_cards(self) -> None:
        cards = [
            self.average_win_card,
            self.average_loss_card,
            self.largest_win_card,
            self.largest_loss_card,
            self.expectancy_card,
            self.closed_card,
            self.wins_card,
            self.losses_card,
        ]

        for card in cards:
            card.set_value("—", "No eligible closed trades")

    def _build_monthly_chart(self, trades: list[Trade]) -> None:
        monthly: dict[str, Decimal] = defaultdict(Decimal)

        for trade in trades:
            if trade.exit_time is None or trade.reported_profit is None:
                continue

            month = trade.exit_time.strftime("%Y-%m")
            monthly[month] += trade.reported_profit

        chart = self._base_chart()
        series = QBarSeries()

        positive_set = QBarSet("Positive monthly P&L")
        positive_set.setColor(QColor(theme.GREEN))

        negative_set = QBarSet("Negative monthly P&L")
        negative_set.setColor(QColor(theme.RED))

        months = sorted(monthly)

        for month in months:
            value = float(monthly[month])
            positive_set.append(value if value > 0 else 0)
            negative_set.append(value if value < 0 else 0)

        series.append(positive_set)
        series.append(negative_set)
        chart.addSeries(series)

        if months:
            axis_x = QBarCategoryAxis()
            axis_x.append(months)
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

            self._set_y_range(
                axis_y,
                [float(monthly[month]) for month in months],
            )

        self.monthly_chart.setChart(chart)

    def _build_distribution_chart(
        self,
        wins: list[Decimal],
        losses: list[Decimal],
        eligible: list[Trade],
    ) -> None:
        chart = self._base_chart()
        series = QBarSeries()

        wins_set = QBarSet("Wins")
        wins_set.setColor(QColor(theme.GREEN))
        wins_set.append(len(wins))

        losses_set = QBarSet("Losses")
        losses_set.setColor(QColor(theme.RED))
        losses_set.append(len(losses))

        breakeven_count = sum(
            1
            for trade in eligible
            if trade.reported_profit == 0
        )

        breakeven_set = QBarSet("Breakeven")
        breakeven_set.setColor(QColor(theme.GOLD))
        breakeven_set.append(breakeven_count)

        series.append(wins_set)
        series.append(losses_set)
        series.append(breakeven_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(["Trade outcomes"])
        axis_x.setLabelsColor(QColor(theme.TEXT_SECONDARY))
        axis_x.setLinePenColor(QColor(theme.BORDER))

        axis_y = QValueAxis()
        axis_y.setTitleText("Number of trades")
        axis_y.setLabelsColor(QColor(theme.TEXT_SECONDARY))
        axis_y.setLinePenColor(QColor(theme.BORDER))
        axis_y.setLabelFormat("%d")
        axis_y.setRange(0, max(len(eligible), 1) * 1.15)

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)

        chart.legend().setVisible(True)
        chart.legend().setLabelColor(QColor(theme.TEXT_SECONDARY))

        self.distribution_chart.setChart(chart)

    def _base_chart(self) -> QChart:
        chart = QChart()
        chart.setBackgroundBrush(QColor(theme.SURFACE))
        chart.setTitleBrush(QColor(theme.TEXT_SECONDARY))
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.legend().setVisible(False)
        return chart

    @staticmethod
    def _empty_chart(message: str) -> QChart:
        chart = QChart()
        chart.setBackgroundBrush(QColor(theme.SURFACE))
        chart.setTitle(message)
        chart.setTitleBrush(QColor(theme.TEXT_SECONDARY))
        chart.legend().hide()
        return chart

    @staticmethod
    def _set_y_range(axis: QValueAxis, values: list[float]) -> None:
        if not values:
            axis.setRange(0, 1)
            return

        low = min(min(values), 0)
        high = max(max(values), 0)

        if low == high:
            axis.setRange(-1, 1)
            return

        padding = (high - low) * 0.12
        axis.setRange(low - padding, high + padding)

    def _money(self, value: Decimal | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:,.2f} {self._currency}"
