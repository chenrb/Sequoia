"""HTML 报告属性测试。"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

from sequoia_x.core.config import Settings
from sequoia_x.notify.html import HtmlNotifier


def make_settings(report_path: str) -> Settings:
    return Settings(
        db_path="data/test.db",
        start_date="2024-01-01",
        feishu_webhook_url="https://example.com/hook",
        report_path=report_path,
    )


# Feature: sequoia-x-v2, Property: HTML 报告包含全部选股代码
@given(
    symbols=st.lists(
        st.text(min_size=6, max_size=6, alphabet="0123456789"),
        min_size=0, max_size=10, unique=True,
    )
)
@h_settings(max_examples=50)
def test_report_contains_all_symbols(symbols: list[str]) -> None:
    """render_report() 写出的 HTML 应包含每一个选股代码。"""
    with tempfile.TemporaryDirectory() as d:
        s = make_settings(str(Path(d) / "report.html"))
        notifier = HtmlNotifier(s)
        with patch.object(HtmlNotifier, "_get_stock_names", return_value={}):
            path = notifier.render_report([("TestStrategy", symbols)])
        content = path.read_text(encoding="utf-8")
        for code in symbols:
            assert code in content


# Feature: sequoia-x-v2, Property: HTML 报告包含策略名称与选股数量
@given(
    name=st.text(
        min_size=1, max_size=20,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll"), whitelist_characters="_"),
    ),
    n=st.integers(min_value=0, max_value=8),
)
@h_settings(max_examples=50)
def test_report_contains_strategy_and_count(name: str, n: int) -> None:
    """HTML 应出现策略名称，且数量单元格显示正确数量。"""
    symbols = [f"{100000 + i:06d}" for i in range(n)]
    with tempfile.TemporaryDirectory() as d:
        s = make_settings(str(Path(d) / "report.html"))
        notifier = HtmlNotifier(s)
        with patch.object(HtmlNotifier, "_get_stock_names", return_value={}):
            path = notifier.render_report([(name, symbols)])
        content = path.read_text(encoding="utf-8")
        assert name in content
        assert f">{n}<" in content  # summary/section 的数量单元格


# Feature: sequoia-x-v2, Property: 代码 → 雪球代码前缀正确
@given(code=st.from_regex(r"[0-9]{6}", fullmatch=True))
@h_settings(max_examples=50)
def test_xueqiu_code_prefix(code: str) -> None:
    """6开头→SH，4/8开头→BJ，其余→SZ，且保留原 6 位代码。"""
    xq = HtmlNotifier._to_xueqiu_code(code)
    if code.startswith("6"):
        assert xq.startswith("SH")
    elif code.startswith(("4", "8")):
        assert xq.startswith("BJ")
    else:
        assert xq.startswith("SZ")
    assert xq.endswith(code)


# Feature: sequoia-x-v2, Property: 空选股结果渲染占位文案
def test_empty_strategy_renders_placeholder() -> None:
    """无选股结果的策略区块应渲染占位文案，且不报错。"""
    with tempfile.TemporaryDirectory() as d:
        s = make_settings(str(Path(d) / "report.html"))
        notifier = HtmlNotifier(s)
        with patch.object(HtmlNotifier, "_get_stock_names", return_value={}):
            path = notifier.render_report([("EmptyStrategy", [])])
        content = path.read_text(encoding="utf-8")
        assert "无选股结果" in content
