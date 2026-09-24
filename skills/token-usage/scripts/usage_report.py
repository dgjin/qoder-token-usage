#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Qoder Token 消费统计 —— 同时覆盖 Qoder 官方模型与自定义模型（BYOK）。

数据源：Qoder 桌面端本地数据库（只读打开，不影响正在运行的 Qoder）
  macOS:   ~/Library/Application Support/Qoder/SharedClientCache/cache/db/local.db
  Windows: %APPDATA%\Qoder\SharedClientCache\cache\db\local.db（另探测 %LOCALAPPDATA%）
  Linux:   ~/.config/Qoder/SharedClientCache/cache/db/local.db
  自动探测上述候选；可用环境变量 QODER_DB_PATH 或 --db 覆盖。表结构：
    chat_message.token_info   {prompt_tokens, completion_tokens, cached_tokens, ...}
    chat_message.model_info   {model_key}    —— custom_model 即自定义模型
    chat_message.gmt_create   毫秒时间戳；session_id 关联 chat_session.project_name

用法：
  python3 usage_report.py                          # 近 7 天，按天
  python3 usage_report.py --days 30 --by model     # 近 30 天，按模型
  python3 usage_report.py --days all --by project   # 全量历史，按项目
  python3 usage_report.py --days 7 --json          # 输出 JSON（供程序消费）
  python3 usage_report.py --since 2026-09-01 --until 2026-09-15  # 自定义日期范围
  python3 usage_report.py --by session --days 7    # 按会话聚合

费用换算：读取同技能目录下的 pricing.json（元 / 百万 tokens，分输入/输出/缓存三项）。
未配置单价的模型只统计 token，费用列显示 "-"。
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

DB_RELATIVE = os.path.join("Qoder", "SharedClientCache", "cache", "db", "local.db")


def db_candidates():
    """各平台 Qoder 桌面端本地数据库候选路径（Electron 用户数据目录约定）。"""
    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    localapp = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return list(dict.fromkeys([
        os.path.join(home, "Library", "Application Support", DB_RELATIVE),  # macOS
        os.path.join(appdata, DB_RELATIVE),  # Windows（Roaming）
        os.path.join(localapp, DB_RELATIVE),  # Windows（Local，兜底）
        os.path.join(xdg, DB_RELATIVE),  # Linux
    ]))


def find_db_path():
    """返回第一个存在的候选路径；都不存在时返回 None。"""
    for path in db_candidates():
        if os.path.exists(path):
            return path
    return None


DB_DEFAULT = os.environ.get("QODER_DB_PATH") or find_db_path() or db_candidates()[0]


def require_db(path):
    """校验数据库存在；缺失时给出候选清单与解决提示后退出。"""
    if os.path.exists(path):
        return
    print(f"未找到 Qoder 本地数据库：{path}", file=sys.stderr)
    print("已尝试的候选路径：", file=sys.stderr)
    for cand in db_candidates():
        print(f"  - {cand}", file=sys.stderr)
    print("提示：先启动过一次 Qoder 桌面端；或用 --db 指定路径；或设置环境变量 QODER_DB_PATH。", file=sys.stderr)
    sys.exit(1)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRICING_DEFAULT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "pricing.json"))
TZ = timezone(timedelta(hours=8))  # 北京时间
UNKNOWN_MODEL = "(未记录)"

# 共享脚注（build_dashboard.py / build_canvas.py 也引用）
FOOTNOTES = [
    "费用为参考估算：单价取自各模型官网（2026-09-23 获取），DeepSeek 系列已按消息时间自动区分高峰/空闲时段。",
    "自定义模型（custom_model）在本地库不区分具体型号，费用按其主力模型 DeepSeek-Flash 计价；切换参考模型见 pricing.json 的 _otherCustomModels。",
    "Qoder 官方档位无公开单价（官方额度以 Credits 口径为准），其 Token 计入总量但费用不计入。",
    "数据源为 Qoder 本地 chat_message 表的一次只读快照，页面数据不自动更新；刷新数据请重新运行生成脚本。",
]


def _parse_days(s):
    """解析 --days 参数：支持整数 N 或 'all'（等同于 0 = 全部历史）。"""
    if isinstance(s, str) and s.strip().lower() == "all":
        return 0
    try:
        return int(s)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(f"--days 应为非负整数或 'all'，得到: {s!r}")


