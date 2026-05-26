# Codex 接入 COMSOL 实时控制教程

通过 Python `mph` 库将 AI 编程助手（Codex / Claude Code 等）接入本地 COMSOL Server，实现参数修改、求解、结果读取的自动化控制，同时保持 COMSOL GUI 实时可视化。

---

## 工作原理

```
COMSOL Server（本机 2036 端口）
    ├── COMSOL GUI      → 可视化查看、手动调整、保存文件
    └── Python (mph)    → AI 助手自动改参 / 求解 / 读取结果
```

三者共享同一个 Server 内存中的模型对象，互相可以看到对方的修改。

---

## 环境要求

- COMSOL Multiphysics 6.4+（需含 COMSOL Server）
- Python 3.10+
- `mph` 包（`pip install mph`）

---

## 快速开始

### 第一步：启动 COMSOL Server

```bat
start_server.bat
```

必须以多客户端模式启动（`-multi on`），否则 GUI 和 Python 同时连接时会报 `Server is in use by another client`。

### 第二步：GUI 连接 Server

打开 COMSOL GUI → 文件 → 连接到服务器 → `127.0.0.1:2036`，然后在 GUI 中打开模型。

### 第三步：检查环境

```powershell
.\.venv\Scripts\python.exe .\check_environment.py
```

检查 Python 版本、mph、COMSOL 路径、端口连通性。

### 第四步：控制模型

**单次命令（适合一次性操作）：**

```powershell
.\.venv\Scripts\python.exe .\shared_session.py --port 2036 --set-param Ip "20[A]" --solve
```

**常驻控制台（适合连续迭代）：**

```powershell
.\.venv\Scripts\python.exe .\resident_control.py --port 2036
```

进入后可用命令：`models` / `use 0` / `params` / `set Ip 20[A]` / `build` / `solve` / `eval mf.normB` / `exit`

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `start_server.bat` | 启动多客户端 COMSOL Server |
| `shared_session.py` | 单次命令执行脚本（连接→操作→断开） |
| `resident_control.py` | 常驻长连接控制台 |
| `session_guard.ps1` | 会话故障恢复脚本（清理残留进程、重启 Server） |
| `session_guard.bat` | `session_guard.ps1` 的 bat 包装器 |
| `check_environment.py` | 环境自检 |
| `check_session_health.py` | 会话健康检查 |
| `USAGE_CN.md` | 详细使用文档 |

---

## 故障处理

**`Server is in use by another client`**

```bat
session_guard.bat -Action cleanup -Port 2036
```

若仍异常，重启 Server：

```bat
session_guard.bat -Action recover -Port 2036
```

**查看当前会话状态：**

```bat
session_guard.bat -Action status -Port 2036
```

---

## 文件锁问题

共享 Session 模式下，建议 Python 只操作 Server 内存中的模型对象，最终由 GUI 保存文件，避免 `.mph` 文件被同时占用。

---

## 推荐工作流

```powershell
# 1. 启动
start_server.bat

# 2. 检查状态
session_guard.bat -Action status -Port 2036

# 3. 环境自检
.\.venv\Scripts\python.exe .\check_environment.py

# 4. 开始操作
.\.venv\Scripts\python.exe .\resident_control.py --port 2036
```
