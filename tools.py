#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一套工具：备份 / 测试 / 版本号 / 定时任务 / 本地服务 / 截图。

为什么用 Python 而不是 PowerShell：
    这个项目里全是中文内容和大量字符串处理。PowerShell 的转义规则特殊
    （反引号是转义符、$ 会插值、单双引号规则和别的语言不同），把这类代码
    内联进命令行极容易炸 —— 之前就因此弄坏过一次文件的语法。
    Python 的三引号、UTF-8 处理、异常栈都更直接。

用法：
    python tools.py backup          同步数据到 GitHub
    python tools.py backup --dry    只看会做什么
    python tools.py test            跑逻辑 + 静态测试 + 设计规范审计
    python tools.py bump            版本号 +1（同时改 sw.js 的缓存版本）
    python tools.py serve           起本地服务器（HTTP 8080 + HTTPS 8443）
    python tools.py task status     看每天 2:00 的定时任务
    python tools.py task install    注册定时任务（需管理员）
    python tools.py task remove     卸载定时任务（需管理员）
    python tools.py check           语法检查 + 所有测试
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
SW = ROOT / "sw.js"
PY = sys.executable
TASK_NAME = "FitTrackerDailyBackup"


def run(cmd, capture=True, **kw):
    """统一跑子进程。

    ⚠️ capture_output 必须显式打开 —— subprocess.run 默认 stdio 是继承的，
       那样 r.stdout 会是 None，拿不到测试结果行。这个坑刚踩过。
    """
    return subprocess.run(cmd, cwd=str(ROOT), text=True,
                          encoding="utf-8", errors="replace",
                          capture_output=capture, **kw)


def hr(title):
    print(f"\n{'=' * 56}\n{title}\n{'=' * 56}")


# ───────────────────────── 版本号 ─────────────────────────

def bump():
    """版本号 +1：App 版本（设置页显示）+ SW 缓存版本（强制刷新用）。"""
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const APP_VER = '(\d{4}\.\d{2}\.\d{2})-(\d+)';", html)
    if not m:
        print("找不到 APP_VER")
        return 1
    date, n = m.group(1), int(m.group(2))
    new_ver = f"{date}-{n + 1}"
    html = html.replace(m.group(0), f"const APP_VER = '{new_ver}';")
    INDEX.write_text(html, encoding="utf-8")
    print(f"App 版本 → {new_ver}")

    sw = SW.read_text(encoding="utf-8")
    m2 = re.search(r"VER = 'v(\d+)'", sw)
    if m2:
        new_cache = f"v{int(m2.group(1)) + 1}"
        sw = sw.replace(m2.group(0), f"VER = '{new_cache}'")
        SW.write_text(sw, encoding="utf-8")
        print(f"缓存版本 → {new_cache}")
    return 0


# ───────────────────────── 语法 & 测试 ─────────────────────────

def check_syntax():
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    if not m:
        print("  找不到 <script>")
        return False
    tmp = ROOT / "_syntax_check.js"
    tmp.write_text(m.group(1), encoding="utf-8")
    try:
        r = run(["node", "--check", str(tmp)])
        ok = r.returncode == 0
        print(f"  {'OK  ' if ok else 'FAIL'} index.html 内联脚本")
        if not ok:
            print((r.stderr or "")[:600])
        return ok
    finally:
        tmp.unlink(missing_ok=True)


def run_tests():
    """跑测试并只显示结论 + 失败项。没脚本时从内联脚本现生成一个。"""
    hr("测试")
    all_ok = True
    for name, script in [("逻辑测试", "_test.js"), ("静态测试", "_static_test.js")]:
        path = ROOT / script
        if not path.exists():
            print(f"  {name}：找不到 {script}，跳过")
            continue
        r = run(["node", str(path)])
        # node 可能把结果写到 stdout 或 stderr，两边都看
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        hits = [l.strip() for l in out.splitlines() if "结果：" in l]
        if hits:
            print(f"  {name}：{hits[-1]}")
        else:
            print(f"  {name}：没拿到结果行（退出码 {r.returncode}）")
            for l in out.splitlines()[:6]:
                if l.strip():
                    print("      " + l.strip()[:100])
        if r.returncode != 0:
            all_ok = False
            fails = [l.strip() for l in out.splitlines() if l.strip().startswith("❌")]
            for l in fails[:12]:
                print("    " + l)
            if len(fails) > 12:
                print(f"    ...还有 {len(fails) - 12} 条")
    return all_ok


