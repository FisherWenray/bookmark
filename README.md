# 万象导航

一个收录 5000+ 标签/链接的高颜值个人导航页，支持快速搜索与折叠分类。

🌐 在线访问：[nav.wenyaoyefei.com](https://nav.wenyaoyefei.com)

---

## 项目结构

```text
.
├── raw_bookmarks/                    # 原始书签文件夹
│   └── CheeseBookmarks_2025_08_25.html # 浏览器导出的原始书签备份
├── generate_nav.py                  # 书签导航页生成脚本（已升级高颜值模板）
├── index.html                       # 生成后的精美导航页面（终产物，部署于 GitHub Pages）
├── logo.svg                         # 万象导航矢量 Logo（页面与浏览器图标）
├── logo.png                         # 社交分享兼容用 PNG Logo
├── CNAME                            # 自定义域名配置文件
└── README.md                        # 本说明文档
```

---

## 快速开始：如何更新您的书签

当您需要在导航页中添加或修改书签时，请按照以下步骤操作：

### 1. 导出书签
在浏览器（Chrome/Edge/Firefox 等）中打开书签管理器，将您的书签导出为 **HTML 格式**，并保存至 `raw_bookmarks/` 目录下。

### 2. 生成新的导航页
在项目根目录下，使用 Python 3 运行生成脚本。
若在 Windows 系统下遇到 Emoji 字符编码问题，请使用下方对应的命令：

* **Windows (PowerShell)**:
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  python generate_nav.py raw_bookmarks/您的新书签.html index.html
  ```
* **macOS / Linux**:
  ```bash
  python3 generate_nav.py raw_bookmarks/您的新书签.html index.html
  ```

### 3. 本地预览
生成成功后，直接双击 `index.html` 或在浏览器中打开，即可在本地预览效果。

### 4. 提交部署
将更新后的 `index.html` 以及您的原始书签 HTML 文件提交并推送到 GitHub 仓库，GitHub Pages 会在几分钟内自动编译并更新到您的自定义域名：
```bash
git add index.html logo.svg logo.png raw_bookmarks/
git commit -m "update: 更新个人书签"
git push origin main
```

---

## 自定义与修改

* **替换 Logo**：以 `logo.svg` 作为页面主标志，并同步导出 `logo.png` 供社交分享兼容；品牌字标样式位于 `generate_nav.py`。
* **修改主色调**：您可以在 `generate_nav.py` 的第 18-21 行中修改 HSL / RGB 的主色与辅色变量：
  * 主色 `--primary` (默认 `#5D7B93`)
  * 辅色 `--secondary` (默认 `#c5b358`)
* **自定义脚本规则**：如果您需要优化页面排版或增加新的动画，可以直接修改 `generate_nav.py` 底部的 HTML 模板字符串。
