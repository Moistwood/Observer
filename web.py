# Web 界面: 查看监控项与历史变化, 并提供增删改的操作
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import changes
import db
import monitor
import notify
import stats

BASE = Path(__file__).parent
app = FastAPI(title="sitewatch")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))


def _site_url(name):
    # 站点名可能带中文和空格, 拼进 URL 前要编码
    return f"/site/{quote(name)}"


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    db.init_db()
    cards = []
    for s in db.get_sites():
        rows = db.get_hist(s["name"])
        cards.append(
            {
                "name": s["name"],
                "url": s["url"],
                "selector": s["selector"],
                "json_keys": s["json_keys"],
                "quiet_min": s["quiet_min"] or 0,
                "stat": changes.summarize(rows),
                "run": db.last_run(s["name"]),
                "fails": db.fail_streak(s["name"]),
            }
        )
    return templates.TemplateResponse(request, "index.html", {"cards": cards})


@app.get("/site/{name}", response_class=HTMLResponse)
def site_detail(request: Request, name: str):
    db.init_db()
    rows = db.get_hist(name)
    info = db.get_site(name)
    if not rows:
        return templates.TemplateResponse(
            request,
            "empty.html",
            {
                "name": name,
                "exists": info is not None,
                "quiet_min": (info["quiet_min"] or 0) if info else 0,
                "runs": db.get_runs(name, 10),
                "fails": db.fail_streak(name),
            },
        )

    items = changes.timeline(rows)
    items.reverse()  # 最新的排在最上面

    return templates.TemplateResponse(
        request,
        "site.html",
        {
            "name": name,
            "url": info["url"] if info else "",
            "selector": info["selector"] if info else None,
            "json_keys": info["json_keys"] if info else None,
            "quiet_min": (info["quiet_min"] or 0) if info else 0,
            "items": items,
            "runs": db.get_runs(name, 10),
            "fails": db.fail_streak(name),
        },
    )


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request):
    db.init_db()
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "over": stats.overview(),
            "days": stats.daily(),
            "fails": stats.fail_hours(),
            "latest": stats.latest(),
        },
    )


@app.get("/add", response_class=HTMLResponse)
def add_form(request: Request):
    return templates.TemplateResponse(
        request, "add.html", {"error": None, "form": {}}
    )


@app.post("/add", response_class=HTMLResponse)
def add_submit(
    request: Request,
    name: str = Form(""),
    url: str = Form(""),
    selector: str = Form(""),
    json_keys: str = Form(""),
    quiet_min: str = Form("0"),
):
    name = name.strip()
    url = url.strip()
    selector = selector.strip() or None
    json_keys = json_keys.strip() or None
    quiet = int(quiet_min) if quiet_min.isdigit() else 0

    form = {
        "name": name,
        "url": url,
        "selector": selector,
        "json_keys": json_keys,
        "quiet_min": quiet,
    }

    def back(msg):
        return templates.TemplateResponse(
            request, "add.html", {"error": msg, "form": form}
        )

    if not name:
        return back("名字不能为空")
    if not url:
        return back("网址不能为空")
    if not url.startswith(("http://", "https://")):
        return back("网址要以 http:// 或 https:// 开头")
    if db.get_site(name) is not None:
        return back(f"已经有一个叫「{name}」的监控项了，换个名字")

    db.add_site(name, url, selector, json_keys, quiet)
    return RedirectResponse(_site_url(name), status_code=303)


@app.post("/quiet/{name}")
def set_quiet(name: str, minutes: str = Form("0")):
    # 详情页改静默期: 0 表示每次变化都通知
    db.set_quiet(name, int(minutes) if minutes.isdigit() else 0)
    return RedirectResponse(_site_url(name), status_code=303)


@app.post("/delete/{name}")
def delete_site(name: str):
    db.del_site(name)
    return RedirectResponse("/", status_code=303)


@app.post("/check/{name}")
def check_site(name: str):
    # 单站点手动抓取: 只更新数据, 不发通知, 免得和自己点的操作重复
    site = db.get_site(name)
    if site is not None:
        monitor.check_one(site)
    return RedirectResponse(_site_url(name), status_code=303)


@app.post("/check")
def check_all_now():
    for s in db.get_sites():
        monitor.check_one(s)
    return RedirectResponse("/", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    q = request.query_params
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "conf": notify._mail_conf(),
            "saved": q.get("saved"),
            "error": q.get("error"),
            "test": q.get("test"),
            "msg": q.get("msg"),
        },
    )


@app.post("/settings")
def settings_save(
    sender: str = Form(""),
    auth_code: str = Form(""),
    receiver: str = Form(""),
    smtp_host: str = Form("smtp.qq.com"),
    smtp_port: str = Form("465"),
):
    sender = sender.strip()
    receiver = receiver.strip()
    host = smtp_host.strip() or "smtp.qq.com"

    if not sender or not receiver:
        return RedirectResponse("/settings?error=empty", status_code=303)

    try:
        port = int(smtp_port)
    except ValueError:
        return RedirectResponse("/settings?error=port", status_code=303)

    # 授权码留空表示沿用原来的, 页面上不回显它
    old = notify._mail_conf()
    code = auth_code.strip() or (old["auth_code"] if old else "")
    if not code:
        return RedirectResponse("/settings?error=code", status_code=303)

    notify.save_conf(sender, code, receiver, host, port)
    return RedirectResponse("/settings?saved=1", status_code=303)


@app.post("/settings/test")
def settings_test():
    ok, err = notify.try_send("这是一封测试邮件，收到就说明邮箱配置没问题。")
    if ok:
        return RedirectResponse("/settings?test=ok", status_code=303)
    return RedirectResponse(f"/settings?test=fail&msg={quote(err[:150])}", status_code=303)
