"""Accounts and data import page."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trading_journal.domain.models import Account
from trading_journal.services.import_service import ImportService
from trading_journal.ui import theme
from trading_journal.ui.components.metric_card import MetricCard


class AccountsPage(QWidget):
    """Manage account selection and import trade history."""

    account_selected = Signal(object)
    data_changed = Signal()

    SUPPORTED_EXTENSIONS = {".html", ".htm", ".xlsx", ".xls", ".csv", ".tsv", ".txt"}

    def __init__(
        self,
        import_service: ImportService,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.import_service = import_service
        self._accounts: list[Account] = []
        self._selected_account: Account | None = None
        self._last_import_message = "No import performed yet."

        self._build_ui()
        self._connect_signals()
        self._refresh_account_table()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(18)

        title = QLabel("Accounts & Data")
        title.setStyleSheet("font-size: 24pt; font-weight: 700;")

        subtitle = QLabel(
            "Select an account, import trade history, and review import status"
        )
        subtitle.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 10pt;"
        )

        root.addWidget(title)
        root.addWidget(subtitle)

        cards = QGridLayout()
        cards.setSpacing(14)

        self.account_count_card = MetricCard("ACCOUNTS", "0")
        self.trade_count_card = MetricCard("SELECTED ACCOUNT TRADES", "0")
        self.closed_count_card = MetricCard("CLOSED TRADES", "0")
        self.import_status_card = MetricCard(
            "LAST IMPORT", "Not run", "Choose a file to import"
        )

        for index, card in enumerate(
            [
                self.account_count_card,
                self.trade_count_card,
                self.closed_count_card,
                self.import_status_card,
            ]
        ):
            cards.addWidget(card, 0, index)

        root.addLayout(cards)

        account_panel = QFrame()
        account_panel.setObjectName("panel")
        account_layout = QVBoxLayout(account_panel)
        account_layout.setContentsMargins(16, 14, 16, 14)
        account_layout.setSpacing(12)

        account_heading = QHBoxLayout()
        account_title = QLabel("Trading Accounts")
        account_title.setStyleSheet(
            "font-size: 12pt; font-weight: 700;"
        )

        self.account_selector = QComboBox()
        self.account_selector.setMinimumWidth(240)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("secondaryButton")

        account_heading.addWidget(account_title)
        account_heading.addStretch()
        account_heading.addWidget(QLabel("Active account"))
        account_heading.addWidget(self.account_selector)
        account_heading.addWidget(self.refresh_button)

        account_layout.addLayout(account_heading)

        self.account_table = QTableWidget(0, 4)
        self.account_table.setHorizontalHeaderLabels(
            ["Account ID", "Account Name", "Currency", "Trades"]
        )
        self.account_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.account_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.account_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.account_table.verticalHeader().setVisible(False)
        self.account_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        account_layout.addWidget(self.account_table)
        root.addWidget(account_panel)

        import_panel = QFrame()
        import_panel.setObjectName("panel")
        import_layout = QVBoxLayout(import_panel)
        import_layout.setContentsMargins(16, 14, 16, 14)
        import_layout.setSpacing(12)

        import_title = QLabel("Import Trade History")
        import_title.setStyleSheet(
            "font-size: 12pt; font-weight: 700;"
        )

        import_description = QLabel(
            "Importing replaces the selected account's existing trade history. "
            "Other accounts are not changed."
        )
        import_description.setWordWrap(True)
        import_description.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY};"
        )

        button_row = QHBoxLayout()
        self.import_button = QPushButton("Choose File & Import")
        self.import_button.setObjectName("primaryButton")

        self.last_file_label = QLabel("No file selected")
        self.last_file_label.setWordWrap(True)
        self.last_file_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY};"
        )

        button_row.addWidget(self.import_button)
        button_row.addWidget(self.last_file_label, 1)

        self.import_log = QLabel(self._last_import_message)
        self.import_log.setWordWrap(True)
        self.import_log.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.import_log.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; padding: 8px;"
        )

        import_layout.addWidget(import_title)
        import_layout.addWidget(import_description)
        import_layout.addLayout(button_row)
        import_layout.addWidget(self.import_log)

        root.addWidget(import_panel)
        root.addStretch()

    def _connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self._refresh_account_table)
        self.account_selector.currentIndexChanged.connect(
            self._on_account_selector_changed
        )
        self.account_table.itemSelectionChanged.connect(
            self._on_table_selection_changed
        )
        self.import_button.clicked.connect(self._choose_and_import)

    def set_accounts(self, accounts: list[Account]) -> None:
        """Supply accounts from the application layer."""
        previous_id = (
            self._selected_account.account_id
            if self._selected_account is not None
            else None
        )

        self._accounts = list(accounts)
        self.account_selector.blockSignals(True)
        self.account_selector.clear()

        selected_index = 0

        for index, account in enumerate(self._accounts):
            self.account_selector.addItem(account.name, account.account_id)
            if account.account_id == previous_id:
                selected_index = index

        if self._accounts:
            self.account_selector.setCurrentIndex(selected_index)
            self._selected_account = self._accounts[selected_index]
        else:
            self._selected_account = None

        self.account_selector.blockSignals(False)
        self._refresh_account_table()
        self._emit_selected_account()

    def set_selected_account(self, account: Account | None) -> None:
        """Select an account explicitly from the application layer."""
        self._selected_account = account

        if account is not None:
            index = self.account_selector.findData(account.account_id)
            if index >= 0:
                self.account_selector.blockSignals(True)
                self.account_selector.setCurrentIndex(index)
                self.account_selector.blockSignals(False)

        self._refresh_account_table()
        self._emit_selected_account()

    def _refresh_account_table(self, *_args) -> None:
        try:
            accounts = self.import_service.accounts.list_all()
        except (AttributeError, TypeError):
            # The application may supply accounts through set_accounts().
            accounts = self._accounts
        except Exception as exc:
            self._show_error("Could not load accounts", str(exc))
            accounts = self._accounts

        if accounts:
            self._accounts = list(accounts)

            current_id = (
                self._selected_account.account_id
                if self._selected_account is not None
                else None
            )

            self.account_selector.blockSignals(True)
            self.account_selector.clear()

            selected_index = 0

            for index, account in enumerate(self._accounts):
                self.account_selector.addItem(
                    account.name,
                    account.account_id,
                )
                if account.account_id == current_id:
                    selected_index = index

            self.account_selector.setCurrentIndex(
                selected_index if self._accounts else -1
            )
            self.account_selector.blockSignals(False)

            self._selected_account = (
                self._accounts[selected_index]
                if self._accounts
                else None
            )

        elif not self._accounts:
            self._selected_account = None

        self.account_table.setRowCount(len(self._accounts))

        for row, account in enumerate(self._accounts):
            try:
                trade_count = self.import_service.trades.count_by_account(
                    account.account_id
                )
            except Exception:
                trade_count = 0

            values = [
                str(account.account_id),
                account.name,
                getattr(account, "currency", "USD"),
                str(trade_count),
            ]

            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column in (2, 3):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                self.account_table.setItem(row, column, cell)

        self.account_count_card.set_value(str(len(self._accounts)))
        self._refresh_selected_account_metrics()
        self._emit_selected_account()

    def _on_account_selector_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._accounts):
            self._selected_account = None
        else:
            self._selected_account = self._accounts[index]

        self._refresh_selected_account_metrics()
        self._highlight_selected_account()
        self._emit_selected_account()

    def _on_table_selection_changed(self) -> None:
        selected = self.account_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        account_id_item = self.account_table.item(row, 0)

        if account_id_item is None:
            return

        account_id = account_id_item.text()

        account = next(
            (
                item
                for item in self._accounts
                if str(item.account_id) == account_id
            ),
            None,
        )

        if account is None:
            return

        self._selected_account = account
        index = self.account_selector.findData(account.account_id)

        if index >= 0:
            self.account_selector.blockSignals(True)
            self.account_selector.setCurrentIndex(index)
            self.account_selector.blockSignals(False)

        self._refresh_selected_account_metrics()
        self._emit_selected_account()

    def _highlight_selected_account(self) -> None:
        if self._selected_account is None:
            self.account_table.clearSelection()
            return

        target_id = str(self._selected_account.account_id)

        for row in range(self.account_table.rowCount()):
            item = self.account_table.item(row, 0)
            if item is not None and item.text() == target_id:
                self.account_table.selectRow(row)
                return

    def _refresh_selected_account_metrics(self) -> None:
        account = self._selected_account

        if account is None:
            self.trade_count_card.set_value("0")
            self.closed_count_card.set_value("0")
            return

        try:
            trades = self.import_service.trades.list_by_account(
                account.account_id
            )
        except Exception:
            trades = []

        closed_count = sum(1 for trade in trades if trade.is_closed)

        self.trade_count_card.set_value(str(len(trades)))
        self.closed_count_card.set_value(str(closed_count))

    def _choose_and_import(self) -> None:
        account = self._selected_account

        if account is None:
            QMessageBox.warning(
                self,
                "No account selected",
                "Select an account before importing a trade history.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select trade history",
            str(Path.home()),
            (
                "Supported files (*.html *.htm *.xlsx *.xls *.csv *.tsv *.txt);;"
                "HTML files (*.html *.htm);;"
                "Excel files (*.xlsx *.xls);;"
                "CSV and TSV files (*.csv *.tsv *.txt);;"
                "All files (*)"
            ),
        )

        if not file_path:
            return

        suffix = Path(file_path).suffix.lower()

        if suffix not in self.SUPPORTED_EXTENSIONS:
            self._record_import_result(
                False,
                f"Unsupported file extension: {suffix or '(none)'}",
            )
            return

        self.last_file_label.setText(Path(file_path).name)
        self.import_button.setEnabled(False)
        self.import_button.setText("Importing...")

        try:
            result = self.import_service.import_file(
                file_path,
                account.account_id,
            )

            imported_count = self._extract_import_count(result)

            self._record_import_result(
                True,
                f"Imported {imported_count} trades into {account.name}.",
            )

            self._refresh_account_table()
            self.data_changed.emit()

            QMessageBox.information(
                self,
                "Import complete",
                (
                    f"Successfully imported {imported_count} trades "
                    f"into account '{account.name}'."
                ),
            )

        except Exception as exc:
            self._record_import_result(False, str(exc))
            self._show_error(
                "Import failed",
                (
                    "The file could not be imported. Check the file format "
                    "and the error details below.\n\n"
                    f"{exc}"
                ),
            )

        finally:
            self.import_button.setEnabled(True)
            self.import_button.setText("Choose File & Import")

    @staticmethod
    def _extract_import_count(result) -> int:
        if isinstance(result, int):
            return result

        if isinstance(result, (list, tuple, set)):
            return len(result)

        for attribute in ("imported_count", "trade_count", "count"):
            value = getattr(result, attribute, None)
            if isinstance(value, int):
                return value

        try:
            return len(result)
        except (TypeError, AttributeError):
            return 0

    def _record_import_result(self, success: bool, message: str) -> None:
        self._last_import_message = message
        self.import_log.setText(message)

        self.import_status_card.set_value(
            "Success" if success else "Failed",
            message,
            theme.GREEN if success else theme.RED,
        )

    def _emit_selected_account(self) -> None:
        self.account_selected.emit(self._selected_account)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