def _parse_date(s):
    """解析 YYYY-MM-DD 日期字符串为毫秒时间戳（北京时间 00:00:00）。"""
    try:
        dt = datetime.strptime(s.strip(), "%Y-%m-%d").replace(tzinfo=TZ)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError(f"日期格式应为 YYYY-MM-DD，得到: {s!r}")


def parse_args():
    p = argparse.ArgumentParser(description="Qoder token 消费统计（官方模型 + 自定义模型）")
    p.add_argument("--days", type=_parse_days, default=7,
                       help="统计近 N 天；0 或 'all' = 全部历史（默认 7）")
    p.add_argument("--by", choices=["day", "model", "project", "session"], default="day",
                       help="聚合维度（默认 day）")
    p.add_argument("--since", type=_parse_date, default=None, metavar="YYYY-MM-DD",
                       help="起始日期（含），与 --days 互斥")
    p.add_argument("--until", type=_parse_date, default=None, metavar="YYYY-MM-DD",
                       help="截止日期（含，当日 23:59:59），与 --days 互斥")
    p.add_argument("--db", default=DB_DEFAULT,
                       help="Qoder 本地数据库路径（默认自动跨平台定位；可用环境变量 QODER_DB_PATH 覆盖）")
    p.add_argument("--pricing", default=PRICING_DEFAULT, help="单价表路径（默认技能目录下 pricing.json）")
    p.add_argument("--top", type=int, default=50, help="model/project/session 维度的最大行数（默认 50）")
    p.add_argument("--json", action="store_true", help="输出 JSON 而非 markdown")
    args = p.parse_args()
    if (args.since is not None or args.until is not None) and args.days != 7:
        p.error("--since/--until 与 --days 互斥，请只选一种方式")
    return args


