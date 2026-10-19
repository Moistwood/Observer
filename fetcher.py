# fetcher.py - 去网上抓内容
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "sitewatch/0.1"}


def fetch(u, sel=None):
    # u=网址 sel=要提取的选择器
    r = requests.get(u, timeout=10, headers=HEADERS)
    r.encoding = r.apparent_encoding  # 用网页自己的编码
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    if sel:
        # 只取匹配选择器的文本
        parts = [el.get_text(strip=True) for el in soup.select(sel)]
        return "\n".join(parts)
    # 去掉脚本样式后取正文
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)
