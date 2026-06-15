"""HTML 报告模块：将选股结果渲染为本地自包含 HTML 文件（替代飞书推送）。

将一个交易日全部策略的选股结果渲染为单个 HTML 文件（内联 CSS、无外部依赖），
默认写入 settings.report_path（data/report.html），含雪球行情链接与 baostock 解析的股票名称。
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from string import Template

from sequoia_x.core.config import Settings
from sequoia_x.core.logger import get_logger

logger = get_logger(__name__)


_PAGE_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 2rem 1rem; color: #1f2329; background: #f5f6f7;
    font-family: -apple-system, "Segoe UI", "Microsoft YaHei", Roboto, sans-serif;
  }
  .wrap { max-width: 880px; margin: 0 auto; }
  header { margin-bottom: 1.5rem; }
  header h1 { margin: 0 0 .25rem; font-size: 1.5rem; }
  .meta { color: #646a73; font-size: .9rem; margin: 0; }
  .meta strong { color: #1f2329; }
  .summary, section {
    background: #fff; border-radius: 10px; padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,.06); margin-bottom: 1rem;
  }
  .summary { margin-bottom: 1.5rem; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: .5rem; text-align: left; border-bottom: 1px solid #eef0f1; }
  th { color: #646a73; font-weight: 600; font-size: .85rem; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  section h2 { margin: 0 0 .75rem; font-size: 1.1rem; }
  .count {
    display: inline-block; min-width: 1.5em; padding: .05em .5em;
    background: #e8eaff; color: #2b54ff; border-radius: 999px;
    font-size: .8rem; font-weight: 600;
  }
  td.code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  a { color: #2b54ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .empty { color: #8f959e; margin: 0; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>$title</h1>
    <p class="meta">
      生成时间 <strong>$rendered_at</strong>
      · 策略 <strong>$total_strategies</strong>
      · 合计选股 <strong>$total_picks</strong>
    </p>
  </header>

  <div class="summary">
    <table>
      <thead><tr><th>策略</th><th class="num">选股数量</th></tr></thead>
      <tbody>
        $summary
      </tbody>
    </table>
  </div>

  $sections
</div>
</body>
</html>
""")


class HtmlNotifier:
    """选股结果 HTML 报告生成器。

    将一个交易日全部策略的选股结果渲染为单个自包含 HTML 文件，
    写入 settings.report_path（默认 data/report.html）。
    """

    def __init__(self, settings: Settings) -> None:
        """
        Args:
            settings: Settings 实例，提供 report_path 等配置。
        """
        self.settings = settings

    @staticmethod
    def _to_xueqiu_code(code: str) -> str:
        """将纯数字代码转为雪球格式：6开头→SH，4/8开头→BJ，其余→SZ。"""
        if code.startswith("6"):
            return f"SH{code}"
        if code.startswith(("4", "8")):
            return f"BJ{code}"
        return f"SZ{code}"

    @staticmethod
    def _get_stock_names(symbols: list[str]) -> dict[str, str]:
        """通过 baostock 批量查询股票名称，返回 {code: name}。

        baostock 不可用时返回空映射，报告降级为仅显示代码。
        """
        import baostock as bs

        mapping: dict[str, str] = {}
        try:
            bs.login()
            for code in symbols:
                prefix = "sh" if code.startswith(("6", "9")) else "sz"
                rs = bs.query_stock_basic(code=f"{prefix}.{code}")
                while rs.next():
                    row = rs.get_row_data()
                    mapping[code] = row[1]  # 第 2 个字段是股票名称
        except Exception as exc:  # noqa: BLE001 - baostock 不可用时降级，不阻断主流程
            logger.warning(f"股票名称查询失败，将仅显示代码：{exc}")
        finally:
            try:
                bs.logout()
            except Exception:  # noqa: BLE001
                pass
        return mapping

    def render_report(
        self,
        results: list[tuple[str, list[str]]],
        path: str | Path | None = None,
    ) -> Path:
        """渲染全部策略结果为单个 HTML 文件，返回写入路径。

        Args:
            results: [(strategy_name, symbols), ...]，按执行顺序，含空结果策略。
            path: 输出路径；默认 settings.report_path。

        Returns:
            实际写入的文件路径。
        """
        out_path = Path(path) if path else Path(self.settings.report_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        rendered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        all_codes = [code for _, symbols in results for code in symbols]
        names = self._get_stock_names(all_codes) if all_codes else {}

        summary_rows = [
            f'<tr><td><a href="#{name}">{html.escape(name)}</a></td>'
            f'<td class="num">{len(symbols)}</td></tr>'
            for name, symbols in results
        ]
        sections = [
            self._render_section(name, symbols, names) for name, symbols in results
        ]

        doc = _PAGE_TEMPLATE.substitute(
            title="Sequoia-X 选股报告",
            rendered_at=html.escape(rendered_at),
            total_strategies=len(results),
            total_picks=len(all_codes),
            summary="\n        ".join(summary_rows) or '<tr><td colspan="2">（无策略）</td></tr>',
            sections="\n  ".join(sections),
        )
        out_path.write_text(doc, encoding="utf-8")
        logger.info(
            f"HTML 报告已生成：{out_path.resolve()}（合计 {len(all_codes)} 只选股）"
        )
        return out_path

    def _render_section(
        self,
        strategy_name: str,
        symbols: list[str],
        names: dict[str, str],
    ) -> str:
        """渲染单个策略区块（标题 + 结果表或占位文案）。"""
        head = (
            f'<section id="{strategy_name}">'
            f"<h2>{html.escape(strategy_name)} "
            f'<span class="count">{len(symbols)}</span></h2>'
        )
        if not symbols:
            return f"{head}<p class=\"empty\">今日无选股结果。</p></section>"

        rows = []
        for i, code in enumerate(symbols, start=1):
            xq = self._to_xueqiu_code(code)
            name = names.get(code, xq)
            link = f"https://xueqiu.com/S/{xq}"
            rows.append(
                "<tr>"
                f'<td class="num">{i}</td>'
                f'<td class="code">{html.escape(code)}</td>'
                f"<td>{html.escape(name)}</td>"
                f'<td><a href="{link}" target="_blank" rel="noopener">'
                f"雪球 {html.escape(xq)}</a></td>"
                "</tr>"
            )
        table = (
            "<table><thead><tr>"
            '<th class="num">#</th><th>代码</th><th>名称</th><th>行情</th>'
            "</tr></thead>"
            f'<tbody>{"".join(rows)}</tbody></table>'
        )
        return f"{head}{table}</section>"