def load_pricing(path):
    """返回 (models_map, currency, exchange_rate)。文件缺失或损坏时返回空映射（仅统计 token）。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        models = data.get("models") or {}
        rate = data.get("_exchangeRate")
        if not isinstance(rate, (int, float)) or rate <= 0:
            rate = None
        return {k: v for k, v in models.items() if isinstance(v, dict)}, data.get("currency", "CNY"), rate
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}, "CNY", None


def _parse_rates(d):
    """解析一组单价 {input, output, cached}；input/output 必须为数字。"""
    if not isinstance(d, dict):
        return None
    inp, out, cac = d.get("input"), d.get("output"), d.get("cached")
    if not isinstance(inp, (int, float)) or not isinstance(out, (int, float)):
        return None
    cac = cac if isinstance(cac, (int, float)) else inp  # 未单独配置缓存价时按输入价
    return {"input": float(inp), "output": float(out), "cached": float(cac)}


class PriceCache:
    """模型价格规则缓存：同一模型只解析一次。"""

    def __init__(self, pricing):
        self._pricing = pricing
        self._cache = {}

    def get(self, key):
        """返回该模型的计价规则：{'flat': {...}} 或 {'peak': {...}, 'offpeak': {...}}；未配置返回 None。"""
        if key in self._cache:
            return self._cache[key]
        p = self._pricing.get(key)
        if not p:
            self._cache[key] = None
            return None
        if isinstance(p.get("peak"), dict) or isinstance(p.get("offpeak"), dict):
            peak, off = _parse_rates(p.get("peak")), _parse_rates(p.get("offpeak"))
            peak, off = peak or off, off or peak
            result = {"peak": peak, "offpeak": off} if peak else None
        else:
            flat = _parse_rates(p)
            result = {"flat": flat} if flat else None
        self._cache[key] = result
        return result

    def label(self, key):
        p = self._pricing.get(key) or {}
        return p.get("display_name") or key


# 兼容旧接口：保留函数式 model_price / model_label 供外部直接调用
_default_cache = None


def model_price(pricing, key):
    global _default_cache
    if _default_cache is None or _default_cache._pricing is not pricing:
        _default_cache = PriceCache(pricing)
    return _default_cache.get(key)


def model_label(pricing, key):
    p = pricing.get(key) or {}
    return p.get("display_name") or key


def is_peak_hour(gmt_ms):
    """DeepSeek 计费高峰：北京时间周一至周五 9:00-12:00、14:00-18:00（法定节假日近似忽略）。"""
    dt = datetime.fromtimestamp((gmt_ms or 0) / 1000, tz=TZ)
    if dt.weekday() >= 5:
        return False
    return (9 <= dt.hour < 12) or (14 <= dt.hour < 18)


def message_cost(price, pt, ct, cd, gmt_ms):
    """单条消息费用：cached 是 prompt 的子集，未命中部分按 input 价、命中部分按 cached 价。"""
    unit = price.get("flat") or (price["peak"] if is_peak_hour(gmt_ms) else price["offpeak"])
    non_cached = max(pt - cd, 0)
    return (non_cached / 1e6 * unit["input"]
            + cd / 1e6 * unit["cached"]
            + ct / 1e6 * unit["output"])


def resolve_range(args):
    """根据参数计算 (since_ms, until_ms, range_label)。"""
    if args.since is not None or args.until is not None:
        since_ms = args.since
        # until 为当日 23:59:59.999
        until_ms = (args.until + 86400000 - 1) if args.until else None
        since_s = datetime.fromtimestamp(since_ms / 1000, tz=TZ).strftime("%Y-%m-%d") if since_ms else "最早"
        until_s = datetime.fromtimestamp(args.until / 1000, tz=TZ).strftime("%Y-%m-%d") if args.until else "至今"
        return since_ms, until_ms, f"{since_s} ~ {until_s}"
    since_ms = None
    if args.days > 0:
        since_ms = int((datetime.now(tz=TZ) - timedelta(days=args.days)).timestamp() * 1000)
    range_label = f"近 {args.days} 天" if args.days > 0 else "全部历史"
    return since_ms, None, range_label


def fetch_usage(db_path, since_ms, until_ms=None):
    """读取全部 token 记录。返回 (project_map, session_map, rows)。

    rows = (gmt_create, prompt_tokens, completion_tokens, cached_tokens, model_key, session_id)
    利用 SQLite JSON1 扩展在 SQL 层提取字段，避免 Python 侧逐行 json.loads。
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=15)
    try:
        # session_id -> 项目名映射（供 project 维度）
        project_map = {}
        session_map = {}  # session_id -> session 标题（供 session 维度）
        for sid, name in conn.execute("SELECT session_id, project_name FROM chat_session"):
            project_map[sid] = (name or "").strip() or "(未命名项目)"
        # 尝试获取 session 标题（如果表中有 title/name 字段）
        try:
            for sid, title in conn.execute(
                "SELECT session_id, COALESCE(NULLIF(TRIM(title), ''), NULLIF(TRIM(name), ''), session_id) FROM chat_session"
            ):
                session_map[sid] = title or sid
        except sqlite3.OperationalError:
            # title/name 列不存在时，session 维度退化为 session_id
            for sid in project_map:
                session_map[sid] = sid

        # SQL 侧用 JSON1 提取 token 字段，避免 Python 逐行解析；
        # CASE WHEN 包裹 json_extract 防止非法 JSON 行导致查询失败
        sql = (
            "SELECT gmt_create,"
            " CASE WHEN json_valid(token_info) THEN COALESCE(CAST(json_extract(token_info, '$.prompt_tokens') AS INTEGER), 0) ELSE 0 END,"
            " CASE WHEN json_valid(token_info) THEN COALESCE(CAST(json_extract(token_info, '$.completion_tokens') AS INTEGER), 0) ELSE 0 END,"
            " CASE WHEN json_valid(token_info) THEN COALESCE(CAST(json_extract(token_info, '$.cached_tokens') AS INTEGER), 0) ELSE 0 END,"
            " CASE WHEN model_info IS NOT NULL AND model_info <> '' AND json_valid(model_info) THEN COALESCE(json_extract(model_info, '$.model_key'), '') ELSE '' END,"
            " session_id"
            " FROM chat_message"
            " WHERE token_info IS NOT NULL AND token_info <> ''"
        )
        params = []
        if since_ms:
            sql += " AND gmt_create >= ?"
            params.append(since_ms)
        if until_ms:
            sql += " AND gmt_create <= ?"
            params.append(until_ms)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return project_map, session_map, rows


