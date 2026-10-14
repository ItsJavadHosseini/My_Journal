
"""Core domain models for Trading Journal.

This module contains framework-independent models for trading accounts
and trades. File parsing, persistence, UI, and analytics belong elsewhere.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4


def _validate_text(value: str, field_name: str) -> None:
    """Ensure a required text field is not empty."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")


def _validate_optional_decimal(
    value: Decimal | None,
    field_name: str,
    *,
    strictly_positive: bool = False,
    non_negative: bool = False,
) -> None:
    """Validate a financial value without converting its type implicitly."""
    if value is None:
        return

    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be Decimal or None.")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if strictly_positive and value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    if non_negative and value < 0:
        raise ValueError(f"{field_name} cannot be negative.")


class TradeDirection(str, Enum):
    """Normalized direction of a trade."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class Account:
    """Identity and basic metadata of a trading account.

    account_id is the stable identifier used to isolate account data.
    It should remain unchanged when the account's display name changes.
    """

    name: str
    account_id: UUID = field(default_factory=uuid4)
    broker: str | None = None
    platform: str | None = None
    currency: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        _validate_text(self.name, "name")

        if not isinstance(self.account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        for field_name in ("broker", "platform"):
            value = getattr(self, field_name)
            if value is not None:
                _validate_text(value, field_name)

        if self.currency is not None:
            _validate_text(self.currency, "currency")
            object.__setattr__(
                self, "currency", self.currency.strip().upper()
            )

        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime.")

        if (
            self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class Trade:
    """Standardized representation of one trading position/trade record.

    Financial values use Decimal for precision.
    Optional values represent information that may be absent from a source.

    reported_profit preserves the profit reported by the source. Its
    inclusion or exclusion of commission and swap must be established
    by the relevant importer/source format before calculating net P&L.
    """

    account_id: UUID
    symbol: str
    direction: TradeDirection
    volume: Decimal
    entry_time: datetime
    entry_price: Decimal

    trade_id: UUID = field(default_factory=uuid4)
    position_id: str | None = None

    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None

    exit_time: datetime | None = None
    exit_price: Decimal | None = None

    commission: Decimal | None = None
    swap: Decimal | None = None
    reported_profit: Decimal | None = None

    # Original source values for traceability, when available.
    source_data: Mapping[str, object] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        if not isinstance(self.trade_id, UUID):
            raise TypeError("trade_id must be a UUID.")

        _validate_text(self.symbol, "symbol")
        object.__setattr__(self, "symbol", self.symbol.strip())

        if not isinstance(self.direction, TradeDirection):
            raise TypeError(
                "direction must be a TradeDirection value."
            )

        _validate_optional_decimal(
            self.volume, "volume", strictly_positive=True
        )
        if self.volume is None:
            raise ValueError("volume is required.")

        _validate_optional_decimal(
            self.entry_price, "entry_price", strictly_positive=True
        )
        if self.entry_price is None:
            raise ValueError("entry_price is required.")

        for field_name in ("stop_loss", "take_profit", "exit_price"):
            _validate_optional_decimal(
                getattr(self, field_name), field_name,
                strictly_positive=True,
            )

        for field_name in ("commission", "swap", "reported_profit"):
            _validate_optional_decimal(
                getattr(self, field_name), field_name
            )

        if not isinstance(self.entry_time, datetime):
            raise TypeError("entry_time must be a datetime.")

        if self.exit_time is not None and not isinstance(
            self.exit_time, datetime
        ):
            raise TypeError("exit_time must be a datetime or None.")

        # An open trade has neither exit field; a closed trade has both.
        if (self.exit_time is None) != (self.exit_price is None):
            raise ValueError(
                "exit_time and exit_price must either both be present "
                "or both be None."
            )

        if self.position_id is not None:
            _validate_text(self.position_id, "position_id")
            object.__setattr__(
                self, "position_id", self.position_id.strip()
            )

        if not isinstance(self.source_data, Mapping):
            raise TypeError("source_data must be a mapping.")

        # Prevent callers from modifying the stored mapping after creation.
        object.__setattr__(
            self,
            "source_data",
            MappingProxyType(dict(self.source_data)),
        )

    @property
    def is_closed(self) -> bool:
        """Whether the trade has both exit time and exit price."""
        return self.exit_time is not None
