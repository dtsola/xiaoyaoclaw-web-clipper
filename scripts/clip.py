#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clip.py — 网页剪藏主入口

功能：
  - 单 URL 剪藏：提取正文 → 保存 Markdown（YAML frontmatter，Obsidian 兼容）
  - 批量剪藏：从文件读 URL 列表，逐条处理 + 汇总报告
  - 去重：按 source_url 查重（输出目录内 .clips-index.json）

用法：
  python clip.py <url> [--dir <保存目录>] [--tags a,b]
  python clip.py --batch <urls.txt> [--dir <保存目录>]
  python clip.py --check           # 检查依赖

上游参考：ClawHub @freedompixels/cn-web-clipper (MIT-0)
增强：中文文件名修复 / 批量真实现 / 去重 / frontmatter / kb-retriever 闭环提示
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

# Windows 控制台 GBK 无法输出 emoji/中文混合，强制 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from extract import extract, fetch_html

DEFAULT_DIR = os.path.expanduser(
    os.environ.get("CLIPPER_OUTPUT_DIR", "~/knowledge/clippings")
)
INDEX_NAME = ".clips-index.json"


# ---------- 依赖检查 ----------

def check_deps() -> bool:
    missing = []
    for mod in ("requests", "bs4", "lxml"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    # readability / trafilatura 是增强引擎，缺了降级，不算硬依赖
    for mod in ("readability", "trafilatura"):
        try:
            __import__(mod)
        except ImportError:
            pass
    if missing:
        print(f"❌ 缺少依赖: {', '.join(missing)}")
        print("   安装: pip install requests beautifulsoup4 lxml")
        return False
    # 提示增强引擎
    for mod, hint in (("readability", "pip install readability-lxml"),
                      ("trafilatura", "pip install trafilatura")):
        try:
            __import__(mod)
        except ImportError:
            print(f"ℹ️ 可选引擎 {mod} 未安装（{hint}），将使用降级提取")
    return True


# ---------- 文件名 ----------

def safe_filename(title: str, max_len: int = 60) -> str:
    """生成安全文件名：保留中文，只去非法字符"""
    if not title:
        title = "untitled"
    # Windows 非法字符 + 控制字符
    title = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", title)
    title = re.sub(r"\s+", " ", title).strip()
    title = title.strip(". ")
    if len(title) > max_len:
        title = title[:max_len].rstrip()
    return title or "untitled"


# ---------- 去重 ----------

def _load_index(out_dir: str) -> dict:
    p = os.path.join(out_dir, INDEX_NAME)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_index(out_dir: str, index: dict):
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, INDEX_NAME)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def is_duplicate(url: str, out_dir: str) -> bool:
    index = _load_index(out_dir)
    return _url_hash(url) in index


# ---------- 保存 ----------

def save_markdown(data: dict, out_dir: str, tags: list = None) -> str:
    """保存为 Markdown（YAML frontmatter，Obsidian 兼容）"""
    os.makedirs(out_dir, exist_ok=True)
    title = data.get("title") or "无标题"
    safe = safe_filename(title)
    date = data.get("publish_date") or data.get("clipped_at", "")[:10]
    fname = f"{datetime.now().strftime('%Y%m%d')}_{safe}.md"
    fpath = os.path.join(out_dir, fname)

    # 重名处理：加序号
    n = 1
    base, ext = os.path.splitext(fpath)
    while os.path.exists(fpath):
        n += 1
        fpath = f"{base}_{n}{ext}"

    tags_str = ""
    if tags:
        tags_str = "".join(f"\n  - {t}" for t in tags)

    md = f"""---
title: "{title.replace(chr(34), '')}"
source: "{data.get('source_url', '')}"
domain: "{data.get('domain', '')}"
author: "{data.get('author', '')}"
date: "{date}"
clipped_at: "{data.get('clipped_at', '')}"
engine: "{data.get('engine', '')}"
tags:{tags_str or ' []'}
---

# {title}

> 原文链接: [{data.get('source_url', '')}]({data.get('source_url', '')})
> 剪藏时间: {data.get('clipped_at', '')[:10]}
> 来源站点: {data.get('domain', '')}

{data.get('text', '')}

---
*由 xiaoyaoclaw-web-clipper 自动剪藏*
"""

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(md)

    # 更新索引
    index = _load_index(out_dir)
    index[_url_hash(data.get("source_url", ""))] = {
        "file": os.path.basename(fpath),
        "title": title,
        "clipped_at": data.get("clipped_at", ""),
    }
    _save_index(out_dir, index)

    return fpath


