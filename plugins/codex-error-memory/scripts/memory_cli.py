#!/usr/bin/env python3
"""SQLite-backed technical error memory for Codex plugins."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Iterable


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
DEFAULT_DB = Path(os.environ.get("CODEX_ERROR_MEMORY_DB") or CODEX_HOME / "error-memory" / "error_memory.sqlite")
LEGACY_DB = PLUGIN_ROOT / "data" / "error_memory.sqlite"

TOKEN_RE = re.compile(r"(?i)(bearer\s+)[a-z0-9._\-]{16,}")
SECRET_RE = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|secret[_-]?key|wx[_-]?secret|access[_-]?key)\b\s*[:=]\s*(['\"]?)[^,\s;'\"]+\2")
COMMON_SECRET_RE = re.compile(
    r"(?i)\b("
    r"sk-[A-Za-z0-9_-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|"
    r"ASIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    r")\b"
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)
EMAIL_RE = re.compile(r"[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
OPENID_RE = re.compile(r"\bo[A-Za-z0-9_-]{20,}\b")
LONG_HEX_RE = re.compile(r"\b[a-fA-F0-9]{32,}\b")

WORD_RE = re.compile(r"[A-Za-z0-9_.$:/\\-]+|[\u4e00-\u9fff]{2,}")


BUILTIN_MEMORIES = [
    {
        "title": "PowerShell 中误用 Bash heredoc",
        "category": "shell",
        "severity": "medium",
        "signature": "python - <<'PY' Missing file specification after redirection operator",
        "keywords": "powershell bash heredoc python redirection",
        "root_cause": "PowerShell 不支持 Bash heredoc。`<<` 会被当成重定向符号解析。",
        "fix_steps": "改用 PowerShell here-string：@' ... '@ | python -，或写临时脚本文件执行。",
        "prevention_rule": "在 PowerShell 中不要使用 `python - <<'PY'`、`cat <<EOF` 等 Bash 写法。",
        "verification_steps": "重新运行命令，确认不再出现 Missing file specification 或 '<' operator 错误。",
        "files_often_involved": "PowerShell commands, scripts",
        "commands_often_used": "@'\\nprint(\"ok\")\\n'@ | python -",
    },
    {
        "title": "WXSS 或配置文件被 UTF-8 BOM 破坏",
        "category": "encoding",
        "severity": "high",
        "signature": "WXSS 文件编译错误 unexpected � at pos 1",
        "keywords": "wxss bom utf-8 unexpected pos 1",
        "root_cause": "文件开头含 UTF-8 BOM，微信开发工具或配置读取把隐藏字节当成非法字符。",
        "fix_steps": "用无 BOM UTF-8 重写文件，并检查 `.wxss`、`.wxml`、`.js`、`.json`、`.env`。",
        "prevention_rule": "不要用会写 BOM 的重定向或旧 Set-Content 写小程序源码。",
        "verification_steps": "重新编译小程序，确认不再出现 unexpected 字符错误。",
        "files_often_involved": "*.wxss, *.wxml, *.json, .env",
        "commands_often_used": "python scripts/check_windows_artifacts.py <path> --release --strict",
    },
    {
        "title": "发布包混入 localhost 或 127.0.0.1",
        "category": "release",
        "severity": "high",
        "signature": "ERR_CONNECTION_REFUSED 127.0.0.1 localhost",
        "keywords": "localhost 127.0.0.1 release err_connection_refused api asset",
        "root_cause": "本地开发地址进入了正式发布包或缓存 URL 没有转换为正式域名。",
        "fix_steps": "把 API/资源地址改为正式域名，必要时对旧缓存本地资源 URL 做正式域名映射。",
        "prevention_rule": "前端审核或上传前扫描发布包中的 localhost、127.0.0.1、测试端口。",
        "verification_steps": "发布包扫描无本地地址；开发工具网络请求只访问正式 API。",
        "files_often_involved": "miniprogram/app.js, config files",
        "commands_often_used": "python scripts/check_windows_artifacts.py <release> --release --strict",
    },
    {
        "title": "发布版本混入 pycache、数据库或日志",
        "category": "release",
        "severity": "high",
        "signature": "__pycache__ .pyc .db .sqlite .log in release artifact",
        "keywords": "pycache pyc db sqlite log release artifact github",
        "root_cause": "在发布目录里运行测试或服务，生成的运行文件被一起提交或上传。",
        "fix_steps": "删除 `__pycache__`、`.pyc`、`.db`、`.log`、临时密码文件；测试尽量不要在发布包目录运行。",
        "prevention_rule": "提交前运行发布包扫描，并保持 `.gitignore` 覆盖生成物。",
        "verification_steps": "扫描结果 0 error；git status 不包含生成文件。",
        "files_often_involved": "release folders, server/",
        "commands_often_used": "Get-ChildItem -Recurse -Directory -Filter __pycache__",
    },
    {
        "title": ".env 首个配置键被 BOM 污染",
        "category": "config",
        "severity": "high",
        "signature": "\\ufeff key missing env bom login stuck config missing",
        "keywords": "env bom config missing login stuck",
        "root_cause": "`.env` 文件开头含 BOM，首个 key 实际变成 `\\ufeffKEY`，导致配置读取失败。",
        "fix_steps": "用无 BOM UTF-8 重写 `.env`，诊断时打印配置 key 名但不要打印 secret。",
        "prevention_rule": "配置文件写入必须明确无 BOM，并在启动诊断中检查关键配置是否存在。",
        "verification_steps": "服务重启后关键配置能被读取，登录或 API 恢复正常。",
        "files_often_involved": ".env, config.py",
        "commands_often_used": "python -c \"from pathlib import Path; print(Path('.env').read_bytes()[:3])\"",
    },
    {
        "title": "PowerShell 写入 .env BOM 导致微信正式登录失败",
        "category": "config",
        "severity": "high",
        "signature": "\\ufeffWX_APPID wechat login failed invalid appid production login stuck set-content utf8 bom",
        "keywords": "wechat login wx_appid bom env powershell set-content utf8 production login stuck code2session",
        "root_cause": "Windows PowerShell 写 `.env` 时写入 UTF-8 BOM，首个键变成 `\\ufeffWX_APPID`，后端读不到正式 AppID/Secret 组合，微信登录失败；健康检查和数据库连接可能仍正常。",
        "fix_steps": "用 Python 以 `encoding='utf-8'` 无 BOM 重写 `.env`，保留真实密钥；重启后端；用无效 code 测试 `/api/login` 应能请求到微信并返回微信的 invalid code，而不是本地配置错误。",
        "prevention_rule": "正式 `.env` 不用 PowerShell `Set-Content -Encoding UTF8` 写入；发布后检查前 3 字节不是 `EF BB BF`，并验证 `Config.WX_APPID` 是正式值、`Config.WX_SECRET` 不是占位符，但不要打印 secret。",
        "verification_steps": "健康接口 200；`Path('.env').read_bytes()[:3]` 不是 `[239,187,191]`；`Config.WX_APPID` 匹配正式 AppID；`ENABLE_DEV_LOGIN=False`；小程序可登录。",
        "files_often_involved": ".env, config.py, app.py",
        "commands_often_used": "@'\\nfrom pathlib import Path\\np=Path('.env')\\ntext=p.read_text(encoding='utf-8-sig')\\np.write_text(text, encoding='utf-8')\\nprint(list(p.read_bytes()[:3]))\\n'@ | python -",
    },
    {
        "title": "Windows SSH 或 Paramiko 命令引号失控",
        "category": "deploy",
        "severity": "medium",
        "signature": "paramiko windows ssh quoting gbk utf-8 command failed",
        "keywords": "paramiko ssh windows quote gbk utf-8 powershell cmd",
        "root_cause": "远程 Windows 命令经过 Python、SSH、cmd/PowerShell 多层解析，特殊字符和编码容易变形。",
        "fix_steps": "上传临时 `.py`、`.ps1` 或 `.bat` 文件执行；输出按 UTF-8/GBK 防御性解码。",
        "prevention_rule": "复杂远程操作不要写成长 `exec_command` 字符串。",
        "verification_steps": "远程脚本执行成功，stdout/stderr 可读，临时文件被删除。",
        "files_often_involved": "deployment scripts, ssh helpers",
        "commands_often_used": "sftp put temp script; ssh exec python temp.py",
    },
    {
        "title": "Windows 计划任务 Last Result 异常",
        "category": "deploy",
        "severity": "medium",
        "signature": "Task Scheduler Last Result 255 exit code batch completed",
        "keywords": "scheduled task last result 255 bat exit code log",
        "root_cause": "bat 或 Python 包装脚本没有明确规范退出码，日志完成但任务结果显示异常。",
        "fix_steps": "bat 中记录开始/结束；失败 `exit /b 1`，成功明确 `exit /b 0`。",
        "prevention_rule": "所有计划任务入口都要有明确退出码和可读日志。",
        "verification_steps": "手动运行任务后 Last Result 为 0，日志有完成时间。",
        "files_often_involved": "*.bat, scheduled task scripts",
        "commands_often_used": "exit /b 0",
    },
    {
        "title": "Flask development server 直接暴露公网",
        "category": "deploy",
        "severity": "high",
        "signature": "Flask development server public 443 external scans",
        "keywords": "flask development server 443 production nginx waitress scans",
        "root_cause": "Flask 自带开发服务器直接承担正式公网入口，容易被外部扫描和异常请求拖住。",
        "fix_steps": "用 Nginx/Caddy 作为公网入口，Python 后端运行在本机端口的 Waitress/WSGI 后面。",
        "prevention_rule": "正式环境不要让 Flask dev server 直接监听公网 443。",
        "verification_steps": "公网只暴露 Nginx/Caddy；Python 服务只监听 127.0.0.1。",
        "files_often_involved": "deploy configs, server startup scripts",
        "commands_often_used": "netstat -ano | findstr :443",
    },
    {
        "title": "GitHub tag 与版本文件夹结构不一致",
        "category": "git",
        "severity": "medium",
        "signature": "tag version folder structure inconsistent old labels",
        "keywords": "github tag version folder archive structure old labels",
        "root_cause": "版本 tag 指向的提交和版本目录内容没有同步，或复制归档时保留旧版本标记。",
        "fix_steps": "统一版本目录、README、tag 指向的提交；必要时 force-update 版本 tag。",
        "prevention_rule": "推送前检查 `git log --decorate`、版本 README 和 `versions/<version>`。",
        "verification_steps": "GitHub tag 页面显示新提交，版本文件夹和说明一致。",
        "files_often_involved": "versions/, README.md",
        "commands_often_used": "git tag -f <version>; git push origin <version> --force",
    },
    {
        "title": "GitHub 推送被失效本地代理拦截",
        "category": "git",
        "severity": "medium",
        "signature": "Failed to connect to github.com port 443 via 127.0.0.1 Could not connect to server",
        "keywords": "git github push proxy 127.0.0.1 port 443 could not connect",
        "root_cause": "全局 Git 配置中的 `http.proxy` 或 `https.proxy` 指向本地代理端口，但该代理没有运行，导致 GitHub 推送无法连接。",
        "fix_steps": "先用 `git config --show-origin --get-regexp \"http.*proxy|https.*proxy\"` 定位代理来源；不想改全局配置时，对单次推送使用 `git -c http.proxy= -c https.proxy= push ...` 绕过代理。",
        "prevention_rule": "GitHub 推送失败且错误里出现 `127.0.0.1` 时，优先检查本机代理配置，不要先怀疑远程仓库或凭证。",
        "verification_steps": "`git push origin main` 成功；`git ls-remote --tags origin` 能查到目标标签。",
        "files_often_involved": ".gitconfig, repository git config",
        "commands_often_used": "git config --show-origin --get-regexp \"http.*proxy|https.*proxy\"; git -c http.proxy= -c https.proxy= push origin main",
    },
    {
        "title": "Codex 插件市场仓库不要同时作为根插件",
        "category": "plugin",
        "severity": "medium",
        "signature": "marketplace root does not contain a supported manifest root plugin mixed marketplace",
        "keywords": "codex plugin marketplace manifest root .codex-plugin .agents plugins",
        "root_cause": "同一个仓库根目录同时保留根插件结构和 marketplace 结构时，安装器可能把仓库根当成单插件或市场，导致 manifest 识别失败。",
        "fix_steps": "发布市场仓库时，根目录只保留 `.agents/plugins/marketplace.json` 和 `plugins/[plugin-name]/...`；不要在根目录保留 `.codex-plugin/`。",
        "prevention_rule": "仓库长期发布前明确选择单插件仓库或 marketplace 仓库，不要混用两种根结构。",
        "verification_steps": "重新添加 marketplace，确认不会出现 marketplace root does not contain a supported manifest。",
        "files_often_involved": ".agents/plugins/marketplace.json, plugins/*/.codex-plugin/plugin.json",
        "commands_often_used": "python C:\\Users\\北妖\\.codex\\skills\\.system\\plugin-creator\\scripts\\validate_plugin.py plugins\\plugin-name",
    },
    {
        "title": "Codex marketplace 旧缓存导致新插件不可见",
        "category": "plugin",
        "severity": "medium",
        "signature": "new plugin not visible marketplace cache stale .tmp marketplaces",
        "keywords": "codex marketplace cache stale plugin not visible tmp marketplaces",
        "root_cause": "Codex 可能仍在读取旧的 marketplace staging/cache 文件，新插件已经推到 GitHub 但本地市场缓存没有刷新。",
        "fix_steps": "检查 GitHub 的 `.agents/plugins/marketplace.json` 与本地 `.codex/.tmp/marketplaces/[marketplace]/.agents/plugins/marketplace.json` 是否一致；必要时重新添加 marketplace 或触发刷新。",
        "prevention_rule": "市场更新后不要只看 GitHub，必须验证本地 marketplace 缓存是否拿到最新 manifest。",
        "verification_steps": "本地 marketplace 缓存包含新插件条目，Codex 插件列表可以看到新插件。",
        "files_often_involved": ".agents/plugins/marketplace.json, .codex/.tmp/marketplaces",
        "commands_often_used": "Get-Content -LiteralPath $marketplaceJson",
    },
    {
        "title": "清理 Codex 插件 cache 会导致已安装插件掉线",
        "category": "plugin",
        "severity": "high",
        "signature": "plugin disappeared after deleting .codex plugins cache",
        "keywords": "codex plugin cache deleted disappeared installed plugin unavailable",
        "root_cause": "已安装插件运行时依赖 `.codex/plugins/cache/[marketplace]/[plugin]/[version]`，直接删除整个市场 cache 会让原本可用的插件掉线。",
        "fix_steps": "恢复对应插件 cache，或重新安装 marketplace/plugin；清理时只删明确的 staging/临时目录，不要删除整个已安装 cache。",
        "prevention_rule": "调试插件安装问题时，先列目录和 config，再定点处理，不做整棵 cache 删除。",
        "verification_steps": "插件 cache 目录存在，`config.toml` 中插件启用项存在，新线程能看到插件 skill。",
        "files_often_involved": ".codex/plugins/cache, .codex/config.toml",
        "commands_often_used": "Get-ChildItem -LiteralPath $env:USERPROFILE\\.codex\\plugins\\cache",
    },
    {
        "title": "Codex 插件 cache 存在但 config.toml 未启用",
        "category": "plugin",
        "severity": "medium",
        "signature": "plugin cache exists but config.toml enabled entry missing",
        "keywords": "codex plugin cache config enabled missing installed not active",
        "root_cause": "插件文件已经在 cache 中，但 `.codex/config.toml` 没有 `[plugins.\"name@marketplace\"] enabled = true`，当前会话或新线程不会启用它。",
        "fix_steps": "核对 cache 目录和 config.toml；通过插件 UI 安装/启用，或在确认格式后补齐启用项。",
        "prevention_rule": "判断插件是否可用必须同时检查 cache、marketplace 记录、config 启用项和新线程 skill 列表。",
        "verification_steps": "新线程的可用 skills 列表包含该插件 skill。",
        "files_often_involved": ".codex/config.toml, .codex/plugins/cache",
        "commands_often_used": "Select-String -LiteralPath $env:USERPROFILE\\.codex\\config.toml -Pattern 'plugins'",
    },
    {
        "title": "PowerShell 参数中的尖括号会被当作重定向符号",
        "category": "shell",
        "severity": "medium",
        "signature": "The '<' operator is reserved for future use Missing file specification after redirection operator",
        "keywords": "powershell angle bracket redirection placeholder command parse",
        "root_cause": "把 `[plugin]` 这类示意参数写成尖括号占位并直接执行时，PowerShell 会把 `<` 或 `>` 当作重定向相关语法。",
        "fix_steps": "不要执行带尖括号的占位命令；真实参数用引号、变量、`--%`、临时脚本，或 Python `subprocess.run([...])` 列表参数。",
        "prevention_rule": "给用户示例可以写占位符，但自己执行命令前必须替换成真实值或改成安全传参。",
        "verification_steps": "命令不再出现 '<' operator 或 redirection 错误。",
        "files_often_involved": "PowerShell commands, plugin install commands",
        "commands_often_used": "python -c \"import subprocess; subprocess.run(['tool','arg with <text>'])\"",
    },
    {
        "title": "PowerShell stdin 脚本里的中文路径可能被控制台编码污染",
        "category": "encoding",
        "severity": "medium",
        "signature": "Chinese path becomes mojibake when passed through piped stdin script",
        "keywords": "powershell chinese path stdin encoding mojibake python",
        "root_cause": "PowerShell 管道传递 stdin 脚本文本时，控制台编码可能让硬编码中文路径变成乱码，导致写入或读取错误位置。",
        "fix_steps": "中文路径不要硬编码在 piped stdin 脚本中；通过 `sys.argv`、环境变量、临时 UTF-8 文件或 PowerShell 变量传入。",
        "prevention_rule": "凡是包含中文用户名或中文目录的路径，优先用参数传递，不依赖控制台文本编码。",
        "verification_steps": "脚本打印 `repr(path)` 与真实路径一致，文件操作命中正确位置。",
        "files_often_involved": "PowerShell commands, Python one-off scripts",
        "commands_often_used": "@'\\nimport sys\\nprint(sys.argv[1])\\n'@ | python - $path",
    },
    {
        "title": "Copy-Item 的 LiteralPath 不会展开通配符",
        "category": "shell",
        "severity": "medium",
        "signature": "Copy-Item LiteralPath wildcard star did not update target old files remain",
        "keywords": "powershell copy-item literalpath wildcard star old files cache not updated",
        "root_cause": "`-LiteralPath` 会把 `*` 当作普通字符，不会展开通配符；看似复制了目录，实际目标文件仍然是旧内容。",
        "fix_steps": "需要通配符时使用 `Copy-Item -Path 'source\\*' -Destination target -Recurse -Force`；同步目录且保留目标额外文件时使用 `robocopy source target /E`。",
        "prevention_rule": "PowerShell 中 `-LiteralPath` 只用于精确路径；任何包含 `*` 的复制命令都要改用 `-Path` 或 robocopy。",
        "verification_steps": "复制后用 `Select-String` 或文件哈希确认目标内容已经更新，而不是只看命令退出码。",
        "files_often_involved": "PowerShell commands, plugin cache sync, release sync",
        "commands_often_used": "Copy-Item -Path 'C:\\source\\*' -Destination 'C:\\target' -Recurse -Force",
    },
    {
        "title": "New-Item 在旧 Windows PowerShell 中不支持 LiteralPath",
        "category": "shell",
        "severity": "low",
        "signature": "New-Item A parameter cannot be found that matches parameter name LiteralPath",
        "keywords": "powershell new-item literalpath parameter not found older windows powershell",
        "root_cause": "部分 Windows PowerShell 版本的 `New-Item` 没有 `-LiteralPath` 参数，虽然其他文件 cmdlet 支持。",
        "fix_steps": "创建目录时先把精确路径放进变量，再使用 `New-Item -ItemType Directory -Path $path`；删除、移动、读取仍优先使用支持 `-LiteralPath` 的 cmdlet。",
        "prevention_rule": "需要兼容旧 Windows PowerShell 时，不要假设所有文件 cmdlet 都支持 `-LiteralPath`。",
        "verification_steps": "目录创建成功，不再出现 parameter name 'LiteralPath' 错误。",
        "files_often_involved": "PowerShell commands, temporary test setup scripts",
        "commands_often_used": "$path = Join-Path $env:TEMP 'example'; New-Item -ItemType Directory -Path $path",
    },
    {
        "title": "Start-Process 二次解析丢失 Program Files 路径引号",
        "category": "shell",
        "severity": "medium",
        "signature": "The term 'C:\\Program' is not recognized Start-Process ArgumentList Program Files quotes",
        "keywords": "powershell start-process argumentlist program files quotes encodedcommand gh auth login",
        "root_cause": "`Start-Process powershell.exe -ArgumentList` 会启动新的 PowerShell 解析命令，带空格的路径如果在二次解析中丢失引号，就会被拆成 `C:\\Program`。",
        "fix_steps": "改用 `-EncodedCommand`、临时 `.ps1` 脚本，或严格分离 `-ArgumentList` 参数；需要可见交互窗口时优先使用 `-EncodedCommand`。",
        "prevention_rule": "打开新 PowerShell 执行 `C:\\Program Files\\...` 下的程序时，不要依赖嵌套引号字符串。",
        "verification_steps": "新窗口中命令能识别完整 exe 路径，不再出现 `C:\\Program` not recognized。",
        "files_often_involved": "PowerShell commands, GitHub CLI login, visible terminal launch",
        "commands_often_used": "$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd)); Start-Process powershell.exe -ArgumentList @('-NoExit','-EncodedCommand',$encoded)",
    },
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def sanitize(text: str) -> str:
    text = PRIVATE_KEY_RE.sub("[PRIVATE_KEY]", text)
    text = TOKEN_RE.sub(r"\1[REDACTED]", text)
    text = COMMON_SECRET_RE.sub("[SECRET]", text)
    text = SECRET_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    text = OPENID_RE.sub("[OPENID]", text)
    text = LONG_HEX_RE.sub("[HEX]", text)
    return text[:4000]


def project_hash(path: str) -> str:
    normalized = str(Path(path).resolve()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def project_label(path: str) -> str:
    resolved = Path(path).resolve()
    name = resolved.name or "project"
    return f"{name}#{project_hash(str(resolved))}"


def builtin_digest(item: dict[str, object]) -> str:
    payload = json.dumps(item, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def migrate_legacy_db(db_path: Path) -> None:
    if db_path.resolve() != DEFAULT_DB.resolve():
        return
    if db_path.exists() or not LEGACY_DB.exists() or LEGACY_DB.resolve() == db_path.resolve():
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(LEGACY_DB.read_bytes())


def connect(db_path: Path) -> sqlite3.Connection:
    migrate_legacy_db(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            root_path_hash TEXT NOT NULL UNIQUE,
            tags TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS error_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT NOT NULL,
            signature TEXT NOT NULL,
            keywords TEXT NOT NULL DEFAULT '',
            stack_pattern TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'runtime',
            severity TEXT NOT NULL DEFAULT 'medium',
            confidence INTEGER NOT NULL DEFAULT 3,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            builtin_hash TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        CREATE TABLE IF NOT EXISTS solutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id INTEGER NOT NULL,
            root_cause TEXT NOT NULL DEFAULT '',
            fix_steps TEXT NOT NULL DEFAULT '',
            prevention_rule TEXT NOT NULL DEFAULT '',
            verification_steps TEXT NOT NULL DEFAULT '',
            files_often_involved TEXT NOT NULL DEFAULT '',
            commands_often_used TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(pattern_id) REFERENCES error_patterns(id)
        );
        CREATE TABLE IF NOT EXISTS occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id INTEGER NOT NULL,
            raw_error_excerpt TEXT NOT NULL DEFAULT '',
            project_path TEXT NOT NULL DEFAULT '',
            resolved INTEGER NOT NULL DEFAULT 0,
            resolution_note TEXT NOT NULL DEFAULT '',
            occurred_at TEXT NOT NULL,
            FOREIGN KEY(pattern_id) REFERENCES error_patterns(id)
        );
        """
    )
    ensure_column(conn, "error_patterns", "builtin_hash", "TEXT NOT NULL DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_error_patterns_project_updated ON error_patterns(project_id, updated_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_error_patterns_builtin ON error_patterns(project_id, title, builtin_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_occurrences_pattern ON occurrences(pattern_id, occurred_at)")
    seed_builtin_memories(conn)
    conn.commit()


