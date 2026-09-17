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
  4. **逐跳校验**：不自动跟随重定向（allow_redirects=False），每一跳重新跑上面
     两层校验，最多 3 跳 —— 公网站点也无法把请求转进内网。
  5. **体积与时长上限**：只读前 N 字节（默认 5 MB），超时默认 30s。
  6. 只发 GET；不发送 cookie、不发送 Authorization、UA 固定。
  7. 明确不做：不写远端、不登录、不发 POST、不探端口、不访问非公网目标。

⚠️ 残余风险（诚实声明）：解析与连接之间仍存在理论上的 DNS 重绑定窗口
（Python requests 无法像 Node 那样注入 connect-time lookup）。缓解手段是
"解析结果必须全部为公网地址" + 逐跳校验 + 只在标准端口 + 体积上限；
若需要更强保证，应在网络层（防火墙/代理）限制出站。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import requests

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


def assert_public_url(url: str) -> str:
    """校验目标：协议 / 凭据 / 端口 / 解析结果必须全为公网地址。返回规范化 URL。"""
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
        return url

    # 域名：解析出的每一个地址都必须公网
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise BlockedTargetError(f"DNS 解析失败：{host}") from exc
    addresses = sorted({info[4][0] for info in infos})
    blocked = [a for a in addresses if is_blocked_ip(a)]
    if blocked:
        raise BlockedTargetError(
            f"目标解析到内网/保留地址，已拒绝：{host} -> {', '.join(blocked)}"
        )
    return url


def safe_get(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    headers: dict | None = None,
) -> requests.Response:
    """带信任边界与体积上限的 GET。

    - 不自动跟随重定向：逐跳校验后自行重发（最多 MAX_REDIRECTS 跳）
    - 只读前 max_bytes 字节（超限即中止，防止恶意大响应）
    - 只发 GET，不带 cookie / Authorization
    """
    current = url
    for hop in range(MAX_REDIRECTS + 1):
        target = assert_public_url(current)
        req_headers = {"User-Agent": UA, "Accept": "*/*"}
        if headers:
            # 只允许覆盖非敏感头，避免把凭据塞进请求
            for k, v in headers.items():
                if k.lower() in ("cookie", "authorization", "proxy-authorization"):
                    continue
                req_headers[k] = v

        resp = requests.get(
            target,
            headers=req_headers,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            resp.close()
            if not location:
                raise BlockedTargetError(f"重定向缺少 Location：{target}")
            if hop == MAX_REDIRECTS:
                raise BlockedTargetError(f"重定向超过 {MAX_REDIRECTS} 跳，已停止")
            current = requests.compat.urljoin(target, location)
            continue

        # 体积上限：只取前 max_bytes 字节
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                chunks.append(chunk[: max_bytes - (total - len(chunk))])
                resp.close()
                raise BlockedTargetError(
                    f"响应体超过上限 {max_bytes} 字节，已中止读取：{target}"
                )
            chunks.append(chunk)
        resp._content = b"".join(chunks)  # noqa: SLF001 - 供 resp.text 使用
        resp._content_consumed = True  # noqa: SLF001
        return resp

    raise BlockedTargetError("重定向未收敛")


def disclosure_note(url: str) -> str:
    """把"这次要联网"显式说出来（人不一定知道剪藏会发外部请求）。"""
    host = urlparse(url).hostname or url
    return (
        f"[net] 即将访问外部站点：{host}（仅 GET，80/443，无 cookie，"
        f"只读前 {DEFAULT_MAX_BYTES // (1024 * 1024)} MB）"
    )
