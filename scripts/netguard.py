#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
netguard.py — 出站请求的信任边界（共享模块）

语言 / Language：注释与报错默认中文；**语言可选**，按用户语言回应即可
（comments default to Chinese; the skill answers in the user's language）。

为什么需要它：剪藏工具会抓取**用户给的任意 URL**，而网页是**不可信输入**。
如果直接 requests.get(url)，恶意/被篡改的目标可以把请求导向内网或云元数据
服务（SSRF），或在重定向里把请求转到内网。本模块把"能连哪里"收窄成一组
可审计的规则，并作为唯一出站口：

  1. 只允许 http / https，禁止 file:// / ftp:// 等其他协议与内嵌凭据（user:pass@）。
  2. 只允许标准端口 80 / 443。
  3. **解析级校验**：域名解析出的**每一个**地址都必须是公网地址；命中回环、
     私有网段、链路本地（含云元数据服务地址）、CGNAT、保留段、IPv6 ULA/回环/
     组播即拒绝，不做任何请求。
  4. **连接级固定（connect-time pinning，核心）**：校验通过后，TCP 连接**直接连到
     被校验的那个 IP**，连接过程中不再做任何域名解析 —— 「被校验的地址」与
     「实际连接的地址」是同一个，因此**不存在可被二次解析改写的窗口**（DNS
     重绑定对出站请求无效）。Host 头与 TLS SNI 仍使用原域名，证书仍按域名校验，
     安全性不打折。
  5. **逐跳校验**：不自动跟随重定向（allow_redirects=False），每一跳重新跑 3+4
     两步，最多 3 跳 —— 公网站点也无法把请求转进内网。
  6. **体积与时长上限**：只读前 N 字节（默认 5 MB），超时默认 30s。
  7. 只发 GET；不发送 cookie、不发送 Authorization、UA 固定；**不读取环境代理**
     （trust_env=False，避免代理改写出站目的地而绕过本模块的校验）。
  8. 明确不做：不写远端、不登录、不发 POST、不探端口、不访问非公网目标。
"""

from __future__ import annotations

import ipaddress
import socket
import threading
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection as _Urllib3HTTPConnection
from urllib3.connection import HTTPSConnection as _Urllib3HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager
from urllib3.util import Timeout as _Timeout

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

ALLOWED_PORTS = (80, 443)
MAX_REDIRECTS = 3
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_TIMEOUT = 30


class BlockedTargetError(RuntimeError):
    """目标不允许访问（内网/保留地址、协议或端口不合规）。"""


def is_blocked_ip(ip: str) -> bool:
    """该 IP 是否属于内网 / 保留 / 云元数据段 —— 命中即拒绝。"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # 解析不出来的一律按"拒绝"处理
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return True
    if isinstance(addr, ipaddress.IPv4Address):
        # 显式补充：云元数据链路本地段、CGNAT、基准测试段
        for net in ("169.254.0.0/16", "100.64.0.0/10", "198.18.0.0/15", "192.0.0.0/24"):
            if addr in ipaddress.ip_network(net):
                return True
    else:
        # IPv6：ULA 与 IPv4 映射
        if addr in ipaddress.ip_network("fc00::/7"):
            return True
        mapped = getattr(addr, "ipv4_mapped", None)
        if mapped is not None and is_blocked_ip(str(mapped)):
            return True
    return False


def _pick_connect_ip(addresses: list[str]) -> str:
    """从"已全部校验为公网"的地址里挑一个用于连接（优先 IPv4，兼容性更好）。"""
    v4 = [a for a in addresses if ":" not in a]
    return (v4 or addresses)[0]


