# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sequoia-X (王者回归) is a Chinese A-share quantitative stock selection system. It syncs daily OHLCV data for ~5200 stocks from baostock into a local SQLite database, runs seven screening strategies, and pushes results to Feishu group chats via webhook. Designed to run as a daily cron job after market close.

## Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run daily pipeline (sync data + run strategies + push notifications)
python main.py

# Run historical backfill (single-threaded, ~12 min for all A-shares)
python main.py --backfill

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/test_strategy.py

# Lint (ruff, configured in pyproject.toml: line-length 100, target py311, rules E/F/I/UP)
uv run ruff check .

# Format
uv run ruff format .
```

## Architecture

Linear pipeline orchestrated in `main.py`:

```
Config (.env) → DataEngine (baostock → SQLite) → Strategy[] (scan market) → FeishuNotifier (webhook push)
```

### Key packages

- **`sequoia_x/core/`** — `config.py` (pydantic-settings singleton, per-strategy webhook routing via `STRATEGY_WEBHOOK_*` env vars with fallback), `logger.py` (Rich handler factory, idempotent)
- **`sequoia_x/data/engine.py`** — `DataEngine`: SQLite persistence + baostock sync. Daily mode uses 8-process parallel fetch; backfill is single-threaded with retry/reconnection logic. Read methods: `get_ohlcv(symbol)` and `get_local_symbols()`
- **`sequoia_x/strategy/`** — All strategies subclass `BaseStrategy` (abstract `run() -> list[str]`, class attribute `webhook_key` for notification routing). Strategies are manually registered in `main.py` as a plain list — no auto-discovery
- **`sequoia_x/notify/feishu.py`** — `FeishuNotifier`: builds interactive card messages with Xueqiu stock links, routes to per-strategy Feishu bots via webhook_key

### Strategy pattern

Every strategy:
1. Inherits `BaseStrategy`, sets `webhook_key`, implements `run() -> list[str]` of 6-digit stock codes
2. Receives `DataEngine` + `Settings` via constructor injection
3. Most strategies loop `get_local_symbols()` → `get_ohlcv(symbol)` per stock

Two architectural exceptions:
- **`RpsBreakoutStrategy`**: loads entire `stock_daily` table in one SQL query for cross-sectional ranking (needs all stocks simultaneously)
- **`PrivatePlacementStrategy`**: does not use `DataEngine` at all; pulls data from akshare (`stock_qbzf_em()`) for 定向增发 announcements

### Adding a new strategy

1. Create `sequoia_x/strategy/<name>.py`, subclass `BaseStrategy`, set `webhook_key`, implement `run()`
2. Add import + instantiation in `main.py`'s strategies list
3. Optionally add `STRATEGY_WEBHOOK_<key>=<url>` to `.env` for dedicated Feishu bot routing

### Configuration

Managed by `pydantic-settings` in `sequoia_x/core/config.py`:
- `DB_PATH` (default `data/sequoia_v2.db`), `START_DATE` (default `2024-01-01`)
- `FEISHU_WEBHOOK_URL` (required) — default webhook
- `STRATEGY_WEBHOOK_*` — prefix-scanned env vars for per-strategy routing, falls back to default

### External services

| Service | Library | Used by |
|---------|---------|---------|
| baostock | `baostock` | DataEngine (sync/backfill), FeishuNotifier (stock name resolution), TurtleTradeStrategy (market cap) |
| akshare | `akshare` | PrivatePlacementStrategy (East Money 定向增发 data) |
| Feishu | `requests` | FeishuNotifier (webhook POST) |

Note: baostock connections are independently managed in three modules — no shared session pool.

### Testing

Tests use **Hypothesis** (property-based) with `pytest`. External services are stubbed via `unittest.mock.patch`. SQLite tests use `tempfile.TemporaryDirectory` for isolation. Key test files: `test_config.py`, `test_data_engine.py`, `test_strategy.py`, `test_feishu.py`, `test_main.py`.
