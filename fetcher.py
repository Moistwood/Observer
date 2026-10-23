# fetcher.py - 去网上抓内容
import hashlib
import json
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}


def _get(u):
    return requests.get(u, timeout=10, headers=HEADERS)


def _split_keys(keys):
    # "title,bvid" -> {"title","bvid"}; 没给就返回 None, 表示不过滤
    if not keys:
        return None
    if isinstance(keys, (list, tuple, set)):
        items = keys
    else:
        items = keys.split(",")
    picked = {k.strip() for k in items if k and k.strip()}
    return picked or None


def _html(r, sel):
    # 传 bytes 给 BS4, 它会看 BOM 和 meta charset, 比自己猜准
    soup = BeautifulSoup(r.content, "html.parser")
    if sel:
        return "\n".join(el.get_text(strip=True) for el in soup.select(sel))
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _json(r, raw=None, keys=None):
    # 返回 (文本, 命中字段数). 没给 keys 就整份格式化, 命中数为 None
    text = raw if raw is not None else r.content.decode("utf-8-sig")
    data = json.loads(text)
    if not keys:
        return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), None

    # 走一遍整棵树, 只留名单里的键
    hits = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in keys:
                    hits.append((k, v))
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)

    lines = []
    for k, v in hits:
        if isinstance(v, (dict, list)):
            val = json.dumps(v, ensure_ascii=False, sort_keys=True)
        elif v is None:
            val = "null"
        elif isinstance(v, bool):
            val = "true" if v else "false"
        else:
            val = str(v)
        lines.append(f"{k}: {val}")
    return "\n".join(lines), len(hits)


def _xml(r):
    root = ET.fromstring(r.content)
    ET.indent(root)
    return ET.tostring(root, encoding="unicode")


def _parse(r, sel=None, keys=None):
    # 看 Content-Type 决定怎么解. 返回 (文本, 命中字段数)
    ct = r.headers.get("Content-Type", "").split(";")[0].strip().lower()

    if ct == "application/json" or ct.endswith("+json"):
        try:
            return _json(r, keys=keys)
        except (ValueError, UnicodeDecodeError):
            pass  # 说是 JSON 其实不是, 往下当纯文本处理

    if ct in ("application/xml", "text/xml") or ct.endswith("+xml"):
        try:
            return _xml(r), None
        except ET.ParseError:
            pass

    if ct in ("text/html", "application/xhtml+xml"):
        return _html(r, sel), None

    # 服务器没给类型, 看一眼开头像不像 HTML
    head = r.content[:512].lstrip().lower()
    if not ct and (head.startswith(b"<!doctype") or head.startswith(b"<html") or head.startswith(b"<head")):
        return _html(r, sel), None

    if ct.startswith("image/") or ct in ("application/pdf", "application/octet-stream"):
        # 二进制没法比文本, 比哈希
        digest = hashlib.sha256(r.content).hexdigest()
        return f"[二进制] {len(r.content)} bytes sha256={digest}", None

    text = r.content.decode(r.apparent_encoding or "utf-8", errors="replace")
    # 有些接口给的是 text/plain, 内容却是 JSON
    stripped = text.strip()
    if stripped[:1] in ("{", "["):
        try:
            return _json(r, raw=stripped, keys=keys)
        except ValueError:
            pass
    return text, None


def fetch(u, sel=None, keys=None):
    # u=网址 sel=要提取的选择器 keys=只监控的JSON字段, 返回纯文本
    text, _ = _parse(_get(u), sel, _split_keys(keys))
    return text


def probe(u, sel=None, keys=None):
    # 抓一次并把状态码、类型一起返回, 给 preview 用
    r = _get(u)
    picked = _split_keys(keys)
    text, matched = _parse(r, sel, picked)
    return {
        "status": r.status_code,
        "content_type": r.headers.get("Content-Type", "").split(";")[0].strip().lower(),
        "chars": len(text),
        "text": text,
        "keys": picked,
        "matched": matched,
    }
