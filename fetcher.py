# fetcher.py - 去网上抓内容
import hashlib
import json
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}


def _get(u):
    # 只负责发请求, 异常由调用方处理
    return requests.get(u, timeout=10, headers=HEADERS)


def _content_type(r):
    # 取干净的 MIME 类型, 去掉 ; charset=utf-8 这类参数
    return r.headers.get("Content-Type", "").split(";")[0].strip().lower()


def _parse_keys(keys):
    # "title,bvid" -> {"title","bvid"}; 空值返回 None, 表示不做过滤
    if not keys:
        return None
    if isinstance(keys, (list, tuple, set)):
        items = keys
    else:
        items = keys.split(",")
    picked = {k.strip() for k in items if k and k.strip()}
    return picked or None


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


def _filter_json(obj, keys):
    # 深度优先走完整棵树, 只收指定键名. 返回 (文本, 匹配个数)
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

    walk(obj)

    lines = []
    for k, v in hits:
        if isinstance(v, (dict, list)):
            # 值是嵌套结构时压成一行, 免得一层层展开太多
            val = json.dumps(v, ensure_ascii=False, sort_keys=True)
        elif v is None:
            val = "null"
        elif isinstance(v, bool):
            val = "true" if v else "false"
        else:
            val = str(v)
        lines.append(f"{k}: {val}")
    return "\n".join(lines), len(hits)


def _json_text(r, raw=None, keys=None):
    # 返回 (文本, 匹配个数). 不过滤时个数为 None
    # JSON 规定必须是 UTF-8, 直接解字节; utf-8-sig 顺带吃掉 BOM
    # sort_keys 固定字段顺序, 否则服务器换个顺序就产生假变化
    text = raw if raw is not None else r.content.decode("utf-8-sig")
    data = json.loads(text)
    if keys:
        return _filter_json(data, keys)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), None


def _xml_text(r):
    root = ET.fromstring(r.content)
    ET.indent(root)  # 需要 Python 3.9+
    return ET.tostring(root, encoding="unicode")


def _binary_text(r):
    # 图片/PDF 这类没法比文本, 比内容哈希: 变了能发现, 但看不出哪里变
    digest = hashlib.sha256(r.content).hexdigest()
    return f"[二进制] {len(r.content)} bytes sha256={digest}"


def _extract(r, sel=None, keys=None):
    # 按 Content-Type 分流. 返回 (文本, 匹配个数), 个数只在按键名过滤时才有值
    ct = _content_type(r)

    if ct == "application/json" or ct.endswith("+json"):
        try:
            return _json_text(r, keys=keys)
        except (ValueError, UnicodeDecodeError):
            pass  # 声明是 JSON 但内容不是, 退回纯文本处理

    if ct in ("application/xml", "text/xml") or ct.endswith("+xml"):
        try:
            return _xml_text(r), None
        except ET.ParseError:
            pass

    if ct in ("text/html", "application/xhtml+xml"):
        return _html_text(r, sel), None

    if ct == "" and _looks_like_html(r.content):
        return _html_text(r, sel), None

    if ct.startswith("image/") or ct in ("application/pdf", "application/octet-stream"):
        return _binary_text(r), None

    # 其余 text/* 和未知类型: 按纯文本处理
    text = r.content.decode(r.apparent_encoding or "utf-8", errors="replace")
    # 有些接口声明 text/plain 但内容是 JSON, 试一次再决定
    stripped = text.strip()
    if stripped[:1] in ("{", "["):
        try:
            return _json_text(r, raw=stripped, keys=keys)
        except ValueError:
            pass
    return text, None


def fetch(u, sel=None, keys=None):
    # u=网址 sel=CSS选择器 keys=JSON键名(逗号分隔或集合). 对外行为和之前兼容
    text, _ = _extract(_get(u), sel, _parse_keys(keys))
    return text


def probe(u, sel=None, keys=None):
    # 抓一次并返回元信息, 给 preview 命令用
    r = _get(u)
    picked = _parse_keys(keys)
    text, matched = _extract(r, sel, picked)
    return {
        "status": r.status_code,
        "content_type": _content_type(r),
        "chars": len(text),
        "text": text,
        "keys": picked,
        "matched": matched,
    }
