import smtplib
from email.mime.text import MIMEText
import configparser
from pathlib import Path

CONF = Path(__file__).parent / "mail.conf"


def _mail_conf():
    # 读不到配置就返回 None, 让调用方降级, 不要抛异常
    if not CONF.exists():
        return None
    cp = configparser.ConfigParser()
    cp.read(CONF, encoding="utf-8")
    if not cp.has_section("mail"):
        return None
    return cp["mail"]


#  通知模块
def notify(message, subject=None):
    print(f"[通知] {message}")

    conf = _mail_conf()
    if conf is None:
        print("[提示] 缺 mail.conf, 只打屏不发邮件")
        return

    sender = conf["sender"]
    auth_code = conf["auth_code"]
    receiver = conf["receiver"]
    host = conf.get("smtp_host", "smtp.qq.com")     # 有默认值
    port = conf.getint("smtp_port", 465)            # 数字要用 getint

    try:
        msg = MIMEText(f"\n{message}", "plain", "utf-8")
        msg["Subject"] = subject or "sitewatch 通知"
        msg["From"] = sender
        msg["To"] = receiver
        with smtplib.SMTP_SSL(host, port, timeout=10) as server:
            server.login(sender, auth_code)
            server.sendmail(sender, receiver, msg.as_string())
    except Exception as e:
        print(f"[邮件失败] {type(e).__name__}: {e}")


    

    print(f"[通知] {message}")


if __name__ == "__main__":
    notify("这是一条测试通知")
