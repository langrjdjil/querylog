"""querylog 的自检测试。用独立临时目录，不污染真实存档。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import querylog  # noqa: E402

ENTRY = os.path.join(BASE, "querylog.py")


def _isolated():
    """把存储目录指向临时位置。"""
    tmp = tempfile.mkdtemp(prefix="querylog_test_")
    querylog.STORE_DIR = querylog.Path(tmp)
    return tmp


def test_slugify_keeps_ascii() -> None:
    assert querylog.slugify("Hello World") == "hello-world"


def test_slugify_handles_chinese() -> None:
    result = querylog.slugify("查找零依赖工具")
    assert result
    assert " " not in result


def test_slugify_empty_falls_back() -> None:
    assert querylog.slugify("") == "query"
    assert querylog.slugify("!!!") == "query"


def test_new_entry_creates_file_with_conditions() -> None:
    tmp = _isolated()
    try:
        result = querylog.new_entry("标题 A", "查询条件", ["https://a.example"],
                                    ["时间范围: 2026"], "备注")
        path = querylog.Path(result["path"])
        assert path.is_file(), result
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["query"] == "查询条件"
        assert data["filters"] == ["时间范围: 2026"]
        assert data["result_state"] == "not_run"
        assert data["condition_hash"], data
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_new_entry_without_query_is_not_replayable() -> None:
    tmp = _isolated()
    try:
        result = querylog.new_entry("标题 B", "", [], [], "")
        check = querylog.replay_check(querylog.Path(result["file"]).name)
        assert not check["replayable"], check
        assert "query" in check["missing"], check
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_add_result_changes_state() -> None:
    tmp = _isolated()
    try:
        result = querylog.new_entry("标题 C", "q", [], [], "")
        name = querylog.Path(result["file"]).name
        entry = querylog.add_result(name, "结果一", "https://r.example", "说明")
        assert entry["result_state"] == "has_results"
        assert len(entry["results"]) == 1
        assert entry["results"][0]["title"] == "结果一"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_mark_empty_is_a_conclusion() -> None:
    tmp = _isolated()
    try:
        result = querylog.new_entry("标题 D", "q", [], [], "")
        name = querylog.Path(result["file"]).name
        entry = querylog.mark_empty(name, "按当前条件没有找到。")
        assert entry["result_state"] == "searched_empty"
        assert "没有" in entry["result_note"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_mark_unavailable_is_a_limitation() -> None:
    tmp = _isolated()
    try:
        result = querylog.new_entry("标题 E", "q", [], [], "")
        name = querylog.Path(result["file"]).name
        entry = querylog.mark_unavailable(name, "服务不可达。")
        assert entry["result_state"] == "unavailable"
        assert entry["result_state"] != "searched_empty"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_empty_and_unavailable_are_distinct() -> None:
    tmp = _isolated()
    try:
        r1 = querylog.new_entry("A", "q", [], [], "")
        r2 = querylog.new_entry("B", "q", [], [], "")
        n1 = querylog.Path(r1["file"]).name
        n2 = querylog.Path(r2["file"]).name
        e1 = querylog.mark_empty(n1, "按当前条件没有。")
        e2 = querylog.mark_unavailable(n2, "服务不可达。")
        assert e1["result_state"] != e2["result_state"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_list_entries_returns_rows() -> None:
    tmp = _isolated()
    try:
        querylog.new_entry("条目一", "q1", [], [], "")
        querylog.new_entry("条目二", "q2", [], [], "")
        rows = querylog.list_entries()
        assert len(rows) == 2, rows
        assert all(r["query"] for r in rows), rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_replay_check_passes_with_query() -> None:
    tmp = _isolated()
    try:
        result = querylog.new_entry("标题 F", "查询", [], [], "")
        check = querylog.replay_check(querylog.Path(result["file"]).name)
        assert check["replayable"], check
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_condition_hash_is_stable() -> None:
    tmp = _isolated()
    try:
        a = querylog.new_entry("标题 G", "同条件", [], ["x"], "")
        b = querylog.new_entry("标题 H", "同条件", [], ["x"], "")
        assert a["entry"]["condition_hash"] == b["entry"]["condition_hash"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_cli_help_exits_zero() -> None:
    r = subprocess.run([sys.executable, ENTRY, "--help"], capture_output=True,
                       text=True, timeout=30, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    assert "querylog" in r.stdout


def test_cli_new_and_list() -> None:
    tmp = tempfile.mkdtemp(prefix="querylog_cli_")
    env = dict(os.environ)
    env["HOME"] = tmp
    env["USERPROFILE"] = tmp
    try:
        r = subprocess.run(
            [sys.executable, ENTRY, "--new", "CLI 标题", "--query", "cli 条件"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace", env=env)
        assert r.returncode == 0, r.stderr
        assert "已创建存档" in r.stdout, r.stdout

        r2 = subprocess.run([sys.executable, ENTRY, "--list"],
                            capture_output=True, text=True, timeout=30,
                            encoding="utf-8", errors="replace", env=env)
        assert r2.returncode == 0, r2.stderr
        assert "CLI 标题" in r2.stdout, r2.stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_cli_check_missing_exits_one() -> None:
    tmp = tempfile.mkdtemp(prefix="querylog_cli2_")
    env = dict(os.environ)
    env["HOME"] = tmp
    env["USERPROFILE"] = tmp
    try:
        subprocess.run([sys.executable, ENTRY, "--new", "无条件标题"],
                       capture_output=True, text=True, timeout=30,
                       encoding="utf-8", errors="replace", env=env)
        rows = subprocess.run([sys.executable, ENTRY, "--list", "--json"],
                              capture_output=True, text=True, timeout=30,
                              encoding="utf-8", errors="replace", env=env).stdout
        name = json.loads(rows)[0]["file"]
        r = subprocess.run([sys.executable, ENTRY, "--check", name],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace", env=env)
        assert r.returncode == 1, (r.returncode, r.stdout)
        assert "无法复现" in r.stdout, r.stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [OK  ] {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  [FAIL] {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n共 {len(tests)} 项，失败 {failed} 项")
    raise SystemExit(1 if failed else 0)
