from enum import Enum
from typing import Dict, List

# 1. 定义车辆的原子动作（接口文档约定）
class ActionType(Enum):
    MOVE_TO = "MOVE_TO"   # 前往某节点
    PICKUP = "PICKUP"     # 装货
    CHARGE = "CHARGE"     # 充电
    IDLE = "IDLE"         # 待命

# 2. 定义统一的动作指令结构
class VehicleAction:
    def __init__(self, vehicle_id: str, action_type: ActionType, target_node_id: str = None):
        self.vehicle_id = vehicle_id
        self.action_type = action_type
        self.target_node_id = target_node_id

# 3. 调度中心基类
class Dispatcher:
    def __init__(self, strategy_name: str = "nearest"):
        """
        :param strategy_name: UI 层传入的策略名称，默认为 nearest
        """
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
        # TODO: 1. 解析 state['vehicles'] 找空闲车辆
        # TODO: 2. 解析 state['tasks'] 找未分配任务
        # TODO: 3. 调用 A 模块的寻路算法计算距离
        # TODO: 4. 生成 VehicleAction 并装入 actions
        return actions

    def _largest_task_first_strategy(self, state: Dict) -> List[VehicleAction]:
        actions = []
        # TODO: 根据任务的 weight 字段进行降序排序后分配
        return actions