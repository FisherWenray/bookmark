#!/usr/bin/env python3
"""
万象导航页面生成器 v2
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

        current_items.append(f'''<a href="{esc(url)}" target="_blank" rel="noopener nofollow" class="bk-card" title="{esc(title)}">
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
            if folder_name == "小书签栏":
                continue
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
            parts.append(f'''<a href="{esc(url)}" target="_blank" rel="noopener nofollow" class="bk-card loose" title="{esc(title)}">
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

    # 将 "资源搜索" 移动到 level1 的最前面，以便作为单列置顶常驻
    search_item = None
    new_level1 = []
    for item in level1:
        if isinstance(item, dict) and item.get("folder") == "资源搜索":
            search_item = item
        else:
            new_level1.append(item)
    if search_item:
        level1 = [search_item] + new_level1

    # 定义分类映射：将一级目录合并为各个侧边栏折叠大类
    GROUP_MAPPING = {
        "哲学心理": "基础学科",
        "社会科学": "基础学科",
        "英语学习": "基础学科",
        "自然科学": "基础学科",
        "电影艺术": "音乐.电影.读书",
        "音乐视频": "音乐.电影.读书",
        "文学知识": "音乐.电影.读书",
        "在线办公": "数字生产力",
        "在线工具": "数字生产力",
        "软件开发": "数字生产力",
        "平面设计": "数字生产力",
        "产品运营": "数字生产力",
        "娱乐休闲": "生活娱乐",
        "生活频道": "生活娱乐",
        "新闻资讯": "资讯与数码",
        "科技数码": "资讯与数码",
    }

    # 按照 GROUP_MAPPING 对 level1 进行预分组排重，使同组项目在侧边栏连续排列
    reordered_level1 = []
    group_contents = {}  # group_name -> list of original items
    
    for item in level1:
        if not isinstance(item, dict) or "folder" not in item or is_separator(item):
            reordered_level1.append(item)
            continue
            
        folder_name = item["folder"]
        group_name = GROUP_MAPPING.get(folder_name)
        
        if group_name:
            if group_name not in group_contents:
                group_contents[group_name] = [item]
                # 用占位符标记该分组在侧边栏的插入位置（保留第一个成员的原始顺序）
                reordered_level1.append({"is_group_placeholder": True, "group_name": group_name})
            else:
                group_contents[group_name].append(item)
        else:
            reordered_level1.append(item)

    # 提取一级文件夹
    nav_items = []
    panels = []

    idx = 0
    for item in reordered_level1:
        if not isinstance(item, dict):
            continue
            
        if item.get("is_group_placeholder"):
            group_name = item["group_name"]
            sub_folders = group_contents[group_name]
            
            group_items_html = []
            for sub in sub_folders:
                sub_name = sub["folder"]
                sub_children = sub.get("children", [])
                panel_id = f"panel-{idx}"
                active = "active" if idx == 0 else ""
                
                # 生成右侧面板内容
                content_html = render_section_content(sub_children, depth=0)
                panels.append(f'<div class="panel {active}" id="{panel_id}">{content_html}</div>')
                
                # 生成侧边栏子项
                group_items_html.append(
                    f'<div class="nav-item sub-item {active}" data-panel="{panel_id}" onclick="switchPanel(this)">{esc(sub_name)}</div>\n'
                )
                idx += 1
                
            # 将该分组作为静态标题栏放入侧边栏
            nav_items.append(f'''<div class="nav-group">
  <div class="nav-group-header">
    <span>{esc(group_name)}</span>
  </div>
  <div class="nav-group-items">
    {"".join(group_items_html)}
  </div>
</div>''')
        else:
            if "folder" not in item:
                continue
            if is_separator(item):
                continue
                
            folder_name = item["folder"]
            children = item.get("children", [])
            panel_id = f"panel-{idx}"
            active = "active" if idx == 0 else ""
            
            # 生成右侧面板内容
            content_html = render_section_content(children, depth=0)
            panels.append(f'<div class="panel {active}" id="{panel_id}">{content_html}</div>')
            
            # 正常的一级导航项
            nav_items.append(
                f'<div class="nav-item {active}" data-panel="{panel_id}" onclick="switchPanel(this)">{esc(folder_name)}</div>\n'
            )
            idx += 1

    nav_html = "".join(nav_items)
    panels_html = "\n".join(panels)

    return '''<!DOCTYPE html>
<html lang="zh-CN">

<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>万象导航 - 精选高效工具与优质资源</title>
  <meta name="description" content="一个收录了数千个精选网站、高效工具、优质资源的个人书签导航页，支持快捷搜索，一站式满足数字生产力需求。">
  <meta name="keywords" content="万象导航,导航网站,书签导航,工具大全,资源搜索,个人主页,wenyaoyefei">
  <meta property="og:title" content="万象导航 - 精选高效工具与优质资源">
  <meta property="og:description" content="收录数千个精选网站与高效工具的个人导航，快速查找各类数字资源。">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://nav.wenyaoyefei.com/">
  <meta property="og:image" content="https://nav.wenyaoyefei.com/logo.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="万象导航 - 精选高效工具与优质资源">
  <meta name="twitter:description" content="收录数千个精选网站与高效工具的个人导航，快速查找各类数字资源。">
  <meta name="twitter:image" content="https://nav.wenyaoyefei.com/logo.png">
  <meta name="author" content="Wenray">
  <meta name="theme-color" content="#0f141b">
  <link rel="canonical" href="https://nav.wenyaoyefei.com/" />
  <link rel="icon" href="logo.svg" type="image/svg+xml">
  <link rel="alternate icon" href="logo.png" type="image/png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Noto+Serif+SC:wght@600;700;900&display=swap" rel="stylesheet">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "万象导航 - 精选高效工具与优质资源",
    "url": "https://nav.wenyaoyefei.com/",
    "description": "一个收录了数千个精选网站、高效工具、优质资源的个人书签导航页。",
    "potentialAction": {
      "@type": "SearchAction",
      "target": "https://nav.wenyaoyefei.com/?q={search_term_string}",
      "query-input": "required name=search_term_string"
    }
  }
  </script>
  <style>

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    .seo-hidden {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    :root {
      --primary: #7896aa;
      --primary-rgb: 120, 150, 170;
      --secondary: #d2b464;
      --secondary-rgb: 210, 180, 100;
      --bg: #071019;
      --panel: #0d1721;
      --panel-strong: #111e2a;
      --surface: #14212d;
      --text-main: #e3e9ef;
      --text-soft: #91a1b0;
      --line-soft: rgba(199, 218, 232, 0.09);
      --line-strong: rgba(var(--primary-rgb), 0.48);
      --shadow-main: 0 24px 70px rgba(0, 0, 0, 0.34);
    }

    body {
      position: relative;
      font-family: "DM Sans", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at 8% 4%, rgba(var(--primary-rgb), 0.19), transparent 27%),
        radial-gradient(circle at 94% 96%, rgba(var(--secondary-rgb), 0.10), transparent 25%),
        linear-gradient(145deg, #071019 0%, #0a131c 48%, #0d1721 100%);
      color: var(--text-main);
      height: 100vh;
      height: 100dvh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .app-body {
      display: flex;
      flex: 1;
      min-height: 0;
      padding: 16px;
      gap: 16px;
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
      background-image:
        linear-gradient(rgba(176, 205, 226, 0.022) 1px, transparent 1px),
        linear-gradient(90deg, rgba(176, 205, 226, 0.022) 1px, transparent 1px);
      background-size: 44px 44px;
      mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.75), transparent 82%);
    }

    body::after {
      background:
        radial-gradient(circle at 50% -12%, transparent 0 25%, rgba(0, 0, 0, 0.17) 68%),
        linear-gradient(110deg, transparent 0 67%, rgba(var(--secondary-rgb), 0.035) 67% 67.2%, transparent 67.2%);
    }

    .sidebar,
    .main {
      position: relative;
      z-index: 1;
    }

    .sidebar {
      width: 226px;
      min-width: 226px;
      height: 100%;
      background: linear-gradient(180deg, rgba(14, 25, 36, 0.97), rgba(8, 16, 24, 0.97));
      border: 1px solid var(--line-soft);
      border-radius: 22px;
      box-shadow: var(--shadow-main);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      padding: 14px 10px 16px;
      backdrop-filter: blur(16px);
      scrollbar-width: thin;
      scrollbar-color: rgba(var(--primary-rgb), 0.28) transparent;
    }

    .sidebar::before {
      content: "";
      position: absolute;
      top: 0;
      left: 28px;
      right: 28px;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(var(--secondary-rgb), 0.48), transparent);
    }

    .sidebar::-webkit-scrollbar {
      width: 5px;
    }

    .sidebar::-webkit-scrollbar-thumb {
      border-radius: 999px;
      background: rgba(var(--primary-rgb), 0.28);
    }

    .sidebar-title {
      padding: 8px 10px 17px;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      border-bottom: 1px solid var(--line-soft);
      margin-bottom: 12px;
    }

    .brand-lockup {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      color: #f4f0e7;
      text-decoration: none;
    }

    .brand-mark {
      width: 44px;
      height: 44px;
      flex: none;
      filter: drop-shadow(0 9px 18px rgba(0, 0, 0, 0.32));
      transition: transform 0.35s ease, filter 0.35s ease;
    }

    .brand-lockup:hover .brand-mark {
      transform: rotate(8deg) scale(1.03);
      filter: drop-shadow(0 10px 22px rgba(var(--secondary-rgb), 0.18));
    }

    .brand-copy {
      display: flex;
      flex-direction: column;
      line-height: 1;
    }

    .brand-name {
      font-family: "Noto Serif SC", serif;
      font-size: 20px;
      font-weight: 900;
      letter-spacing: 0.10em;
      text-shadow: 0 1px 20px rgba(255, 255, 255, 0.08);
    }

    .brand-tagline {
      margin-top: 8px;
      color: rgba(var(--primary-rgb), 0.88);
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.22em;
    }

    .homepage-btn,
    .set-home-btn {
      display: block;
      width: calc(100% - 20px);
      margin: 0 10px 8px;
      padding: 9px 12px;
      text-align: center;
      background: rgba(var(--primary-rgb), 0.08);
      color: #dbe5ec;
      text-decoration: none;
      border-radius: 10px;
      font-size: 12px;
      font-weight: 600;
      font-family: inherit;
      border: 1px solid rgba(var(--primary-rgb), 0.18);
      cursor: pointer;
      transition: color 0.2s ease, background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
      box-shadow: none;
    }

    .homepage-btn:hover,
    .set-home-btn:hover {
      color: #ffffff;
      background: rgba(var(--primary-rgb), 0.16);
      border-color: rgba(var(--primary-rgb), 0.4);
      transform: translateY(-1px);
      box-shadow: none;
    }

    .set-home-btn {
      margin-bottom: 13px;
      color: rgba(239, 222, 171, 0.88);
      background: rgba(var(--secondary-rgb), 0.055);
      border-color: rgba(var(--secondary-rgb), 0.18);
    }

    .set-home-btn:hover {
      background: rgba(var(--secondary-rgb), 0.12);
      border-color: rgba(var(--secondary-rgb), 0.36);
    }

    .homepage-toast {
      position: fixed;
      right: 28px;
      bottom: 28px;
      z-index: 2000;
      width: min(360px, calc(100vw - 40px));
      padding: 14px 16px;
      border: 1px solid rgba(var(--secondary-rgb), 0.30);
      border-radius: 12px;
      background: rgba(11, 20, 29, 0.97);
      color: #f6f1d7;
      font-size: 13px;
      line-height: 1.6;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.48);
      backdrop-filter: blur(18px);
      opacity: 0;
      transform: translateY(14px);
      pointer-events: none;
      transition: opacity 0.22s ease, transform 0.22s ease;
    }

    .homepage-toast.show {
      opacity: 1;
      transform: translateY(0);
    }

    .site-footer {
      position: relative;
      z-index: 1;
      text-align: center;
      padding: 12px 16px 13px;
      font-size: 11px;
      letter-spacing: 0.03em;
      color: rgba(145, 161, 176, 0.78);
      border-top: 1px solid var(--line-soft);
      background: rgba(6, 13, 20, 0.72);
    }

    .site-footer a {
      color: rgba(var(--primary-rgb), 0.94);
      text-decoration: none;
      font-weight: 600;
      transition: color 0.2s;
    }

    .site-footer a:hover {
      color: #f0d894;
    }

    .nav-item {
      position: relative;
      display: flex;
      align-items: center;
      min-height: 42px;
      padding: 8px 13px;
      font-size: 13px;
      line-height: 1.4;
      letter-spacing: 0.02em;
      color: rgba(215, 228, 239, 0.66);
      cursor: pointer;
      transition: color 0.2s ease, background 0.2s ease, transform 0.2s ease;
      border: 1px solid transparent;
      border-radius: 9px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin: 1px 0;
      font-weight: 500;
    }

    .nav-item:hover {
      color: #edf4f8;
      border-color: transparent;
      background: rgba(var(--primary-rgb), 0.08);
      transform: translateX(1px);
    }

    .nav-item.active {
      color: #fffdf8;
      background: linear-gradient(90deg, rgba(var(--primary-rgb), 0.19), rgba(var(--primary-rgb), 0.065));
      border-color: rgba(var(--primary-rgb), 0.16);
      box-shadow: none;
      font-weight: 700;
    }

    .nav-item.active::before {
      content: "";
      position: absolute;
      left: -1px;
      top: 9px;
      bottom: 9px;
      width: 2px;
      border-radius: 999px;
      background: var(--secondary);
      box-shadow: 0 0 12px rgba(var(--secondary-rgb), 0.35);
    }

    .main {
      flex: 1;
      min-width: 0;
      height: 100%;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border-radius: 22px;
      background: linear-gradient(180deg, rgba(15, 26, 37, 0.94), rgba(8, 16, 24, 0.96));
      border: 1px solid var(--line-soft);
      box-shadow: var(--shadow-main);
      backdrop-filter: blur(16px);
    }

    .main::before {
      content: "";
      position: absolute;
      z-index: 2;
      top: 0;
      left: 32px;
      right: 32px;
      height: 1px;
      pointer-events: none;
      background: linear-gradient(90deg, transparent, rgba(var(--primary-rgb), 0.42), transparent);
    }

    .search-bar {
      position: relative;
      z-index: 1;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line-soft);
      background:
        radial-gradient(circle at 12% 0%, rgba(var(--primary-rgb), 0.10), transparent 38%),
        rgba(8, 16, 24, 0.72);
      flex-shrink: 0;
    }

    .search-bar input {
      width: 100%;
      padding: 13px 17px;
      font-size: 14px;
      border: 1px solid rgba(var(--primary-rgb), 0.20);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.025);
      color: #f8fbff;
      outline: none;
      transition: border-color 0.25s ease, background 0.25s ease, box-shadow 0.25s ease;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.025);
    }

    .search-bar input:focus {
      border-color: rgba(var(--secondary-rgb), 0.52);
      background: rgba(var(--primary-rgb), 0.07);
      box-shadow: 0 0 0 3px rgba(var(--secondary-rgb), 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.04);
    }

    .search-bar input::placeholder {
      color: rgba(212, 225, 235, 0.42);
    }

    .content {
      flex: 1;
      overflow-y: auto;
      padding: 22px 24px 30px;
      scrollbar-width: thin;
      scrollbar-color: rgba(var(--primary-rgb), 0.28) transparent;
    }

    .content::-webkit-scrollbar {
      width: 7px;
    }

    .content::-webkit-scrollbar-thumb {
      background: rgba(var(--primary-rgb), 0.28);
      border-radius: 999px;
      border: 2px solid transparent;
      background-clip: padding-box;
    }

    .panel {
      display: none;
    }

    .panel.active {
      display: block;
      animation: panelFade 0.32s ease;
    }

    @keyframes panelFade {
      from {
        opacity: 0;
        transform: translateY(6px);
      }

      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .tier-group {
      margin-bottom: 12px;
    }

    .tier-group+.tier-group {
      border-top: 1px solid rgba(var(--secondary-rgb), 0.15);
      margin-top: 24px;
      padding-top: 24px;
    }

    .tier-group-body {
      padding: 0;
    }

    .sub-section {
      margin-bottom: 12px;
      border-radius: 15px;
      overflow: hidden;
      border: 1px solid transparent;
      transition: border-color 0.25s ease, background 0.25s ease;
    }

    .sub-section.depth-0 {
      background: linear-gradient(155deg, rgba(255, 255, 255, 0.022), rgba(var(--primary-rgb), 0.04));
      border-color: rgba(var(--primary-rgb), 0.14);
      box-shadow: 0 12px 34px rgba(0, 0, 0, 0.12);
    }

    .sub-section.depth-1,
    .sub-section.depth-2 {
      background: rgba(255, 255, 255, 0.014);
      border-color: rgba(255, 255, 255, 0.055);
      margin: 8px 3px;
    }

    .sub-section:hover {
      border-color: rgba(var(--primary-rgb), 0.27);
    }

    .sub-header {
      position: relative;
      display: flex;
      align-items: center;
      gap: 11px;
      padding: 14px 15px;
      cursor: pointer;
      user-select: none;
      transition: background 0.2s ease;
    }

    .sub-header:hover {
      background: rgba(var(--primary-rgb), 0.055);
    }

    .sub-header .arrow {
      width: 21px;
      height: 21px;
      border-radius: 7px;
      display: grid;
      place-items: center;
      font-size: 9px;
      color: rgba(235, 225, 194, 0.82);
      background: rgba(var(--secondary-rgb), 0.07);
      border: 1px solid rgba(var(--secondary-rgb), 0.18);
      transition: transform 0.24s ease, background 0.24s ease;
      flex-shrink: 0;
    }

    .sub-section:not(.collapsed)>.sub-header .arrow {
      transform: rotate(90deg);
      background: rgba(var(--secondary-rgb), 0.12);
    }

    .sub-title {
      font-family: "Noto Serif SC", "Kaiti SC", serif;
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: #edf1f3;
      flex: 1;
    }

    .depth-1 .sub-title,
    .depth-2 .sub-title {
      font-size: 14px;
      color: #b5c3ce;
      font-family: "DM Sans", "PingFang SC", sans-serif;
      font-weight: 600;
    }

    .sub-count {
      font-size: 11px;
      font-variant-numeric: tabular-nums;
      color: rgba(var(--secondary-rgb), 0.9);
      background: rgba(var(--secondary-rgb), 0.06);
      padding: 2px 7px;
      border-radius: 999px;
      border: 1px solid rgba(var(--secondary-rgb), 0.22);
    }

    .sub-section.collapsed>.sub-body {
      display: none;
    }

    .sub-body {
      padding: 2px 13px 13px;
    }

    .grid-group-label {
      position: relative;
      font-size: 11px;
      font-weight: 700;
      color: rgba(var(--secondary-rgb), 0.78);
      letter-spacing: 0.12em;
      padding: 11px 2px 7px 12px;
      margin-top: 2px;
      text-transform: uppercase;
    }

    .grid-group-label::before {
      content: "";
      position: absolute;
      left: 1px;
      top: 50%;
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: var(--secondary);
      box-shadow: 0 0 8px rgba(var(--secondary-rgb), 0.4);
    }

    .bk-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
      gap: 8px;
      padding: 3px 0 8px;
    }

    .bk-card {
      position: relative;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 11px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.025);
      border: 1px solid rgba(202, 220, 233, 0.075);
      text-decoration: none;
      color: #dde6ec;
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease, color 0.2s ease;
      overflow: hidden;
      min-height: 43px;
    }

    .bk-card:hover {
      color: #ffffff;
      background: linear-gradient(105deg, rgba(var(--primary-rgb), 0.16), rgba(var(--primary-rgb), 0.055));
      border-color: rgba(var(--primary-rgb), 0.34);
      box-shadow: 0 8px 22px rgba(0, 0, 0, 0.18), inset 2px 0 0 rgba(var(--secondary-rgb), 0.66);
      transform: translateY(-1px);
    }

    .bk-card img {
      width: 20px;
      height: 20px;
      border-radius: 6px;
      flex-shrink: 0;
      padding: 1px;
      background: rgba(255, 255, 255, 0.055);
      filter: saturate(0.82);
      transition: filter 0.2s ease, transform 0.2s ease;
    }

    .bk-card:hover img {
      filter: saturate(1.05);
      transform: scale(1.04);
    }

    .bk-name {
      font-size: 13px;
      line-height: 1.4;
      letter-spacing: 0.005em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .bk-card.loose {
      display: inline-flex;
      margin: 3px;
    }

    .nav-group {
      margin: 13px 0 7px;
    }

    .nav-group-header {
      padding: 11px 13px 6px;
      font-size: 11px;
      font-weight: 700;
      color: rgba(var(--primary-rgb), 0.92);
      letter-spacing: 0.13em;
      user-select: none;
      display: flex;
      align-items: center;
    }

    .nav-group-items {
      display: flex;
      flex-direction: column;
      gap: 1px;
      border-left: 1px solid rgba(var(--primary-rgb), 0.10);
      margin-left: 14px;
      padding-left: 7px;
    }

    .nav-item.sub-item {
      min-height: 37px;
      padding: 8px 12px;
      margin: 1px 0;
      font-size: 13px;
      font-weight: 500;
      color: rgba(215, 228, 239, 0.61);
      background: transparent;
      border: 1px solid transparent;
      transition: all 0.2s ease;
    }

    .nav-item.sub-item:hover {
      color: #ffffff;
      background: rgba(var(--primary-rgb), 0.07);
      border-color: transparent;
    }

    .nav-item.sub-item.active {
      color: #ffffff;
      background: linear-gradient(90deg, rgba(var(--primary-rgb), 0.18), rgba(var(--primary-rgb), 0.045));
      border-color: rgba(var(--primary-rgb), 0.13);
      box-shadow: none;
      font-weight: 700;
    }

    .search-hidden {
      display: none !important;
    }

    mark {
      background: rgba(var(--secondary-rgb), 0.28);
      color: #fff9dc;
      border-radius: 2px;
      padding: 0 2px;
    }

    a:focus-visible,
    button:focus-visible,
    input:focus-visible,
    .nav-item:focus-visible,
    .sub-header:focus-visible {
      outline: 2px solid rgba(var(--secondary-rgb), 0.78);
      outline-offset: 2px;
    }

    @media (max-width: 1080px) {
      .app-body {
        padding: 10px;
        gap: 10px;
      }

      .sidebar {
        width: 210px;
        min-width: 210px;
      }

      .content {
        padding: 18px;
      }
    }

    .mobile-header {
      display: none;
    }

    .sidebar-overlay {
      display: none;
    }

    @media (max-width: 768px) {
      body {
        flex-direction: column;
      }

      .app-body {
        flex-direction: column;
        padding: 0;
        gap: 0;
      }

      .mobile-header {
        display: flex;
        flex: none;
        width: 100%;
        align-items: center;
        justify-content: space-between;
        padding: 11px 18px;
        background: rgba(8, 17, 26, 0.96);
        border-bottom: 1px solid var(--line-soft);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.16);
        backdrop-filter: blur(16px);
        z-index: 1000;
        position: sticky;
        top: 0;
      }

      .mobile-header .brand-mark {
        width: 35px;
        height: 35px;
      }

      .mobile-header .brand-name {
        font-size: 18px;
      }

      .mobile-header .brand-tagline {
        display: none;
      }

      .homepage-toast {
        right: 20px;
        bottom: 20px;
      }

      .hamburger-btn {
        width: 38px;
        height: 38px;
        display: grid;
        place-items: center;
        background: rgba(var(--primary-rgb), 0.06);
        border: 1px solid rgba(var(--primary-rgb), 0.15);
        border-radius: 10px;
        color: #e8eef2;
        font-size: 21px;
        cursor: pointer;
        transition: background 0.2s ease, border-color 0.2s ease;
      }

      .hamburger-btn:hover {
        background: rgba(var(--primary-rgb), 0.13);
        border-color: rgba(var(--primary-rgb), 0.32);
      }

      .sidebar {
        position: fixed;
        left: -280px;
        top: 0;
        bottom: 0;
        width: 268px;
        min-width: 268px;
        z-index: 1001;
        transition: left 0.3s ease;
        border-radius: 0;
        padding-top: 18px;
        box-shadow: 18px 0 54px rgba(0, 0, 0, 0.48);
      }

      .sidebar.open {
        left: 0;
      }

      .sidebar-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(2, 8, 13, 0.72);
        backdrop-filter: blur(3px);
        z-index: 1000;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.3s ease;
      }

      .sidebar-overlay.open {
        display: block;
        opacity: 1;
        pointer-events: auto;
      }

      .sidebar-title {
        display: none;
      }

      .main {
        width: 100%;
        padding: 10px;
        border: 0;
        border-radius: 20px 20px 0 0;
        box-shadow: none;
        background: rgba(8, 17, 25, 0.94);
      }

      .main::before {
        left: 40px;
        right: 40px;
      }

      .search-bar {
        padding: 18px 16px 16px;
        border-radius: 15px 15px 0 0;
      }

      .content {
        padding: 16px 14px 24px;
      }

      .sub-header {
        padding: 13px 13px;
      }

      .sub-body {
        padding: 2px 11px 12px;
      }

      .sub-title {
        font-size: 16px;
      }
      
      .bk-grid {
        grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
        gap: 8px;
      }

      .bk-card {
        min-height: 46px;
        padding: 10px;
      }

      .site-footer {
        padding: 11px 10px 12px;
        font-size: 10px;
      }
    }

    @media (max-width: 420px) {
      .bk-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .bk-name {
        font-size: 12px;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        scroll-behavior: auto !important;
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
      }
    }
  </style>
  <script defer src="https://cloud.umami.is/script.js" data-website-id="7f657995-bcbb-47bc-aac7-6445d433598c"></script>
</head>

<body>
  <h1 class="seo-hidden">万象导航 - 精选高效工具与优质资源导航大全</h1>

  <div class="app-body">

  <div class="mobile-header">
    <a class="brand-lockup" href="/" aria-label="万象导航首页">
      <img class="brand-mark" src="logo.svg" alt="">
      <span class="brand-copy"><span class="brand-name">万象导航</span><span class="brand-tagline">EXPLORE EVERYTHING</span></span>
    </a>
    <button class="hamburger-btn" onclick="toggleMobileSidebar()">☰</button>
  </div>
  <div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleMobileSidebar(true)"></div>

  <div class="sidebar" id="sidebar">
    <div class="sidebar-title">
      <a class="brand-lockup" href="/" aria-label="万象导航首页">
        <img class="brand-mark" src="logo.svg" alt="">
        <span class="brand-copy"><span class="brand-name">万象导航</span><span class="brand-tagline">EXPLORE EVERYTHING</span></span>
      </a>
    </div>
    <a href="https://www.wenyaoyefei.com" target="_blank" class="homepage-btn">🏠 访问我的主页</a>
    <button type="button" class="set-home-btn" onclick="setAsHomepage()">⌂ 设为浏览器首页</button>
    ''' + nav_html + '''
  </div>

  <div class="homepage-toast" id="homepageToast" role="status" aria-live="polite"></div>

  <div class="main">
    <div class="search-bar">
      <input type="text" id="searchInput" placeholder="🔍 搜索书签... (Cmd+K)" autocomplete="off">
    </div>
    <div class="content" id="content">
      ''' + panels_html + '''
    </div>
  </div>

  <script>
    const homepageUrl = 'https://nav.wenyaoyefei.com/';
    let homepageToastTimer;

    function showHomepageToast(message) {
      const toast = document.getElementById('homepageToast');
      toast.textContent = message;
      toast.classList.add('show');
      clearTimeout(homepageToastTimer);
      homepageToastTimer = setTimeout(() => toast.classList.remove('show'), 6500);
    }

    function copyHomepageUrl() {
      if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(homepageUrl);
      }
      const input = document.createElement('textarea');
      input.value = homepageUrl;
      input.setAttribute('readonly', '');
      input.style.position = 'fixed';
      input.style.opacity = '0';
      document.body.appendChild(input);
      input.select();
      const copied = document.execCommand('copy');
      input.remove();
      return copied ? Promise.resolve() : Promise.reject(new Error('copy failed'));
    }

    function setAsHomepage() {
      const confirmed = window.confirm('是否将万象导航设为浏览器首页？');
      if (!confirmed) return;

      // 兼容仍支持 setHomePage 的旧版浏览器。
      try {
        document.body.style.behavior = 'url(#default#homepage)';
        if (document.body && typeof document.body.setHomePage === 'function') {
          document.body.setHomePage(homepageUrl);
          showHomepageToast('已将万象导航设为浏览器首页。');
          return;
        }
      } catch (error) {
        // 现代浏览器不提供网页修改主页的权限，继续使用引导流程。
      }

      const ua = navigator.userAgent;
      let guide = '请在浏览器设置的“主页”或“启动时”选项中粘贴。';
      if (/Edg\//.test(ua)) {
        guide = '请打开 Edge 设置 → 开始、主页和新建标签页 → 打开以下页面，并粘贴网址。';
      } else if (/Chrome\//.test(ua)) {
        guide = '请打开 Chrome 设置 → 启动时 → 打开特定网页，并粘贴网址。';
      } else if (/Firefox\//.test(ua)) {
        guide = '请打开 Firefox 设置 → 主页 → 主页和新窗口，并粘贴网址。';
      } else if (/Safari\//.test(ua)) {
        guide = '请打开 Safari 设置 → 通用 → 主页，并粘贴网址。';
      }

      copyHomepageUrl()
        .then(() => showHomepageToast('万象导航网址已复制。' + guide))
        .catch(() => showHomepageToast('请复制 ' + homepageUrl + '，然后' + guide));
    }

    function toggleMobileSidebar(forceClose = false) {
      const sidebar = document.getElementById('sidebar');
      const overlay = document.getElementById('sidebarOverlay');
      if (forceClose || sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
      } else {
        sidebar.classList.add('open');
        overlay.classList.add('open');
      }
    }

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
      if (window.innerWidth <= 768) {
        toggleMobileSidebar(true);
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
      content.querySelectorAll('.bk-card, .sub-section, .tier-group').forEach(el => el.classList.add('search-hidden'));

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

    // ── URL 参数搜索支持（配合 JSON-LD SearchAction）──
    (function() {
      const params = new URLSearchParams(window.location.search);
      const q = params.get('q');
      if (q && searchInput) {
        searchInput.value = q;
        searchInput.dispatchEvent(new Event('input'));
      }
    })();
  </script>
  </div><!-- end .app-body -->

  <footer class="site-footer">
    © 2025 Wenray | <a href="https://www.wenyaoyefei.com" target="_blank">🏠 访问我的主页</a> | <a href="https://nav.wenyaoyefei.com">万象导航</a>
  </footer>
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
