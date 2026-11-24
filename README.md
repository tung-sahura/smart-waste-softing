# 智能垃圾分拣上位机

基于 PyQt5、Ultralytics YOLO 和二进制串口/TCP 协议实现的智能垃圾分拣上位机。系统可读取视频或摄像头画面，在后台线程中执行真实 YOLO 推理，通过分拣状态机与模拟下位机或实际下位机通信，并在界面中展示检测结果、分类统计、输入源状态和原始 TX/RX 数据帧。

截至 **2026-11-24**：

- 30 个公开测试全部通过；
- `assets/assessment_demo.mp4` 干净闭环验收通过；
- 四类垃圾均有完整 `WASTE_RESULT → ACK → ACTION_DONE` 记录；
- Windows 摄像头切换、断流重连和最小窗口缩放已完成实际验证。

## 功能概览

- **视频输入**：导入指定视频，支持开始、暂停、跳转、继续播放和重新播放。
- **摄像头输入**：支持 Linux 摄像头编号、本地网络流和 Windows 摄像头转流。
- **YOLO 推理**：实际调用 `Predict/best.pt`，将模型类别映射为四类垃圾，并按置信度排序。
- **后台处理**：视频读取和模型推理在独立 Qt 工作线程中执行，不阻塞界面主线程。
- **通信协议**：支持半包、粘包、噪声、错误校验和重新同步。
- **分拣状态机**：连续 3 帧稳定后发送动作，处理 ACK、超时重发、满载、压缩和错误状态。
- **可靠计数**：仅在收到对应 `ACTION_DONE` 后更新分类数量。
- **通信日志**：界面直接显示命令名称、序号和原始十六进制报文。
- **响应式界面**：窗口缩放后主要操作仍可使用，右侧信息区支持滚动。

## 系统架构

```text
Windows 摄像头
    │ FFmpeg + RTSP
    ▼
MediaMTX ─────────────┐
                      ▼
视频文件 ────────> FrameSource
                      │
                      ▼
               SortingWorker（后台线程）
                      │
                      ├──> YoloDetector ──> Predict/best.pt
                      │
                      ├──> SortingController
                      │          │
                      │          ├──> TcpTransport ──> 模拟下位机
                      │          └──> SerialTransport ──> Nano / 串口下位机
                      │
                      └──> Qt Signals ──> PyQt 主界面
```

检测循环只负责获取画面和生成识别结果。是否发送动作由状态机决定，超时重发继续使用原序号；下位机返回匹配的 `ACTION_DONE` 后，界面才增加对应分类计数。

## 快速启动

推荐使用 Docker Desktop，避免 Windows 本机 Python、OpenCV 和 PyQt 环境差异。首次从 GitHub 复现时按以下顺序执行：

```powershell
git clone https://github.com/tung-sahura/smart-waste-softing.git
cd smart-waste-softing
docker compose up --build -d
docker compose exec app python3 -m unittest discover -s tests -v
```

这些命令也记录在 [MEMO.md](MEMO.md) 中。如果本机已经有项目，进入项目根目录后只需执行后两条 Docker 命令。

`--build` 会重新构建 `app` 镜像，确保容器使用当前源代码。启动过程可能需要等待 YOLO 权重和界面完成加载。检查容器状态：

```powershell
docker compose ps
```

正常情况下会看到：

- `app`：PyQt 界面、YOLO 和主程序；
- `lower-sim`：TCP 下位机模拟器，状态为 healthy；
- `camera-stream`：Windows 摄像头的 RTSP 转发服务。

## Docker 网页界面

容器启动后，在浏览器打开：

```text
http://localhost:6080/vnc.html?autoconnect=1&resize=scale
```

程序默认自动加载并处理 `assets/assessment_demo.mp4`。界面底部可以导入视频、打开摄像头、播放宣传视频、暂停/继续识别、重置统计和退出程序。

停止容器：

```powershell
docker compose down
```

## 测试

所有公开测试都在 Docker 的 `app` 容器内运行：

```powershell
docker compose exec app python3 -m unittest discover -s tests -v
```

全部通过时终端末尾显示：

```text
Ran 30 tests in ...
OK
```

| 测试文件 | 数量 | 覆盖内容 |
|---|---:|---|
| `test_protocol.py` | 9 | 编码、长度、校验和、半包、粘包、噪声和重新同步 |
| `test_controller.py` | 7 | 稳定识别、ACK/重发、冷却期、满载、错误回复和压缩 |
| `test_cv_detector.py` | 5 | 视频读取/跳转/重播、YOLO 接口和未知类别 |
| `test_yolo_adapter.py` | 3 | 多目标转换与排序、空结果和批量数组格式 |
| `test_frame_sources.py` | 1 | 网络摄像头断流重连 |
| `test_ui_smoke.py` | 4 | 主界面控件、状态反馈和 TX/RX 日志 |
| `test_promo_player.py` | 1 | 宣传视频后台解码 |

测试详情见 [tests/README.md](tests/README.md)。公开测试是基础逻辑验证，不能完全替代摄像头、完整 Docker 闭环和 Nano 硬件验收；现场还可能有未公开边界测试。

### 已完成的闭环验收

干净重启 `app` 和 `lower-sim` 后，考核视频产生 6 个不同序号的动作：

