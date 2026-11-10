#!/usr/bin/env python3
"""涨停概念记忆 · 题库构建脚本（增量合并）

把 Obsidian 交接文档 `80-交接文档/涨停概念分类.md` 解析成题库，
并与已有题库做**增量合并**（不是覆盖）：

  - 新出现的「股票 × 概念」→ 追加，打上 addedAt 日期（页面上显示 NEW 标记）
  - 已存在的条目 → 更新备注 / 名称 / 在榜状态 / 日期，备注变了记 noteUpdatedAt
  - 文档里已经消失的条目 → 保留但 active=false（页面默认不出题，可在设置里打开）

产物：
  data/bank.json  题库快照（给脚本 / 其他工具读）
  data/bank.js    window.QUIZ_DATA = ...（给 index.html 直接 <script> 引入，
                  这样双击打开本地文件也能跑，不需要起服务器）

用法：
  ./refresh.sh                     # 日常刷新（推荐）
  python3 scripts/build_bank.py    # 手动跑
  python3 scripts/build_bank.py --md /path/to/别的.md --out data
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

DEFAULT_MD = os.path.expanduser(
    "~/Library/CloudStorage/OneDrive-个人/KnowledgeBase/80-交接文档/涨停概念分类.md"
)
MD_ENV = "MR_CONCEPT_MD"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")

SKIP_CONCEPT_WORDS = ("概念总览", "按概念分组")


def split_row(line):
    """按未转义的 | 切分表格行。"""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", body)]


def clean_cell(s):
    s = s.replace("\\|", "|").replace("<br>", "\n").replace("<br/>", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def clean_name(s):
    # 交易所名称里有「达 意 隆」这种补位空格，展示时去掉
    return re.sub(r"\s+", "", s)


def parse_md(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()

    doc_date = None
    m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
    if m:
        doc_date = m.group(1)
    export_at = None
    m = re.search(r"导出时间：(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text)
    if m:
        export_at = m.group(1)

    items = []
    concept = None
    in_detail = False
    has_board_col = True

    for line in text.split("\n"):
        if line.startswith("## "):
            head = line[3:].strip()
            in_detail = head.startswith("按概念分组")
            if not in_detail:
                concept = None
            continue

        m = re.match(r"^###\s+(.+?)\s*[（(]\s*\d+\s*只\s*[)）]\s*$", line)
        if m and in_detail:
            concept = m.group(1).strip()
            continue

        if not in_detail or not concept or not line.startswith("|"):
            continue

        cells = split_row(line)
        if len(cells) < 6:
            continue
        if cells[0] in ("代码", "---") or set(cells[0]) <= set("-: "):
            continue
        if "代码" in cells[0]:
            has_board_col = len(cells) >= 7
            continue
        if not re.fullmatch(r"\d{6}", cells[0]):
            continue

        code = cells[0]
        name = clean_name(clean_cell(cells[1]))
        note = clean_cell(cells[2])
        if note in ("—", "-", ""):
            note = ""
        first = clean_cell(cells[3]) if len(cells) > 3 else ""
        last = clean_cell(cells[4]) if len(cells) > 4 else ""
        try:
            days = int(clean_cell(cells[5])) if len(cells) > 5 else 1
        except ValueError:
            days = 1
        on_board = True
        if has_board_col and len(cells) > 6:
            on_board = clean_cell(cells[6]) == "是"

        items.append(
            {
                "code": code,
                "name": name,
                "concept": concept,
                "note": note,
                "first": first,
                "last": last,
                "days": days,
                "onBoard": on_board,
            }
        )

    return items, {"docDate": doc_date, "exportAt": export_at}


def build(md_path, out_dir, today):
    items, meta = parse_md(md_path)

    bank_path = os.path.join(out_dir, "bank.json")
    old = {}
    if os.path.exists(bank_path):
        try:
            with open(bank_path, encoding="utf-8") as f:
                prev = json.load(f)
            for it in prev.get("items", []):
                old[it["id"]] = it
        except Exception as e:  # 坏档不阻塞，重新来
            print(f"! 读取旧题库失败，按全新构建：{e}", file=sys.stderr)

    first_build = not old
    merged, seen = [], set()
    new_cnt = note_chg = 0
    for it in items:
        key = f'{it["code"]}::{it["concept"]}'
        if key in seen:  # 同概念重复行，去重
            continue
        seen.add(key)
        prev = old.get(key)
        rec = dict(it)
        rec["id"] = key
        rec["active"] = True
        if prev:
            rec["addedAt"] = prev.get("addedAt", today)
            rec["noteUpdatedAt"] = (
                today if prev.get("note", "") != it["note"] else prev.get("noteUpdatedAt")
            )
            if prev.get("note", "") != it["note"]:
                note_chg += 1
        else:
            # 首次建库时用「首次标记」当入库日，避免整库都算新题；
            # 之后的增量才用今天。
            rec["addedAt"] = (it.get("first") or today) if first_build else today
            rec["noteUpdatedAt"] = today
            new_cnt += 1
        merged.append(rec)

    # 文档里已消失的旧条目：保留历史，标记下线
    gone = 0
    for key, prev in old.items():
        if key in seen:
            continue
        rec = dict(prev)
        if rec.get("active", True):
            gone += 1
        rec["active"] = False
        merged.append(rec)

    merged.sort(key=lambda x: (not x.get("active", True), x["concept"], x["code"]))

    concepts = {}
    for it in merged:
        if not it.get("active", True):
            continue
        c = concepts.setdefault(it["concept"], {"count": 0, "notes": 0})
        c["count"] += 1
        if it.get("note"):
            c["notes"] += 1

    codes = {it["code"] for it in merged if it.get("active", True)}
    boards = {it["code"] for it in merged if it.get("active", True) and it.get("onBoard")}
    multi = set()
    per_code = {}
    for it in merged:
        if it.get("active", True):
            per_code[it["code"]] = per_code.get(it["code"], 0) + 1
    for c, n in per_code.items():
        if n > 1:
            multi.add(c)

    payload = {
        "meta": {
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "docDate": meta.get("docDate"),
            "exportAt": meta.get("exportAt"),
            "source": md_path,
            "items": len(merged),
            "activeItems": len([i for i in merged if i.get("active", True)]),
            "stocks": len(codes),
            "concepts": len(concepts),
            "singleStocks": len(codes) - len(multi),
            "multiStocks": len(multi),
            "onBoardStocks": len(boards),
            "newThisBuild": new_cnt,
            "noteChanged": note_chg,
            "wentInactive": gone,
        },
        "concepts": dict(
            sorted(concepts.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
        ),
        "items": merged,
    }

    os.makedirs(out_dir, exist_ok=True)
    with open(bank_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    js_path = os.path.join(out_dir, "bank.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("/* 自动生成，勿手改。来源：涨停概念分类.md */\n")
        f.write("window.QUIZ_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    m = payload["meta"]
    print(f"题库已更新 → {bank_path}")
    print(
        f"  {m['activeItems']} 条关系 / {m['stocks']} 只股票 / {m['concepts']} 个概念"
        f"（单选 {m['singleStocks']} · 多选 {m['multiStocks']}）"
    )
    print(
        f"  本次新增 {m['newThisBuild']} 条，备注更新 {m['noteChanged']} 条，"
        f"下线 {m['wentInactive']} 条"
    )
    print(f"  文档日期 {m['docDate']}，导出时间 {m['exportAt']}")
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=os.environ.get(MD_ENV, DEFAULT_MD))
    ap.add_argument("--out", default=DATA_DIR)
    ap.add_argument("--today", default=datetime.now().strftime("%Y-%m-%d"))
    a = ap.parse_args()

    if not os.path.exists(a.md):
        print(f"找不到文档：{a.md}", file=sys.stderr)
        print("用 --md 指定路径，或设环境变量 MR_CONCEPT_MD", file=sys.stderr)
        sys.exit(2)

    payload = build(a.md, a.out, a.today)
    if payload["meta"]["activeItems"] == 0:
        print("! 解析到 0 条，文档结构可能变了，请检查。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
