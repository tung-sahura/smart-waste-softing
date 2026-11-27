# 公开测试说明

这些测试覆盖视频输入、YOLO 适配、通信协议、分拣状态机、摄像头重连和界面反馈。测试应在 Docker 的 `app` 容器内运行。

```bash
docker compose exec app python3 -m unittest discover -s tests -v
```

截至 2026-11-27，35 个公开测试全部通过：

```text
Ran 35 tests in ...
OK
```

- `test_protocol.py`：半包、粘包、噪声和错误校验；
- `test_controller.py`：稳定识别、短暂丢框防重复、完整分拣周期、重试与满载；
- `test_cv_detector.py`：两段视频的读取/跳转、YOLO API 适配和未知类别。
- `test_yolo_adapter.py`：多目标排序、空结果和真实批量数组格式适配。
- `test_frame_sources.py`：空输入源、网络摄像头读取失败后的自动重连。
- `test_lower_simulator.py`：四类垃圾桶分别累计，每类 3 次后满载。
- `test_ui_smoke.py`：关键界面控件、空输入提示、摄像头打开/关闭、识别状态、满桶状态和 TX/RX 日志。
- `test_promo_player.py`：宣传视频在后台线程中的逐帧解码。

公开测试只是最低要求；验收还会覆盖更多边界条件。
