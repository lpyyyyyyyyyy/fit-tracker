#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每天自动备份 —— 把 App 的打卡数据同步到 GitHub。

为什么用 Python 而不是 PowerShell：
    这个脚本里有大量中文文本和字符串处理。PowerShell 的转义规则和别的语言不一样
    （反引号是转义符、$ 会插值、单双引号规则特殊），把这类代码内联进命令行
    极容易炸，之前就因此弄坏过一次文件。Python 的三引号、unicode 处理、
    异常栈都更直接，适合这种活。

用法：
    python _backup.py            正常备份
    python _backup.py --dry      只看会做什么，不真上传
    python _backup.py --token x  临时指定 token
"""
import argparse
import base64
import hashlib
import json
import os
import re
import socket
import ssl
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

# Windows 控制台默认是 GBK，中文会乱码 —— 强制用 UTF-8 输出
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "backup.log"
TOKEN_FILE = ROOT / "_token.txt"          # 只存本机，已加进 .gitignore
CFG_FILE = ROOT / "_backup.json"
CDP_PORT = 9222

# 跟着代码一起同步的文件（不含 _ 开头的本地工具）
CODE_FILES = [
    "index.html", "sw.js", "manifest.json", "README.md",
    "tools.py", "_backup.py", "run-backup.cmd",   # Python 工具 + 任务包装也进仓库
    ".gitignore", ".nojekyll",
]

DEFAULT_CFG = {"repo": "lpyyyyyyyyyy/fit-tracker", "dataPath": "data.json"}


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ─────────────────────────── 数据来源 ───────────────────────────

def read_from_browser():
    """从 Edge 的 DevTools 端口读 localStorage 里的最新打卡数据。

    用最原始的 WebSocket 帧收发，避免依赖 websocket-client 这个第三方包。
    """
    try:
        r = requests.get(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=4)
        pages = r.json()
    except Exception:
        return None

    page = None
    for p in pages:
        if p.get("type") == "page" and re.search(r"fit-tracker|:8443|:8080", p.get("url", "")):
            page = p
            break
    if not page:
        return None

    try:
        raw = _ws_call(page["webSocketDebuggerUrl"],
                       'JSON.stringify({v: localStorage.getItem("ran_fit_v1")})')
        if not raw:
            return None
        outer = json.loads(raw)            # {"v": "..."} 或 {"v": null}
        if not outer.get("v"):
            return None
        return json.loads(outer["v"])      # 真正的数据
    except Exception as e:
        log(f"（浏览器读取出错，忽略：{type(e).__name__}）")
        return None


def _ws_call(ws_url: str, js_expression: str, timeout: float = 8.0):
    """极简 CDP 调用：连上、发一个 Runtime.evaluate、读回结果。"""
    m = re.match(r"ws://([^:/]+):(\d+)(/.*)", ws_url)
    if not m:
        return None
    host, port, path = m.group(1), int(m.group(2)), m.group(3)

    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    try:
        key = base64.b64encode(os.urandom(16)).decode()
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(handshake.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                return None
            buf += chunk
        if b"101" not in buf.split(b"\r\n")[0]:
            return None

        payload = json.dumps({
            "id": 1, "method": "Runtime.evaluate",
            "params": {"expression": js_expression, "returnByValue": True},
        }).encode()
        sock.sendall(_ws_frame(payload))

        deadline = datetime.now().timestamp() + timeout
        while datetime.now().timestamp() < deadline:
            msg = _ws_read(sock)
            if not msg:
                continue
            try:
                data = json.loads(msg)
            except Exception:
                continue
            if data.get("id") == 1:
                return data.get("result", {}).get("result", {}).get("value")
        return None
    finally:
        try:
            sock.close()
        except OSError:
            pass


def _ws_frame(data: bytes) -> bytes:
    """构造一个客户端 WebSocket 文本帧（带掩码）。"""
    mask = os.urandom(4)
    n = len(data)
    header = bytearray([0x81])
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header += n.to_bytes(2, "big")
    else:
        header.append(0x80 | 127)
        header += n.to_bytes(8, "big")
    header += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return bytes(header) + masked


def _ws_read(sock):
    """读一个 WebSocket 帧，返回文本内容（分片太多就直接返回 None）。"""
    head = _recv_exact(sock, 2)
    if not head:
        return None
    length = head[1] & 0x7F
    if length == 126:
        length = int.from_bytes(_recv_exact(sock, 2) or b"\0\0", "big")
    elif length == 127:
        length = int.from_bytes(_recv_exact(sock, 8) or b"\0" * 8, "big")
    payload = _recv_exact(sock, length)
    if payload is None:
        return None
    try:
        return payload.decode("utf-8", "replace")
    except Exception:
        return None


def _recv_exact(sock, n: int):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def read_from_file():
    """浏览器没开时的兜底：用最近一次导出的 JSON。"""
    cands = sorted(ROOT.glob("减脂打卡备份-*.json"))
    for f in reversed(cands):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


# ─────────────────────────── GitHub ───────────────────────────

def find_token(cli_token=None):
    if cli_token:
        return cli_token.strip()
    env = os.environ.get("GH_TOKEN", "").strip()
    if env:
        return env
    if TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if t:
            return t
    # 退路：问 git 自己的凭据管理器
    gcm_paths = [
        r"C:\Program Files\Git\mingw64\bin\git-credential-manager.exe",
        r"C:\Program Files\Git\mingw64\libexec\git-core\git-credential-manager.exe",
    ]
    for gcm in gcm_paths:
        if not os.path.exists(gcm):
            continue
        try:
            out = subprocess.run([gcm, "get"], input="protocol=https\nhost=github.com\n\n",
                                 capture_output=True, text=True, timeout=20).stdout
            for line in out.splitlines():
                if line.startswith("password="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            continue
    return ""


def git_blob_sha(data: bytes) -> str:
    """算 git 的 blob SHA —— 用来判断远端和本地内容是否真的一样。
    （不要用文件大小判断，大小一样内容不同会漏同步，这个坑踩过。）"""
    h = hashlib.sha1()
    h.update(b"blob " + str(len(data)).encode() + b"\0")
    h.update(data)
    return h.hexdigest()


class GitHub:
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "fit-tracker-backup",
        })

    def _url(self, path: str) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{path}"

    def get_sha(self, path: str):
        r = self.s.get(self._url(path), params={"t": int(datetime.now().timestamp())}, timeout=25)
        if r.status_code == 200:
            return r.json().get("sha")
        return None

    def put(self, path: str, content: bytes, message: str, sha=None):
        body = {"message": message, "content": base64.b64encode(content).decode()}
        if sha:
            body["sha"] = sha
        return self.s.put(self._url(path), json=body, timeout=40)


# ─────────────────────────── 主流程 ───────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="把打卡数据同步到 GitHub")
    ap.add_argument("--dry", action="store_true", help="只显示会做什么，不真上传")
    ap.add_argument("--token", help="临时指定 GitHub token")
    args = ap.parse_args()

    log("===== 自动备份开始 =====")

    token = find_token(args.token)
    if not token:
        log("找不到 GitHub 令牌。请把 token 写进 _token.txt，或设置 GH_TOKEN 环境变量。")
        return 1

    cfg = dict(DEFAULT_CFG)
    if CFG_FILE.exists():
        try:
            cfg.update(json.loads(CFG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    gh = GitHub(token, cfg["repo"])
    log(f"仓库：{cfg['repo']}")

    # 1. 取数据
    data = read_from_browser()
    src = "浏览器 localStorage"
    if data is None:
        data = read_from_file()
        src = "导出文件"
    if data is None:
        log("既读不到浏览器数据，也没有导出文件 —— 这次只同步代码，不动 data.json")
    else:
        records = data.get("records", {}) or {}
        days = len(records)
        weights = sum(1 for k, v in records.items() if (v or {}).get("weight") is not None)
        log(f"数据来源：{src}　打卡 {days} 天，体重记录 {weights} 条")

    # 2. 上传 data.json
    if data is not None and not args.dry:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        sha = gh.get_sha(cfg["dataPath"])
        r = gh.put(cfg["dataPath"], payload,
                   f"数据备份 {datetime.now():%Y-%m-%d}（{len(data.get('records', {}))} 天）", sha)
        if r.status_code in (200, 201):
            log("data.json 已更新")
        else:
            log(f"data.json 失败 HTTP {r.status_code}：{r.text[:160]}")

    # 3. 同步代码（用 blob SHA 比对，别用文件大小）
    changed = 0
    for name in CODE_FILES:
        f = ROOT / name
        if not f.exists():
            continue
        content = f.read_bytes()
        remote = gh.get_sha(name)
        if remote == git_blob_sha(content):
            continue
        if args.dry:
            log(f"（dry）会同步 {name}")
            changed += 1
            continue
        r = gh.put(name, content, f"自动同步 {name}", remote)
        if r.status_code in (200, 201):
            log(f"{name} 已同步")
            changed += 1
        else:
            log(f"{name} 失败 HTTP {r.status_code}")

    log(f"完成（同步 {changed} 个代码文件）")
    log("")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("被中断")
        sys.exit(130)
    except Exception as e:
        log(f"出错：{type(e).__name__}: {e}")
        sys.exit(1)
