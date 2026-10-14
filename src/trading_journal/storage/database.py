
"""SQLite database infrastructure for Trading Journal."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "trading_journal.db"
)


class Database:
    """Manage SQLite connections, schema creation, and transactions."""

    def __init__(
        self,
        database_path: str | Path = DEFAULT_DATABASE_PATH,
    ) -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        """Create a configured SQLite connection."""
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        connection = sqlite3.connect(
            str(self.database_path),
            timeout=30.0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")

        return connection

    def initialize(self) -> None:
        """Create tables and indexes atomically if they do not exist."""

        statements = (
            """
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
                    CHECK (length(trim(name)) > 0),
                broker TEXT,
                platform TEXT,
                currency TEXT,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                position_id TEXT,
                symbol TEXT NOT NULL
                    CHECK (length(trim(symbol)) > 0),
                direction TEXT NOT NULL
                    CHECK (direction IN ('BUY', 'SELL')),
                volume TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                entry_price TEXT NOT NULL,
                stop_loss TEXT,
                take_profit TEXT,
                exit_time TEXT,
                exit_price TEXT,
                commission TEXT,
                swap TEXT,
                reported_profit TEXT,
                source_data TEXT NOT NULL DEFAULT '{}',

                FOREIGN KEY (account_id)
                    REFERENCES accounts(account_id)
                    ON DELETE CASCADE,

                CHECK (
                    (exit_time IS NULL AND exit_price IS NULL)
                    OR
                    (exit_time IS NOT NULL AND exit_price IS NOT NULL)
                )
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trades_account
            ON trades(account_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trades_account_entry_time
            ON trades(account_id, entry_time)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trades_account_symbol
            ON trades(account_id, symbol)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_trades_account_position
            ON trades(account_id, position_id)
            """,
        )

        with self.transaction() as connection:
            for statement in statements:
                connection.execute(statement)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit on success and roll back on failure."""
        connection = self.connect()

        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
