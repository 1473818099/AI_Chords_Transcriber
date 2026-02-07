# AI_Chords_Transcriber

本项目提供一个本地 Web UI + Python 后端，用于运行 **ISMIR2019-Large-Vocabulary-Chord-Recognition** 和弦识别，并把识别结果以“时间轴对齐的和弦块”方式可视化展示。

## 功能

- 前端：上传音频 → 调用后端分析 → 展示和弦段落（timecode-synced chord blocks）
- 后端：FastAPI 提供接口
  - `POST /analyze`
  - `GET /health`

---

## 安装步骤

克隆:
 https://github.com/music-x-lab/ISMIR2019-Large-Vocabulary-Chord-Recognition

---

## 依赖

将 上述链接 丢给GPT, 询问需要安装的环境配置, 依步骤安装.


---

## 启动步骤（本地）

1) 放置 ISMIR2019 仓库  
把克隆后的 **ISMIR2019-Large-Vocabulary-Chord-Recognition** 放到以下路径（必须是这个目录名）：

```
AI_Chords_Transcriber/backend/ISMIR2019-Large-Vocabulary-Chord-Recognition/
```

2) 进入项目目录并启动

```bash
cd AI_Chords_Transcriber
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