"""Trading Journal desktop application entry point."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from trading_journal.services.import_service import ImportService
from trading_journal.storage.database import Database
from trading_journal.ui import theme
from trading_journal.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Trading Journal")
    app.setOrganizationName("Trading Journal")

    theme.configure_application(app)

    try:
        database = Database()
        database.initialize()

        import_service = ImportService(database)
        window = MainWindow(import_service)
        window.show()

    except Exception as exc:
        QMessageBox.critical(
            None,
            "Trading Journal — Startup Error",
            f"The application could not start.\n\n{exc}",
        )
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