- 可回收垃圾 3 次；
- 厨余垃圾 1 次；
- 有害垃圾 1 次；
- 其他垃圾 1 次；
- 每个序号均收到一次 `ACK` 和一次 `ACTION_DONE`；
- 界面最终统计与 `ACTION_DONE` 数量一致。

验收截图：

- [完整闭环与统计](docs/images/full-cycle.png)
- [TX/RX 命令日志](docs/images/communication-log.png)
- [摄像头接入（画面已隐私遮罩）](docs/images/camera-connected-sanitized.png)
- [摄像头断流提示](docs/images/camera-reconnecting.png)
- [最小窗口 980×680（画面已隐私遮罩）](docs/images/ui-resized-980x680.png)

## 操作说明

### 视频文件

1. 点击“导入视频”；
2. 选择 `assets/assessment_demo.mp4` 或 `vedio/dep.mp4`；
3. 点击“开始识别”；
4. 使用进度条跳转，点击“暂停识别”暂停；
5. 视频结束后点击“重新播放”从头开始。

### Windows 摄像头

Docker Desktop 的 Linux 容器无法直接访问 Windows 摄像头，因此项目通过 FFmpeg、MediaMTX 和 RTSP 完成转流：

```text
Windows FFmpeg
    → 127.0.0.1:8555
    → camera-stream 容器（MediaMTX）
    → rtsp://camera-stream:8554/camera
    → app 容器中的 OpenCV
```

首次使用需安装 FFmpeg：

```powershell
winget install -e --id Gyan.FFmpeg
```

保持 Docker 运行，然后启动摄像头推流：

```powershell
.\scripts\start-camera-stream.ps1
```

也可以双击 `scripts\start-camera-stream.cmd`。看到 `Publish URL` 和
`Waiting for the Docker app` 后，在 Docker 网页中点击“打开摄像头”。程序会自动开始识别，并保持推流窗口运行。

脚本默认设备为 `HP True Vision FHD Camera`，以 1280×720、30fps 采集，以 15fps 通过 RTSP 推送。端口只绑定在 `127.0.0.1:8555`，不需要向校园网开放。

如果设备名称不同：

```powershell
ffmpeg -list_devices true -f dshow -i dummy
.\scripts\start-camera-stream.ps1 -DeviceName "你的摄像头名称"
```

摄像头无画面时，优先检查笔记本物理隐私拨片、键盘摄像头开关、Windows 相机权限和推流窗口是否仍运行。

### 下位机通信

Docker 默认连接 `lower-sim:9000`。切换为 Nano 串口时，可通过命令参数选择：

```text
--transport serial --serial-port /dev/ttyUSB0 --baudrate 9600
```

协议帧格式、命令字和序号规则见 [PROTOCOL.md](PROTOCOL.md)。

## Jetson Nano

`Dockerfile.nano` 面向经典 Jetson Nano 的 JetPack 4.x/L4T 32.x，基于 Ultralytics Jetson JetPack 4 镜像：

```bash
cat /etc/nv_tegra_release
docker compose -f compose.yaml -f compose.nano.yaml up --build
```

实际使用摄像头或串口时，需要按板卡设备增加 `/dev/video0` 或 `/dev/ttyUSB0` 映射。普通电脑完成考核不要求 Nano 硬件；当前 Nano 镜像尚未在实体板卡上完成 GPU、摄像头和串口验证。

## 项目结构

```text
app/
  main.py              程序入口和命令行参数
  ui.py                PyQt 主界面
  worker.py            后台读取、推理和通信线程
  detectors.py         YOLO 权重调用与结果转换
  controller.py        分拣状态机
  protocol.py          二进制帧编码与流解析
  transport.py         TCP/串口传输
  frame_sources.py     视频、摄像头和网络流输入
vedio/
  video_module.py      原项目视频读取、跳转和重播
simulator/
  lower_simulator.py   TCP 下位机模拟器
tests/                 30 个公开测试
assets/                考核演示视频
Predict/best.pt        比赛 YOLO 权重
docker/start-ui.sh     Xvfb、VNC 和程序启动脚本
compose.yaml           普通电脑 Docker 环境
compose.nano.yaml      Jetson Nano 覆盖配置
docs/images/           脱敏后的验收截图
```

## 本地运行（可选）

优先使用 Docker。确实需要在本机调试时，可使用 Python 3.8：

```bash
python -m pip install -r requirements-local.txt
python -m simulator.lower_simulator
python -m app.main --auto-start
```

## 已知限制

- Windows 摄像头需要额外运行 FFmpeg 推流脚本；
- Jetson Nano 配置尚需在实体板卡上验证；
- CPU 推理帧率取决于电脑性能，Docker 镜像体积也相对较大；
- 公开测试主要覆盖软件逻辑，最终验收仍需完成实物摄像头、完整闭环和现场问辩。

## 考核约束

- 必须实际调用 `Predict/best.pt`，不得使用颜色阈值、标注文件或固定答案代替推理。
- 视频读取和 YOLO 推理不得阻塞 Qt 主线程。
- 同一物体未离开画面时不得重复发送动作。
- 超时重发必须使用原序号。
- 计数只能在收到匹配的 `ACTION_DONE` 后增加。
- 不得删除或绕过公开测试。
- 不得提交虚拟环境、Docker 镜像或额外的大体积模型。

最终还需提交 3～4 分钟连续运行录屏、6～10 页 16:9 PPT、可访问的 GitHub 仓库，并准备现场代码讲解和问辩。具体评分和现场验收要求以考核通知为准。
