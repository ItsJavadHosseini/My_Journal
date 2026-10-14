"""Main application window and page navigation."""

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from trading_journal.domain.models import Account
from trading_journal.imports.base import ImportValidationError
from trading_journal.services.import_service import ImportService
from trading_journal.storage.repositories import AccountRepository
from trading_journal.ui import theme
from trading_journal.ui.components.sidebar import Sidebar
from trading_journal.ui.pages.accounts_page import AccountsPage
from trading_journal.ui.pages.behavior_page import BehaviorPage
from trading_journal.ui.pages.overview_page import OverviewPage
from trading_journal.ui.pages.performance_page import PerformancePage
from trading_journal.ui.pages.trade_explorer_page import TradeExplorerPage


class CreateAccountDialog(QDialog):
    """Dialog for creating a trading account."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Create trading account")
        self.setMinimumWidth(400)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. FundedNext 6000")

        self.broker_input = QLineEdit()
        self.broker_input.setPlaceholderText("Optional")

        self.platform_input = QLineEdit()
        self.platform_input.setPlaceholderText("e.g. MetaTrader 5")

        self.currency_input = QLineEdit("USD")

        form = QFormLayout()
        form.addRow("Account name *", self.name_input)
        form.addRow("Broker", self.broker_input)
        form.addRow("Platform", self.platform_input)
        form.addRow("Currency", self.currency_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self.name_input.text().strip():
            QMessageBox.warning(
                self,
                "Missing account name",
                "Enter a name for this account.",
            )
            self.name_input.setFocus()
            return

        self.accept()

    def build_account(self) -> Account:
        return Account(
            name=self.name_input.text().strip(),
            broker=self.broker_input.text().strip() or None,
            platform=self.platform_input.text().strip() or None,
            currency=self.currency_input.text().strip().upper() or None,
        )


class MainWindow(QMainWindow):
    """Application shell that coordinates navigation and account data."""

    PAGE_TITLES = {
        "overview": "Overview",
        "performance": "Performance",
        "trade_explorer": "Trade Explorer",
        "behavior": "Behavior",
        "accounts": "Accounts & Data",
    }

    def __init__(self, import_service: ImportService) -> None:
        super().__init__()

        self.import_service = import_service
        self.account_repository = AccountRepository(import_service.database)
        self.trade_repository = import_service.trades

        self._accounts: list[Account] = []
        self._selected_account_id: UUID | None = None
        self._syncing_account_selection = False

        self.setWindowTitle("Trading Journal")
        self.resize(1440, 920)
        self.setMinimumSize(1050, 700)

        self._build_pages()
        self._build_ui()
        self._connect_signals()
        self._refresh_accounts()

    def _build_pages(self) -> None:
        """Create each page once and keep it alive in the stack."""
        self.sidebar = Sidebar()
        self.page_stack = QStackedWidget()

        self.overview_page = OverviewPage()
        self.performance_page = PerformancePage()
        self.trade_explorer_page = TradeExplorerPage()
        self.behavior_page = BehaviorPage()
        self.accounts_page = AccountsPage(self.import_service)

        self.pages: dict[str, QWidget] = {
            "overview": self.overview_page,
            "performance": self.performance_page,
            "trade_explorer": self.trade_explorer_page,
            "behavior": self.behavior_page,
            "accounts": self.accounts_page,
        }

        self.page_indexes: dict[str, int] = {}

        for page_id, page in self.pages.items():
            self.page_indexes[page_id] = self.page_stack.addWidget(page)

        # Use the confirmation-protected import workflow already present
        # in MainWindow rather than the page's direct import handler.
        try:
            self.accounts_page.import_button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass

        self.accounts_page.import_button.clicked.connect(
            self._import_history
        )

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self.sidebar)

        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(24, 18, 24, 18)
        main_layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(12)

        heading_layout = QVBoxLayout()
        heading_layout.setSpacing(3)

        self.page_title = QLabel("Overview")
        self.page_title.setStyleSheet(
            "font-size: 21pt; font-weight: 700;"
        )

        self.page_subtitle = QLabel(
            "Trading performance, risk and account history"
        )
        self.page_subtitle.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 9pt;"
        )

        heading_layout.addWidget(self.page_title)
        heading_layout.addWidget(self.page_subtitle)

        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(230)
        self.account_combo.setToolTip("Select the active trading account")

        self.create_account_button = QPushButton("Create account")
        self.create_account_button.setObjectName("primaryButton")

        header.addLayout(heading_layout, 1)
        header.addWidget(QLabel("Account"))
        header.addWidget(self.account_combo)
        header.addWidget(self.create_account_button)

        main_layout.addLayout(header)
        main_layout.addWidget(self.page_stack, 1)

        root_layout.addWidget(main_area, 1)
        self.setCentralWidget(root)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        self.setStyleSheet(
            theme.APP_STYLESHEET
            + f"""
            QPushButton#primaryButton {{
                background-color: {theme.GREEN};
                color: #07130D;
                border: none;
                border-radius: 7px;
                padding: 9px 14px;
                font-weight: 700;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {theme.GREEN_HOVER};
            }}
            QPushButton#secondaryButton {{
                background-color: {theme.SURFACE_ALT};
                border: 1px solid {theme.BORDER};
                border-radius: 7px;
                padding: 8px 12px;
            }}
            """
        )

    def _connect_signals(self) -> None:
        self.sidebar.page_changed.connect(self._show_page)
        self.account_combo.currentIndexChanged.connect(
            self._on_account_changed
        )
        self.create_account_button.clicked.connect(self._create_account)

        self.accounts_page.account_selected.connect(
            self._on_page_account_selected
        )
        self.accounts_page.data_changed.connect(self._on_import_completed)

    def _show_page(self, page_id: str) -> None:
        """Switch the central page using its stable identifier."""
        if page_id not in self.pages:
            return

        self.page_stack.setCurrentIndex(self.page_indexes[page_id])
        self.page_title.setText(self.PAGE_TITLES[page_id])

        subtitles = {
            "overview": "A high-level view of trading results",
            "performance": "Detailed statistics and outcome analysis",
            "trade_explorer": "Search, filter and inspect individual trades",
            "behavior": "Explore results by symbol, weekday and direction",
            "accounts": "Manage accounts and import trading history",
        }
        self.page_subtitle.setText(subtitles[page_id])

    def _refresh_accounts(
        self,
        selected_account_id: UUID | None = None,
    ) -> None:
        """Reload accounts while preserving the selected account if possible."""
        try:
            accounts = self.account_repository.list_all()
        except Exception as exc:
            self.statusBar().showMessage(
                f"Could not load accounts: {exc}", 8000
            )
            return

        previous_id = (
            selected_account_id
            or self._selected_account_id
        )

        self._accounts = list(accounts)
        self._syncing_account_selection = True

        self.account_combo.blockSignals(True)
        self.account_combo.clear()

        selected_index = -1

        for index, account in enumerate(self._accounts):
            self.account_combo.addItem(
                self._account_label(account),
                userData=account.account_id,
            )
            if account.account_id == previous_id:
                selected_index = index

        if selected_index < 0 and self._accounts:
            selected_index = 0

        self.account_combo.setCurrentIndex(selected_index)
        self.account_combo.blockSignals(False)

        self.accounts_page.set_accounts(self._accounts)

        selected_account = (
            self._accounts[selected_index]
            if selected_index >= 0
            else None
        )
        self._selected_account_id = (
            selected_account.account_id
            if selected_account is not None
            else None
        )

        self.accounts_page.set_selected_account(selected_account)

        self._syncing_account_selection = False
        self._load_selected_account()

    @staticmethod
    def _account_label(account: Account) -> str:
        details = [
            value
            for value in (account.broker, account.platform)
            if value
        ]

        if details:
            return f"{account.name} ({' / '.join(details)})"

        return account.name

    def _selected_account(self) -> Account | None:
        account_id = self._selected_account_id
        if account_id is None:
            return None

        return next(
            (
                account
                for account in self._accounts
                if account.account_id == account_id
            ),
            None,
        )

    def _on_account_changed(self, index: int) -> None:
        if self._syncing_account_selection:
            return

        if index < 0:
            self._selected_account_id = None
            self._load_selected_account()
            return

        account_id = self.account_combo.itemData(index)
        self._selected_account_id = (
            account_id if isinstance(account_id, UUID) else None
        )

        account = self._selected_account()
        self._syncing_account_selection = True
        self.accounts_page.set_selected_account(account)
        self._syncing_account_selection = False

        self._load_selected_account()

    def _on_page_account_selected(self, account: Account | None) -> None:
        """Keep the global selector aligned with the Accounts page."""
        if self._syncing_account_selection:
            return

        account_id = account.account_id if account is not None else None
        self._selected_account_id = account_id

        self._syncing_account_selection = True

        index = self.account_combo.findData(account_id)
        if index >= 0:
            self.account_combo.setCurrentIndex(index)

        self._syncing_account_selection = False
        self._load_selected_account()

    def _load_selected_account(self) -> None:
        """Load one account's trades into all analytical pages."""
        account = self._selected_account()

        if account is None:
            self.accounts_page.set_selected_account(None)
            self.overview_page.set_account_name("No account selected")
            self.overview_page.set_trades([])
            self.performance_page.set_trades([])
            self.trade_explorer_page.set_trades([])
            self.behavior_page.set_trades([])
            self.statusBar().showMessage(
                "Create or select an account to begin."
            )
            return

        try:
            trades = self.trade_repository.list_by_account(
                account.account_id
            )
        except Exception as exc:
            self.statusBar().showMessage(
                f"Could not load trades: {exc}", 8000
            )
            return

        currency = account.currency or "USD"

        self.overview_page.set_account_name(account.name)
        self.overview_page.set_trades(trades, currency)
        self.performance_page.set_trades(trades, currency)
        self.trade_explorer_page.set_trades(trades, currency)
        self.behavior_page.set_trades(trades, currency)

        self.statusBar().showMessage(
            f"{account.name} · {len(trades)} trades loaded"
        )

    def _create_account(self) -> None:
        dialog = CreateAccountDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        account = dialog.build_account()

        try:
            self.account_repository.save(account)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Account creation failed",
                str(exc),
            )
            return

        self._refresh_accounts(account.account_id)
        self.statusBar().showMessage(
            f"Account created: {account.name}", 5000
        )

    def _import_history(self) -> None:
        """Import history after confirming account-history replacement."""
        account = self._selected_account()

        if account is None:
            QMessageBox.warning(
                self,
                "No account selected",
                "Create or select an account first.",
            )
            return

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select trading history report",
            str(Path.home() / "Downloads"),
            (
                "Trading reports (*.html *.htm *.xlsx *.csv *.tsv);;"
                "HTML reports (*.html *.htm);;"
                "Excel reports (*.xlsx);;"
                "CSV reports (*.csv *.tsv);;"
                "All files (*)"
            ),
        )

        if not file_name:
            return

        answer = QMessageBox.warning(
            self,
            "Replace account history?",
            (
                f"Account: {account.name}\n\n"
                "Importing this report replaces the existing trade "
                "history for this account. Other accounts are not affected.\n\n"
                "Continue?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.accounts_page.import_button.setEnabled(False)
        self.create_account_button.setEnabled(False)
        self.account_combo.setEnabled(False)
        self.statusBar().showMessage("Importing report...")

        try:
            result = self.import_service.import_file(
                file_name,
                account.account_id,
            )

        except (
            ImportValidationError,
            ValueError,
            TypeError,
        ) as exc:
            message = f"Import failed: {exc}"
            self.accounts_page._record_import_result(False, message)

            QMessageBox.warning(
                self,
                "Import failed",
                (
                    f"{exc}\n\n"
                    "Existing history should remain unchanged if parsing "
                    "or validation failed."
                ),
            )

        except Exception as exc:
            message = f"Unexpected import error: {exc}"
            self.accounts_page._record_import_result(False, message)

            QMessageBox.critical(
                self,
                "Import error",
                f"An unexpected error occurred:\n{exc}",
            )

        else:
            imported_count = len(result.trades)
            message = (
                f"Imported {imported_count} trades into {account.name}."
            )

            self.accounts_page.last_file_label.setText(
                Path(file_name).name
            )
            self.accounts_page._record_import_result(True, message)

            self._refresh_accounts(account.account_id)

            self.statusBar().showMessage(
                f"Imported {imported_count} trades.", 8000
            )

            QMessageBox.information(
                self,
                "Import completed",
                (
                    f"{imported_count} trades were imported into "
                    f"'{account.name}'."
                ),
            )

        finally:
            self.accounts_page.import_button.setEnabled(True)
            self.create_account_button.setEnabled(True)
            self.account_combo.setEnabled(True)

    def _on_import_completed(self) -> None:
        """Refresh data after an import initiated by the Accounts page."""
        self._refresh_accounts(self._selected_account_id)