def cmd_check():
    hr("语法检查")
    ok = check_syntax()
    run_tests()
    return 0 if ok else 1


# ───────────────────────── 本地服务 ─────────────────────────

def serve(_args):
    """起本地服务器：HTTP 8080 + HTTPS 8443（HTTPS 才能用通知和 PWA）。"""
    import http.server
    import socketserver
    import ssl
    import threading

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT), **kw)

        def end_headers(self):
            self.send_header("Service-Worker-Allowed", "/")
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, fmt, *a):
            pass

    def lan_ips():
        import socket as sk
        ips = []
        try:
            for info in sk.getaddrinfo(sk.gethostname(), None, sk.AF_INET):
                ip = info[4][0]
                if ip.startswith(("127.", "169.254.", "28.", "172.24.")):
                    continue
                if ip not in ips:
                    ips.append(ip)
        except Exception:
            pass
        return ips

    def start(port, use_ssl):
        httpd = socketserver.ThreadingTCPServer(("0.0.0.0", port), Handler)
        httpd.daemon_threads = True
        if use_ssl:
            cert, key = ROOT / "_cert.pem", ROOT / "_key.pem"
            if not (cert.exists() and key.exists()):
                print(f"  跳过 HTTPS {port}（缺 _cert.pem / _key.pem）")
                return None
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(str(cert), str(key))
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd

    s1 = start(8080, False)
    s2 = start(8443, True)

    print("本地服务器已启动：")
    print("  电脑   http://localhost:8080/")
    for ip in lan_ips():
        print(f"  手机   http://{ip}:8080/")
        if s2:
            print(f"  手机   https://{ip}:8443/   ← 通知/PWA 要用这个")
    print("\n按 Ctrl+C 停止。")
    try:
        while True:
            import time
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


# ───────────────────────── 定时任务 ─────────────────────────

def task(action: str):
    """用 Windows 的 schtasks 管理每天 02:00 的任务。

    ⚠️ 传参一律用列表形式（shell=False），不拼命令字符串 —— 这就是
       为什么这个脚本里不需要任何转义。"""
    xml_cmd = f'"{PY}" "{ROOT / "_backup.py"}"'

    if action == "status":
        r = run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"])
        if r.returncode != 0:
            print(f"尚未注册。注册：python tools.py task install")
            return 0
        keep = ("TaskName", "Status", "Next Run Time", "Last Run Time", "Last Result", "任务名", "状态", "下次运行时间", "上次运行时间", "上次结果")
        for line in (r.stdout or "").splitlines():
            if any(k in line for k in keep):
                print("  " + line.strip())
        return 0

    if action == "install":
        r = run(["schtasks", "/Create", "/TN", TASK_NAME, "/TR", xml_cmd,
                 "/SC", "DAILY", "/ST", "02:00", "/F", "/RL", "LIMITED"])
        if r.returncode == 0:
            print(f"已注册：{TASK_NAME}（每天 02:00）")
            print(f"  执行：{xml_cmd}")
        else:
            print("注册失败（需要管理员权限）：")
            print((r.stderr or r.stdout or "")[:400])
        return r.returncode

    if action == "remove":
        r = run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
        print("已卸载。" if r.returncode == 0 else "卸载失败（可能没有这个任务，或需要管理员）。")
        return r.returncode

    if action == "run":
        return run([PY, str(ROOT / "_backup.py")]).returncode

    print(f"未知动作：{action}")
    return 1


# ───────────────────────── 入口 ─────────────────────────

def main():
    ap = argparse.ArgumentParser(description="fit-tracker 工具集")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("backup", help="把数据同步到 GitHub")
    p.add_argument("--dry", action="store_true")

    sub.add_parser("test", help="跑全部测试")
    sub.add_parser("bump", help="版本号 +1")
    sub.add_parser("check", help="语法检查 + 测试")
    sub.add_parser("serve", help="起本地服务器")

    t = sub.add_parser("task", help="定时任务")
    t.add_argument("action", nargs="?", default="status",
                   choices=["status", "install", "remove", "run"])

    args = ap.parse_args()

    if args.cmd == "backup":
        cmd = [PY, str(ROOT / "_backup.py")]
        if args.dry:
            cmd.append("--dry")
        return run(cmd, capture=False).returncode
    if args.cmd == "test":
        return 0 if run_tests() else 1
    if args.cmd == "bump":
        return bump()
    if args.cmd == "check":
        return cmd_check()
    if args.cmd == "serve":
        return serve(args)
    if args.cmd == "task":
        return task(args.action)

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
