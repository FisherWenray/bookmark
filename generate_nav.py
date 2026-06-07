#!/usr/bin/env python3
"""
书签导航页生成器 v2
左侧竖导航 + 右侧内容区 + 响应式多列书签网格

用法: python3 generate_nav.py [书签.html] [输出.html]
"""

import sys
import re
import html as html_lib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


# ─────────────────── 解析书签 HTML ───────────────────

class BookmarkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = []
        self.stack = [self.root]
        self.current_folder = None
        self.in_a = False
        self.in_h3 = False
        self.text_buf = ""
        self.current_attrs = {}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = dict(attrs)
        if tag == "dl":
            if self.current_folder is not None:
                children = self.current_folder.setdefault("children", [])
                self.stack.append(children)
        elif tag == "h3":
            self.in_h3 = True
            self.text_buf = ""
            self.current_attrs = attrs_dict
        elif tag == "a":
            self.in_a = True
            self.text_buf = ""
            self.current_attrs = attrs_dict

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "dl":
            if len(self.stack) > 1:
                self.stack.pop()
            self.current_folder = None
        elif tag == "h3":
            self.in_h3 = False
            folder = {"folder": self.text_buf.strip()}
            if self.current_attrs.get("personal_toolbar_folder") == "true":
                folder["toolbar"] = True
            self.current_folder = folder
            self.stack[-1].append(folder)
        elif tag == "a":
            self.in_a = False
            title = self.text_buf.strip()
            href = self.current_attrs.get("href", "")
            self.stack[-1].append({"title": title, "url": href})

    def handle_data(self, data):
        if self.in_a or self.in_h3:
            self.text_buf += data


def parse_bookmarks(html_path: str) -> list:
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    parser = BookmarkParser()
    parser.feed(content)
    return parser.root


# ─────────────────── 辅助函数 ───────────────────

def is_separator(item: dict) -> bool:
    if "url" not in item:
        return False
    url = item.get("url", "")
    title = item.get("title", "")
    if "separator.mayastudios.com" in url:
        return True
    if title and re.match(r'^[─━\-=\s]+$', title.strip()):
        return True
    return False


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc or ""
    except Exception:
        return ""


def get_favicon_url(url: str) -> str:
    domain = get_domain(url)
    if not domain:
        return ""
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=32"


def is_leaf_folder(item: dict) -> bool:
    children = item.get("children", [])
    return all("folder" not in child for child in children)


def esc(text: str) -> str:
    return html_lib.escape(text, quote=True)


def get_level1_folders(bookmarks: list) -> list:
    """提取一级文件夹列表（跳过书签栏外壳）"""
    for item in bookmarks:
        if isinstance(item, dict) and item.get("toolbar"):
            return item.get("children", [])
    
    # 如果只有一个顶级文件夹，且是书签栏外壳，自动跳过并返回其子文件夹
    folders = [item for item in bookmarks if isinstance(item, dict) and "folder" in item]
    if len(folders) == 1:
        f_name = folders[0]["folder"].strip()
        if f_name in ["书签栏", "Bookmarks Bar", "Favorites Bar", "Favorites", "Bookmarks", "书签"]:
            return folders[0].get("children", [])
            
    return bookmarks


# ─────────────────── 渲染函数 ───────────────────

def extract_separator_label(title: str) -> str:
    return re.sub(r'[─━\-=\s]+', '', (title or "").strip())

def render_bookmark_grid(bookmarks: list) -> str:
    """将书签列表渲染为响应式网格（最后一级）"""
    parts = []
    current_group_label = None
    current_items = []

    def flush_group():
        nonlocal current_items, current_group_label
        if not current_items:
            current_group_label = None
            return
        label_html = ""
        if current_group_label:
            label_html = f'<div class="grid-group-label">{esc(current_group_label)}</div>'
        items_html = "\n".join(current_items)
        parts.append(f'{label_html}<div class="bk-grid">{items_html}</div>')
        current_items = []
        current_group_label = None

    for item in bookmarks:
        if is_separator(item):
            flush_group()
            sep_title = item.get("title", "").strip()
            clean = re.sub(r'[─━\-=\s]', '', sep_title)
            if clean:
                current_group_label = clean
            continue
        url = item.get("url", "")
        if not url or url.strip().lower().startswith("javascript:"):
            continue
        title = item.get("title", "无标题")
        domain = get_domain(url)
        favicon = get_favicon_url(url)

        current_items.append(f'''<a href="{esc(url)}" target="_blank" rel="noopener" class="bk-card" title="{esc(title)}">
  <img src="{esc(favicon)}" alt="" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22><rect width=%2232%22 height=%2232%22 rx=%226%22 fill=%22%23334155%22/><text x=%2216%22 y=%2222%22 text-anchor=%22middle%22 fill=%22%239ca3af%22 font-size=%2216%22>{esc(title[:1])}</text></svg>'">
  <span class="bk-name">{esc(title)}</span>
</a>''')

    flush_group()
    return "\n".join(parts) if parts else ""


