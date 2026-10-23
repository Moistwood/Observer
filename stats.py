# 统计查询, 只读不写
import datetime

import db


def overview():
    # 每个站点的总体表现: 抓了几次 / 成功几次 / 成功率 / 平均耗时 / 变了多少次
    # 用 LEFT JOIN 是为了让"还没抓过"的站点也出现在列表里
    c = db.conn()
    rows = c.execute("""
        SELECT s.name AS sn,
               COUNT(r.rowid) AS n,
               COALESCE(SUM(CASE WHEN r.ok = 1 THEN 1 ELSE 0 END), 0) AS ok_n,
               CASE WHEN COUNT(r.rowid) = 0 THEN NULL
                    ELSE ROUND(SUM(CASE WHEN r.ok = 1 THEN 1 ELSE 0 END)
                               * 100.0 / COUNT(r.rowid), 1)
               END AS rate,
               -- 只算成功的耗时, 失败那条可能含着 10 秒超时, 会把均值拉高
               AVG(CASE WHEN r.ok = 1 THEN r.cost END) AS avg_cost,
               (SELECT COUNT(*) FROM snapshots p WHERE p.sn = s.name) AS changes
        FROM sites s
        LEFT JOIN runs r ON r.sn = s.name
        GROUP BY s.name
        ORDER BY s.name
    """).fetchall()
    c.close()
    return rows


def daily(days=7):
    # 最近 N 天: 每天抓了多少次、失败几次
    since = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
    c = db.conn()
    rows = c.execute("""
        SELECT strftime('%Y-%m-%d', ts) AS d,
               COUNT(*) AS n,
               SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) AS fail,
               AVG(CASE WHEN ok = 1 THEN cost END) AS avg_cost
        FROM runs
        WHERE ts >= ?
        GROUP BY d
        ORDER BY d DESC
    """, (since,)).fetchall()
    c.close()
    return rows


def fail_hours():
    # 失败集中在一天里的哪些时段
    c = db.conn()
    rows = c.execute("""
        SELECT strftime('%H', ts) AS h,
               COUNT(*) AS n,
               SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) AS fail
        FROM runs
        GROUP BY h
        HAVING SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) > 0
        ORDER BY h
    """).fetchall()
    c.close()
    return rows


def latest():
    # 每个站点最近一次抓取, 没抓过的也要列出来
    c = db.conn()
    rows = c.execute("""
        SELECT s.name AS sn, r.ts, r.ok, r.status, r.cost, r.chars, r.err
        FROM sites s
        LEFT JOIN (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY sn ORDER BY ts DESC) AS rn
            FROM runs
        ) r ON r.sn = s.name AND r.rn = 1
        ORDER BY s.name
    """).fetchall()
    c.close()
    return rows
