# 独立窗口启动器: 后台跑本地服务, 前台开一个窗口
import socket
import threading
import time
import traceback
import webbrowser

import uvicorn
import webview

from web import app


def _pick_port():
    # 让系统分配一个空闲端口, 避免和别的程序撞车
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(port):
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    # 子线程里不能注册信号处理, 否则会抛 ValueError
    server.install_signal_handlers = lambda: None
    server.run()


def _wait_until_ready(port, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    print("正在启动本地服务...")
    port = _pick_port()
    threading.Thread(target=_serve, args=(port,), daemon=True).start()

    if not _wait_until_ready(port):
        raise SystemExit("本地服务没能启动, 检查依赖是否装全")

    url = f"http://127.0.0.1:{port}"
    print(f"服务已就绪: {url}")
    print("正在打开窗口...")

    try:
        webview.create_window(
            "Observer",
            url,
            width=1080,
            height=800,
            min_size=(760, 560),
        )
        webview.start()
        print("窗口已关闭, 程序退出。")
    except Exception:
        print("\n窗口打不开, 详细错误如下:")
        traceback.print_exc()
        print(f"\n改用浏览器打开: {url}")
        webbrowser.open(url)
        input("\n按回车键退出...")


if __name__ == "__main__":
    main()
