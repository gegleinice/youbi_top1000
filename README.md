# Top1000 达人数据采集与可视化

本项目包含两部分：
- 数据采集：从 `https://matrix.sbapis.com/b/tiktok/top` 分页抓取达人数据。
- 可视化看板：单页 HTML 仪表盘，支持搜索、筛选、排序与榜单查看。

## 目录结构

- `scripts/fetch_top1000.py`：采集脚本（分页、重试、去重、raw 落盘、汇总输出）
- `data/raw/`：每页原始响应
- `data/top1000.json`：规范化汇总数据
- `dashboard/index.html`：看板入口
- `dashboard/app.js`：看板逻辑
- `dashboard/styles.css`：看板样式

## 1) 采集数据

### 方式 A：环境变量

```bash
export CLIENT_ID="你的 clientid"
export TOKEN="你的 token"
python3 scripts/fetch_top1000.py
```

### 方式 B：命令行参数

```bash
python3 scripts/fetch_top1000.py \
  --clientid "你的 clientid" \
  --token "你的 token"
```

### 常用参数

- `--limit`：目标条数（默认 `1000`）
- `--start-page`：起始页（默认 `0`）
- `--max-pages`：最多抓取页数（默认 `1000`）
- `--query`：排序字段（默认 `followers`）

示例：

```bash
python3 scripts/fetch_top1000.py \
  --clientid "xxx" \
  --token "xxx" \
  --limit 1000 \
  --query followers
```

## 2) 启动可视化页面

在项目根目录启动静态服务：

```bash
python3 -m http.server 8000
```

浏览器打开：
- `http://localhost:8000/dashboard/`

注意：看板通过 `fetch` 读取 `data/top1000.json`，因此建议通过本地 HTTP 服务访问，不要直接双击 `index.html`。

## 3) 托管到 GitHub Pages（给别人看）

本仓库使用 **GitHub Pages（legacy，从 `main` 分支根目录发布静态文件）**。

### 公开访问地址

- `https://gegleinice.github.io/youbi_top1000/`（根路径会自动跳转到 `dashboard/`）
- `https://gegleinice.github.io/youbi_top1000/dashboard/`

### 数据文件说明

- 站点发布内容来自仓库根目录的静态文件：`index.html`、`dashboard/`、`data/top1000.json`
- `data/raw/` 已在 `.gitignore` 中忽略（体积大、且通常不需要公开）

### 安全提醒

不要把 API `token` / `clientid` 写进仓库或提交到 GitHub。采集请在本地执行，只提交 `data/top1000.json`（或你脱敏后的数据文件）。

### 说明：为什么不用 GitHub Actions 工作流发布？

在本机使用 `gh` 的默认 OAuth token 推送 `.github/workflows/*.yml` 往往需要额外的 `workflow` scope。
为减少你本地授权步骤，这里改为 **直接从 `main` 发布静态站点**（同样可公开访问）。

## 4) 数据刷新流程（一键思路）

每次更新数据只需两步：

1. 重新执行采集脚本生成 `data/top1000.json`
2. 刷新浏览器页面

可参考：

```bash
python3 scripts/fetch_top1000.py --clientid "xxx" --token "xxx"
python3 -m http.server 8000
```

## 5) 当前已知限制

- 当接口返回 `402 Payment Required` 时，脚本会优雅停止并保留已抓取结果。
- 停止原因会写入 `data/top1000.json` 的 `meta.stop_reason` 字段。
- 例如当前数据可能是 `500` 条（受接口额度限制），不是脚本故障。
