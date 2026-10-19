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
    rebuild = False
    try:
        c.execute("SELECT url FROM sites LIMIT 1")
    except sqlite3.OperationalError:
        rebuild = True
    if rebuild:
        c.execute("DROP TABLE IF EXISTS sites")
        c.execute("DROP TABLE IF EXISTS snapshots")
        #  lc=上次内容 ua=更新时间
        c.execute("""CREATE TABLE sites (
            name TEXT PRIMARY KEY,
            url    TEXT,
            selector  TEXT,
            lc   TEXT,
            ua   TEXT
        )""")
        #  cap=抓取时间
        c.execute("""CREATE TABLE snapshots (
            sn   TEXT,
            c    TEXT,
            cap  TEXT
        )""")
    else:
        c.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            sn TEXT, c TEXT, cap TEXT)""")
    c.commit()
    c.close()


def add_site(name, url, selector):
    c = conn()
    c.execute(
        "INSERT OR REPLACE INTO sites (name, url, selector, lc, ua) VALUES (?, ?, ?, ?, ?)",
        (name, url, selector, None, None),
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
