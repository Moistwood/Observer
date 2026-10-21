# fetcher.py - 去网上抓内容
import hashlib
import json
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "sitewatch/0.1"}


def _get(u):
    # 只负责发请求, 异常由调用方处理
    return requests.get(u, timeout=10, headers=HEADERS)


def _content_type(r):
    # 取干净的 MIME 类型, 去掉 ; charset=utf-8 这类参数
    return r.headers.get("Content-Type", "").split(";")[0].strip().lower()


def _looks_like_html(raw):
    # 服务器没声明类型时, 用它判断该不该走 HTML 解析
    head = raw[:512].lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html") or head.startswith(b"<head")


def _html_text(r, sel):
    # 传 bytes 给 BS4: 它会自己看 BOM 和 meta charset, 比猜编码准
    soup = BeautifulSoup(r.content, "html.parser")
    if sel:
        # 只取匹配选择器的文本
        parts = [el.get_text(strip=True) for el in soup.select(sel)]
        return "\n".join(parts)
    # 去掉脚本样式后取正文
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _json_text(r, raw=None):
    # JSON 规定必须是 UTF-8, 直接解字节; utf-8-sig 顺带吃掉 BOM
    # sort_keys 固定字段顺序, 否则服务器换个顺序就产生假变化
    text = raw if raw is not None else r.content.decode("utf-8-sig")
    data = json.loads(text)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)


def _xml_text(r):
    root = ET.fromstring(r.content)
    ET.indent(root)  
    return ET.tostring(root, encoding="unicode")


def _binary_text(r):
    # 图片/PDF 这类没法比文本, 比内容哈希: 变了能发现, 但看不出哪里变
    digest = hashlib.sha256(r.content).hexdigest()
    return f"[二进制] {len(r.content)} bytes sha256={digest}"


def _extract(r, sel=None):
    # 按 Content-Type 分流, 不同类型用不同解析方式
    ct = _content_type(r)

    if ct == "application/json" or ct.endswith("+json"):
        try:
            return _json_text(r)
        except (ValueError, UnicodeDecodeError):
            pass  # 声明是 JSON 但内容不是, 退回纯文本处理

    if ct in ("application/xml", "text/xml") or ct.endswith("+xml"):
        try:
            return _xml_text(r)
        except ET.ParseError:
            pass

    if ct in ("text/html", "application/xhtml+xml"):
        return _html_text(r, sel)

    if ct == "" and _looks_like_html(r.content):
        return _html_text(r, sel)

    if ct.startswith("image/") or ct in ("application/pdf", "application/octet-stream"):
        return _binary_text(r)

    text = r.content.decode(r.apparent_encoding or "utf-8", errors="replace")
    stripped = text.strip()
    if stripped[:1] in ("{", "["):
        try:
            return _json_text(r, raw=stripped)
        except ValueError:
            pass
    return text


def fetch(u, sel=None):
    # u=网址 sel=要提取的选择器. 对外行为和之前一致
    return _extract(_get(u), sel)


def probe(u, sel=None):
    # 抓一次并返回元信息, 给 preview 命令用
    r = _get(u)
    text = _extract(r, sel)
    return {
        "status": r.status_code,
        "content_type": _content_type(r),
        "chars": len(text),
        "text": text,
    }
