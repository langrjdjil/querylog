"""querylog —— 把查询条件与结果清单一起存档。

设计原则：
1. 查询条件必须和结果存在一起，缺一个这份存档就没有意义。
2. 「没有」和「没查到」永远分开写，不混用。
3. 只读公开信息，不绕过任何访问控制。

仅依赖 Python 标准库。

用法:
    python querylog.py --help
    python querylog.py --new "查找零依赖 CSV 工具" --query "csv parser stdlib"
    python querylog.py --new "标题" --query "关键词" --source https://example.com
    python querylog.py --list
    python querylog.py --show 2026-10-26-xxx.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

STORE_DIR = Path.home() / ".querylog"


def slugify(text: str, limit: int = 40) -> str:
    """把标题变成文件名安全的短标识。中文保留，其余转连字符。"""
    out = []
    for ch in text.strip().lower():
        if ch.isalnum() and (ch.isascii() or ord(ch) > 127):
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    result = "".join(out).strip("-")
    return (result[:limit] or "query").strip("-")


def _entry_path(name: str) -> Path:
    """把用户给的标识解析成实际文件路径。"""
    candidate = STORE_DIR / name
    if candidate.is_file():
        return candidate
    candidate = STORE_DIR / f"{name}.json"
    if candidate.is_file():
        return candidate
    return STORE_DIR / f"{name}.json"


def new_entry(title: str, query: str, sources: list[str], filters: list[str],
              notes: str) -> dict:
    """创建一条存档。查询条件与结果清单一起写进同一条记录。"""
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d")
    base = slugify(title)
    name = f"{stamp}-{base}"
    path = STORE_DIR / f"{name}.json"
    index = 2
    while path.exists():
        path = STORE_DIR / f"{name}-{index}.json"
        index += 1

    content_hash = hashlib.sha256(
        (query + "|" + "|".join(sorted(filters))).encode("utf-8")).hexdigest()[:12]

    entry = {
        "title": title,
        "query": query,
        "filters": filters,
        "sources": sources,
        "notes": notes,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "condition_hash": content_hash,
        "results": [],
        "result_state": "not_run",
        "result_note": "尚未执行检索，因此没有结果；这与「查下来没有」是不同的事。",
    }
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"file": path.name, "path": str(path), "entry": entry}


def list_entries() -> list[dict]:
    """列出所有存档。"""
    if not STORE_DIR.is_dir():
        return []
    rows = []
    for path in sorted(STORE_DIR.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rows.append({
            "file": path.name,
            "title": raw.get("title", ""),
            "query": raw.get("query", ""),
            "created_at": raw.get("created_at", ""),
            "result_state": raw.get("result_state", "unknown"),
            "result_count": len(raw.get("results") or []),
        })
    return rows


def load_entry(name: str) -> dict:
    path = _entry_path(name)
    if not path.is_file():
        raise FileNotFoundError(f"找不到存档：{name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save(entry: dict, name: str) -> Path:
    path = _entry_path(name)
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def add_result(name: str, title: str, url: str, note: str) -> dict:
    """往存档里追加一条结果。"""
    entry = load_entry(name)
    results = entry.setdefault("results", [])
    results.append({"title": title, "url": url, "note": note,
                    "added_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    entry["result_state"] = "has_results"
    entry["result_note"] = f"已记录 {len(results)} 条结果。"
    _save(entry, name)
    return entry


def mark_empty(name: str, note: str) -> dict:
    """标记为「查下来没有」。这是结论，和「没查到」不同。"""
    entry = load_entry(name)
    entry["result_state"] = "searched_empty"
    entry["result_note"] = note or "按当前查询条件检索，没有找到结果。"
    _save(entry, name)
    return entry


def mark_unavailable(name: str, reason: str) -> dict:
    """标记为「没能查到」。这是工具的局限，不是结论。"""
    entry = load_entry(name)
    entry["result_state"] = "unavailable"
    entry["result_note"] = reason or "本次未能完成检索，因此不能得出任何结论。"
    _save(entry, name)
    return entry


def replay_check(name: str) -> dict:
    """检查存档的查询条件是否完整——条件不全，存档就不可复现。"""
    entry = load_entry(name)
    missing = []
    if not entry.get("query"):
        missing.append("query")
    if not entry.get("created_at"):
        missing.append("created_at")
    if not entry.get("condition_hash"):
        missing.append("condition_hash")
    return {
        "entry": name,
        "replayable": not missing,
        "missing": missing,
        "query": entry.get("query", ""),
        "filters": entry.get("filters", []),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="querylog",
        description="把查询条件与结果清单一起存档，支持复现（仅依赖标准库）",
        epilog=(
            "示例:\n"
            "  python querylog.py --new '查找零依赖 CSV 工具' --query 'csv parser stdlib'\n"
            "  python querylog.py --add <文件> --result-title '标题' --result-url https://example.com\n"
            "  python querylog.py --empty <文件> --note '按当前条件查下来没有'\n"
            "  python querylog.py --unavailable <文件> --reason '检索服务不可达'\n"
            "  python querylog.py --list\n"
            "  python querylog.py --show <文件>\n"
            "  python querylog.py --check <文件>\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--new", metavar="标题", help="新建一条存档")
    ap.add_argument("--query", default="", help="查询条件（配合 --new）")
    ap.add_argument("--filter", action="append", default=[],
                    help="过滤条件，可重复（配合 --new）")
    ap.add_argument("--source", action="append", default=[],
                    help="来源 URL，可重复（配合 --new）")
    ap.add_argument("--notes", default="", help="备注（配合 --new）")

    ap.add_argument("--add", metavar="文件", help="往存档里追加一条结果")
    ap.add_argument("--result-title", default="", help="结果标题")
    ap.add_argument("--result-url", default="", help="结果 URL")
    ap.add_argument("--result-note", default="", help="结果说明")

    ap.add_argument("--empty", metavar="文件", help="标记为「查下来没有」")
    ap.add_argument("--note", default="", help="说明（配合 --empty）")

    ap.add_argument("--unavailable", metavar="文件", help="标记为「没能查到」")
    ap.add_argument("--reason", default="", help="原因（配合 --unavailable）")

    ap.add_argument("--list", action="store_true", help="列出所有存档")
    ap.add_argument("--show", metavar="文件", help="显示一条存档")
    ap.add_argument("--check", metavar="文件", help="检查存档是否可复现")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    if args.new:
        result = new_entry(args.new, args.query, args.source,
                           args.filter, args.notes)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"已创建存档：{result['path']}")
            print(f"  查询条件：{args.query or '（未填写 —— 这份存档将无法复现）'}")
            print(f"  条件指纹：{result['entry']['condition_hash']}")
        return 0

    if args.add:
        try:
            entry = add_result(args.add, args.result_title,
                               args.result_url, args.result_note)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        else:
            print(f"已追加结果，当前共 {len(entry['results'])} 条。")
        return 0

    if args.empty:
        try:
            entry = mark_empty(args.empty, args.note)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"已标记为「查下来没有」：{entry['result_note']}")
        return 0

    if args.unavailable:
        try:
            entry = mark_unavailable(args.unavailable, args.reason)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"已标记为「没能查到」：{entry['result_note']}")
        return 0

    if args.list:
        rows = list_entries()
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return 0
        if not rows:
            print("还没有任何存档。用 --new 建一条。")
            return 0
        print(f"共 {len(rows)} 条存档：")
        for row in rows:
            state = {
                "not_run": "未检索",
                "has_results": "有结果",
                "searched_empty": "查下来没有",
                "unavailable": "没能查到",
            }.get(row["result_state"], row["result_state"])
            print(f"  {row['file']}")
            print(f"    标题：{row['title']}")
            print(f"    条件：{row['query'] or '（缺失）'}")
            print(f"    状态：{state}（{row['result_count']} 条结果）")
        return 0

    if args.show:
        try:
            entry = load_entry(args.show)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(entry, ensure_ascii=False, indent=2))
            return 0
        print(f"标题：{entry.get('title', '')}")
        print(f"时间：{entry.get('created_at', '')}")
        print(f"查询条件：{entry.get('query', '')}")
        if entry.get("filters"):
            print(f"过滤条件：{'、'.join(entry['filters'])}")
        if entry.get("sources"):
            print("来源：")
            for s in entry["sources"]:
                print(f"  - {s}")
        print(f"状态：{entry.get('result_state', '')} —— {entry.get('result_note', '')}")
        print(f"结果（{len(entry.get('results') or [])} 条）：")
        for r in entry.get("results") or []:
            print(f"  - {r.get('title', '')}  {r.get('url', '')}")
            if r.get("note"):
                print(f"    {r['note']}")
        return 0

    if args.check:
        try:
            result = replay_check(args.check)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["replayable"] else 1
        if result["replayable"]:
            print("这份存档的查询条件完整，可以在同样条件下重跑。")
            print(f"  条件：{result['query']}")
            if result["filters"]:
                print(f"  过滤：{'、'.join(result['filters'])}")
            return 0
        print("这份存档缺少必要字段，无法复现：")
        for field in result["missing"]:
            print(f"  - 缺少 {field}")
        return 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
