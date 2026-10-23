# 进行对比的主程序
import datetime
import time

import db
import fetcher
import notify

FAIL_ALERT = 3  # 连续失败几次才提醒, 挡掉偶发的网络抖动


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def check_one(site):
    # site 是 sites 表的一行
    # 返回这次抓取的结果, 顺便把状态码/字符数/耗时记进 runs 表
    n = site["name"]
    ts = _now()
    t0 = time.perf_counter()

    try:
        info = fetcher.probe(site["url"], site["selector"], site["json_keys"])
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        rid = db.add_run(n, ts, False, cost=time.perf_counter() - t0, err=err)
        print(f"[出错] {n}: {err}")
        return {"changed": False, "ok": False, "content": None,
                "run_id": rid, "ts": ts, "err": err}

    cost = time.perf_counter() - t0
    c = info["text"]
    rid = db.add_run(n, ts, True, status=info["status"], chars=info["chars"], cost=cost)

    prev = site["lc"]                    # 上次的内容
    ch = prev is None or prev != c       # 变了吗
    if ch:
        db.upd(n, c, ts)
        db.add_snap(n, c, ts)

    db.prune_runs(n)
    return {"changed": ch, "ok": True, "content": c,
            "run_id": rid, "ts": ts, "err": None}


def _in_quiet(site):
    # 静默期内不再重复提醒。quiet_min=0 表示不节流, 每次都通知
    q = site["quiet_min"] or 0
    if q <= 0:
        return False
    last = db.last_notified(site["name"])
    if not last:
        return False
    try:
        delta = datetime.datetime.now() - datetime.datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return delta.total_seconds() < q * 60


def _digest(changed, failed):
    lines = []
    if changed:
        lines.append(f"本次检查 {len(changed)} 个站点有变化：\n")
        for i, (s, r) in enumerate(changed, 1):
            lines.append(f"{i}. {s['name']}")
            lines.append(f"   {s['url']}")
            lines.append(f"   {r['ts']}\n")
    if failed:
        lines.append(f"另有 {len(failed)} 个站点抓取失败：\n")
        for s, r, k in failed:
            lines.append(f"  {s['name']}  连续失败 {k} 次")
            lines.append(f"   {r['err']}")
            lines.append(f"   {s['url']}\n")
    return "\n".join(lines).rstrip()


def check_all():
    sites = db.get_sites()
    if not sites:
        print("还没有监控项, 先用 add 添加。")
        return

    changed = []   # 有变化且不在静默期
    failed = []    # 连续失败刚满阈值
    quiet_skip = 0

    for s in sites:
        r = check_one(s)

        if r["ok"]:
            if not r["changed"]:
                print(f"[无变化] {s['name']}")
            elif _in_quiet(s):
                quiet_skip += 1
                print(f"[静默] {s['name']} 有变化, 但还在静默期里")
            else:
                changed.append((s, r))
        else:
            k = db.fail_streak(s["name"])
            if k == FAIL_ALERT:
                failed.append((s, r, k))

    if quiet_skip:
        print(f"[提示] {quiet_skip} 个站在静默期内, 这次没发通知")

    if not changed and not failed:
        print("[完成] 没有需要通知的变化")
        return

    subject = f"sitewatch: {len(changed)} 个站点有变化" if changed else "sitewatch: 有站点抓取失败"
    notify.notify(_digest(changed, failed), subject=subject)

    for s, r in changed:
        db.mark_notified(r["run_id"])
