
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from trading_journal.domain.models import Trade


ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class EquityPoint:
    trade_id: UUID
    exit_time: datetime
    cumulative_pnl: Decimal


@dataclass(frozen=True, slots=True)
class TradingMetrics:
    total_trades: int
    closed_trades: int
    open_trades: int
    trades_with_pnl: int

    winning_trades: int
    losing_trades: int
    breakeven_trades: int

    reported_pnl: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    win_rate: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None

    max_drawdown: Decimal
    equity_curve: tuple[EquityPoint, ...]


def calculate_metrics(
    trades: Iterable[Trade],
) -> TradingMetrics:
    """Calculate performance metrics from closed trades."""

    all_trades = list(trades)

    closed_trades = [
        trade for trade in all_trades
        if trade.is_closed
    ]

    open_trades = len(all_trades) - len(closed_trades)

    eligible_trades = [
        trade for trade in closed_trades
        if trade.reported_profit is not None
    ]

    profits = [
        trade.reported_profit
        for trade in eligible_trades
    ]

    winning_profits = [p for p in profits if p > ZERO]
    losing_profits = [p for p in profits if p < ZERO]

    breakeven_count = sum(
        1 for p in profits if p == ZERO
    )

    gross_profit = sum(winning_profits, ZERO)
    gross_loss = abs(sum(losing_profits, ZERO))
    reported_pnl = sum(profits, ZERO)

    win_rate = (
        Decimal(len(winning_profits))
        / Decimal(len(profits))
        * Decimal("100")
        if profits else None
    )

    average_win = (
        gross_profit / Decimal(len(winning_profits))
        if winning_profits else None
    )

    average_loss = (
        gross_loss / Decimal(len(losing_profits))
        if losing_profits else None
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > ZERO else None
    )

    # Exit times are required for a chronological equity curve.
    ordered_trades = sorted(
        eligible_trades,
        key=lambda trade: (
            trade.exit_time,
            str(trade.trade_id),
        ),
    )

    cumulative_pnl = ZERO
    peak_pnl = ZERO
    max_drawdown = ZERO
    equity_points = []

    for trade in ordered_trades:
        cumulative_pnl += trade.reported_profit
        peak_pnl = max(peak_pnl, cumulative_pnl)

        drawdown = peak_pnl - cumulative_pnl
        max_drawdown = max(max_drawdown, drawdown)

        equity_points.append(
            EquityPoint(
                trade_id=trade.trade_id,
                exit_time=trade.exit_time,
                cumulative_pnl=cumulative_pnl,
            )
        )

    return TradingMetrics(
        total_trades=len(all_trades),
        closed_trades=len(closed_trades),
        open_trades=open_trades,
        trades_with_pnl=len(eligible_trades),
        winning_trades=len(winning_profits),
        losing_trades=len(losing_profits),
        breakeven_trades=breakeven_count,
        reported_pnl=reported_pnl,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        max_drawdown=max_drawdown,
        equity_curve=tuple(equity_points),
    )
