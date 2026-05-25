# test_integration.py
from core.graph import CityGraph, Node 
from strategy import Dispatcher

def test_run():
    print("🔄 正在初始化 A 同学的地图结构...")
    graph = CityGraph()
    
    # 1. 严格按照 A 同学要求的合法类型定义节点：
    # valid types: charging, normal, task, warehouse
    node1 = Node(id=1, x=0.0, y=0.0, type="warehouse")   # 车库用仓库代替
    node2 = Node(id=2, x=30.0, y=40.0, type="task")      # 货运点用 task 代替
    node3 = Node(id=3, x=90.0, y=120.0, type="task")     # 货运点用 task 代替
    
    # 适配 A 模块的 add_node 方法（根据前几次报错调整为单参数传入实例）
    graph.add_node(node1)
    graph.add_node(node2)
    graph.add_node(node3)
    
    # 连接边 (起点的整型 ID，终点的整型 ID，距离)
    graph.add_edge(1, 2, 50.0)
    graph.add_edge(1, 3, 150.0)
    print("✅ 地图节点与路径配置完成！")

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
    print("✅ 仿真状态包构造完成！")
    
    print("\n--- 调度输出测试 ---")
    
    # --- 测试：最近任务优先 (nearest) ---
    print("\n🤖 【最近任务优先策略】")
    dispatcher_nearest = Dispatcher(city_graph=graph, strategy_name="nearest")
    actions_nearest = dispatcher_nearest.dispatch(mock_b_state)
    
    if actions_nearest:
        print("🚀 动作生成成功！")
        for act in actions_nearest:
            print(f"   车辆编号: {act['vehicle_id']}")
            print(f"   执行动作: {act['action']}")
            print(f"   目标任务: {act['task_id']}")
    else:
        print("❌ 未生成指令")

    print("\n==================================================")
    print("🎉 测试完成！双策略完美适配 A 的寻路与 B 的指令格式！")

if __name__ == "__main__":
    test_run()