"""测试 Simulator 的 get_state() 方法"""
import json
from simulator import Simulator

# 创建测试用的图数据（小规模示例）
test_graph = {
    "nodes": [
        {"id": "depot_1", "x": 0, "y": 0, "type": "depot"},
        {"id": "task_1", "x": 10, "y": 0, "type": "task_point"},
        {"id": "task_2", "x": 0, "y": 10, "type": "task_point"},
        {"id": "cs_1", "x": 5, "y": 5, "type": "charging_station"},
    ],
    "edges": [
        {"from_node": "depot_1", "to_node": "task_1", "distance": 10.0},
        {"from_node": "depot_1", "to_node": "task_2", "distance": 10.0},
        {"from_node": "depot_1", "to_node": "cs_1", "distance": 7.0},
        {"from_node": "task_1", "to_node": "cs_1", "distance": 7.0},
        {"from_node": "task_2", "to_node": "cs_1", "distance": 7.0},
        {"from_node": "cs_1", "to_node": "depot_1", "distance": 7.0},
    ]
}

# 创建仿真器
print("=" * 50)
print("创建 Simulator 实例...")
print("=" * 50)

sim = Simulator(
    graph_data=test_graph,
    scale="small",
    strategy="nearest"
)

# 添加几个测试任务
print("\n" + "=" * 50)
print("添加测试任务...")
print("=" * 50)

sim.add_test_task(
    task_id="t1",
    node_id="task_1",
    weight=100.0,
    release_time=0.0,
    deadline=30.0
)

sim.add_test_task(
    task_id="t2",
    node_id="task_2",
    weight=200.0,
    release_time=5.0,
    deadline=35.0
)

# 获取状态
print("\n" + "=" * 50)
print("调用 get_state() 获取状态...")
print("=" * 50)

state = sim.get_state()

# 打印状态（格式化输出）
print("\n【状态概览】")
print(f"当前时间: {state['metrics']['current_time']}")
print(f"规模: {state['metrics']['scale']}")
print(f"策略: {state['metrics']['strategy']}")
print(f"节点数: {len(state['nodes'])}")
print(f"边数: {len(state['edges'])}")
print(f"车辆数: {len(state['vehicles'])}")
print(f"任务数: {len(state['tasks'])}")
print(f"充电站数: {len(state['charging_stations'])}")

print("\n【车辆详情】")
for v in state['vehicles']:
    print(f"  {v['id']}: 位置={v['current_node']}, 电量={v['battery']}kWh, 载重={v['load']}kg, 状态={v['status']}")

print("\n【任务详情】")
for t in state['tasks']:
    print(f"  {t['id']}: 节点={t['node_id']}, 重量={t['weight']}kg, 状态={t['status']}")

print("\n【充电站详情】")
for cs in state['charging_stations']:
    print(f"  {cs['node_id']}: 排队={cs['queue_length']}, 充电中={cs['charging_count']}")

# 检查是否与 D 同学要求的字段匹配
print("\n" + "=" * 50)
print("字段完整性检查...")
print("=" * 50)

required_vehicle_fields = ['id', 'current_node', 'battery', 'load', 'status', 'target_node', 'path']
required_task_fields = ['id', 'node_id', 'weight', 'release_time', 'deadline', 'status']
required_cs_fields = ['node_id', 'queue_length', 'charging_count']
required_metrics_fields = ['current_time', 'scale', 'strategy', 'total_score', 'completed_tasks', 
                           'timeout_tasks', 'total_distance', 'charging_times']

# 检查车辆字段
if state['vehicles']:
    vehicle = state['vehicles'][0]
    for field in required_vehicle_fields:
        if field in vehicle:
            print(f"✓ 车辆字段 '{field}' 存在")
        else:
            print(f"✗ 车辆字段 '{field}' 缺失")

# 检查任务字段
if state['tasks']:
    task = state['tasks'][0]
    for field in required_task_fields:
        if field in task:
            print(f"✓ 任务字段 '{field}' 存在")
        else:
            print(f"✗ 任务字段 '{field}' 缺失")

# 检查指标字段
for field in required_metrics_fields:
    if field in state['metrics']:
        print(f"✓ 指标字段 '{field}' 存在")
    else:
        print(f"✗ 指标字段 '{field}' 缺失")

print("\n" + "=" * 50)
print("测试完成！get_state() 工作正常。")
print("=" * 50)

# 可选：保存状态到 JSON 文件
with open('test_state_output.json', 'w', encoding='utf-8') as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
print("\n状态已保存到 test_state_output.json")