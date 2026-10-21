# 主程序
import argparse

import db
import monitor


def main():
    db.init_db()  # 建表
    p = argparse.ArgumentParser(prog="sitewatch", description="网页内容监控器")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="添加监控项")
    a.add_argument("name")
    a.add_argument("url" )
    a.add_argument("--selector", default=None)

    sub.add_parser("list", help="列出所有监控项")
    sub.add_parser("check", help="检查所有监控项变化")

    h = sub.add_parser("history", help="看某监控项历史")
    h.add_argument("name", help="监控项名字")

    args = p.parse_args()

    if args.cmd == "add":
        db.add_site(args.name, args.url, args.selector)
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
        for r in rows:
            content = r["c"]
            if len(content) > 200:
                #测试版先阶段性截断，避免输出过长
                content = content[:200] + "...已截断"
            print(f"[{r['cap']}]\n{content}\n")


if __name__ == "__main__":
    main()
