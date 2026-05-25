# test_integration.py
from core.graph import CityGraph, Node 
from strategy import Dispatcher, ActionType

def test_run():
    # 1. 初始化地图
    graph = CityGraph()
    
    # 【核心修正】：用 A 同学的 Node 类来创建节点，传入整型 id、浮点型坐标和合法类型
    node1 = Node(id=1, x=0.0, y=0.0, type="normal") 
    node2 = Node(id=2, x=10.0, y=10.0, type="task")
    
    # 这样传参就只有一个 node 对象，完美符合 add_node(self, node: Node) 的要求
    graph.add_node(node1)
    graph.add_node(node2)
    
    # 边连接也使用整型 id
    graph.add_edge(1, 2, 14.14)
    print("✅ 地图基础节点与边配置完成")

    # 2. 构造模拟状态（注意：B 模块传过来的节点 ID 也必须改成对应的整数 1 和 2）
    mock_state = {
        "vehicles": [{"id": "vehicle_01", "status": "IDLE", "current_node": 1}],
        "tasks": [{"id": "task_01", "node_id": 2, "status": "UNASSIGNED", "weight": 100}]
    }
    print("✅ 仿真状态包构造完成")
    
    # 3. 初始化你的调度器并执行
    dispatcher = Dispatcher(city_graph=graph, strategy_name="nearest")
    actions = dispatcher.dispatch(mock_state)
    
    # 4. 验证结果
    print("\n--- 调度输出测试 ---")
    if actions:
        for action in actions:
            print(f"🚀 动作生成成功!")
            print(f"   车辆编号: {action.vehicle_id}")
            print(f"   执行动作: {action.action_type.value}")
            print(f"   目标节点: {action.target_node_id} (类型: {type(action.target_node_id).__name__})")
    else:
        print("❌ 未成功生成调度指令")

if __name__ == "__main__":
    test_run()