def render_section_items(items: list, depth: int) -> str:
    parts = []
    for item in items:
        if is_separator(item):
            continue

        if "folder" in item:
            folder_name = item["folder"]
            sub_children = item.get("children", [])
            real_children = [c for c in sub_children if not is_separator(c) or True]
            if not real_children:
                continue

            collapsed = "" if depth == 0 else "collapsed"

            if is_leaf_folder(item):
                grid_html = render_bookmark_grid(sub_children)
                if not grid_html:
                    continue
                bk_count = len([c for c in sub_children if "url" in c and not is_separator(c) and not c.get("url", "").strip().lower().startswith("javascript:")])
                parts.append(f'''<div class="sub-section depth-{depth} {collapsed}">
  <div class="sub-header" onclick="toggleSub(this)">
    <span class="arrow">▶</span>
    <span class="sub-title">{esc(folder_name)}</span>
    <span class="sub-count">{bk_count}</span>
  </div>
  <div class="sub-body">{grid_html}</div>
</div>''')
            else:
                inner = render_section_content(sub_children, depth + 1)
                if not inner.strip():
                    continue
                parts.append(f'''<div class="sub-section depth-{depth} {collapsed}">
  <div class="sub-header" onclick="toggleSub(this)">
    <span class="arrow">▶</span>
    <span class="sub-title">{esc(folder_name)}</span>
  </div>
  <div class="sub-body">{inner}</div>
</div>''')

        elif "url" in item:
            url = item.get("url", "")
            if not url or url.strip().lower().startswith("javascript:"):
                continue
            title = item.get("title", "")
            favicon = get_favicon_url(url)
            parts.append(f'''<a href="{esc(url)}" target="_blank" rel="noopener" class="bk-card loose" title="{esc(title)}">
  <img src="{esc(favicon)}" alt="" loading="lazy" onerror="this.style.display='none'">
  <span class="bk-name">{esc(title)}</span>
</a>''')

    return "\n".join(parts)


def render_section_content(children: list, depth: int = 0) -> str:
    """递归渲染二级及以下内容"""
    if depth != 0:
        return render_section_items(children, depth)

    has_separator = any(is_separator(item) for item in children)
    if not has_separator:
        return render_section_items(children, depth)

    grouped = []
    buffer_items = []
    pending_label = ""

    for item in children:
        if is_separator(item):
            if buffer_items:
                grouped.append((pending_label, buffer_items))
                buffer_items = []
            pending_label = extract_separator_label(item.get("title", ""))
            continue
        buffer_items.append(item)

    if buffer_items:
        grouped.append((pending_label, buffer_items))

    output = []
    for _label, items in grouped:
        group_html = render_section_items(items, depth)
        if not group_html.strip():
            continue
        output.append(f'''<section class="tier-group">
  <div class="tier-group-body">{group_html}</div>
</section>''')

    return "\n".join(output)


