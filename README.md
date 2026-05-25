# Data-Structure-Course-Design

## D 可视化模块使用说明

本模块由 D / yyb 负责，用于展示“新能源物流车队协同调度”的图形界面和实验结果图表。

### 1. 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

### 2. 运行 Pygame UI 原型

```bash
python3 ui/pygame_app.py
```

当前 UI 是假数据原型，不依赖 A/B/C 的真实模块。界面中可以看到道路、节点、仓库、充电站、任务点、车辆和运行指标。

键盘操作：

- `SPACE`：暂停 / 继续
- `1`：切换策略为 `nearest`
- `2`：切换策略为 `largest`
- `R`：重置假数据
- `ESC`：退出

后续 B 的仿真引擎完成后，联调时只需要在 `pygame_app.py` 中把 demo state 替换成 `simulator.get_state()`。

当前已经新增 `ui/state_adapter.py` 作为 UI 和仿真引擎之间的数据对接层：

- `get_demo_state(demo_world)`：保留当前假数据原型。
- `load_state_from_simulator(simulator)`：后续接入真实仿真器时调用，内部会执行 `simulator.get_state()`。
- `validate_state(state)`：检查 state 是否包含 `nodes`、`edges`、`vehicles`、`tasks`、`charging_stations`、`metrics` 六个核心字段。

### 3. 生成 Matplotlib 实验图表

```bash
python3 visualization/plot_results.py
```

脚本会读取 `results/experiment_results.csv`。如果 CSV 不存在或为空，会自动生成一份示例实验数据。

生成的图片会保存到：

```text
results/figures/
```

### 4. 后续需要 A/B/C 提供的统一 state 字典格式

D 模块后续会通过统一的 `state` 字典接入 A/B/C 的真实模块，建议格式如下：

```python
{
    "nodes": ...,
    "edges": ...,
    "vehicles": ...,
    "tasks": ...,
    "charging_stations": ...,
    "metrics": ...
}
```

其中：

- `nodes`：图中的节点，包括普通节点、仓库、充电站等。
- `edges`：道路边，用于绘制城市路网。
- `vehicles`：车辆信息，包括位置、电量、状态等。
- `tasks`：当前任务点信息，包括位置、重量、状态等。
- `charging_stations`：充电站信息，包括位置和排队长度。
- `metrics`：当前时间、策略、总收益、完成任务数、超时任务数、总路径长度、充电次数等统计指标。