def aggregate(rows, by, project_map, pricing, session_map=None):
    """聚合 token 记录。buckets: key -> {msgs, prompt, completion, cached, cost, missing}"""
    price_cache = PriceCache(pricing) if not isinstance(pricing, PriceCache) else pricing
    buckets = {}

    def new_bucket():
        return {"msgs": 0, "prompt": 0, "completion": 0, "cached": 0, "cost": 0.0, "missing": set()}

    for gmt, pt, ct, cd, mk, session_id in rows:
        pt = int(pt or 0)
        ct = int(ct or 0)
        cd = int(cd or 0)
        mk = mk or UNKNOWN_MODEL

        if by == "day":
            key = datetime.fromtimestamp((gmt or 0) / 1000, tz=TZ).strftime("%Y-%m-%d")
        elif by == "model":
            key = mk
        elif by == "session":
            key = (session_map or {}).get(session_id, session_id or "(未知会话)")
        else:
            key = project_map.get(session_id, "(未知项目)")

        b = buckets.setdefault(key, new_bucket())
        b["msgs"] += 1
        b["prompt"] += pt
        b["completion"] += ct
        b["cached"] += cd
        price = price_cache.get(mk)
        if price is None:
            b["missing"].add(mk)
        else:
            b["cost"] += message_cost(price, pt, ct, cd, gmt)
    return buckets


def build_result(args, buckets, pricing):
    """组装最终行结构（费用已在聚合时按消息逐条累计）。"""
    rows_out, missing_all = [], set()
    for key, b in buckets.items():
        missing_all |= b["missing"]
        rows_out.append({
            "key": key,
            "label": model_label(pricing, key) if args.by == "model" else key,
            "msgs": b["msgs"],
            "prompt": b["prompt"],
            "completion": b["completion"],
            "cached": b["cached"],
            "total": b["prompt"] + b["completion"],
            "cost": round(b["cost"], 2) if b["cost"] > 0 else None,
        })
    if args.by == "day":
        rows_out.sort(key=lambda r: r["key"], reverse=True)
    else:
        rows_out.sort(key=lambda r: r["total"], reverse=True)
        rows_out = rows_out[: args.top]
    return rows_out, sorted(missing_all)


def fmt_int(n):
    return f"{n:,}"


def fmt_cost(cost, currency):
    if cost is None:
        return "-"
    return f"{'¥' if currency == 'CNY' else ''}{cost:,.2f}"


def render_markdown(args, rows, missing, pricing, range_label, currency):
    dim = {"day": "日期", "model": "模型", "project": "项目", "session": "会话"}[args.by]
    lines = [
        f"# Qoder Token 消费统计（{range_label}）",
        "",
        f"- 聚合维度：按{dim}",
        f"- 消息数合计：{fmt_int(sum(r['msgs'] for r in rows))}",
        f"- Token 合计：{fmt_int(sum(r['total'] for r in rows))}（输入 {fmt_int(sum(r['prompt'] for r in rows))} / 输出 {fmt_int(sum(r['completion'] for r in rows))} / 缓存命中 {fmt_int(sum(r['cached'] for r in rows))}）",
        "",
        f"| {dim} | 消息数 | 输入 Tokens | 输出 Tokens | 缓存 Tokens | 合计 Tokens | 预估费用 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {fmt_int(r['msgs'])} | {fmt_int(r['prompt'])} | "
            f"{fmt_int(r['completion'])} | {fmt_int(r['cached'])} | {fmt_int(r['total'])} | "
            f"{fmt_cost(r['cost'], currency)} |"
        )
    if missing:
        lines += [
            "",
            "> 未配置单价的模型（费用未计入）：" + "、".join(missing),
            "> 在 pricing.json 的 models 中填入单价（元 / 百万 tokens）后重跑即可显示费用。",
        ]
    lines += [
        "",
        "> 费用为参考估算：单价取自各模型官网（2026-09-23），DeepSeek 系列已按消息时间自动区分高峰/空闲时段。",
        "> 自定义模型在本地库统一记录为 custom_model，费用按 pricing.json 中其配置的参考模型计价（见 display_name）。",
    ]
    return "\n".join(lines)


def main():
    args = parse_args()
    require_db(args.db)

    pricing, currency, _exchange_rate = load_pricing(args.pricing)
    since_ms, until_ms, range_label = resolve_range(args)

    project_map, session_map, rows = fetch_usage(args.db, since_ms, until_ms)
    buckets = aggregate(rows, args.by, project_map, pricing, session_map=session_map)
    result_rows, missing = build_result(args, buckets, pricing)

    if args.json:
        payload = {
            "range": range_label,
            "by": args.by,
            "currency": currency,
            "rows": result_rows,
            "missingPricing": missing,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(render_markdown(args, result_rows, missing, pricing, range_label, currency))


if __name__ == "__main__":
    main()