def seed_builtin_memories(conn: sqlite3.Connection) -> None:
    for item in BUILTIN_MEMORIES:
        digest = builtin_digest(item)
        exists = conn.execute(
            """
            SELECT p.id, p.builtin_hash
            FROM error_patterns p
            WHERE p.project_id IS NULL AND p.title = ?
            """,
            (item["title"],),
        ).fetchone()
        if exists:
            if exists["builtin_hash"] == digest:
                continue
            ts = now()
            conn.execute(
                """
                UPDATE error_patterns
                SET signature = ?, keywords = ?, category = ?, severity = ?, confidence = MAX(confidence, 4),
                    builtin_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (item["signature"], item["keywords"], item["category"], item["severity"], digest, ts, exists["id"]),
            )
            conn.execute(
                """
                UPDATE solutions
                SET root_cause = ?, fix_steps = ?, prevention_rule = ?, verification_steps = ?,
                    files_often_involved = ?, commands_often_used = ?, updated_at = ?
                WHERE pattern_id = ?
                """,
                (
                    item["root_cause"],
                    item["fix_steps"],
                    item["prevention_rule"],
                    item["verification_steps"],
                    item["files_often_involved"],
                    item["commands_often_used"],
                    ts,
                    exists["id"],
                ),
            )
            continue
        ts = now()
        cur = conn.execute(
            """
            INSERT INTO error_patterns
            (project_id, title, signature, keywords, stack_pattern, category, severity, confidence, created_at, updated_at, builtin_hash)
            VALUES (NULL, ?, ?, ?, '', ?, ?, 4, ?, ?, ?)
            """,
            (item["title"], item["signature"], item["keywords"], item["category"], item["severity"], ts, ts, digest),
        )
        conn.execute(
            """
            INSERT INTO solutions
            (pattern_id, root_cause, fix_steps, prevention_rule, verification_steps, files_often_involved, commands_often_used, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cur.lastrowid,
                item["root_cause"],
                item["fix_steps"],
                item["prevention_rule"],
                item["verification_steps"],
                item["files_often_involved"],
                item["commands_often_used"],
                ts,
                ts,
            ),
        )


