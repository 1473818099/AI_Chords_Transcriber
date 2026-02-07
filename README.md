# web-chord

本项目提供一个本地 Web UI + Python 后端，用于运行 **ISMIR2019-Large-Vocabulary-Chord-Recognition** 和弦识别，并把识别结果以“时间轴对齐的和弦块”方式可视化展示。

## 功能

- 前端：上传音频 → 调用后端分析 → 展示和弦段落（timecode-synced chord blocks）
- 后端：FastAPI 提供接口
  - `POST /analyze`
  - `GET /health`

---

## 目录结构

- `backend/server.py`：FastAPI 后端（`POST /analyze`, `GET /health`）
- `backend/requirements.txt`：后端依赖
- `backend/ISMIR2019-Large-Vocabulary-Chord-Recognition/`：放置 ISMIR2019 识别仓库（本项目不包含该仓库）
- `public/index2.html`：前端 UI
- `start.sh`：一键启动后端 + 前端

---

## 依赖

- Python（建议使用 conda/miniforge 环境，确保能安装依赖）
- （推荐）ffmpeg：用于音频转码/兼容更多格式

macOS 安装 ffmpeg：
```bash
brew install ffmpeg
```

---

## 启动步骤（本地）

1) 放置 ISMIR2019 仓库  
把 **ISMIR2019-Large-Vocabulary-Chord-Recognition** 放到以下路径（必须是这个目录名）：

```
web-chord/backend/ISMIR2019-Large-Vocabulary-Chord-Recognition/
```

2) 进入项目目录并启动

```bash
cd web-chord
chmod +x start.sh
./start.sh
```

3) 打开前端页面（默认）

- 前端：
  - `http://127.0.0.1:5173/index2.html`
- 后端（健康检查）：
  - `http://127.0.0.1:8710/health`

---

## 可选环境变量

如果你把 ISMIR2019 仓库放在别处，设置：

```bash
export CHORD_REPO_DIR="/path/to/ISMIR2019-Large-Vocabulary-Chord-Recognition"
```

一些常见端口/绑定（如果 `start.sh` 支持读取）：

```bash
export BACKEND_HOST="127.0.0.1"
export BACKEND_PORT="8710"
export FRONTEND_HOST="127.0.0.1"
export FRONTEND_PORT="5173"
```

---

## 常见问题排查

1) 前端提示 `network error` / 控制台 `ERR_CONNECTION_REFUSED`  
通常是后端没有跑起来或已崩溃。

- 先用浏览器访问：
  - `http://127.0.0.1:8710/health`
- 若打不开：
  - 说明后端未监听该端口（进程退出/崩溃/端口被占用）
  - 请回到终端查看 `./start.sh` 输出
  - 若项目生成了 `backend.log`，优先查看其末尾报错信息（如果你的 start.sh 有写日志）

2) `CORS policy` 且 origin 显示 `null`  
通常是用 `file://` 方式直接打开了 html 文件。请确保通过脚本启动的本地静态服务器访问：

- ✅ `http://127.0.0.1:5173/index2.html`
- ❌ `file:///.../public/index2.html`

---

## Run（快速复述）

```bash
cd web-chord
chmod +x start.sh
./start.sh
# open: http://127.0.0.1:5173/index2.html
```
