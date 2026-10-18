# 扫雷 (Minesweeper)

经典复古风格的现代网页版扫雷游戏，纯原生 HTML5 / CSS3 / Vanilla JS 实现，零外部依赖，极速加载。

- 🌐 **在线访问**: [https://ms.505250.xyz](https://ms.505250.xyz)
- ☁️ **部署平台**: Cloudflare Workers (Static Assets)

---

## 功能特性

- **三种难度模式**：初级（9×9, 10雷）、中级（16×16, 40雷）、高级（16×30, 99雷）
- **首次点击安全保底**：首点击区域绝不生成地雷
- **和弦双击支持**：已翻开数字若周围插旗数符合，双击/点击即可自动快翻周围空白
- **移动端触控优化**：自适应格子大小与屏幕宽度，支持长按插旗与触控操作
- **计时器与表情反馈**：实时显示剩余雷数、用时秒数及状态表情（🙂 / 😵 / 😎）

---

## 目录结构

```text
minesweeper/
├── public/                 # 静态资源发布目录（Cloudflare 托管）
│   ├── index.html          # 首页入口
│   ├── minesweeper.html    # 别名入口
│   ├── favicon.svg         # 高清矢量 Favicon 图标
│   ├── favicon.ico         # 多分辨率兼容 ICO 图标 (16/32/48px)
│   └── apple-touch-icon.png# 移动端触控高清图标 (180px)
├── deploy.py               # Cloudflare Workers API 自动化一键部署脚本
├── wrangler.jsonc          # Cloudflare 部署与自定义域名路由配置
├── package.json            # 辅助命令脚本
└── .gitignore
```

---

## 本地开发与重新部署

### 1. 本地预览开发

```bash
python3 -m http.server 8080 --directory public
# 或 npm run dev
```

### 2. 一键发布更新至 Cloudflare

修改代码后，执行以下命令即可自动完成资源打包与全网部署：

```bash
python3 deploy.py
# 或 npm run deploy
```

发布后将自动推送到 Cloudflare 边缘节点，并在自定义域名 `https://ms.505250.xyz` 生效。