def get_project(conn: sqlite3.Connection, project: str | None, *, create: bool = True) -> int | None:
    if not project:
        return None
    path = Path(project).resolve()
    root_hash = project_hash(str(path))
    row = conn.execute("SELECT id FROM projects WHERE root_path_hash = ?", (root_hash,)).fetchone()
    if row:
        return int(row["id"])
    if not create:
        return None
    ts = now()
    cur = conn.execute(
        "INSERT INTO projects (name, root_path_hash, tags, created_at, updated_at) VALUES (?, ?, '', ?, ?)",
        (path.name or str(path), root_hash, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def tokens(text: str) -> set[str]:
    return {item.lower() for item in WORD_RE.findall(text) if len(item.strip()) >= 2}


def score(text: str, row: sqlite3.Row) -> float:
    haystack = " ".join([row["title"], row["signature"], row["keywords"], row["stack_pattern"] or ""])
    query_tokens = tokens(text)
    memory_tokens = tokens(haystack)
    if not query_tokens or not memory_tokens:
        return 0.0
    overlap = len(query_tokens & memory_tokens)
    base = overlap / max(6, min(len(query_tokens), len(memory_tokens)))
    exact_bonus = 0.35 if row["signature"].lower() and row["signature"].lower() in text.lower() else 0.0
    confidence_bonus = min(int(row["confidence"]), 5) * 0.04
    return min(1.0, base + exact_bonus + confidence_bonus)


def read_text_arg(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8", errors="replace")
    if getattr(args, "text", None):
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def command_search(args: argparse.Namespace) -> int:
    with connect(Path(args.db)) as conn:
        init_db(conn)
        project_id = get_project(conn, args.project, create=False)
        text = sanitize(read_text_arg(args))
        if not text.strip():
            print("No error text provided.")
            return 1
        query_tokens = sorted(tokens(text), key=len, reverse=True)[:8]
        where = ["(p.project_id IS NULL OR p.project_id = ?)"]
        params: list[object] = [project_id]
        if query_tokens:
            like_parts = []
            for item in query_tokens:
                like_parts.append("(p.title LIKE ? OR p.signature LIKE ? OR p.keywords LIKE ? OR p.stack_pattern LIKE ?)")
                needle = f"%{item}%"
                params.extend([needle, needle, needle, needle])
            where.append("(" + " OR ".join(like_parts) + ")")
        params.append(max(args.limit * 40, 200))
        rows = conn.execute(
            f"""
            SELECT p.*, s.root_cause, s.fix_steps, s.prevention_rule, s.verification_steps,
                   s.files_often_involved, s.commands_often_used
            FROM error_patterns p
            LEFT JOIN solutions s ON s.pattern_id = p.id
            WHERE {' AND '.join(where)}
            ORDER BY p.confidence DESC, p.updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        if not rows and query_tokens:
            rows = conn.execute(
                """
                SELECT p.*, s.root_cause, s.fix_steps, s.prevention_rule, s.verification_steps,
                       s.files_often_involved, s.commands_often_used
                FROM error_patterns p
                LEFT JOIN solutions s ON s.pattern_id = p.id
                WHERE p.project_id IS NULL OR p.project_id = ?
                ORDER BY p.confidence DESC, p.updated_at DESC
                LIMIT ?
                """,
                (project_id, max(args.limit * 40, 200)),
            ).fetchall()
        ranked = sorted(((score(text, row), row) for row in rows), key=lambda item: item[0], reverse=True)
        matches = [(value, row) for value, row in ranked if value >= args.min_score][: args.limit]
        if not matches:
            print(json.dumps({"matches": [], "message": "No strong memory match."}, ensure_ascii=False, indent=2))
            return 0
        payload = []
        for value, row in matches:
            payload.append(
                {
                    "score": round(value, 3),
                    "id": row["id"],
                    "title": row["title"],
                    "category": row["category"],
                    "severity": row["severity"],
                    "confidence": row["confidence"],
                    "root_cause": row["root_cause"] or "",
                    "fix_steps": row["fix_steps"] or "",
                    "prevention_rule": row["prevention_rule"] or "",
                    "verification_steps": row["verification_steps"] or "",
                    "files_often_involved": row["files_often_involved"] or "",
                    "commands_often_used": row["commands_often_used"] or "",
                }
            )
        print(json.dumps({"matches": payload}, ensure_ascii=False, indent=2))
        return 0


def command_add(args: argparse.Namespace) -> int:
    with connect(Path(args.db)) as conn:
        init_db(conn)
        project_id = get_project(conn, args.project, create=True)
        raw_error = sanitize(read_text_arg(args))
        signature = sanitize(args.signature or raw_error[:500] or args.title)
        ts = now()
        cur = conn.execute(
            """
            INSERT INTO error_patterns
            (project_id, title, signature, keywords, stack_pattern, category, severity, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                args.title,
                signature,
                args.keywords or "",
                args.stack_pattern or "",
                args.category,
                args.severity,
                args.confidence,
                ts,
                ts,
            ),
        )
        pattern_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO solutions
            (pattern_id, root_cause, fix_steps, prevention_rule, verification_steps, files_often_involved, commands_often_used, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pattern_id,
                args.root_cause or "",
                args.fix_steps or "",
                args.prevention_rule or "",
                args.verification_steps or "",
                args.files_often_involved or "",
                args.commands_often_used or "",
                ts,
                ts,
            ),
        )
        if raw_error:
            conn.execute(
                "INSERT INTO occurrences (pattern_id, raw_error_excerpt, project_path, resolved, resolution_note, occurred_at) VALUES (?, ?, ?, 1, ?, ?)",
                (pattern_id, raw_error[:1000], project_label(args.project) if args.project else "", "memory added", ts),
            )
        conn.commit()
        print(json.dumps({"added": True, "pattern_id": pattern_id}, ensure_ascii=False, indent=2))
        return 0


def command_record(args: argparse.Namespace) -> int:
    with connect(Path(args.db)) as conn:
        init_db(conn)
        exists = conn.execute("SELECT id FROM error_patterns WHERE id = ?", (args.pattern_id,)).fetchone()
        if not exists:
            print(json.dumps({"recorded": False, "error": f"pattern_id {args.pattern_id} does not exist"}, ensure_ascii=False, indent=2))
            return 2
        raw_error = sanitize(read_text_arg(args))
        ts = now()
        conn.execute(
            "INSERT INTO occurrences (pattern_id, raw_error_excerpt, project_path, resolved, resolution_note, occurred_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                args.pattern_id,
                raw_error[:1000],
                project_label(args.project) if args.project else "",
                1 if args.resolved else 0,
                args.note or "",
                ts,
            ),
        )
        if args.resolved:
            conn.execute(
                "UPDATE error_patterns SET confidence = MIN(confidence + 1, 5), updated_at = ? WHERE id = ?",
                (ts, args.pattern_id),
            )
        conn.commit()
        print(json.dumps({"recorded": True, "pattern_id": args.pattern_id}, ensure_ascii=False, indent=2))
        return 0


def command_list(args: argparse.Namespace) -> int:
    with connect(Path(args.db)) as conn:
        init_db(conn)
        project_id = get_project(conn, args.project, create=False)
        rows = conn.execute(
            """
            SELECT id, title, category, severity, confidence, updated_at
            FROM error_patterns
            WHERE project_id IS NULL OR project_id = ?
            ORDER BY confidence DESC, updated_at DESC
            LIMIT ?
            """,
            (project_id, args.limit),
        ).fetchall()
        print(json.dumps({"memories": [dict(row) for row in rows]}, ensure_ascii=False, indent=2))
        return 0


def markdown_safe(value: object, *, max_len: int = 3000) -> str:
    text = sanitize(str(value or ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?m)^(#{1,6})", r"\\\1", text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    if len(text) > max_len:
        return text[:max_len] + "\n\n...[truncated]"
    return text


def command_export(args: argparse.Namespace) -> int:
    with connect(Path(args.db)) as conn:
        init_db(conn)
        project_id = get_project(conn, args.project, create=False)
        rows = conn.execute(
            """
            SELECT p.*, s.root_cause, s.fix_steps, s.prevention_rule, s.verification_steps,
                   s.files_often_involved, s.commands_often_used
            FROM error_patterns p
            LEFT JOIN solutions s ON s.pattern_id = p.id
            WHERE p.project_id IS NULL OR p.project_id = ?
            ORDER BY p.category, p.title
            LIMIT ?
            """,
            (project_id, args.limit),
        ).fetchall()
    parts = ["# Codex Error Memory", ""]
    for row in rows:
        parts.extend(
            [
                f"## {markdown_safe(row['title'], max_len=120)}",
                "",
                f"- Category: `{markdown_safe(row['category'], max_len=80)}`",
                f"- Severity: `{markdown_safe(row['severity'], max_len=80)}`",
                f"- Confidence: `{int(row['confidence'])}`",
                "",
                "### Signature",
                "",
                markdown_safe(row["signature"]),
                "",
                "### Root Cause",
                "",
                markdown_safe(row["root_cause"]),
                "",
                "### Fix Steps",
                "",
                markdown_safe(row["fix_steps"]),
                "",
                "### Prevention",
                "",
                markdown_safe(row["prevention_rule"]),
                "",
                "### Verification",
                "",
                markdown_safe(row["verification_steps"]),
                "",
            ]
        )
    Path(args.out).write_text("\n".join(parts), encoding="utf-8")
    print(json.dumps({"exported": len(rows), "out": args.out}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex local technical error memory.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite database path.")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search prior error memories.")
    search.add_argument("--project", default="", help="Project root path.")
    search.add_argument("--text", default="", help="Error text.")
    search.add_argument("--file", default="", help="File containing error text.")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--min-score", type=float, default=0.18)
    search.set_defaults(func=command_search)

    add = sub.add_parser("add", help="Add a reusable technical error memory.")
    add.add_argument("--project", default="", help="Project root path.")
    add.add_argument("--title", required=True)
    add.add_argument("--text", default="", help="Error text.")
    add.add_argument("--file", default="", help="File containing error text.")
    add.add_argument("--signature", default="")
    add.add_argument("--keywords", default="")
    add.add_argument("--stack-pattern", default="")
    add.add_argument("--category", default="runtime")
    add.add_argument("--severity", default="medium")
    add.add_argument("--confidence", type=int, default=3)
    add.add_argument("--root-cause", default="")
    add.add_argument("--fix-steps", default="")
    add.add_argument("--prevention-rule", default="")
    add.add_argument("--verification-steps", default="")
    add.add_argument("--files-often-involved", default="")
    add.add_argument("--commands-often-used", default="")
    add.set_defaults(func=command_add)

    record = sub.add_parser("record", help="Record a repeated occurrence.")
    record.add_argument("--pattern-id", type=int, required=True)
    record.add_argument("--project", default="")
    record.add_argument("--text", default="")
    record.add_argument("--file", default="")
    record.add_argument("--resolved", action="store_true")
    record.add_argument("--note", default="")
    record.set_defaults(func=command_record)

    list_cmd = sub.add_parser("list", help="List known memories.")
    list_cmd.add_argument("--project", default="")
    list_cmd.add_argument("--limit", type=int, default=20)
    list_cmd.set_defaults(func=command_list)

    export_cmd = sub.add_parser("export", help="Export known memories to sanitized Markdown.")
    export_cmd.add_argument("--project", default="")
    export_cmd.add_argument("--out", required=True)
    export_cmd.add_argument("--limit", type=int, default=1000)
    export_cmd.set_defaults(func=command_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