def _getaddrinfo_within(host: str, port: int, deadline: float | None) -> list:
    """在整体时限内完成 DNS 解析。

    `socket.getaddrinfo` 本身**没有超时参数**，系统解析器在慢 DNS / 黑洞
    场景下可以挂住几十秒（远超整体时限）。这里放到守护线程里跑，并用剩余
    预算 join：到点仍未返回就中止请求（线程是 daemon，不阻塞退出）。
    """
    if deadline is None:
        return socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)

    box: dict = {}
    cancel = threading.Event()

    def _worker():
        try:
            box["infos"] = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except BaseException as exc:  # noqa: BLE001 - 转发给调用方处理
            box["err"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    budget = max(0.1, deadline - time.monotonic())
    t.join(budget)
    if t.is_alive():
        # 显式取消信号（系统解析器无法强杀，但请求不再等它——不会继续发起连接）
        cancel.set()
        raise BlockedTargetError(f"DNS 解析超出整体时限（剩余预算 {budget:.1f}s），已取消并中止：{host}")
    if "err" in box:
        raise box["err"]
    return box.get("infos", [])


def _request_headers_within(session, target: str, headers: dict, deadline: float):
    """在整体时限内拿到**响应头**（请求阶段同样可能挂住）。

    `session.get(stream=True)` 会阻塞到响应头到齐才返回；对端若慢速滴流响应头
    （每次只吐几个字节），socket 读超时管不住——它只约束「单次无数据间隔」。
    这里把请求放进守护线程，用剩余预算 join；到点仍未拿到响应头就**显式取消**：
    置位取消信号 + 关闭 session（连同 socket），让这次请求真正停下来，
    而不是只放弃等待、留下仍在跑的工作。
    """
    box: dict = {}
    cancel = threading.Event()

    def _worker():
        try:
            box["resp"] = session.get(
                target,
                headers=headers,
                timeout=max(1, deadline - time.monotonic()),
                allow_redirects=False,
                stream=True,
            )
        except BaseException as exc:  # noqa: BLE001 - 转发给调用方处理
            box["err"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    budget = max(0.1, deadline - time.monotonic())
    t.join(budget)
    if t.is_alive():
        # 显式取消：先置取消信号，再关闭连接（解除阻塞中的读），最后中止请求
        cancel.set()
        try:
            session.close()
        except Exception:  # noqa: BLE001 - 关闭失败不影响中止结论
            pass
        raise BlockedTargetError(
            f"等待响应头超出整体时限（剩余预算 {budget:.1f}s），已取消并断开连接：{target}"
        )
    if "err" in box:
        raise box["err"]
    return box.get("resp")


def resolve_public_target(url: str, deadline: float | None = None) -> tuple[str, str]:
    """校验目标：协议 / 凭据 / 端口 / 解析结果必须全为公网地址。

    返回 `(规范化 URL, 用于连接的 IP)` —— 第二个值是**唯一**允许连接的地址，
    调用方必须把它交给连接级固定使用，不得再次解析域名。

    `deadline`（`time.monotonic()` 基准）给定时，DNS 解析也受该时限约束。
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise BlockedTargetError(f"非法 URL：{url}") from exc
    if parsed.scheme not in ("http", "https"):
        raise BlockedTargetError(f"仅允许 http/https，已拒绝：{parsed.scheme or '(空)'}")
    if parsed.username or parsed.password:
        raise BlockedTargetError("URL 不得内嵌凭据（user:pass@）")
    host = parsed.hostname
    if not host:
        raise BlockedTargetError(f"URL 缺少主机名：{url}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise BlockedTargetError(f"仅允许 80/443 端口，已拒绝：{port}")

    # 字面量 IP：直接判
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if is_blocked_ip(host):
            raise BlockedTargetError(f"目标为内网/保留地址，已拒绝：{host}")
        return url, host

    # 域名：解析出的每一个地址都必须公网；只取一个用于固定连接
    try:
        infos = _getaddrinfo_within(host, port, deadline)
    except socket.gaierror as exc:
        raise BlockedTargetError(f"DNS 解析失败：{host}") from exc
    addresses = sorted({info[4][0] for info in infos})
    blocked = [a for a in addresses if is_blocked_ip(a)]
    if blocked:
        raise BlockedTargetError(
            f"目标解析到内网/保留地址，已拒绝：{host} -> {', '.join(blocked)}"
        )
    if not addresses:
        raise BlockedTargetError(f"DNS 未返回任何地址：{host}")
    return url, _pick_connect_ip(addresses)


def assert_public_url(url: str) -> str:
    """兼容入口：只做校验，返回规范化 URL（不暴露连接用 IP）。"""
    return resolve_public_target(url)[0]


# --- 连接级固定：把 TCP 连接钉死在已校验 IP 上 -------------------------------

class _PinnedHTTPConnection(_Urllib3HTTPConnection):
    """HTTP 连接：TCP 连到 pinned_ip，Host 头仍用域名。"""

    def __init__(self, *args, pinned_ip: str | None = None, **kwargs):
        self._pinned_ip = pinned_ip
        super().__init__(*args, **kwargs)

    def _new_conn(self):
        if not self._pinned_ip:
            return super()._new_conn()
        return socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address
        )


class _PinnedHTTPSConnection(_Urllib3HTTPSConnection):
    """HTTPS 连接：TCP 连到 pinned_ip，SNI 与证书校验仍按域名（self.host）。"""

    def __init__(self, *args, pinned_ip: str | None = None, **kwargs):
        self._pinned_ip = pinned_ip
        super().__init__(*args, **kwargs)

    def _new_conn(self):
        if not self._pinned_ip:
            return super()._new_conn()
        return socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address
        )


class _PinnedPoolManager(PoolManager):
    """把 pinned_ip 注入每个连接池，保证该池内的连接全部固定到它。"""

    def __init__(self, pinned_ip: str, **kwargs):
        self._pinned_ip = pinned_ip
        super().__init__(**kwargs)

    def _new_pool(self, scheme, host, port, request_context=None):
        pool = super()._new_pool(scheme, host, port, request_context=request_context)
        if isinstance(pool, HTTPSConnectionPool):
            pool.ConnectionCls = _PinnedHTTPSConnection
        elif isinstance(pool, HTTPConnectionPool):
            pool.ConnectionCls = _PinnedHTTPConnection
        if isinstance(pool, (HTTPConnectionPool, HTTPSConnectionPool)):
            conn_kw = dict(getattr(pool, "conn_kw", None) or {})
            conn_kw["pinned_ip"] = self._pinned_ip
            pool.conn_kw = conn_kw
        return pool


class _PinnedIPAdapter(HTTPAdapter):
    """requests adapter：本 adapter 发出的所有连接固定到 pinned_ip。

    `total_timeout` 给出时，连接池使用 urllib3 的 `Timeout(total=...)`——
    **传输层总期限**：urllib3 用「total 减去已耗时」推导每次读写的 socket 超时，
    于是连阻塞中的 recv 也会在 deadline 到点被切断，请求不可能活过声明时限。
    """

    def __init__(self, pinned_ip: str, *, total_timeout: float | None = None, **kwargs):
        self._pinned_ip = pinned_ip
        self._total_timeout = total_timeout
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        if self._total_timeout is not None:
            budget = max(1.0, float(self._total_timeout))
            pool_kwargs["timeout"] = _Timeout(total=budget, connect=budget, read=budget)
        self.poolmanager = _PinnedPoolManager(
            self._pinned_ip,
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs,
        )


def _pinned_session(pinned_ip: str, total_timeout: float | None = None) -> requests.Session:
    """构造一个"出站只走 pinned_ip"的会话（不读环境代理）。

    `total_timeout` 给出时，会话底层的 urllib3 连接池使用
    `Timeout(total=...)`——**传输层的总期限**：urllib3 会用「total 减去已耗时」
    推导每一次读/写的 socket 超时，于是连阻塞中的 recv 也会在 deadline 到点被
    切断，请求不可能活过它的声明时限（否则放弃的读线程会一直占着 socket）。
    """
    session = requests.Session()
    session.trust_env = False  # 不读 HTTP(S)_PROXY，避免代理改写目的地
    if total_timeout is not None:
        adapter = _PinnedIPAdapter(pinned_ip, total_timeout=total_timeout)
    else:
        adapter = _PinnedIPAdapter(pinned_ip)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def safe_get(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    headers: dict | None = None,
) -> requests.Response:
    """带信任边界与体积上限的 GET。

    - 每个请求先校验（协议/端口/解析结果全公网），再把连接**固定**到校验过的
      那个 IP：连接期间不发生任何域名解析，DNS 重绑定无法把请求改道
    - 不自动跟随重定向：逐跳校验 + 逐跳重新固定（最多 MAX_REDIRECTS 跳）
    - 只读前 max_bytes 字节（超限即中止，防止恶意大响应）
    - **整体墙钟时限**：timeout 是整个请求（含所有重定向跳）的总预算，不是单次
      socket 读超时——慢速滴流（持续小包）无法靠 socket 超时收敛，故在读循环里
      按剩余预算判定，超时即中止
    - 只发 GET，不带 cookie / Authorization，不读环境代理
    """
    deadline = time.monotonic() + timeout  # 整体时限：覆盖连接 + 全部重定向 + 读体
    current = url
    for hop in range(MAX_REDIRECTS + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BlockedTargetError(f"整体请求超时（{timeout}s 总预算已用尽）：{current}")
        target, pinned_ip = resolve_public_target(current, deadline=deadline)
        # DNS 解析也算在整体预算内：解析慢也要能被时限截断
        if time.monotonic() > deadline:
            raise BlockedTargetError(
                f"整体请求超时（{timeout}s 总预算已用尽，DNS 解析阶段）：{target}"
            )
        req_headers = {"User-Agent": UA, "Accept": "*/*"}
        if headers:
            # 只允许覆盖非敏感头，避免把凭据塞进请求
            for k, v in headers.items():
                if k.lower() in ("cookie", "authorization", "proxy-authorization"):
                    continue
                req_headers[k] = v

        # 传输层总期限：socket 层面也受剩余预算约束（连阻塞中的 recv 也会被切断）
        session = _pinned_session(pinned_ip, total_timeout=max(1.0, deadline - time.monotonic()))
        try:
            # 响应头阶段同样受整体时限约束（见 _request_headers_within）
            resp = _request_headers_within(session, target, req_headers, deadline)

            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                resp.close()
                if not location:
                    raise BlockedTargetError(f"重定向缺少 Location：{target}")
                if hop == MAX_REDIRECTS:
                    raise BlockedTargetError(f"重定向超过 {MAX_REDIRECTS} 跳，已停止")
                current = requests.compat.urljoin(target, location)
                continue

            # 读体放到独立线程里跑，主线程按整体 deadline 等它 —— 这才是真硬上限。
            # 为什么必须这样：
            #   * iter_content 在攒够 chunk_size 之前是**阻塞**的，循环里的时限检查
            #     在「慢速滴流」（每秒几字节）下根本轮不到执行；
            #   * socket 超时只约束「单次无数据间隔」，约束不了请求总时长；
            #   * 关连接也未必能唤醒阻塞中的 recv（Windows 上尤其如此）。
            # 于是：读线程负责体积上限与逐块时限检查，主线程只负责「最多等多久」。
            state: dict = {"chunks": [], "total": 0, "error": None}
            cancel = threading.Event()

            def _read_body():
                try:
                    for chunk in resp.iter_content(chunk_size=16 * 1024):
                        if cancel.is_set():
                            # 主线程已判定超时并要求取消：立刻停止读
                            raise BlockedTargetError(f"读体已被取消：{target}")
                        if not chunk:
                            continue
                        state["total"] += len(chunk)
                        if state["total"] > max_bytes:
                            raise BlockedTargetError(
                                f"响应体超过上限 {max_bytes} 字节，已中止读取：{target}"
                            )
                        if time.monotonic() > deadline:
                            raise BlockedTargetError(
                                f"整体请求超时（{timeout}s 总预算已用尽），已中止读取：{target}"
                            )
                        state["chunks"].append(chunk)
                except Exception as e:  # noqa: BLE001 - 统一交给主线程判定
                    state["error"] = e

            reader = threading.Thread(target=_read_body, daemon=True)
            reader.start()
            reader.join(max(0.1, deadline - time.monotonic()))
            if reader.is_alive():
                # 显式取消：置取消信号（读循环下一轮即退出）+ 关闭连接（解除阻塞读）
                cancel.set()
                resp.close()
                raise BlockedTargetError(
                    f"整体请求超时（{timeout}s 总预算已用尽），已取消读体并断开连接：{target}"
                )
            if state["error"] is not None:
                err = state["error"]
                if isinstance(err, BlockedTargetError):
                    raise err
                if time.monotonic() > deadline:
                    raise BlockedTargetError(
                        f"整体请求超时（{timeout}s 总预算已用尽），已中止读取：{target}"
                    ) from None
                raise err
            chunks: list[bytes] = state["chunks"]
            resp._content = b"".join(chunks)  # noqa: SLF001 - 供 resp.text 使用
            resp._content_consumed = True  # noqa: SLF001
            return resp
        finally:
            session.close()

    raise BlockedTargetError("重定向未收敛")


def disclosure_note(url: str) -> str:
    """把"这次要联网"显式说出来（人不一定知道剪藏会发外部请求）。"""
    host = urlparse(url).hostname or url
    return (
        f"[net] 即将访问外部站点：{host}（仅 GET，80/443，无 cookie，"
        f"只读前 {DEFAULT_MAX_BYTES // (1024 * 1024)} MB）"
    )
