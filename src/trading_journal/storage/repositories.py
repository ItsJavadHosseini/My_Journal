
"""Repositories for persisting trading accounts and trades in SQLite."""

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Iterator
from uuid import UUID

from trading_journal.domain.models import (
    Account,
    Trade,
    TradeDirection,
)
from trading_journal.storage.database import Database


def _json_default(value: object) -> str:
    """Serialize supported non-JSON values from source data."""
    if isinstance(value, (Decimal, UUID, datetime)):
        return str(value) if isinstance(value, Decimal) else (
            str(value) if isinstance(value, UUID) else value.isoformat()
        )

    if isinstance(value, Enum):
        return value.value

    raise TypeError(
        f"Object of type {type(value).__name__} "
        "is not JSON serializable."
    )


def _serialize_datetime(value: datetime) -> str:
    return value.isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


class _Repository:
    """Shared connection and transaction handling."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @contextmanager
    def _read_connection(
        self,
        connection: sqlite3.Connection | None = None,
    ) -> Iterator[sqlite3.Connection]:
        if connection is not None:
            yield connection
            return

        with closing(self.database.connect()) as owned_connection:
            yield owned_connection

    @contextmanager
    def _write_connection(
        self,
        connection: sqlite3.Connection | None = None,
    ) -> Iterator[sqlite3.Connection]:
        if connection is not None:
            yield connection
            return

        with self.database.transaction() as owned_connection:
            yield owned_connection


class AccountRepository(_Repository):
    """Create, update, and retrieve trading accounts."""

    def save(
        self,
        account: Account,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        """Insert an account or update its metadata without deleting trades."""
        if not isinstance(account, Account):
            raise TypeError("account must be an Account instance.")

        with self._write_connection(connection) as conn:
            conn.execute(
                """
                INSERT INTO accounts (
                    account_id, name, broker, platform,
                    currency, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    name = excluded.name,
                    broker = excluded.broker,
                    platform = excluded.platform,
                    currency = excluded.currency
                """,
                (
                    str(account.account_id),
                    account.name,
                    account.broker,
                    account.platform,
                    account.currency,
                    _serialize_datetime(account.created_at),
                ),
            )

    def get(
        self,
        account_id: UUID,
        connection: sqlite3.Connection | None = None,
    ) -> Account | None:
        """Return one account by its stable identifier."""
        if not isinstance(account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        with self._read_connection(connection) as conn:
            row = conn.execute(
                """
                SELECT account_id, name, broker, platform,
                       currency, created_at
                FROM accounts
                WHERE account_id = ?
                """,
                (str(account_id),),
            ).fetchone()

        if row is None:
            return None

        created_at = _parse_datetime(row["created_at"])
        assert created_at is not None

        return Account(
            account_id=UUID(row["account_id"]),
            name=row["name"],
            broker=row["broker"],
            platform=row["platform"],
            currency=row["currency"],
            created_at=created_at,
        )

    def list_all(
        self,
        connection: sqlite3.Connection | None = None,
    ) -> list[Account]:
        """Return all accounts ordered by creation time."""
        with self._read_connection(connection) as conn:
            rows = conn.execute(
                """
                SELECT account_id, name, broker, platform,
                       currency, created_at
                FROM accounts
                ORDER BY created_at, account_id
                """
            ).fetchall()

        accounts: list[Account] = []

        for row in rows:
            created_at = _parse_datetime(row["created_at"])
            assert created_at is not None

            accounts.append(
                Account(
                    account_id=UUID(row["account_id"]),
                    name=row["name"],
                    broker=row["broker"],
                    platform=row["platform"],
                    currency=row["currency"],
                    created_at=created_at,
                )
            )

        return accounts


class TradeRepository(_Repository):
    """Persist and query trades without mixing account histories."""

    def save(
        self,
        trade: Trade,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        """Insert one trade. Duplicate trade IDs are rejected."""
        self.save_many((trade,), connection=connection)

    def save_many(
        self,
        trades: tuple[Trade, ...] | list[Trade],
        connection: sqlite3.Connection | None = None,
    ) -> None:
        """Insert multiple trades, optionally inside an existing transaction."""
        if not isinstance(trades, (tuple, list)):
            raise TypeError("trades must be a tuple or list.")

        if not all(isinstance(trade, Trade) for trade in trades):
            raise TypeError("Every item in trades must be a Trade.")

        records = []

        for trade in trades:
            try:
                source_data = json.dumps(
                    dict(trade.source_data),
                    default=_json_default,
                    ensure_ascii=False,
                    allow_nan=False,
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Trade {trade.trade_id} has invalid source_data."
                ) from exc

            records.append(
                (
                    str(trade.trade_id),
                    str(trade.account_id),
                    trade.position_id,
                    trade.symbol,
                    trade.direction.value,
                    str(trade.volume),
                    _serialize_datetime(trade.entry_time),
                    str(trade.entry_price),
                    (
                        str(trade.stop_loss)
                        if trade.stop_loss is not None
                        else None
                    ),
                    (
                        str(trade.take_profit)
                        if trade.take_profit is not None
                        else None
                    ),
                    (
                        _serialize_datetime(trade.exit_time)
                        if trade.exit_time is not None
                        else None
                    ),
                    (
                        str(trade.exit_price)
                        if trade.exit_price is not None
                        else None
                    ),
                    (
                        str(trade.commission)
                        if trade.commission is not None
                        else None
                    ),
                    (
                        str(trade.swap)
                        if trade.swap is not None
                        else None
                    ),
                    (
                        str(trade.reported_profit)
                        if trade.reported_profit is not None
                        else None
                    ),
                    source_data,
                )
            )

        with self._write_connection(connection) as conn:
            conn.executemany(
                """
                INSERT INTO trades (
                    trade_id, account_id, position_id, symbol,
                    direction, volume, entry_time, entry_price,
                    stop_loss, take_profit, exit_time, exit_price,
                    commission, swap, reported_profit, source_data
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                records,
            )

    def get(
        self,
        trade_id: UUID,
        connection: sqlite3.Connection | None = None,
    ) -> Trade | None:
        """Return one trade by its unique identifier."""
        if not isinstance(trade_id, UUID):
            raise TypeError("trade_id must be a UUID.")

        with self._read_connection(connection) as conn:
            row = conn.execute(
                "SELECT * FROM trades WHERE trade_id = ?",
                (str(trade_id),),
            ).fetchone()

        return self._to_domain(row) if row is not None else None

    def list_by_account(
        self,
        account_id: UUID,
        connection: sqlite3.Connection | None = None,
    ) -> list[Trade]:
        """Return only trades belonging to the requested account."""
        if not isinstance(account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        with self._read_connection(connection) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM trades
                WHERE account_id = ?
                ORDER BY entry_time, trade_id
                """,
                (str(account_id),),
            ).fetchall()

        return [self._to_domain(row) for row in rows]

    def count_by_account(
        self,
        account_id: UUID,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        """Return the number of trades for one account."""
        if not isinstance(account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        with self._read_connection(connection) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM trades
                WHERE account_id = ?
                """,
                (str(account_id),),
            ).fetchone()

        return int(row[0])

    def delete_by_account(
        self,
        account_id: UUID,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        """Delete only the trades belonging to one account."""
        if not isinstance(account_id, UUID):
            raise TypeError("account_id must be a UUID.")

        with self._write_connection(connection) as conn:
            cursor = conn.execute(
                "DELETE FROM trades WHERE account_id = ?",
                (str(account_id),),
            )
            return cursor.rowcount

    @staticmethod
    def _to_domain(row: sqlite3.Row) -> Trade:
        """Convert a database record back into a domain Trade."""
        source_data = json.loads(row["source_data"])

        if not isinstance(source_data, dict):
            raise ValueError("Stored source_data must be a JSON object.")

        entry_time = _parse_datetime(row["entry_time"])
        assert entry_time is not None

        return Trade(
            trade_id=UUID(row["trade_id"]),
            account_id=UUID(row["account_id"]),
            position_id=row["position_id"],
            symbol=row["symbol"],
            direction=TradeDirection(row["direction"]),
            volume=Decimal(row["volume"]),
            entry_time=entry_time,
            entry_price=Decimal(row["entry_price"]),
            stop_loss=(
                Decimal(row["stop_loss"])
                if row["stop_loss"] is not None
                else None
            ),
            take_profit=(
                Decimal(row["take_profit"])
                if row["take_profit"] is not None
                else None
            ),
            exit_time=_parse_datetime(row["exit_time"]),
            exit_price=(
                Decimal(row["exit_price"])
                if row["exit_price"] is not None
                else None
            ),
            commission=(
                Decimal(row["commission"])
                if row["commission"] is not None
                else None
            ),
            swap=(
                Decimal(row["swap"])
                if row["swap"] is not None
                else None
            ),
            reported_profit=(
                Decimal(row["reported_profit"])
                if row["reported_profit"] is not None
                else None
            ),
            source_data=source_data,
        )
