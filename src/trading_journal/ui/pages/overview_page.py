"""Overview dashboard page."""

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

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
    QDateTimeAxis,
    QLineSeries,
    QValueAxis,
)

from trading_journal.analytics.metrics import calculate_metrics
from trading_journal.domain.models import Trade
from trading_journal.ui import theme
from trading_journal.ui.components.metric_card import MetricCard


class OverviewPage(QWidget):
    """Overview of the selected account's trading results."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._trades: list[Trade] = []
        self._account_currency = "USD"

        self._build_ui()
        self.set_trades([])

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(20)

        header = QHBoxLayout()

        title_area = QVBoxLayout()
        title = QLabel("Overview")
        title.setStyleSheet("font-size: 24pt; font-weight: 700;")

        subtitle = QLabel(
            "A consolidated view of your trading performance"
        )
        subtitle.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 10pt;"
        )

        title_area.addWidget(title)
        title_area.addWidget(subtitle)
        header.addLayout(title_area)
        header.addStretch()

        self.account_label = QLabel("No account selected")
        self.account_label.setStyleSheet(
            f"color: {theme.GOLD}; font-weight: 600;"
        )
        header.addWidget(self.account_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header)

        self.empty_label = QLabel(
            "No trading data available for this account.\n"
            "Create or select an account, then import your trading history."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setMinimumHeight(120)
        self.empty_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY};"
            f"background-color: {theme.SURFACE};"
            f"border: 1px solid {theme.BORDER};"
            "border-radius: 12px; padding: 24px;"
        )
        root.addWidget(self.empty_label)

        cards = QGridLayout()
        cards.setSpacing(14)

        self.total_pnl_card = MetricCard(
            "REPORTED P&L", "—", "Closed trades with reported profit"
        )
        self.win_rate_card = MetricCard("WIN RATE", "—")
        self.profit_factor_card = MetricCard("PROFIT FACTOR", "—")
        self.drawdown_card = MetricCard("MAX DRAWDOWN", "—")

        card_widgets = [
            self.total_pnl_card,
            self.win_rate_card,
            self.profit_factor_card,
            self.drawdown_card,
        ]

        for index, card in enumerate(card_widgets):
            cards.addWidget(card, 0, index)

        root.addLayout(cards)

        chart_grid = QGridLayout()
        chart_grid.setSpacing(16)

        self.equity_chart_view = self._make_chart_view()
        self.drawdown_chart_view = self._make_chart_view()
        self.daily_chart_view = self._make_chart_view()

        chart_grid.addWidget(
            self._chart_panel("Equity Curve", self.equity_chart_view),
            0, 0, 1, 2,
        )
        chart_grid.addWidget(
            self._chart_panel("Drawdown", self.drawdown_chart_view),
            1, 0,
        )
        chart_grid.addWidget(
            self._chart_panel("Daily Reported P&L", self.daily_chart_view),
            1, 1,
        )

        root.addLayout(chart_grid)
        root.addStretch()

    @staticmethod
    def _make_chart_view() -> QChartView:
        view = QChartView()
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(270)
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

    def set_account_name(self, name: str | None) -> None:
        self.account_label.setText(name or "No account selected")

    def set_trades(
        self,
        trades: list[Trade],
        currency: str = "USD",
    ) -> None:
        """Refresh the page from the selected account's trades."""
        self._trades = list(trades)
        self._account_currency = currency or "USD"

        metrics = calculate_metrics(self._trades)

        if metrics.closed_trades == 0:
            self.empty_label.show()
            self._set_empty_state()
            self._show_empty_charts()
            return

        self.empty_label.hide()

        pnl = metrics.reported_pnl
        pnl_color = (
            theme.GREEN if pnl > 0
            else theme.RED if pnl < 0
            else theme.TEXT_PRIMARY
        )

        self.total_pnl_card.set_value(
            self._format_money(pnl),
            "Sum of reported profit on eligible closed trades",
            pnl_color,
        )
        self.win_rate_card.set_value(
            f"{metrics.win_rate:.1f}%",
            f"{metrics.winning_trades} wins / "
            f"{metrics.losing_trades} losses",
            theme.GREEN if metrics.win_rate >= 50 else theme.GOLD,
        )

        if metrics.profit_factor is None:
            factor_text = "N/A"
            factor_subtitle = "No gross losses recorded"
            factor_color = theme.TEXT_SECONDARY
        else:
            factor_text = f"{metrics.profit_factor:.2f}"
            factor_subtitle = "Gross profit / gross loss"
            factor_color = (
                theme.GREEN
                if metrics.profit_factor >= 1
                else theme.RED
            )

        self.profit_factor_card.set_value(
            factor_text, factor_subtitle, factor_color
        )

        self.drawdown_card.set_value(
            self._format_money(metrics.max_drawdown),
            "Maximum peak-to-trough decline",
            theme.RED if metrics.max_drawdown > 0 else theme.TEXT_PRIMARY,
        )

        self._build_equity_chart(metrics.equity_curve)
        self._build_drawdown_chart(metrics.equity_curve)
        self._build_daily_chart()

    def _set_empty_state(self) -> None:
        self.total_pnl_card.set_value("—", "No eligible closed trades")
        self.win_rate_card.set_value("—", "No eligible closed trades")
        self.profit_factor_card.set_value("—", "No eligible closed trades")
        self.drawdown_card.set_value("—", "No eligible closed trades")

    def _show_empty_charts(self) -> None:
        self.equity_chart_view.setChart(self._empty_chart("No equity data"))
        self.drawdown_chart_view.setChart(
            self._empty_chart("No drawdown data")
        )
        self.daily_chart_view.setChart(
            self._empty_chart("No daily P&L data")
        )

    @staticmethod
    def _empty_chart(message: str) -> QChart:
        chart = QChart()
        chart.setBackgroundBrush(QColor(theme.SURFACE))
        chart.setTitle(message)
        chart.setTitleBrush(QColor(theme.TEXT_SECONDARY))
        chart.setTitleFont(chart.titleFont())
        chart.legend().hide()
        return chart

    def _build_equity_chart(self, points) -> None:
        chart = self._base_chart()

        series = QLineSeries()
        series.setName("Cumulative reported P&L")
        series.setColor(QColor(theme.GREEN))
        series.setPen(series.pen())

        for point in points:
            series.append(
                float(point.exit_time.timestamp() * 1000),
                float(point.cumulative_pnl),
            )

        chart.addSeries(series)

        if points:
            axis_x = QDateTimeAxis()
            axis_x.setFormat("dd MMM")
            axis_x.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis_x.setLinePenColor(QColor(theme.BORDER))

            axis_y = QValueAxis()
            axis_y.setTitleText(self._account_currency)
            axis_y.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis_y.setLinePenColor(QColor(theme.BORDER))
            axis_y.setLabelFormat("%.2f")

            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)

            first_ms = points[0].exit_time.timestamp() * 1000
            last_ms = points[-1].exit_time.timestamp() * 1000
            if first_ms == last_ms:
                first_ms -= 86_400_000
                last_ms += 86_400_000
            axis_x.setRange(
                __import__("PySide6.QtCore", fromlist=["QDateTime"])
                .QDateTime.fromMSecsSinceEpoch(int(first_ms)),
                __import__("PySide6.QtCore", fromlist=["QDateTime"])
                .QDateTime.fromMSecsSinceEpoch(int(last_ms)),
            )
            self._set_y_range(axis_y, [float(p.cumulative_pnl) for p in points])

        self.equity_chart_view.setChart(chart)

    def _build_drawdown_chart(self, points) -> None:
        chart = self._base_chart()
        series = QLineSeries()
        series.setName("Drawdown")
        series.setColor(QColor(theme.RED))

        peak = Decimal("0")
        values = []

        for point in points:
            peak = max(peak, point.cumulative_pnl)
            drawdown = peak - point.cumulative_pnl
            x = point.exit_time.timestamp() * 1000
            y = float(drawdown)
            series.append(x, y)
            values.append(y)

        chart.addSeries(series)

        if points:
            axis_x = QDateTimeAxis()
            axis_x.setFormat("dd MMM")
            axis_x.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis_x.setLinePenColor(QColor(theme.BORDER))

            axis_y = QValueAxis()
            axis_y.setTitleText(self._account_currency)
            axis_y.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis_y.setLinePenColor(QColor(theme.BORDER))
            axis_y.setLabelFormat("%.2f")

            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)

            first_ms = points[0].exit_time.timestamp() * 1000
            last_ms = points[-1].exit_time.timestamp() * 1000
            if first_ms == last_ms:
                first_ms -= 86_400_000
                last_ms += 86_400_000

            from PySide6.QtCore import QDateTime

            axis_x.setRange(
                QDateTime.fromMSecsSinceEpoch(int(first_ms)),
                QDateTime.fromMSecsSinceEpoch(int(last_ms)),
            )
            self._set_y_range(axis_y, values, include_zero=True)

        self.drawdown_chart_view.setChart(chart)

    def _build_daily_chart(self) -> None:
        daily_pnl: dict[str, Decimal] = defaultdict(Decimal)

        for trade in self._trades:
            if (
                not trade.is_closed
                or trade.exit_time is None
                or trade.reported_profit is None
            ):
                continue

            day = trade.exit_time.date().isoformat()
            daily_pnl[day] += trade.reported_profit

        chart = self._base_chart()
        series = QBarSeries()
        profits = QBarSet("Daily reported P&L")
        profits.setColor(QColor(theme.GREEN))
        losses = QBarSet("Daily reported loss")
        losses.setColor(QColor(theme.RED))

        days = sorted(daily_pnl)

        for day in days:
            value = float(daily_pnl[day])
            profits.append(value if value > 0 else 0)
            losses.append(value if value < 0 else 0)

        series.append(profits)
        series.append(losses)
        chart.addSeries(series)

        if days:
            axis_x = QBarCategoryAxis()
            axis_x.append([day[5:] for day in days])
            axis_x.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis_x.setLinePenColor(QColor(theme.BORDER))

            axis_y = QValueAxis()
            axis_y.setTitleText(self._account_currency)
            axis_y.setLabelsColor(QColor(theme.TEXT_SECONDARY))
            axis_y.setLinePenColor(QColor(theme.BORDER))
            axis_y.setLabelFormat("%.2f")

            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)
            self._set_y_range(
                axis_y,
                [float(daily_pnl[day]) for day in days],
                include_zero=True,
            )

        self.daily_chart_view.setChart(chart)

    def _base_chart(self) -> QChart:
        chart = QChart()
        chart.setBackgroundBrush(QColor(theme.SURFACE))
        chart.setTitleBrush(QColor(theme.TEXT_SECONDARY))
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.legend().setVisible(False)
        chart.setMargins(__import__("PySide6.QtCore", fromlist=["QMargins"])
                         .QMargins(8, 8, 8, 8))
        return chart

    @staticmethod
    def _set_y_range(
        axis: QValueAxis,
        values: list[float],
        *,
        include_zero: bool = False,
    ) -> None:
        if not values:
            axis.setRange(0, 1)
            return

        low = min(values)
        high = max(values)

        if include_zero:
            low = min(low, 0)
            high = max(high, 0)

        if low == high:
            padding = max(abs(low) * 0.1, 1)
        else:
            padding = (high - low) * 0.12

        axis.setRange(low - padding, high + padding)

    def _format_money(self, value: Decimal) -> str:
        return f"{value:,.2f} {self._account_currency}"