# ---------- 单条剪藏 ----------

def clip_one(url: str, out_dir: str = None, tags: list = None, quiet: bool = False) -> dict:
    out_dir = out_dir or DEFAULT_DIR

    if is_duplicate(url, out_dir):
        msg = f"⏭️ 已剪藏过，跳过: {url}"
        if not quiet:
            print(msg)
        return {"success": False, "skipped": "duplicate", "url": url,
                "message": msg}

    if not quiet:
        print(f"📎 正在剪藏: {url}")
    try:
        html = fetch_html(url)
    except Exception as e:
        return {"success": False, "error": str(e), "url": url,
                "message": f"❌ 抓取失败: {e}"}

    data = extract(url, html=html)
    if not data.get("success"):
        return {"success": False, "error": data.get("error"), "url": url,
                "message": f"❌ 提取失败: {data.get('error')}"}

    fpath = save_markdown(data, out_dir, tags)
    if not quiet:
        wc = len(data["text"])
        print(f"✅ 提取成功: {data['title']}（{data['engine']}，{wc} 字）")
        print(f"💾 已保存: {fpath}")

    return {"success": True, "url": url, "title": data["title"],
            "file": fpath, "engine": data["engine"],
            "word_count": len(data["text"]),
            "message": f"✅ 已保存: {fpath}"}


# ---------- 批量剪藏 ----------

def clip_batch(urls_file: str, out_dir: str = None, tags: list = None) -> dict:
    out_dir = out_dir or DEFAULT_DIR
    with open(urls_file, encoding="utf-8") as f:
        urls = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]

    print(f"📋 批量剪藏 {len(urls)} 条 → {out_dir}\n")
    results = {"ok": [], "skip": [], "fail": []}
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] ", end="")
        r = clip_one(url, out_dir, tags, quiet=False)
        if r.get("success"):
            results["ok"].append(r)
        elif r.get("skipped"):
            results["skip"].append(r)
        else:
            results["fail"].append(r)

    # 汇总
    print("\n" + "=" * 50)
    print(f"📊 汇总: 成功 {len(results['ok'])} | 跳过 {len(results['skip'])} | 失败 {len(results['fail'])}")
    for r in results["fail"]:
        print(f"  ❌ {r.get('url')}: {r.get('error')}")
    return results


# ---------- 主入口 ----------

def main():
    parser = argparse.ArgumentParser(description="网页剪藏工具（六件套·输入）")
    parser.add_argument("url", nargs="?", help="要剪藏的网页 URL")
    parser.add_argument("--batch", "-b", metavar="FILE", help="批量剪藏：URL 列表文件（每行一个，# 注释）")
    parser.add_argument("--dir", "-d", default=None, help="保存目录（默认 ~/knowledge/clippings 或 $CLIPPER_OUTPUT_DIR）")
    parser.add_argument("--tags", "-t", default=None, help="标签，逗号分隔: ai,research")
    parser.add_argument("--check", action="store_true", help="检查依赖")
    args = parser.parse_args()

    if args.check:
        sys.exit(0 if check_deps() else 1)

    if not args.url and not args.batch:
        parser.print_help()
        sys.exit(1)

    if not check_deps():
        sys.exit(1)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None

    if args.batch:
        clip_batch(args.batch, args.dir, tags)
    else:
        r = clip_one(args.url, args.dir, tags)
        if not r.get("success"):
            sys.exit(1)


if __name__ == "__main__":
    main()
