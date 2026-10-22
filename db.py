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
    #  lc=上次内容 ua=更新时间 json_keys=只监控的JSON键名
    c.execute("""CREATE TABLE IF NOT EXISTS sites (
            name TEXT PRIMARY KEY,
            url    TEXT,
            selector  TEXT,
            json_keys TEXT,
            lc   TEXT,
            ua   TEXT
        )""")
    #  cap=抓取时间
    c.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            sn   TEXT,
            c    TEXT,
            cap  TEXT
        )""")
    # 老版本的库可能缺列: 逐列补上, 不 DROP, 已有数据不动
    have = {r[1] for r in c.execute("PRAGMA table_info(sites)").fetchall()}
    for col in ("url", "selector", "json_keys", "lc", "ua"):
        if col not in have:
            c.execute(f"ALTER TABLE sites ADD COLUMN {col} TEXT")
    have = {r[1] for r in c.execute("PRAGMA table_info(snapshots)").fetchall()}
    for col in ("sn", "c", "cap"):
        if col not in have:
            c.execute(f"ALTER TABLE snapshots ADD COLUMN {col} TEXT")
    c.commit()
    c.close()


def add_site(name, url, selector, json_keys=None):
    c = conn()
    c.execute(
        "INSERT OR REPLACE INTO sites (name, url, selector, json_keys, lc, ua) VALUES (?, ?, ?, ?, ?, ?)",
        (name, url, selector, json_keys, None, None),
    )
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
