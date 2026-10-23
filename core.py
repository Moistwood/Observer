# 主程序
import argparse

import db
import fetcher
import monitor


def main():
    db.init_db()  # 建表
    p = argparse.ArgumentParser(prog="sitewatch", description="网页内容监控器")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="添加监控项")
    a.add_argument("name")
    a.add_argument("url" )
    a.add_argument("--selector", default=None)
    a.add_argument("--json-keys", default=None, help="只监控这些JSON键名, 逗号分隔")

    sub.add_parser("list", help="列出所有监控项")
    sub.add_parser("check", help="检查所有监控项变化")

    h = sub.add_parser("history", help="看某监控项历史")
    h.add_argument("name", help="监控项名字")

    pv = sub.add_parser("preview", help="抓一次看看抓到了什么")
    pv.add_argument("url")
    pv.add_argument("--selector", default=None)
    pv.add_argument("--json-keys", default=None, help="只监控这些JSON键名, 逗号分隔")

    args = p.parse_args()

    if args.cmd == "add":
        db.add_site(args.name, args.url, args.selector, args.json_keys)
        if args.json_keys:
            print(f"已添加: {args.name} -> {args.url} (只监控 {args.json_keys})")
        else:
            print(f"已添加: {args.name} -> {args.url}")

    elif args.cmd == "list":
        rows = db.get_sites()
        if not rows:
            print("没有监控项。")
            return
        print("名字\t网址\t上次变化")
        for s in rows:
            # ua 只在内容变化时才更新, 空值表示"还没变过", 不是"没检查过"
            print(f"{s['name']}\t{s['url']}\t{s['ua'] or '尚未变化'}")

    elif args.cmd == "check":
        monitor.check_all()

    elif args.cmd == "history":
        rows = db.get_hist(args.name)
        if not rows:
            print("暂无历史。")
            return
        for r in rows:
            content = r["c"]
            if len(content) > 500:
                content = content[:500] + "...已截断"
            print(f"[{r['cap']}]\n{content}\n")


    elif args.cmd == "preview":
        try:
            info = fetcher.probe(args.url, args.selector, args.json_keys)
        except Exception as e:
            print(f"[出错] {e}")
            return
        print(f"状态码    {info['status']}")
        print(f"内容类型  {info['content_type'] or '未声明'}")
        print(f"字符数    {info['chars']}")
        if info["keys"]:
            n = info["matched"]
            print(f"过滤      {','.join(sorted(info['keys']))} -> 匹配 {n} 个字段")
            if n == 0:
                print("[警告] 一个字段都没匹配到, 键名可能写错了")
        elif info["content_type"].find("json") >= 0:
            print("[提示] 这是 JSON, 加 --json-keys 可以只监控你关心的字段")
        print("-" * 40)
        lines = info["text"].splitlines()
        for line in lines[:20]:
            print(line)
        if len(lines) > 20:
            print(f"... 共 {len(lines)} 行")


if __name__ == "__main__":
    main()
