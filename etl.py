# ODS(snapshots) -> DWD(changes) -> DWS(daily_stats)
# 原则: snapshots 是唯一真相源, 下面两层随时可以从它重算出来, 所以重算必须幂等
import datetime
import hashlib

import changes
import db


def _hash(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def rebuild_changes():
    # 全量重建 DWD: 把每个站点的快照按时间排好, 相邻两条比一次
    c = db.conn()
    rows = c.execute("SELECT sn, c, cap FROM snapshots ORDER BY sn, cap").fetchall()

    out = []
    prev_sn = None
    prev_text = None
    seq = 0

    for r in rows:
        sn, text, ts = r["sn"], r["c"], r["cap"]
        if sn != prev_sn:          # 换站点了, 重新起头
            prev_sn = sn
            prev_text = None
            seq = 0
        seq += 1

        cur_lines = len(text.splitlines())
        if prev_text is None:
            # 第一次抓到的内容不算"变化", 只是个基准
            out.append((sn, ts, seq, len(text), None, cur_lines, None,
                        0, 0, _hash(text), 1))
        else:
            d = changes.diff_lines(prev_text, text)
            out.append((sn, ts, seq, len(text), len(prev_text),
                        cur_lines, len(prev_text.splitlines()),
                        len(d["added"]), len(d["removed"]), _hash(text), 0))
        prev_text = text

    # 先删后插, 保证重跑结果一样
    c.execute("DELETE FROM changes")
    c.executemany(
        "INSERT INTO changes (sn, ts, seq, chars, prev_chars, lines, prev_lines,"
        " add_n, del_n, hash, is_first) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        out,
    )
    c.commit()
    c.close()
    return len(out)


def rebuild_daily(days=90):
    # 全量重算最近 N 天的 DWS. 两张来源表各聚合一次, 再按 (日期, 站点) 合并
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    c = db.conn()

    runs = c.execute("""
        SELECT substr(ts, 1, 10) AS d, sn,
               COUNT(*) AS n,
               SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END) AS ok_n,
               SUM(CASE WHEN ok = 1 THEN cost ELSE 0 END) AS sum_cost,
               MAX(CASE WHEN ok = 1 THEN cost END) AS max_cost
        FROM runs WHERE ts >= ?
        GROUP BY d, sn
    """, (since,)).fetchall()

    chg = c.execute("""
        SELECT substr(ts, 1, 10) AS d, sn,
               COUNT(*) AS n, SUM(add_n) AS add_n, SUM(del_n) AS del_n
        FROM changes WHERE ts >= ? AND is_first = 0
        GROUP BY d, sn
    """, (since,)).fetchall()

    # 用字典合并, 因为某个站点某天可能只有抓取没有变化, 或者反过来
    bucket = {}
    for r in runs:
        bucket[(r["d"], r["sn"])] = {
            "runs": r["n"], "ok_runs": r["ok_n"],
            "changes": 0, "add_n": 0, "del_n": 0,
            "sum_cost": r["sum_cost"] or 0.0, "max_cost": r["max_cost"],
        }
    for r in chg:
        b = bucket.setdefault((r["d"], r["sn"]), {
            "runs": 0, "ok_runs": 0, "changes": 0, "add_n": 0, "del_n": 0,
            "sum_cost": 0.0, "max_cost": None,
        })
        b["changes"] = r["n"]
        b["add_n"] = r["add_n"] or 0
        b["del_n"] = r["del_n"] or 0

    out = [
        (d, sn, v["runs"], v["ok_runs"], v["changes"],
         v["add_n"], v["del_n"], round(v["sum_cost"], 3), v["max_cost"])
        for (d, sn), v in bucket.items()
    ]

    c.execute("DELETE FROM daily_stats WHERE d >= ?", (since,))
    c.executemany(
        "INSERT INTO daily_stats (d, sn, runs, ok_runs, changes, add_n, del_n,"
        " sum_cost, max_cost) VALUES (?,?,?,?,?,?,?,?,?)",
        out,
    )
    c.commit()
    c.close()
    return len(out)


def run(days=90):
    # 抓取完调一次, 把下面两层刷新出来
    n_change = rebuild_changes()
    n_daily = rebuild_daily(days)
    return n_change, n_daily
