# 把相邻快照的变化算成结构化数据, 供 Web 页面使用
from collections import Counter


def _take(lines, counter):
    # 按原顺序取出 counter 里计过数的行, 重复行按出现次数取
    out = []
    seen = Counter()
    for line in lines:
        if seen[line] < counter.get(line, 0):
            out.append(line)
            seen[line] += 1
    return out


def diff_lines(old_text, new_text):
    # 按集合比, 不管顺序. 返回 {"added": [...], "removed": [...]}
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    old_c = Counter(old_lines)
    new_c = Counter(new_lines)
    return {
        "added": _take(new_lines, new_c - old_c),
        "removed": _take(old_lines, old_c - new_c),
    }


def timeline(rows):
    # rows 来自 db.get_hist(), 已按 cap 升序. 返回每条快照相对上一条的变化
    out = []
    prev = None
    for i, r in enumerate(rows, 1):
        content = r["c"]
        item = {
            "index": i,
            "captured_at": r["cap"],
            "line_count": len(content.splitlines()),
            "char_count": len(content),
            "first": prev is None,
            "added": [],
            "removed": [],
        }
        if prev is not None:
            d = diff_lines(prev, content)
            item["added"] = d["added"]
            item["removed"] = d["removed"]
        out.append(item)
        prev = content
    return out


def summarize(rows):
    # 首页用: 只要最近一次变化的数量
    if not rows:
        return None
    if len(rows) == 1:
        return {
            "total": 1,
            "last_at": rows[0]["cap"],
            "added": 0,
            "removed": 0,
            "first": True,
        }
    d = diff_lines(rows[-2]["c"], rows[-1]["c"])
    return {
        "total": len(rows),
        "last_at": rows[-1]["cap"],
        "added": len(d["added"]),
        "removed": len(d["removed"]),
        "first": False,
    }
