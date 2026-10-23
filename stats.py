# 统计查询, 只读不写
# 汇总口径全部走 DWS(daily_stats), 不再直接扫原始表
import datetime

import db


def overview():
    # 每个站点的总体表现: 抓了几次 / 成功几次 / 成功率 / 平均耗时 / 变了多少次
    # 用 LEFT JOIN 让还没统计数据的站点也出现
    c = db.conn()
    rows = c.execute("""
        SELECT s.name AS sn,
               COALESCE(SUM(d.runs), 0) AS n,
               COALESCE(SUM(d.ok_runs), 0) AS ok_n,
               CASE WHEN COALESCE(SUM(d.runs), 0) = 0 THEN NULL
                    ELSE ROUND(SUM(d.ok_runs) * 100.0 / SUM(d.runs), 1)
               END AS rate,
               -- 存的是耗时总和, 除回成功次数才是真平均; 直接平均日均值会失真
               SUM(d.sum_cost) / NULLIF(SUM(d.ok_runs), 0) AS avg_cost,
               COALESCE(SUM(d.changes), 0) AS changes
        FROM sites s
        LEFT JOIN daily_stats d ON d.sn = s.name
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
        SELECT d AS day,
               SUM(runs) AS n,
               SUM(runs - ok_runs) AS fail,
               SUM(sum_cost) / NULLIF(SUM(ok_runs), 0) AS avg_cost
        FROM daily_stats
        WHERE d >= ?
        GROUP BY d
        ORDER BY d DESC
    """, (since,)).fetchall()
    c.close()
    return rows


def fail_hours():
    # 失败集中在一天里的哪些时段. 这个要看到小时, DWS 是天的粒度, 只能回原始表
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


def change_shape():
    # 每次变化改了多少行, 从 DWD 直接看: 用来判断是"小修"还是"整页换血"
    c = db.conn()
    rows = c.execute("""
        SELECT sn,
               COUNT(*) AS n,
               ROUND(AVG(add_n + del_n), 1) AS avg_moved,
               MAX(add_n + del_n) AS max_moved,
               ROUND(AVG(ABS(chars - prev_chars)), 0) AS avg_char_delta
        FROM changes
        WHERE is_first = 0
        GROUP BY sn
        ORDER BY avg_moved DESC
    """).fetchall()
    c.close()
    return rows
