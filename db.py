# 存储仓库
import sqlite3
from pathlib import Path


DB = Path.home() / ".sitewatch.db"


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row  # 结果能用名字取字段
    return c


def init_db():
    c = conn()
    # 表在但连主键都没有, 说明结构已损坏, 只能删掉重建
    have = {r[1] for r in c.execute("PRAGMA table_info(sites)").fetchall()}
    if have and "name" not in have:
        c.execute("DROP TABLE sites")
    #  lc=上次内容 ua=上次变化时间 json_keys=只监控的JSON键名
    #  quiet_min=静默期(分钟), 0 表示每次变化都通知
    c.execute("""CREATE TABLE IF NOT EXISTS sites (
            name TEXT PRIMARY KEY,
            url    TEXT,
            selector  TEXT,
            json_keys TEXT,
            lc   TEXT,
            ua   TEXT,
            quiet_min INTEGER DEFAULT 0
        )""")
    #  cap=抓取时间
    c.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            sn   TEXT,
            c    TEXT,
            cap  TEXT
        )""")
    #  每次抓取一条, 用来回答"这个站到底还活着吗"
    c.execute("""CREATE TABLE IF NOT EXISTS runs (
            sn       TEXT,
            ts       TEXT,
            ok       INTEGER,
            status   INTEGER,
            chars    INTEGER,
            cost     REAL,
            err      TEXT,
            notified INTEGER DEFAULT 0
        )""")
    # DWD 明细层: 每一次"内容变了"的结构化记录, 由 snapshots 算出来, 可以随时重算
    c.execute("""CREATE TABLE IF NOT EXISTS changes (
            sn         TEXT,
            ts         TEXT,
            seq        INTEGER,
            chars      INTEGER,
            prev_chars INTEGER,
            lines      INTEGER,
            prev_lines INTEGER,
            add_n      INTEGER,
            del_n      INTEGER,
            hash       TEXT,
            is_first   INTEGER DEFAULT 0,
            PRIMARY KEY (sn, seq)
        )""")
    # DWS 汇总层: 按天按站点聚合. 只存可加性度量(sum_cost 能重算出平均, 反过来不行)
    c.execute("""CREATE TABLE IF NOT EXISTS daily_stats (
            d        TEXT,
            sn       TEXT,
            runs     INTEGER,
            ok_runs  INTEGER,
            changes  INTEGER,
            add_n    INTEGER,
            del_n    INTEGER,
            sum_cost REAL,
            max_cost REAL,
            PRIMARY KEY (d, sn)
        )""")
    # 老版本的库可能缺列: 逐列补上, 不 DROP, 已有数据不动
    have = {r[1] for r in c.execute("PRAGMA table_info(sites)").fetchall()}
    for col in ("url", "selector", "json_keys", "lc", "ua"):
        if col not in have:
            c.execute(f"ALTER TABLE sites ADD COLUMN {col} TEXT")
    if "quiet_min" not in have:
        c.execute("ALTER TABLE sites ADD COLUMN quiet_min INTEGER DEFAULT 0")
    have = {r[1] for r in c.execute("PRAGMA table_info(snapshots)").fetchall()}
    for col in ("sn", "c", "cap"):
        if col not in have:
            c.execute(f"ALTER TABLE snapshots ADD COLUMN {col} TEXT")
    c.execute("CREATE INDEX IF NOT EXISTS idx_snap ON snapshots(sn, cap)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_runs ON runs(sn, ts)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_changes ON changes(sn, ts)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_daily ON daily_stats(d, sn)")
    c.commit()
    c.close()


def add_site(name, url, selector, json_keys=None, quiet_min=0):
    c = conn()
    c.execute(
        "INSERT OR REPLACE INTO sites (name, url, selector, json_keys, lc, ua, quiet_min)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, url, selector, json_keys, None, None, quiet_min),
    )
    c.commit()
    c.close()


def set_quiet(name, minutes):
    c = conn()
    c.execute("UPDATE sites SET quiet_min=? WHERE name=?", (minutes, name))
    c.commit()
    c.close()


def get_sites():
    c = conn()
    rows = c.execute("SELECT * FROM sites").fetchall()
    c.close()
    return rows


def get_site(name):
    c = conn()
    row = c.execute("SELECT * FROM sites WHERE name=?", (name,)).fetchone()
    c.close()
    return row


def del_site(name):
    # 连历史快照和抓取记录一起删, 返回删掉的快照条数
    c = conn()
    n = c.execute("SELECT COUNT(*) FROM snapshots WHERE sn=?", (name,)).fetchone()[0]
    c.execute("DELETE FROM snapshots WHERE sn=?", (name,))
    c.execute("DELETE FROM runs WHERE sn=?", (name,))
    c.execute("DELETE FROM sites WHERE name=?", (name,))
    c.commit()
    c.close()
    return n


def upd(name, c, t):
    # c=新内容 t=时间
    cn = conn()
    cn.execute("UPDATE sites SET lc=?, ua=? WHERE name=?", (c, t, name))
    cn.commit()
    cn.close()


def add_snap(name, c, t):
    # c=内容 t=抓取时间
    cn = conn()
    cn.execute("INSERT INTO snapshots (sn, c, cap) VALUES (?, ?, ?)", (name, c, t))
    cn.commit()
    cn.close()


def get_hist(name):
    c = conn()
    rows = c.execute(
        "SELECT c, cap FROM snapshots WHERE sn=? ORDER BY cap", (name,)
    ).fetchall()
    c.close()
    return rows


# ---------- 抓取记录 ----------

def add_run(sn, ts, ok, status=None, chars=None, cost=None, err=None, pending=False):
    # pending=True 表示这次有变化、通知还没发出去; 否则记 2 表示无需通知
    c = conn()
    cur = c.execute(
        "INSERT INTO runs (sn, ts, ok, status, chars, cost, err, notified)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (sn, ts, 1 if ok else 0, status, chars, cost,
         (err or "")[:300] or None, 0 if pending else 2),
    )
    rid = cur.lastrowid
    c.commit()
    c.close()
    return rid


def get_runs(sn, limit=10):
    c = conn()
    rows = c.execute(
        "SELECT * FROM runs WHERE sn=? ORDER BY ts DESC, rowid DESC LIMIT ?", (sn, limit)
    ).fetchall()
    c.close()
    return rows


def last_run(sn):
    c = conn()
    row = c.execute(
        "SELECT * FROM runs WHERE sn=? ORDER BY ts DESC, rowid DESC LIMIT 1", (sn,)
    ).fetchone()
    c.close()
    return row


def fail_streak(sn):
    # 最近连续失败了几次, 一遇到成功就归零
    c = conn()
    rows = c.execute(
        "SELECT ok FROM runs WHERE sn=? ORDER BY ts DESC, rowid DESC LIMIT 20", (sn,)
    ).fetchall()
    c.close()
    n = 0
    for r in rows:
        if r["ok"]:
            break
        n += 1
    return n


def last_notified(sn):
    # 这个站点上一次发出通知的时间, 用来算静默期
    c = conn()
    row = c.execute(
        "SELECT MAX(ts) FROM runs WHERE sn=? AND notified=1", (sn,)
    ).fetchone()
    c.close()
    return row[0]


def mark_notified(run_id):
    c = conn()
    c.execute("UPDATE runs SET notified=1 WHERE rowid=?", (run_id,))
    c.commit()
    c.close()


def mark_skipped(run_id):
    # 静默期内故意不通知, 记成 2 免得以后被当成积压补发出去
    c = conn()
    c.execute("UPDATE runs SET notified=2 WHERE rowid=?", (run_id,))
    c.commit()
    c.close()


def get_pending(limit=30):
    # 还没通知出去的变化, 连站点地址一起取出来
    c = conn()
    rows = c.execute(
        """SELECT r.rowid AS rid, r.sn, r.ts, s.url
           FROM runs r JOIN sites s ON s.name = r.sn
           WHERE r.notified = 0 AND r.ok = 1
           ORDER BY r.ts LIMIT ?""",
        (limit,),
    ).fetchall()
    c.close()
    return rows


def prune_runs(sn, keep=200):
    # 只保留最近 N 条, 老的删掉, 否则表会一直长
    # 还没通知出去的那几条要留着, 不然就丢了
    c = conn()
    c.execute(
        "DELETE FROM runs WHERE sn=? AND notified<>0 AND rowid NOT IN "
        "(SELECT rowid FROM runs WHERE sn=? ORDER BY ts DESC, rowid DESC LIMIT ?)",
        (sn, sn, keep),
    )
    c.commit()
    c.close()
