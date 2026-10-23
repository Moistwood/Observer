# Web 界面: 查看监控项与历史变化, 并提供增删改的操作
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import changes
import db
import monitor

BASE = Path(__file__).parent
app = FastAPI(title="sitewatch")
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
                "stat": changes.summarize(rows),
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
            {"name": name, "exists": info is not None},
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
            "items": items,
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
):
    name = name.strip()
    url = url.strip()
    selector = selector.strip() or None
    json_keys = json_keys.strip() or None

    form = {"name": name, "url": url, "selector": selector, "json_keys": json_keys}

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

    db.add_site(name, url, selector, json_keys)
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
