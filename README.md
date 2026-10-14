# Trading Journal

**A Python desktop application for trade tracking, performance analysis, and risk management.**

Trading Journal is an early-stage personal project designed to help traders organize their trading history, analyze performance, and gain better insights into their trading activity.

The project is currently at its **simplest foundational version**. Its architecture and features will evolve as development continues, with the long-term goal of building a more comprehensive and practical trading analysis tool.

> **Project status:** Early development — foundational version  
> This is a work in progress, not a finished or production-ready application.

## Overview

Trading Journal aims to bring trading records, performance metrics, and behavioral analysis into a single desktop application.

The initial focus is on building a reliable foundation: structured trade data, account separation, historical trade imports, local data storage, and a modular interface that can be extended over time.

## Current Features

- **Account management** — Create and select trading accounts.
- **Trade history import** — Import historical trading data from supported HTML, Excel (`.xlsx`), CSV, and TSV files.
- **Account-level data isolation** — Importing a new history replaces the selected account's trade history without intentionally affecting other accounts.
- **Performance overview** — View key metrics such as reported P&L, win rate, profit factor, and maximum drawdown.
- **Performance analysis** — Explore average trade outcomes, largest wins and losses, monthly performance, and trade outcome distribution.
- **Trade Explorer** — Search and filter trades by symbol, direction, and status, with individual trade details.
- **Behavioral analysis** — Examine results by symbol, weekday, trade direction, and holding duration.
- **Local database** — Store trading data locally using SQLite.
- **Modular UI** — Separate pages and reusable components to support future development.

The availability and accuracy of individual metrics depend on the imported data and the information present in the source report.

## Technology Stack

- **Python** — Core application logic
- **PySide6** — Desktop user interface
- **SQLite** — Local database
- **Decimal** — Financial calculations using decimal arithmetic
- **UUID** — Unique identifiers for accounts and trades
- **openpyxl** — Excel file processing
- **Beautiful Soup** — HTML report parsing
- **uv** — Python project and dependency management

## Architecture

The project follows a modular, layered structure that separates domain models, data import, business services, persistence, analytics, and the user interface.

```text
src/trading_journal/
├── analytics/
│   └── metrics.py
├── domain/
│   └── models.py
├── imports/
│   ├── base.py
│   ├── csv_importer.py
│   ├── excel_importer.py
│   └── html_importer.py
├── services/
│   └── import_service.py
├── storage/
│   ├── database.py
│   └── repositories.py
└── ui/
    ├── components/
    ├── pages/
    ├── main_window.py
    └── theme.py
```

This structure is intended to make future changes easier to isolate, test, and maintain without coupling the interface directly to database and import logic.

## Getting Started

### Requirements

- Python version compatible with the project's `pyproject.toml`
- [uv](https://docs.astral.sh/uv/)
- Windows is the current development environment.

### Installation

Clone the repository and navigate to the project directory:

```bash
git clone <repository-url>
cd trading-journal
```

Install the project and its dependencies:

```bash
uv sync
```

Launch the application:

```bash
uv run trading-journal
```

Replace `<https://github.com/ItsJavadHosseini/My_Journal.git>` with the actual URL of this repository.

## Data Storage

The application uses a local SQLite database.

By default, the database is stored at:

```text
data/trading_journal.db
```

Trading data is intended to remain local to the application unless additional functionality is introduced in the future. Users should keep appropriate backups of important trading records.

## Financial Metrics and Data Limitations

The current analytics implementation uses reported trade profit from imported records.

Commission and swap are not automatically added to reported profit in the current metrics calculation because the accounting semantics and consistency of source fields need to be established first.

Other limitations include:

- Results depend on the completeness and consistency of imported trading history.
- Historical performance metrics do not guarantee future results.
- The application is an analytical tool, not a financial advisor or an automated trading system.
- Import formats and report structures may require further compatibility testing.

## Development Approach and AI Assistance

This project was developed with assistance from **ChatGPT through a conversational, iterative coding workflow**.

The initial foundational version was assembled over a few hours, starting at approximately **1:00 AM**. The development process involved discussing the architecture, generating and reviewing code, integrating modules, and troubleshooting errors interactively.

For clarity, this refers to development with a conversational AI assistant. It should not be confused with autonomous coding agents that operate directly in the terminal and independently execute coding tasks.

AI assistance accelerated the initial implementation, but the project remains under active development. Generated code and implemented features require continued testing, review, and refinement.

## Roadmap

Planned directions for future development include:

- More robust import validation and error reporting
- Expanded performance and risk metrics
- Improved trade filtering and inspection
- Deeper behavioral analysis and performance breakdowns
- More comprehensive testing and data integrity checks
- UI and usability improvements
- Better handling of commissions, swaps, and account-level financial reporting
- Additional import formats and compatibility improvements

This roadmap is provisional and may change as the project develops and practical requirements become clearer.

## Contributing

The project is currently being developed iteratively, with a focus on establishing a dependable foundation before expanding its scope.

Suggestions, bug reports, and ideas for improvement are welcome.

## Disclaimer

Trading Journal is an independent software project intended for personal trading analysis and educational development. It does not provide investment advice, execute trades, or guarantee the accuracy of third-party trading reports.

**The current version is an initial foundation, not the final product.**