def generate_nav_html(bookmarks: list) -> str:
    level1 = get_level1_folders(bookmarks)

    # 定义分类映射：将特定一级目录合并为“基础学科”
    GROUP_MAPPING = {
        "哲学心理": "基础学科",
        "社会科学": "基础学科",
        "英语学习": "基础学科",
        "自然科学": "基础学科",
    }

    grouped_level1 = []
    seen_groups = {}  # group_name -> index in grouped_level1

    for item in level1:
        if not isinstance(item, dict) or "folder" not in item:
            grouped_level1.append(item)
            continue
        
        folder_name = item["folder"]
        if folder_name in GROUP_MAPPING:
            group_name = GROUP_MAPPING[folder_name]
            if group_name not in seen_groups:
                group_item = {
                    "folder": group_name,
                    "is_group": True,
                    "sub_folders": [item]
                }
                seen_groups[group_name] = len(grouped_level1)
                grouped_level1.append(group_item)
            else:
                idx_pos = seen_groups[group_name]
                grouped_level1[idx_pos]["sub_folders"].append(item)
        else:
            grouped_level1.append(item)

    # 提取一级文件夹
    nav_items = []
    panels = []

    idx = 0
    for item in grouped_level1:
        if not isinstance(item, dict):
            continue
        if "folder" not in item:
            continue
        if is_separator(item):
            continue

        folder_name = item["folder"]
        panel_id = f"panel-{idx}"
        active = "active" if idx == 0 else ""

        # 侧边栏导航项
        nav_items.append(
            f'<div class="nav-item {active}" data-panel="{panel_id}" onclick="switchPanel(this)">{esc(folder_name)}</div>'
        )

        # 右侧面板
        if item.get("is_group"):
            content_parts = []
            for sub in item["sub_folders"]:
                sub_name = sub["folder"]
                sub_children = sub.get("children", [])
                sub_content = render_section_content(sub_children, depth=0)
                if not sub_content.strip():
                    continue
                content_parts.append(f'''<div class="group-sub-category">
  <div class="group-sub-category-title">{esc(sub_name)}</div>
  <div class="group-sub-category-content">{sub_content}</div>
</div>''')
            content_html = "\n".join(content_parts)
        else:
            children = item.get("children", [])
            content_html = render_section_content(children, depth=0)

        panels.append(f'<div class="panel {active}" id="{panel_id}">{content_html}</div>')
        idx += 1

    nav_html = "\n".join(nav_items)
    panels_html = "\n".join(panels)

    return '''<!DOCTYPE html>
<html lang="zh-CN">

<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>书签导航</title>
  <style>
    @import url("https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Noto+Serif+SC:wght@600;700;900&display=swap");

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    :root {
      --primary: #5D7B93;
      --primary-rgb: 93, 123, 147;
      --secondary: #c5b358;
      --secondary-rgb: 197, 179, 88;
      --bg: #0f141b;
      --panel: #121a23;
      --panel-strong: #172230;
      --text-main: #d7dfeb;
      --text-soft: #90a3b8;
      --line-soft: rgba(255, 255, 255, 0.08);
      --line-strong: rgba(var(--primary-rgb), 0.45);
      --shadow-main: 0 22px 46px rgba(0, 0, 0, 0.36);
    }

    body {
      position: relative;
      font-family: "DM Sans", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at 12% 8%, rgba(var(--primary-rgb), 0.30), transparent 30%),
        radial-gradient(circle at 88% 92%, rgba(var(--secondary-rgb), 0.18), transparent 32%),
        linear-gradient(140deg, #0a1016, #0f141b 48%, #151c26);
      color: var(--text-main);
      height: 100vh;
      overflow: hidden;
      display: flex;
      padding: 14px;
      gap: 14px;
    }

    body::before,
    body::after {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
    }

    body::before {
      background-image: linear-gradient(transparent 97%, rgba(255, 255, 255, 0.03) 100%);
      background-size: 100% 5px;
      opacity: 0.18;
      mix-blend-mode: soft-light;
    }

    body::after {
      background: linear-gradient(120deg, transparent 0%, rgba(var(--primary-rgb), 0.12) 48%, transparent 85%);
      transform: translateX(-100%);
      animation: sweep 10s ease-in-out infinite;
    }

    @keyframes sweep {
      0% {
        transform: translateX(-100%);
      }

      55%,
      100% {
        transform: translateX(100%);
      }
    }

    .sidebar,
    .main {
      position: relative;
      z-index: 1;
    }

    .sidebar {
      width: 236px;
      min-width: 236px;
      height: calc(100vh - 28px);
      background: linear-gradient(180deg, rgba(22, 31, 43, 0.94), rgba(11, 16, 24, 0.94));
      border: 1px solid var(--line-soft);
      border-radius: 18px;
      box-shadow: var(--shadow-main);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      padding: 12px 10px 14px;
      backdrop-filter: blur(10px);
      scrollbar-width: thin;
      scrollbar-color: rgba(var(--primary-rgb), 0.34) transparent;
    }

    .sidebar::-webkit-scrollbar {
      width: 6px;
    }

    .sidebar::-webkit-scrollbar-thumb {
      border-radius: 999px;
      background: rgba(var(--primary-rgb), 0.34);
    }

    .sidebar-title {
      padding: 6px 12px 18px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-bottom: 1px dashed rgba(var(--primary-rgb), 0.30);
      margin-bottom: 10px;
    }

    .sidebar-logo {
      width: 140px;
      max-width: 100%;
      height: auto;
      display: block;
      filter: drop-shadow(0 7px 14px rgba(var(--primary-rgb), 0.32));
    }

    .nav-item {
      padding: 11px 14px;
      font-size: 13px;
      letter-spacing: 0.2px;
      color: rgba(220, 233, 247, 0.62);
      cursor: pointer;
      transition: all 0.22s ease;
      border: 1px solid transparent;
      border-radius: 11px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin: 1px 0;
      font-weight: 500;
    }

    .nav-item:hover {
      color: #f2f7ff;
      border-color: rgba(var(--primary-rgb), 0.20);
      background: rgba(var(--primary-rgb), 0.12);
      transform: translateX(2px);
    }

    .nav-item.active {
      color: #ffffff;
      background:
        linear-gradient(110deg, rgba(var(--primary-rgb), 0.48), rgba(var(--primary-rgb), 0.2)),
        rgba(255, 255, 255, 0.02);
      border-color: var(--line-strong);
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06), 0 10px 20px rgba(0, 0, 0, 0.28);
      font-weight: 700;
    }

    .main {
      flex: 1;
      min-width: 0;
      height: calc(100vh - 28px);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(20, 28, 39, 0.9), rgba(10, 15, 22, 0.9));
      border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: var(--shadow-main);
      backdrop-filter: blur(8px);
    }

    .search-bar {
      padding: 18px 24px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      background:
        linear-gradient(145deg, rgba(var(--primary-rgb), 0.12), transparent 45%),
        rgba(11, 17, 24, 0.85);
      flex-shrink: 0;
    }

    .search-bar input {
      width: 100%;
      padding: 13px 18px;
      font-size: 14px;
      border: 1px solid rgba(var(--primary-rgb), 0.26);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.045);
      color: #f8fbff;
      outline: none;
      transition: all 0.3s ease;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.03);
    }

    .search-bar input:focus {
      border-color: rgba(var(--primary-rgb), 0.65);
      background: rgba(var(--primary-rgb), 0.13);
      box-shadow: 0 0 0 4px rgba(var(--primary-rgb), 0.15);
    }

    .search-bar input::placeholder {
      color: rgba(227, 236, 247, 0.45);
    }

    .content {
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px 28px;
      scrollbar-width: thin;
      scrollbar-color: rgba(var(--primary-rgb), 0.35) transparent;
    }

    .content::-webkit-scrollbar {
      width: 8px;
    }

    .content::-webkit-scrollbar-thumb {
      background: rgba(var(--primary-rgb), 0.35);
      border-radius: 999px;
    }

    .panel {
      display: none;
    }

    .panel.active {
      display: block;
      animation: panelFade 0.28s ease;
    }

    @keyframes panelFade {
      from {
        opacity: 0;
        transform: translateY(8px);
      }

      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .tier-group {
      margin-bottom: 14px;
    }

    .tier-group+.tier-group {
      border-top: 1px dashed rgba(var(--secondary-rgb), 0.56);
      margin-top: 18px;
      padding-top: 18px;
    }

    .tier-group-body {
      padding: 0;
    }

    .sub-section {
      margin-bottom: 10px;
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid transparent;
      transition: border-color 0.25s ease, transform 0.25s ease;
    }

    .sub-section.depth-0 {
      background: linear-gradient(160deg, rgba(255, 255, 255, 0.03), rgba(var(--primary-rgb), 0.09));
      border-color: rgba(var(--primary-rgb), 0.24);
      box-shadow: 0 14px 26px rgba(0, 0, 0, 0.18);
    }

    .sub-section.depth-1,
    .sub-section.depth-2 {
      background: rgba(255, 255, 255, 0.02);
      border-color: rgba(255, 255, 255, 0.08);
      margin: 7px 4px;
    }

    .sub-section:hover {
      border-color: rgba(var(--primary-rgb), 0.5);
      transform: translateY(-1px);
    }

    .sub-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      cursor: pointer;
      user-select: none;
      transition: background 0.18s ease;
    }

    .sub-header:hover {
      background: rgba(var(--primary-rgb), 0.12);
    }

    .sub-header .arrow {
      width: 20px;
      height: 20px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      font-size: 10px;
      color: rgba(233, 244, 255, 0.72);
      background: rgba(var(--primary-rgb), 0.26);
      transition: transform 0.24s ease;
      flex-shrink: 0;
    }

    .sub-section:not(.collapsed)>.sub-header .arrow {
      transform: rotate(90deg);
    }

    .sub-title {
      font-family: "Noto Serif SC", "Kaiti SC", serif;
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0.3px;
      color: #e7f0fb;
      flex: 1;
    }

    .depth-1 .sub-title,
    .depth-2 .sub-title {
      font-size: 14px;
      color: #abc0d5;
      font-family: "DM Sans", "PingFang SC", sans-serif;
      font-weight: 600;
    }

    .sub-count {
      font-size: 11px;
      color: rgba(var(--secondary-rgb), 0.96);
      background: rgba(var(--secondary-rgb), 0.12);
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid rgba(var(--secondary-rgb), 0.42);
    }

    .sub-section.collapsed>.sub-body {
      display: none;
    }

    .sub-body {
      padding: 4px 12px 12px;
    }

    .grid-group-label {
      font-size: 11px;
      font-weight: 700;
      color: rgba(var(--secondary-rgb), 0.88);
      letter-spacing: 1.2px;
      padding: 10px 2px 6px;
      margin-top: 3px;
      text-transform: uppercase;
    }

    .bk-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
      gap: 9px;
      padding: 4px 0 8px;
    }

    .bk-card {
      display: flex;
      align-items: center;
      gap: 9px;
      padding: 10px 12px;
      border-radius: 11px;
      background: linear-gradient(135deg, rgba(255, 255, 255, 0.04), rgba(var(--primary-rgb), 0.10));
      border: 1px solid rgba(255, 255, 255, 0.11);
      text-decoration: none;
      color: #e2ecf8;
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
      overflow: hidden;
      min-height: 44px;
    }

    .bk-card:hover {
      background: linear-gradient(135deg, rgba(var(--primary-rgb), 0.32), rgba(var(--primary-rgb), 0.14));
      border-color: rgba(var(--primary-rgb), 0.56);
      box-shadow: 0 10px 18px rgba(0, 0, 0, 0.22);
      transform: translateY(-2px);
    }

    .bk-card img {
      width: 18px;
      height: 18px;
      border-radius: 5px;
      flex-shrink: 0;
      filter: saturate(0.95);
    }

    .bk-name {
      font-size: 13px;
      line-height: 1.4;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .bk-card.loose {
      display: inline-flex;
      margin: 3px;
    }

    .group-sub-category {
      margin-bottom: 28px;
    }

    .group-sub-category-title {
      font-family: "Noto Serif SC", "Kaiti SC", serif;
      font-size: 20px;
      font-weight: 900;
      color: #ffffff;
      padding-left: 12px;
      border-left: 4px solid var(--secondary);
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      letter-spacing: 0.5px;
    }

    .group-sub-category-content {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .search-hidden {
      display: none !important;
    }

    mark {
      background: rgba(var(--secondary-rgb), 0.32);
      color: #fff9dc;
      border-radius: 3px;
      padding: 0 2px;
    }

    @media (max-width: 1080px) {
      body {
        padding: 10px;
        gap: 10px;
      }

      .sidebar {
        width: 206px;
        min-width: 206px;
      }

      .content {
        padding: 16px;
      }
    }

    @media (max-width: 768px) {
      body {
        padding: 8px;
      }

      .sidebar {
        width: 166px;
        min-width: 166px;
      }

      .nav-item {
        padding: 9px 10px;
        font-size: 12px;
      }

      .search-bar {
        padding: 14px;
      }

      .content {
        padding: 14px;
      }

      .bk-grid {
        grid-template-columns: repeat(auto-fill, minmax(145px, 1fr));
      }
    }

    @media (max-width: 540px) {
      body {
        flex-direction: column;
        overflow: auto;
        height: auto;
      }

      .sidebar,
      .main {
        width: 100%;
        min-width: 100%;
        height: auto;
      }

      .sidebar {
        flex-direction: row;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 10px;
        border-radius: 14px;
      }

      .sidebar-title {
        display: none;
      }

      .nav-item {
        min-width: fit-content;
      }

      .main {
        min-height: calc(100vh - 120px);
      }

      .content {
        overflow: visible;
      }
    }
  </style>
</head>

<body>

  <div class="sidebar">
    <div class="sidebar-title"><img class="sidebar-logo" src="logo.png" alt="导航 Logo"></div>
    ''' + nav_html + '''
  </div>

  <div class="main">
    <div class="search-bar">
      <input type="text" id="searchInput" placeholder="🔍 搜索书签... (Cmd+K)" autocomplete="off">
    </div>
    <div class="content" id="content">
      ''' + panels_html + '''
    </div>
  </div>

  <script>
    // ── 侧边栏切换面板 ──
    function switchPanel(el) {
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      el.classList.add('active');
      const panel = document.getElementById(el.dataset.panel);
      if (panel) {
        panel.classList.add('active');
        document.getElementById('content').scrollTop = 0;
      }
    }

    // ── 折叠/展开子区 ──
    function toggleSub(header) {
      header.parentElement.classList.toggle('collapsed');
    }

    // ── 搜索 ──
    const searchInput = document.getElementById('searchInput');
    const content = document.getElementById('content');

    searchInput.addEventListener('input', function () {
      const query = this.value.trim().toLowerCase();

      // 清除高亮
      content.querySelectorAll('mark').forEach(m => m.replaceWith(m.textContent));

      if (!query) {
        content.querySelectorAll('.search-hidden').forEach(el => el.classList.remove('search-hidden'));
        // 恢复当前活跃面板
        const activeNav = document.querySelector('.nav-item.active');
        if (activeNav) {
          document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
          const panel = document.getElementById(activeNav.dataset.panel);
          if (panel) panel.classList.add('active');
        }
        // 恢复折叠
        content.querySelectorAll('.sub-section.depth-1, .sub-section.depth-2').forEach(s => s.classList.add('collapsed'));
        content.querySelectorAll('.sub-section.depth-0').forEach(s => s.classList.remove('collapsed'));
        return;
      }

      // 搜索模式：显示所有面板
      document.querySelectorAll('.panel').forEach(p => p.classList.add('active'));
      content.querySelectorAll('.bk-card, .sub-section, .tier-group, .group-sub-category').forEach(el => el.classList.add('search-hidden'));

      const queryRegex = new RegExp('(' + query.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
      const highlightedSubTitles = new Set();

      content.querySelectorAll('.bk-card').forEach(card => {
        const name = card.querySelector('.bk-name');
        if (!name) return;
        const text = name.textContent.toLowerCase();
        const url = (card.getAttribute('href') || '').toLowerCase();
        const sectionTitles = [];
        let section = card.closest('.sub-section');
        while (section) {
          const subTitle = section.querySelector(':scope > .sub-header .sub-title');
          if (subTitle) sectionTitles.push(subTitle.textContent.toLowerCase());
          section = section.parentElement.closest('.sub-section');
        }
        const subTitleText = sectionTitles.join(' ');

        if (text.includes(query) || url.includes(query) || subTitleText.includes(query)) {
          card.classList.remove('search-hidden');
          name.innerHTML = name.textContent.replace(queryRegex, '<mark>$1</mark>');
          let parent = card.closest('.sub-section');
          while (parent) {
            parent.classList.remove('search-hidden', 'collapsed');
            const parentTitle = parent.querySelector(':scope > .sub-header .sub-title');
            if (
              parentTitle &&
              !highlightedSubTitles.has(parentTitle) &&
              parentTitle.textContent.toLowerCase().includes(query)
            ) {
              parentTitle.innerHTML = parentTitle.textContent.replace(queryRegex, '<mark>$1</mark>');
              highlightedSubTitles.add(parentTitle);
            }
            parent = parent.parentElement.closest('.sub-section');
          }
          let panel = card.closest('.panel');
          if (panel) panel.classList.remove('search-hidden');
          let tier = card.closest('.tier-group');
          if (tier) tier.classList.remove('search-hidden');
          let groupSub = card.closest('.group-sub-category');
          if (groupSub) groupSub.classList.remove('search-hidden');
        }
      });
    });

    // ── 快捷键 ──
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      }
      if (e.key === 'Escape') {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input'));
        searchInput.blur();
      }
    });
  </script>
</body>

</html>'''


# ─────────────────── CLI ───────────────────

def main():
    html_path = sys.argv[1] if len(sys.argv) > 1 else "raw_bookmarks/RunningCheese_Bookmarks_2026_05_06.html"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "index.html"

    print(f"📖 正在解析书签: {html_path}")
    bookmarks = parse_bookmarks(html_path)

    print("🎨 正在生成导航页...")
    nav_html = generate_nav_html(bookmarks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(nav_html)

    total = nav_html.count('class="bk-card"')
    print(f"✓ 导航页已生成: {output_path}")
    print(f"  书签数: {total}")
    print(f"\n  open {output_path}")


if __name__ == "__main__":
    main()
