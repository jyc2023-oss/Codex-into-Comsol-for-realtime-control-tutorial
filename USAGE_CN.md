# COMSOL Shared-Session 使用文档（Windows）

本文档用于说明本项目中各个脚本的用途、典型用法、故障恢复方式，以及如何结合你已经写好的 `comsol-shared-session-guardrails` skill 持续工作。

适用目录：
`F:\simulation\Codex-into-Comsol-for-realtime-control-tutorial`

---

## 1. 目标与工作方式

本项目采用“共享会话”模式：
1. COMSOL Server 运行在本机（默认 `127.0.0.1:2036`）。
2. COMSOL GUI 连接同一个 Server，用于可视化和人工检查。
3. Python 脚本（`mph`）也连接同一个 Server，用于自动化改参/重建/求解。

---

## 2. 文件总览（你最常用的）

### 2.1 `start_server.bat`
用途：启动 COMSOL Server（多客户端模式）。

默认配置：
- COMSOL 路径：`D:\COMSOL\bin\win64\comsolmphserver.exe`
- 端口：`2036`
- 登录模式：`-login auto`

运行：
```bat
start_server.bat
```

---

### 2.2 `check_environment.py`
用途：检查环境是否满足基本要求。

检查内容：
1. Python 版本（>=3.10）
2. `mph` 是否可导入
3. `comsolmphserver.exe` 是否存在
4. Python 路径是否 ASCII（防 JPype/COMSOL 路径问题）
5. `127.0.0.1:2036` 是否可达

运行：
```powershell
.\.venv\Scripts\python.exe .\check_environment.py
```

---

### 2.3 `shared_session.py`
用途：一次性命令执行（连接 -> 操作 -> 断开）。

常见参数：
- `--set-param NAME VALUE`：设置参数
- `--build`：重建
- `--solve`：求解
- `--model-index`：指定模型索引
- `--save-as`：另存为

示例：
```powershell
.\.venv\Scripts\python.exe .\shared_session.py --port 2036 --set-param Ip "20[A]" --solve
```

说明：
脚本已增加 `finally -> client.disconnect()`，异常退出时也会尽量释放连接，减少残留占用。

---

### 2.4 `resident_control.py`
用途：常驻控制台（长连接），避免反复短连短断。

启动：
```powershell
.\.venv\Scripts\python.exe .\resident_control.py --port 2036
```

进入后常用命令：
1. `models`
2. `use 0`
3. `params`
4. `set Ip 20[A]`
5. `build`
6. `solve`
7. `eval mf.normB`
8. `exit`

说明：
该脚本也已增加退出时 `disconnect()`。

---

### 2.5 `session_guard.ps1`（核心恢复脚本）
用途：解决“长时求解/中断后残留 Python 进程导致假死或占用冲突”。

参数：
- `-Action status|cleanup|recover`
- `-Port`（默认 2036）
- `-ComsolServer`（默认 `D:\COMSOL\bin\win64\comsolmphserver.exe`）

动作说明：
1. `status`：查看监听、客户端连接、可疑 Python 控制进程。
2. `cleanup`：只清理残留 Python 控制进程，不重启 server。
3. `recover`：清理残留 + 重启 comsolmphserver + 输出新状态。

运行示例：
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\session_guard.ps1 -Action status -Port 2036
powershell -NoProfile -ExecutionPolicy Bypass -File .\session_guard.ps1 -Action cleanup -Port 2036
powershell -NoProfile -ExecutionPolicy Bypass -File .\session_guard.ps1 -Action recover -Port 2036
```

---

### 2.6 `session_guard.bat`
用途：`session_guard.ps1` 的 bat 包装器（更方便双击或命令行调用）。

示例：
```bat
session_guard.bat -Action status -Port 2036
session_guard.bat -Action cleanup -Port 2036
session_guard.bat -Action recover -Port 2036
```

---

## 3. 推荐工作流（每次开工照这个顺序）

1. 进入目录：
```powershell
cd F:\simulation\Codex-into-Comsol-for-realtime-control-tutorial
```

2. 先看状态：
```powershell
.\session_guard.bat -Action status -Port 2036
```

3. 如果有残留冲突，先清理：
```powershell
.\session_guard.bat -Action cleanup -Port 2036
```

4. 如果端口没监听或状态异常，直接恢复：
```powershell
.\session_guard.bat -Action recover -Port 2036
```

5. 环境自检：
```powershell
.\.venv\Scripts\python.exe .\check_environment.py
```

6. 开始操作模型：
- 单次命令用 `shared_session.py`
- 连续迭代优先用 `resident_control.py`

---

## 4. 常见问题与处理

### 4.1 `Server is in use by another client`
处理顺序：
1. 先执行 `session_guard cleanup`
2. 不行再 `session_guard recover`
3. 确认 GUI 是否正在强占会话（尤其正在求解时）

---

### 4.2 求解超时后后续都连不上
典型原因：残留 Python 控制进程。

处理：
```powershell
.\session_guard.bat -Action cleanup -Port 2036
```
若仍异常：
```powershell
.\session_guard.bat -Action recover -Port 2036
```

---

### 4.3 `InvalidPathException` / 路径乱码问题
原因：COMSOL Java 对非 ASCII 路径兼容差。

建议：
1. 模型放在 ASCII 路径，如 `F:\simulation\models\...`
2. 虚拟环境也尽量在 ASCII 路径

---

## 5. 你之前写好的 skill 怎么用

skill 文件：
`C:\Users\陈健伊\.codex\skills\comsol-shared-session-guardrails\SKILL.md`

skill 名称：
`comsol-shared-session-guardrails`

作用：
1. 固化共享会话稳定化步骤（先稳 server，再改模型）。
2. 明确处理 `Server is in use by another client`、超时残留、路径编码、B-H 非线性等高频坑。
3. 约束 B-H 曲线改造流程，避免循环依赖和错误写入。

在 Codex 中调用示例（直接发给助手）：
1. `请用 comsol-shared-session-guardrails 继续做 4.1`
2. `按 comsol-shared-session-guardrails 先做会话体检，再跑 40A`
3. `请严格按 comsol-shared-session-guardrails 处理 Server is in use 问题`

---

## 6. 一组最短可用命令（可直接复制）

```powershell
cd F:\simulation\Codex-into-Comsol-for-realtime-control-tutorial
.\session_guard.bat -Action recover -Port 2036
.\.venv\Scripts\python.exe .\check_environment.py
.\.venv\Scripts\python.exe .\shared_session.py --port 2036 --set-param Ip "20[A]" --solve
```

如需持续迭代：
```powershell
.\.venv\Scripts\python.exe .\resident_control.py --port 2036
```

