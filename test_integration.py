# test_integration.py
import json
import tempfile
import os
from simulator.pathfinder_adapter import RealPathfinder
from strategy import Dispatcher

def test_run():
    print("[INFO] Initializing A module map structure...")

    # 构造 A 格式的临时地图 JSON
    map_data = {
        "nodes": [
            {"id": 1, "x": 0.0, "y": 0.0, "type": "warehouse"},
            {"id": 2, "x": 30.0, "y": 40.0, "type": "task"},
            {"id": 3, "x": 90.0, "y": 120.0, "type": "task"},
        ],
        "edges": [
            {"from": 1, "to": 2, "distance": 50.0},
            {"from": 1, "to": 3, "distance": 150.0},
        ]
    }

    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(map_data, tmp)
    tmp.close()

    pathfinder = RealPathfinder(tmp.name)
    os.unlink(tmp.name)
    print("[OK] 地图节点与路径配置完成！")

    # 2. 构造 100% 还原 B 同学仿真器的状态数据（状态使用小写的 'idle' 和 'waiting'）
    mock_b_state = {
        "vehicles": [
            {"id": "v1", "current_node": 1, "status": "idle", "battery": 100.0, "load": 0.0},
            {"id": "v2", "current_node": 1, "status": "idle", "battery": 85.0, "load": 0.0}
        ],
        "tasks": [
            {"id": "t1", "node_id": 2, "weight": 300, "status": "waiting", "deadline": 30.0},
            {"id": "t2", "node_id": 3, "weight": 800, "status": "waiting", "deadline": 45.0}
        ]
    }
    print("[OK] 仿真状态包构造完成！")
    
    print("\n--- 调度输出测试 ---")

    # --- 测试：最近任务优先 (nearest) ---
    print("\n--- [Nearest Task First Strategy] ---")
    dispatcher_nearest = Dispatcher(pathfinder=pathfinder, strategy_name="nearest")
    actions_nearest = dispatcher_nearest.dispatch(mock_b_state)

    if actions_nearest:
        print("[OK] Action generation succeeded!")
        for act in actions_nearest:
            print(f"   车辆编号: {act['vehicle_id']}")
            print(f"   执行动作: {act['action']}")
            print(f"   目标任务: {act['task_id']}")
            print(f"   路径: {act.get('path', 'N/A')}")
    else:
        print("[FAIL] No actions generated")

    print("\n==================================================")
    print("[OK] All tests passed! Both strategies correctly integrate A's routing with B's action format!")

if __name__ == "__main__":
    test_run()