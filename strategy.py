from core.graph import CityGraph
from enum import Enum
from typing import Dict, List

# 1. 定义车辆的原子动作
class ActionType(Enum):
    MOVE_TO = "MOVE_TO"   # 前往某节点
    PICKUP = "PICKUP"     # 装货
    CHARGE = "CHARGE"     # 充电
    IDLE = "IDLE"         # 待命

# 2. 定义统一的动作指令结构
class VehicleAction:
    def __init__(self, vehicle_id: str, action_type: ActionType, target_node_id: int = None):
        self.vehicle_id = vehicle_id
        self.action_type = action_type
        self.target_node_id = target_node_id

# 3. 调度中心
class Dispatcher:
    def __init__(self, city_graph: CityGraph, strategy_name: str = "nearest"):
        """
        :param city_graph: A 模块实例化的城市地图对象
        :param strategy_name: UI 层传入的策略名称，默认为 nearest
        """
        self.city_graph = city_graph
        self.strategy_name = strategy_name

    def dispatch(self, state: Dict) -> List[VehicleAction]:
        """
        全组统一联调入口：接收 B 的状态字典，返回动作列表
        """
        if self.strategy_name == "nearest":
            return self._nearest_task_strategy(state)
        elif self.strategy_name == "largest":
            return self._largest_task_first_strategy(state)
        return []

    def _nearest_task_strategy(self, state: Dict) -> List[VehicleAction]:
        actions = []
        vehicles = state.get("vehicles", [])
        tasks = state.get("tasks", [])
        
        idle_vehicles = [v for v in vehicles if v.get('status') == 'IDLE']
        unassigned_tasks = [t for t in tasks if t.get('status') == 'UNASSIGNED']

        for vehicle in idle_vehicles:
            if not unassigned_tasks:
                break
                
            best_task = None
            min_dist = float('inf')
            
            for task in unassigned_tasks:
                # 关键修正：确保节点 ID 转换为 int 类型以适配 A 模块
                start_node = int(vehicle['current_node'])
                end_node = int(task['node_id'])
                
                # 关键修正：解包 A 模块返回的元组 (path_list, distance)
                path, road_distance = self.city_graph.shortest_path(start_node, end_node)
                
                if path: # 如果路径存在（列表非空）
                    if road_distance < min_dist:
                        min_dist = road_distance
                        best_task = task
            
            if best_task:
                actions.append(VehicleAction(vehicle['id'], ActionType.MOVE_TO, int(best_task['node_id'])))
                unassigned_tasks.remove(best_task)
                
        return actions

    def _largest_task_first_strategy(self, state: Dict) -> List[VehicleAction]:
        actions = []
        vehicles = state.get("vehicles", [])
        tasks = state.get("tasks", [])

        idle_vehicles = [v for v in vehicles if v.get('status') == 'IDLE']
        unassigned_tasks = [t for t in tasks if t.get('status') == 'UNASSIGNED']

        # 按权重（weight）降序排列任务
        sorted_tasks = sorted(unassigned_tasks, key=lambda x: x.get('weight', 0), reverse=True)

        for vehicle in idle_vehicles:
            if not sorted_tasks:
                break
                
            best_task = sorted_tasks.pop(0)
            actions.append(VehicleAction(vehicle['id'], ActionType.MOVE_TO, int(best_task['node_id'])))
            
        return actions