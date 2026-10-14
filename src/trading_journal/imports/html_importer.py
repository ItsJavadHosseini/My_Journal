
"""Import MetaTrader trade-history reports from HTML files."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID

from bs4 import BeautifulSoup
from bs4.element import Tag

from trading_journal.domain.models import Trade, TradeDirection
from trading_journal.imports.base import (
    ImportResult,
    ImportValidationError,
    TradeImporter,
)


SECTION_TITLE = "positions"

SECTION_TERMINATORS = {
    "orders",
    "deals",
    "results",
    "history",
    "open positions",
    "closed positions",
}

HEADER_ALIASES = {
    "position": {"position", "positionid", "ticket"},
    "symbol": {"symbol", "instrument"},
    "type": {"type", "direction", "side"},
    "volume": {"volume", "lots", "size"},
    "sl": {"sl", "s/l", "stop loss"},
    "tp": {"tp", "t/p", "take profit"},
    "commission": {"commission", "comm"},
    "swap": {"swap", "swaps"},
    "profit": {"profit", "p/l", "pnl"},
}

DATETIME_FORMATS = (
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y.%m.%d",
    "%Y-%m-%d",
)


class HTMLImporter(TradeImporter):
    """Import the Positions table from an HTML MetaTrader report."""

    supported_extensions = frozenset({".html", ".htm"})

    def import_file(
        self,
        file_path: str | Path,
        account_id: UUID,
    ) -> ImportResult:
        if not isinstance(account_id, UUID):
            raise ImportValidationError(
                "account_id must be a UUID matching the domain model."
            )

        path = Path(file_path)

        if not path.exists():
            raise ImportValidationError(f"File not found: {path}")

        if not path.is_file():
            raise ImportValidationError(f"Path is not a file: {path}")

        if not self.supports(path):
            raise ImportValidationError(
                f"Unsupported HTML file extension {path.suffix!r}. "
                "Supported extensions: .html, .htm."
            )

        html_text = self._read_html(path)
        soup = BeautifulSoup(html_text, "html.parser")

        section_table = self._find_positions_table(soup)
        header, rows = self._extract_table_rows(section_table)
        columns = self._resolve_columns(header)

        trades: list[Trade] = []
        rows_read = 0

        for row_number, row in enumerate(rows, start=1):
            if self._is_blank_row(row):
                continue

            if self._is_section_terminator(row):
                break

            if self._is_footer_row(row):
                break

            if not self._looks_like_trade_row(row, columns):
                if self._is_non_trade_note(row):
                    continue

                raise ImportValidationError(
                    f"HTML table row {row_number}: non-empty row inside "
                    "the Positions table could not be identified as a trade. "
                    "Import cancelled to avoid silently losing data."
                )

            trade = self._parse_trade(
                row,
                columns,
                account_id=account_id,
                row_number=row_number,
            )
            trades.append(trade)
            rows_read += 1

        if not trades:
            raise ImportValidationError(
                "No trades were found in the HTML Positions table."
            )

        return ImportResult(
            account_id=account_id,
            trades=tuple(trades),
            source_path=str(path.resolve()),
            source_format="html",
            rows_read=rows_read,
        )

    @staticmethod
    def _read_html(path: Path) -> str:
        """Read HTML with common encodings used by exported reports."""
        raw = path.read_bytes()

        for encoding in ("utf-8-sig", "utf-16", "cp1252"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        raise ImportValidationError(
            f"Could not decode HTML file {path.name!r}. "
            "Supported encodings: UTF-8, UTF-16, and Windows-1252."
        )

    @staticmethod
    def _normalize(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    @classmethod
    def _normalize_header(cls, value: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", cls._normalize(value))

    @classmethod
    def _find_positions_table(cls, soup: BeautifulSoup) -> Tag:
        """
        Find the HTML table associated with the Positions section.

        The section title can appear in a heading, paragraph, or a table cell.
        A candidate table must have a recognizable trade header.
        """
        tables = soup.find_all("table")

        for table in tables:
            table_text = cls._normalize(table.get_text(" ", strip=True))

            if not table_text:
                continue

            rows = table.find_all("tr")

            for row_index, tr in enumerate(rows):
                row_cells = cls._extract_row_cells(tr)
                if not any(
                    cls._normalize(cell) == SECTION_TITLE for cell in row_cells
                ):
                    continue

                # The section title and header may be in the same table.
                for header_tr in rows[row_index + 1 :]:
                    header = cls._extract_row_cells(header_tr)
                    if cls._is_positions_header(header):
                        return table

        # Some exports place the section title outside its table.
        for heading in soup.find_all(
            ["h1", "h2", "h3", "h4", "p", "div", "b", "strong"]
        ):
            if cls._normalize(heading.get_text(" ", strip=True)) != SECTION_TITLE:
                continue

            for sibling in heading.find_all_next("table"):
                header = cls._find_header_in_table(sibling)
                if header is not None and cls._is_positions_header(header):
                    return sibling

        # Fallback for HTML exports where the section title is absent but the
        # table structure itself is recognizable. This is accepted only when
        # exactly one table matches, to avoid importing Orders or Deals.
        candidates = [
            table
            for table in tables
            if cls._find_header_in_table(table) is not None
            and cls._is_positions_header(cls._find_header_in_table(table) or [])
        ]

        if len(candidates) == 1:
            return candidates[0]

        if len(candidates) > 1:
            raise ImportValidationError(
                "Multiple HTML tables resemble a Positions table, but their "
                "section identity is ambiguous. Refusing to guess."
            )

        raise ImportValidationError(
            "Could not find an HTML table for the Positions section."
        )

    @classmethod
    def _find_header_in_table(cls, table: Tag) -> list[str] | None:
        for tr in table.find_all("tr"):
            row = cls._extract_row_cells(tr)
            if cls._is_positions_header(row):
                return row
        return None

    
    
    @staticmethod
    def _extract_row_cells(tr: Tag) -> list[str]:
        """Extract visible cells and ignore hidden placeholder cells."""
        values: list[str] = []

        for cell in tr.find_all(["th", "td"], recursive=False):
            classes = cell.get("class", [])

            if isinstance(classes, str):
                classes = classes.split()

            if any(
                str(class_name).lower() == "hidden"
                for class_name in classes
            ):
                continue

            style = str(cell.get("style", "")).lower()
            style = re.sub(r"\s+", "", style)

            if (
                "display:none" in style
                or "visibility:hidden" in style
            ):
                continue

            values.append(cell.get_text(" ", strip=True))

        return values

    @classmethod
    def _extract_table_rows(
        cls,
        table: Tag,
    ) -> tuple[list[str], list[list[str]]]:
        """
        Extract header and data rows after the recognized Positions header.
        """
        rows = table.find_all("tr")
        header_index: int | None = None
        header: list[str] | None = None

        for index, tr in enumerate(rows):
            candidate = cls._extract_row_cells(tr)
            if cls._is_positions_header(candidate):
                header_index = index
                header = candidate
                break

        if header_index is None or header is None:
            raise ImportValidationError(
                "The selected HTML table does not contain a recognizable "
                "Positions header."
            )

        data_rows: list[list[str]] = []

        for tr in rows[header_index + 1 :]:
            row = cls._extract_row_cells(tr)

            if cls._is_blank_row(row):
                continue

            if cls._is_section_terminator(row):
                break

            data_rows.append(row)

        return header, data_rows

    @classmethod
    def _is_positions_header(cls, row: Sequence[Any]) -> bool:
        normalized = [cls._normalize_header(value) for value in row if value]

        counts: dict[str, int] = {}
        for value in normalized:
            counts[value] = counts.get(value, 0) + 1

        time_count = counts.get("time", 0)
        price_count = counts.get("price", 0)

        required_aliases = (
            {"position", "positionid", "ticket"},
            {"symbol", "instrument"},
            {"type", "direction", "side"},
            {"volume", "lots", "size"},
            {"profit", "pl", "pnl"},
        )

        return (
            time_count >= 2
            and price_count >= 2
            and all(any(alias in counts for alias in group) for group in required_aliases)
        )

    @classmethod
    def _resolve_columns(cls, header: Sequence[str]) -> dict[str, int | None]:
        time_indices: list[int] = []
        price_indices: list[int] = []
        found: dict[str, int] = {}

        aliases = {
            key: {cls._normalize_header(alias) for alias in values}
            for key, values in HEADER_ALIASES.items()
        }

        for index, raw in enumerate(header):
            normalized = cls._normalize_header(raw)

            if normalized == "time":
                time_indices.append(index)
                continue

            if normalized == "price":
                price_indices.append(index)
                continue

            for field, field_aliases in aliases.items():
                if normalized in field_aliases:
                    if field in found:
                        raise ImportValidationError(
                            f"Duplicate HTML header for column {field!r}."
                        )
                    found[field] = index
                    break

        missing = [
            field
            for field in ("position", "symbol", "type", "volume", "profit")
            if field not in found
        ]

        if len(time_indices) < 2:
            missing.append("two Time columns")

        if len(price_indices) < 2:
            missing.append("two Price columns")

        if missing:
            raise ImportValidationError(
                "Missing required HTML columns: " + ", ".join(missing)
            )

        return {
            "entry_time": time_indices[0],
            "exit_time": time_indices[1],
            "entry_price": price_indices[0],
            "exit_price": price_indices[1],
            "position": found["position"],
            "symbol": found["symbol"],
            "direction": found["type"],
            "volume": found["volume"],
            "sl": found.get("sl"),
            "tp": found.get("tp"),
            "commission": found.get("commission"),
            "swap": found.get("swap"),
            "profit": found["profit"],
        }

    @classmethod
    def _parse_trade(
        cls,
        row: Sequence[Any],
        columns: dict[str, int | None],
        *,
        account_id: UUID,
        row_number: int,
    ) -> Trade:
        def get(field: str) -> Any:
            index = columns[field]
            if index is None or index >= len(row):
                return None
            return row[index]

        position_id = cls._text(get("position"))
        symbol = cls._text(get("symbol"))
        direction_text = cls._text(get("direction")).upper()

        if not position_id:
            raise ImportValidationError(
                f"HTML row {row_number}: Position identifier is empty."
            )

        if not symbol:
            raise ImportValidationError(
                f"HTML row {row_number}: Symbol is empty."
            )

        try:
            direction = TradeDirection(direction_text)
        except ValueError as exc:
            raise ImportValidationError(
                f"HTML row {row_number}: invalid trade direction "
                f"{direction_text!r}; expected Buy or Sell."
            ) from exc

        entry_time = cls._parse_datetime(
            get("entry_time"), field="entry_time", row_number=row_number
        )
        entry_price = cls._parse_decimal(
            get("entry_price"), field="entry_price", row_number=row_number
        )
        volume = cls._parse_decimal(
            get("volume"), field="volume", row_number=row_number
        )

        exit_time_raw = get("exit_time")
        exit_price_raw = get("exit_price")

        exit_time = (
            cls._parse_datetime(
                exit_time_raw, field="exit_time", row_number=row_number
            )
            if cls._text(exit_time_raw)
            else None
        )

        exit_price = (
            cls._parse_decimal(
                exit_price_raw, field="exit_price", row_number=row_number
            )
            if cls._text(exit_price_raw)
            else None
        )

        if (exit_time is None) != (exit_price is None):
            raise ImportValidationError(
                f"HTML row {row_number}: exit_time and exit_price must both "
                "be present or both be empty."
            )

        stop_loss = cls._parse_decimal(
            get("sl"),
            field="stop_loss",
            row_number=row_number,
            required=False,
        )
        take_profit = cls._parse_decimal(
            get("tp"),
            field="take_profit",
            row_number=row_number,
            required=False,
        )
        commission = cls._parse_decimal(
            get("commission"),
            field="commission",
            row_number=row_number,
            required=False,
            default=Decimal("0"),
        )
        swap = cls._parse_decimal(
            get("swap"),
            field="swap",
            row_number=row_number,
            required=False,
            default=Decimal("0"),
        )
        reported_profit = cls._parse_decimal(
            get("profit"), field="reported_profit", row_number=row_number
        )

        try:
            return Trade(
                account_id=account_id,
                symbol=symbol,
                direction=direction,
                volume=volume,
                entry_time=entry_time,
                entry_price=entry_price,
                position_id=position_id,
                stop_loss=stop_loss,
                take_profit=take_profit,
                exit_time=exit_time,
                exit_price=exit_price,
                commission=commission,
                swap=swap,
                reported_profit=reported_profit,
            )
        except (TypeError, ValueError) as exc:
            raise ImportValidationError(
                f"HTML row {row_number}: trade violates domain validation: {exc}"
            ) from exc

    @classmethod
    def _looks_like_trade_row(
        cls,
        row: Sequence[Any],
        columns: dict[str, int | None],
    ) -> bool:
        for field in ("position", "symbol", "entry_time"):
            index = columns[field]
            if index is not None and index < len(row) and cls._text(row[index]):
                return True
        return False

    @classmethod
    def _is_section_terminator(cls, row: Sequence[Any]) -> bool:
        return any(cls._normalize(value) in SECTION_TERMINATORS for value in row)

    @classmethod
    def _is_footer_row(cls, row: Sequence[Any]) -> bool:
        prefixes = ("balance:", "equity:", "credit facility:", "margin:", "free margin:")
        return any(
            cls._normalize(value).startswith(prefix)
            for value in row
            for prefix in prefixes
        )

    @classmethod
    def _is_blank_row(cls, row: Sequence[Any]) -> bool:
        return all(not cls._text(value) for value in row)

    @classmethod
    def _is_non_trade_note(cls, row: Sequence[Any]) -> bool:
        non_empty = [cls._text(value) for value in row if cls._text(value)]
        if len(non_empty) != 1:
            return False

        value = cls._normalize(non_empty[0])
        return (
            value in SECTION_TERMINATORS
            or value.startswith("balance:")
            or value.startswith("equity:")
            or value.startswith("total:")
        )

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()

    @classmethod
    def _parse_datetime(
        cls,
        value: Any,
        *,
        field: str,
        row_number: int,
    ) -> datetime:
        if isinstance(value, datetime):
            return value

        text = cls._text(value)
        if not text:
            raise ImportValidationError(
                f"HTML row {row_number}: {field} is empty."
            )

        for fmt in DATETIME_FORMATS:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(text)
        except ValueError as exc:
            raise ImportValidationError(
                f"HTML row {row_number}: invalid {field} value {text!r}."
            ) from exc

    @staticmethod
    def _parse_decimal(
        value: Any,
        *,
        field: str,
        row_number: int,
        required: bool = True,
        default: Decimal | None = None,
    ) -> Decimal | None:
        if value is None or str(value).strip() == "":
            if required:
                raise ImportValidationError(
                    f"HTML row {row_number}: {field} is empty."
                )
            return default

        text = str(value).strip().replace("\u2212", "-").replace("\u00a0", "")
        text = re.sub(r"\s+", "", text)

        if "," in text and "." in text:
            text = text.replace(",", "")
        elif re.fullmatch(r"-?\d{1,3}(,\d{3})+", text):
            text = text.replace(",", "")

        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise ImportValidationError(
                f"HTML row {row_number}: invalid {field} value {value!r}."
            ) from exc

        if not number.is_finite():
            raise ImportValidationError(
                f"HTML row {row_number}: {field} must be a finite number."
            )

        return number
