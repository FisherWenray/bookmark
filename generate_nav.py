#!/usr/bin/env python3
"""
书签导航页生成器 v3 - JSON 数据驱动 + Lazy Rendering
左侧竖导航 + 右侧内容区 + 响应式多列书签网格

用法: python3 generate_nav.py [书签.html] [输出.html]
"""

import sys
import re
import json
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

def esc(text: str) -> str:
    return html_lib.escape(text, quote=True)

def get_level1_folders(bookmarks: list) -> list:
    for item in bookmarks:
        if isinstance(item, dict) and item.get("toolbar"):
            return item.get("children", [])
    
    folders = [item for item in bookmarks if isinstance(item, dict) and "folder" in item]
    if len(folders) == 1:
        f_name = folders[0]["folder"].strip()
        if f_name in ["书签栏", "Bookmarks Bar", "Favorites Bar", "Favorites", "Bookmarks", "书签"]:
            return folders[0].get("children", [])
            
    return bookmarks

def extract_separator_label(title: str) -> str:
    return re.sub(r'[─━\-=\s]+', '', (title or "").strip())

# ─────────────────── 数据处理 ───────────────────
def process_node(node, depth=0, parent_titles=None):
    if parent_titles is None:
        parent_titles = []

    if isinstance(node, dict):
        if is_separator(node):
            clean = extract_separator_label(node.get("title", ""))
            return {"type": "separator", "label": clean}
        elif "folder" in node:
            folder_name = node["folder"]
            new_parent_titles = parent_titles + [folder_name]
            children = node.get("children", [])
            processed_children = []
            
            for child in children:
                pc = process_node(child, depth + 1, new_parent_titles)
                if pc:
                    processed_children.append(pc)
                    
            if not processed_children:
                return None

            is_leaf = all(c.get("type") != "folder" for c in processed_children)

            return {
                "type": "folder",
                "folder": folder_name,
                "is_leaf": is_leaf,
                "children": processed_children
            }
        elif "url" in node:
            title = node.get("title", "")
            url = node.get("url", "")
            favicon = get_favicon_url(url)
            return {
                "type": "link",
                "title": title,
                "url": url,
                "favicon": favicon,
                "path": " > ".join(parent_titles)
            }
    return None

def build_flat_index(processed_nodes):
    flat = []
    def traverse(nodes):
        for n in nodes:
            if n["type"] == "link":
                flat.append({
                    "title": n["title"],
                    "url": n["url"],
                    "favicon": n["favicon"],
                    "path": n.get("path", "")
                })
            elif n["type"] == "folder":
                traverse(n["children"])
    traverse(processed_nodes)
    return flat

def generate_nav_html(bookmarks: list) -> str:
    level1 = get_level1_folders(bookmarks)
    
    panels_data = []
    nav_items = []
    
    idx = 0
    total_links = 0
    for item in level1:
        if not isinstance(item, dict) or "folder" not in item or is_separator(item):
            continue
        
        folder_name = item["folder"]
        raw_children = item.get("children", [])
        
        processed_children = []
        for child in raw_children:
            pc = process_node(child, depth=0, parent_titles=[folder_name])
            if pc:
                processed_children.append(pc)
                
        panel_id = f"panel-{idx}"
        active = "active" if idx == 0 else ""
        
        nav_items.append(
            f'<div class="nav-item {active}" data-panel-idx="{idx}" data-panel="{panel_id}" onclick="switchPanel(this, {idx})">{esc(folder_name)}</div>'
        )
        
        panels_data.append({
            "id": panel_id,
            "folder": folder_name,
            "children": processed_children
        })
        
        idx += 1
        
    flat_index = []
    for p in panels_data:
        flat_index.extend(build_flat_index(p["children"]))
    total_links = len(flat_index)
    
    json_data = json.dumps(panels_data, ensure_ascii=False, separators=(',', ':'))
    json_index = json.dumps(flat_index, ensure_ascii=False, separators=(',', ':'))
    
    nav_html = "\n".join(nav_items)

    html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>数字驾驶舱 - 精选高效工具与优质资源导航</title>
  <meta name="description" content="一个收录了数千个精选网站、高效工具、优质资源的个人书签导航页，支持快捷搜索，一站式满足数字生产力需求。">
  <meta name="keywords" content="导航网站,书签导航,工具大全,资源搜索,数字驾驶舱,个人主页,wenyaoyefei">
  <meta property="og:title" content="数字驾驶舱 - 精选高效工具与优质资源导航">
  <meta property="og:description" content="收录数千个精选网站与高效工具的个人导航，快速查找各类数字资源。">
  <meta property="og:type" content="website">
  <meta property="og:image" content="https://nav.wenyaoyefei.com/logo.png">
  <meta property="og:url" content="https://nav.wenyaoyefei.com/">
  <link rel="canonical" href="https://nav.wenyaoyefei.com/" />
  <link rel="icon" href="logo.png" type="image/png">
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "数字驾驶舱 - 精选高效工具与优质资源导航",
    "url": "https://nav.wenyaoyefei.com/",
    "description": "一个收录了数千个精选网站、高效工具、优质资源的个人书签导航页，一站式满足数字生产力需求。"
  }
  </script>
  <style>
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

    /* 增加 search result active 样式 */
    .bk-card.active-focus {{
      background: linear-gradient(135deg, rgba(var(--primary-rgb), 0.42), rgba(var(--primary-rgb), 0.24));
      border-color: rgba(var(--primary-rgb), 0.86);
      box-shadow: 0 10px 18px rgba(0, 0, 0, 0.32);
      transform: translateY(-2px);
    }}
  </style>
  <script defer src="https://cloud.umami.is/script.js" data-website-id="7f657995-bcbb-47bc-aac7-6445d433598c"></script>
