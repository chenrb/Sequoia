# Sequoia-X: 王者回归 | The King Returns

> A 股量化选股系统 V2 | A-Share Quantitative Stock Selection System V2

---

## 简介 | Introduction

Sequoia-X V2 是面向 A 股市场的量化选股系统，基于现代 Python 工程化标准从零重构。
系统以 OOP 架构、向量化计算和增量数据更新为核心设计原则，每日收盘后自动选股并推送至飞书群。

数据层使用 [baostock](http://baostock.com)（免费、无需注册、无限流）拉取历史及增量日 K 数据（后复权），
存储于本地 SQLite，彻底规避东方财富反爬问题。

---

## 两种运行模式

```bash
python main.py               # 日常模式：8进程增量补数据 + 跑策略 + 飞书推送（2~3分钟）
python main.py --backfill     # 回填模式：全市场历史K线一次性灌入（约12分钟）
```

---

## 内置策略 | Strategies

| 策略 | 说明 |
|---|---|
| **TurtleTrade** | 海龟突破：20日新高 + 成交额过亿 + 阳线防诱多，按流通市值排序 |
| **MaVolume** | 均线+放量突破：5日均线上穿20日均线 + 成交量 > 1.5倍20日均量 |
| **HighTightFlag** | 高而窄的旗形整理突破：40日涨幅 > 60%，近10日振幅 < 15% |
| **LimitUpShakeout** | 涨停洗盘回踩确认：昨日涨停 + 今日阴线放量但守住支撑 |
| **UptrendLimitDown** | 上升趋势中的跌停反包：MA20 > MA60 + 跌停 + 2倍放量 |
| **RpsBreakout** | 欧奈尔 RPS 相对强度突破：120日涨幅百分位 ≥ 90 + 接近滚动新高 |
| **PrivatePlacement** | 定向增发公告监控：从东方财富抓取近7日定增公告（akshare 数据源） |

---

## 执行流程

### 日常模式 (`python main.py`)

```
配置加载 (.env) → 数据增量同步 (8进程) → 顺序执行7个策略 → 飞书推送
```

1. **加载配置** — `get_settings()` 从 `.env` / 环境变量读取配置（DB路径、Webhook URL等）
2. **增量同步** — `engine.sync_today_bulk()` 对比 SQLite 中每只股票最后更新日期，8 进程并发从 baostock 拉取缺失日K线，写入 SQLite
3. **执行策略** — 顺序遍历 7 个策略，每个策略扫描全市场 ~5200 只股票，返回符合条件的股票代码列表
4. **推送结果** — 有选股结果时，通过 `FeishuNotifier` 按 `webhook_key` 路由到对应飞书机器人，发送交互式卡片消息

### 回填模式 (`python main.py --backfill`)

1. 从 baostock 获取全 A 股 ~5200 只股票列表
2. 单线程逐只拉取历史日K线，每只股票 3 次重试 + 指数退避，每 200 只重连一次
3. 已有数据自动跳过，支持断点续跑

---

## 快速开始 | Quick Start

### 环境要求

- Python >= 3.10

### 1. 安装依赖

```bash
# 推荐使用 uv（快速包管理器）
uv sync

# 或者 pip
pip install .
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写飞书 Webhook URL
```

### 3. 首次回填历史数据

```bash
python main.py --backfill
```

约 12 分钟完成 ~5200 只 A 股历史后复权日 K 数据回填。

### 4. 日常运行

```bash
python main.py
```

建议配合 crontab 每个交易日收盘后自动执行：

```cron
15 19 * * 1-5 cd /root/Sequoia-X && .venv/bin/python main.py >> log.txt 2>&1
```

---

## 目录结构 | Project Structure

```
Sequoia-X/
├── main.py                      # 入口：argparse 分发日常/回填模式
├── pyproject.toml               # 依赖声明 + ruff/pytest 配置
├── .env.example                 # 环境变量模板
├── data/                        # SQLite 数据库（运行时生成，不入 git）
├── sequoia_x/
│   ├── core/
│   │   ├── config.py            # Pydantic-settings 配置管理
│   │   └── logger.py            # rich 结构化日志
│   ├── data/
│   │   └── engine.py            # 数据引擎（baostock 回填 + 增量同步 + SQLite）
│   ├── strategy/
│   │   ├── base.py              # 策略抽象基类
│   │   ├── turtle_trade.py      # 海龟交易策略
│   │   ├── ma_volume.py         # 均线放量策略
│   │   ├── high_tight_flag.py   # 高窄旗形策略
│   │   ├── limit_up_shakeout.py # 涨停洗盘策略
│   │   ├── uptrend_limit_down.py # 上升跌停策略
│   │   ├── rps_breakout.py      # RPS 突破策略
│   │   └── private_placement.py # 定向增发策略
│   └── notify/
│       └── feishu.py            # 飞书 Webhook 推送
└── tests/                       # 属性测试（hypothesis）
```

---

## 数据说明

- **数据源**：[baostock](http://baostock.com)（免费、无需注册、无限流）
- **复权方式**：后复权（hfq）— 历史价格不变，适合增量存储，避免除权导致数据错乱
- **存储**：本地 SQLite（`data/sequoia_v2.db`），可直接拷贝到其他机器使用
- **日常增量**：8 进程并行通过 baostock 拉取，2~3 分钟完成全市场更新

---

## 许可证 | License

MIT
