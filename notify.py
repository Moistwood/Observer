import smtplib
from email.mime.text import MIMEText
import configparser
from pathlib import Path

CONF = Path(__file__).parent / "mail.conf"


def _mail_conf():
    # 读不到配置就返回 None, 让调用方降级, 不要抛异常
    if not CONF.exists():
        return None
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(CONF, encoding="utf-8")
    if not cp.has_section("mail"):
        return None
    return cp["mail"]


def save_conf(sender, auth_code, receiver, host="smtp.qq.com", port=465):
    # 界面里保存的设置写回 mail.conf
    cp = configparser.ConfigParser(interpolation=None)
    cp["mail"] = {
        "sender": sender,
        "auth_code": auth_code,
        "receiver": receiver,
        "smtp_host": host,
        "smtp_port": str(port),
    }
    with open(CONF, "w", encoding="utf-8") as f:
        cp.write(f)


def _send(conf, message, subject):
    msg = MIMEText(f"\n{message}", "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = conf["sender"]
    msg["To"] = conf["receiver"]
    host = conf.get("smtp_host", "smtp.qq.com")
    port = conf.getint("smtp_port", 465)
    with smtplib.SMTP_SSL(host, port, timeout=10) as server:
        server.login(conf["sender"], conf["auth_code"])
        server.sendmail(conf["sender"], conf["receiver"], msg.as_string())


#  通知模块
def notify(message, subject=None):
    print(f"[通知] {message}")

    conf = _mail_conf()
    if conf is None:
        print("[提示] 还没有配置收件邮箱")
        return False

    try:
        _send(conf, message, subject or "Observer 通知")
        return True
    except Exception as e:
        print(f"[邮件失败] {type(e).__name__}: {e}")
        return False


def try_send(message, subject="Observer 测试"):
    # 给界面用: 不打印, 直接把成功与否返回
    conf = _mail_conf()
    if conf is None:
        return False, "还没有填写邮箱配置"
    try:
        _send(conf, message, subject)
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


if __name__ == "__main__":
    notify("这是一条测试通知")