</head>
<body>
  <h1 class="seo-hidden">数字驾驶舱 - 精选高效工具与优质资源导航大全</h1>

  <nav class="sidebar">
    <h1 class="sidebar-title"><img class="sidebar-logo" src="logo.png" alt="书签导航 Logo"></h1>
    REPLACE_NAV_HTML
  </nav>

  <main class="main">
    <header class="search-bar">
      <input type="text" id="searchInput" placeholder="🔍 搜索书签... (Cmd+K)" autocomplete="off">
    </header>
    <div class="content" id="content">
      <!-- 动态渲染内容 -->
    </div>
  </main>

  <script>
    // 注入 JSON 数据
    window.bookmarkData = REPLACE_JSON_DATA;
    window.searchIndex = REPLACE_JSON_INDEX;

    const contentDiv = document.getElementById("content");
    const searchInput = document.getElementById("searchInput");
    let currentPanelIdx = 0;
    
    function escapeHtml(unsafe) {{
        return (unsafe || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }}

    function renderBookmarkGrid(items) {{
        let html = "";
        let currentGroupLabel = null;
        let currentGroupItems = [];

        function flushGroup() {{
            if (currentGroupItems.length === 0) return;
            if (currentGroupLabel) {{
                html += `<div class="grid-group-label">${{escapeHtml(currentGroupLabel)}}</div>`;
            }}
            html += `<div class="bk-grid">${{currentGroupItems.join("")}}</div>`;
            currentGroupItems = [];
            currentGroupLabel = null;
        }}

        for (let item of items) {{
            if (item.type === "separator") {{
                flushGroup();
                if (item.label) currentGroupLabel = item.label;
            }} else if (item.type === "link") {{
                currentGroupItems.push(`
                    <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener external nofollow" class="bk-card" title="${{escapeHtml(item.title)}}">
                        <img src="${{escapeHtml(item.favicon)}}" alt="" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22><rect width=%2232%22 height=%2232%22 rx=%226%22 fill=%22%23334155%22/><text x=%2216%22 y=%2222%22 text-anchor=%22middle%22 fill=%22%239ca3af%22 font-size=%2216%22>${{escapeHtml(item.title.charAt(0))}}</text></svg>'">
                        <span class="bk-name">${{escapeHtml(item.title)}}</span>
                    </a>
                `);
            }}
        }}
        flushGroup();
        return html;
    }}

    function renderSectionItems(items, depth) {{
        let html = "";
        for (let item of items) {{
            if (item.type === "separator") continue;
            
            if (item.type === "folder") {{
                let collapsed = depth === 0 ? "" : "collapsed";
                if (item.is_leaf) {{
                    let gridHtml = renderBookmarkGrid(item.children);
                    if (!gridHtml) continue;
                    let bkCount = item.children.filter(c => c.type === "link").length;
                    html += `
                        <div class="sub-section depth-${{depth}} ${{collapsed}}">
                            <div class="sub-header" onclick="toggleSub(this)">
                                <span class="arrow">▶</span>
                                <h3 class="sub-title">${{escapeHtml(item.folder)}}</h3>
                                <span class="sub-count">${{bkCount}}</span>
                            </div>
                            <div class="sub-body">${{gridHtml}}</div>
                        </div>
                    `;
                }} else {{
                    let inner = renderSectionContent(item.children, depth + 1);
                    if (!inner.trim()) continue;
                    html += `
                        <div class="sub-section depth-${{depth}} ${{collapsed}}">
                            <div class="sub-header" onclick="toggleSub(this)">
                                <span class="arrow">▶</span>
                                <h3 class="sub-title">${{escapeHtml(item.folder)}}</h3>
                            </div>
                            <div class="sub-body">${{inner}}</div>
                        </div>
                    `;
                }}
            }} else if (item.type === "link") {{
                html += `
                    <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener external nofollow" class="bk-card loose" title="${{escapeHtml(item.title)}}">
                        <img src="${{escapeHtml(item.favicon)}}" alt="" loading="lazy" onerror="this.style.display='none'">
                        <span class="bk-name">${{escapeHtml(item.title)}}</span>
                    </a>
                `;
            }}
        }}
        return html;
    }}

    function renderSectionContent(children, depth) {{
        if (depth !== 0) return renderSectionItems(children, depth);
        
        let hasSeparator = children.some(c => c.type === "separator");
        if (!hasSeparator) return renderSectionItems(children, depth);

        let grouped = [];
        let bufferItems = [];
        let pendingLabel = "";

        for (let item of children) {{
            if (item.type === "separator") {{
                if (bufferItems.length > 0) {{
                    grouped.push({{label: pendingLabel, items: bufferItems}});
                    bufferItems = [];
                }}
                pendingLabel = item.label;
                continue;
            }}
            bufferItems.push(item);
        }}
        if (bufferItems.length > 0) {{
            grouped.push({{label: pendingLabel, items: bufferItems}});
        }}

        let output = "";
        for (let group of grouped) {{
            let groupHtml = renderSectionItems(group.items, depth);
            if (!groupHtml.trim()) continue;
            output += `<section class="tier-group"><div class="tier-group-body">${{groupHtml}}</div></section>`;
        }}
        return output;
    }}

    // 缓存渲染结果
    const panelCache = {{}};

    function switchPanel(el, idx) {{
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        if(el) el.classList.add('active');
        
        currentPanelIdx = idx;
        
        if (panelCache[idx]) {{
            contentDiv.innerHTML = panelCache[idx];
        }} else {{
            let data = window.bookmarkData[idx];
            if (data) {{
                let html = `<section class="panel active" id="${{data.id}}">` + renderSectionContent(data.children, 0) + `</section>`;
                panelCache[idx] = html;
                contentDiv.innerHTML = html;
            }}
        }}
        contentDiv.scrollTop = 0;
    }}

    function toggleSub(header) {{
        header.parentElement.classList.toggle('collapsed');
    }}

    // ── 搜索引擎与按键导航 ──
    let searchResults = [];
    let focusedIndex = -1;

    function renderSearchResults(results, query) {{
        if (results.length === 0) {{
            contentDiv.innerHTML = `<div style="padding: 20px; color: var(--text-soft); text-align: center;">没有找到符合条件的书签 😅</div>`;
            return;
        }}
        
        let queryRegex = new RegExp('(' + query.replace(/[.*+?^${{}}()|[\]\\]/g, '\\$&') + ')', 'gi');
        
        let html = `<div class="grid-group-label" style="margin-bottom: 10px;">搜索结果 (${{results.length}})</div><div class="bk-grid" id="searchGrid">`;
        
        for (let i = 0; i < results.length; i++) {{
            let item = results[i];
            let titleHtml = escapeHtml(item.title).replace(queryRegex, '<mark>$1</mark>');
            let pathHtml = item.path ? `<div style="font-size: 10px; color: var(--text-soft); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${{escapeHtml(item.path)}}</div>` : '';
            
            html += `
                <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener external nofollow" class="bk-card search-card" data-index="${{i}}" title="${{escapeHtml(item.title)}}" style="flex-direction: column; align-items: flex-start; justify-content: center; padding: 8px 12px;">
                    <div style="display: flex; align-items: center; gap: 9px; width: 100%;">
                        <img src="${{escapeHtml(item.favicon)}}" alt="" loading="lazy" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22><rect width=%2232%22 height=%2232%22 rx=%226%22 fill=%22%23334155%22/><text x=%2216%22 y=%2222%22 text-anchor=%22middle%22 fill=%22%239ca3af%22 font-size=%2216%22>${{escapeHtml(item.title.charAt(0))}}</text></svg>'">
                        <span class="bk-name" style="width: calc(100% - 27px);">${{titleHtml}}</span>
                    </div>
                    ${{pathHtml}}
                </a>
            `;
        }}
        html += `</div>`;
        contentDiv.innerHTML = `<section class="panel active">${{html}}</section>`;
        focusedIndex = -1;
    }}

    function updateSearchFocus() {{
        let cards = document.querySelectorAll('.search-card');
        cards.forEach((c, idx) => {{
            if (idx === focusedIndex) {{
                c.classList.add('active-focus');
                c.scrollIntoView({{behavior: 'smooth', block: 'nearest'}});
            }} else {{
                c.classList.remove('active-focus');
            }}
        }});
    }}

    searchInput.addEventListener('input', function () {{
        const query = this.value.trim().toLowerCase();
        if (!query) {{
            // 恢复
            let activeNav = document.querySelector('.nav-item.active');
            if (activeNav) {{
                switchPanel(activeNav, currentPanelIdx);
            }} else {{
                switchPanel(document.querySelector('.nav-item'), 0);
            }}
            return;
        }}
        
        searchResults = window.searchIndex.filter(item => 
            item.title.toLowerCase().includes(query) || 
            item.url.toLowerCase().includes(query) || 
            (item.path && item.path.toLowerCase().includes(query))
        ).slice(0, 200); // 限制最多展示 200 条，保证性能

        renderSearchResults(searchResults, query);
    }});

    // ── 快捷键 ──
    document.addEventListener('keydown', function (e) {{
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {{
            e.preventDefault();
            searchInput.focus();
            searchInput.select();
        }}
        if (e.key === 'Escape') {{
            searchInput.value = '';
            searchInput.dispatchEvent(new Event('input'));
            searchInput.blur();
        }}
        
        // 搜索结果键盘导航
        if (document.activeElement === searchInput && searchInput.value.trim() && searchResults.length > 0) {{
            let cards = document.querySelectorAll('.search-card');
            let cols = 1; // 估算列数，目前响应式可能是 2-5 列，由于键盘操作复杂，暂做一维导航或简单二维估算
            // 简单化，上下左右都当作一维切换
            if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {{
                e.preventDefault();
                focusedIndex = Math.min(focusedIndex + 1, cards.length - 1);
                updateSearchFocus();
            }} else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {{
                e.preventDefault();
                focusedIndex = Math.max(focusedIndex - 1, 0);
                updateSearchFocus();
            }} else if (e.key === 'Enter') {{
                e.preventDefault();
                if (focusedIndex >= 0 && focusedIndex < cards.length) {{
                    cards[focusedIndex].click();
                }} else if (cards.length > 0) {{
                    cards[0].click(); // 默认回车打开第一个
                }}
            }}
        }}
    }});

    // 初始化加载第一屏
    window.addEventListener('DOMContentLoaded', () => {{
        let firstNav = document.querySelector('.nav-item');
        if (firstNav) switchPanel(firstNav, 0);
    }});
  </script>
</body>
</html>'''

    return html_template.replace("REPLACE_JSON_DATA", json_data).replace("REPLACE_JSON_INDEX", json_index).replace("REPLACE_NAV_HTML", nav_html), total_links

# ─────────────────── CLI ───────────────────

def main():
    html_path = sys.argv[1] if len(sys.argv) > 1 else "raw_bookmarks/RunningCheese_Bookmarks_2026_05_06.html"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "index.html"

    print(f"📖 正在解析书签: {html_path}")
    bookmarks = parse_bookmarks(html_path)

    print("🎨 正在生成纯数据驱动导航页 (JSON Lazy Rendering)...")
    nav_html, total_links = generate_nav_html(bookmarks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(nav_html)

    print(f"✓ 导航页已生成: {output_path}")
    print(f"  提取书签数: {total_links}")
    print(f"\n  open {output_path}")

if __name__ == "__main__":
    main()
