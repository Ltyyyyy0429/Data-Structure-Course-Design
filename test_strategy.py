import json
from strategy import Dispatcher

# ==========================================
# 1. 伪造 A 同学的地图模块 (Mock Graph)
# ==========================================
class MockCityGraph:
    def shortest_path(self, start_node, end_node):
        # 节点 0: 小车位置 | 1: 近任务 | 2: 远任务 | 3: 近充电站 | 4: 远充电站
        distances = {
            (0, 1): 10,   # 小车到近任务：距离 10
            (0, 2): 100,  # 小车到远任务：距离 100
            (1, 3): 5,    # 近任务到近充电站：距离 5
            (2, 4): 5,    # 远任务到远充电站：距离 5
        }
        dist = distances.get((start_node, end_node)) or distances.get((end_node, start_node))
        if dist is not None:
            return [], dist 
        return [], 999 

# ==========================================
# 2. 伪造 B 同学的状态数据字典 (Mock State)
# ==========================================
def create_mock_state(battery_level, far_charger_queue=0):
    return {
        'current_time': 100,
        'vehicles': [
            {'id': 'v1', 'status': 'idle', 'current_node': 0, 'battery': battery_level, 'max_battery': 100}
        ],
        'tasks': [
            {'id': 'task_near_light', 'status': 'waiting', 'node_id': 1, 'weight': 10, 'deadline': 1000},
            {'id': 'task_far_heavy', 'status': 'waiting', 'node_id': 2, 'weight': 100, 'deadline': 1000}
        ],
        'chargers': [
            {'node_id': 3, 'queue_length': 0},                 # 靠近 task_near_light 的充电站
            {'node_id': 4, 'queue_length': far_charger_queue}  # 靠近 task_far_heavy 的充电站
        ]
    }

# ==========================================
# 3. 运行测试用例
# ==========================================
def run_tests():
    mock_graph = MockCityGraph()
    # 实例化带有假地图的调度器，启用新策略
    dispatcher = Dispatcher(city_graph=mock_graph, strategy_name="energy_aware_hybrid")
    
    print("=== 开始测试能量感知调度算法 ===\n")
    
    # ----------------------------------------------------
    # 测试用例 1：满电状态 (100%) - 测试“贪心收益”
    # ----------------------------------------------------
    print("【测试用例 1：小车满电 (100%)，充电站空闲】")
    state_100 = create_mock_state(battery_level=100)
    result_100 = dispatcher.dispatch(state_100)
    print(f"预期行为: 无视距离惩罚，被巨大收益吸引，去接 'task_far_heavy'")
    print(f"实际输出: {json.dumps(result_100, indent=2, ensure_ascii=False)}\n")
    
    # ----------------------------------------------------
    # 测试用例 2：低电量危机 (15%) - 测试“硬门槛拦截”
    # ----------------------------------------------------
    print("【测试用例 2：小车低电量 (15%)】")
    state_15 = create_mock_state(battery_level=15)
    result_15 = dispatcher.dispatch(state_15)
    print(f"预期行为: 触发安全电量拦截，放弃远任务，保底选择 'task_near_light'")
    print(f"实际输出: {json.dumps(result_15, indent=2, ensure_ascii=False)}\n")

    # ----------------------------------------------------
    # 测试用例 3：极度缺电 (5%) - 测试“全面拒绝”
    # ----------------------------------------------------
    print("【测试用例 3：小车极度缺电 (5%)】")
    state_5 = create_mock_state(battery_level=5)
    result_5 = dispatcher.dispatch(state_5)
    print(f"预期行为: 所有任务都不满足安全底线，拒绝接单，返回空指令 []")
    print(f"实际输出: {json.dumps(result_5, indent=2, ensure_ascii=False)}\n")

    # ----------------------------------------------------
    # 测试用例 4：充电站大排长龙 - 测试“排队惩罚” (新增)
    # ----------------------------------------------------
    print("【测试用例 4：小车满电，但高收益任务附近的充电站大排长龙】")
    # 传入参数：满电 100%，远任务的充电站排队人数设置为 20 辆车
    state_queue = create_mock_state(battery_level=100, far_charger_queue=20)
    result_queue = dispatcher.dispatch(state_queue)
    print(f"预期行为: 目标充电站排队 20 辆车 (惩罚分: 20*10 = -200分)，综合得分被拉低，车辆果断放弃高收益，改选 'task_near_light'")
    print(f"实际输出: {json.dumps(result_queue, indent=2, ensure_ascii=False)}\n")

if __name__ == "__main__":
    run_tests()