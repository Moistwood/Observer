# 进行对比的主程序
import datetime

import db
import fetcher
import notify
def check_one(site):
    # site 是 sites 表的一行
    n = site["name"]       # 名字
    c = fetcher.fetch(site["url"], site["selector"])  # 新抓到的内容
    prev = site["lc"]      # 上次的内容
    ch = prev is None or prev != c  # 变了吗
    t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 当前时间
    if ch:
        db.upd(n, c, t)
        db.add_snap(n, c, t)
    return ch, c


def check_all():
    sites = db.get_sites()
    if not sites:
        print("还没有监控项, 先用 add 添加。")
        return
    for s in sites:
        ch, _ = check_one(s)
        if ch:
            notify.notify(f"{s['name']} 内容有变化: {s['u']}")
        else:
            print(f"[无变化] {s['name']}")
