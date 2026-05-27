"""数据类定义 - 统一整数ID版本（与UI接口严格对齐）"""
from dataclasses import dataclass
from typing import List, Literal, Optional
from enum import Enum


class VehicleStatus(Enum):
    """车辆状态枚举"""
    IDLE = "idle"           # 空闲
    MOVING = "moving"       # 移动中
    CHARGING = "charging"   # 充电中
    WAITING_FOR_CHARGE = "waiting_for_charge"  # 等待充电桩


class TaskStatus(Enum):
    """任务状态枚举"""
    WAITING = "waiting"         # 未分配
    ASSIGNED = "assigned"       # 已分配未完成
    COMPLETED = "completed"     # 已完成  # 修复：COMPLETed → COMPLETED
    TIMEOUT = "timeout"         # 超时


@dataclass
class Node:
    """道路节点 - 使用整数ID"""
    id: int
    x: float
    y: float
    type: Literal["depot", "task_point", "charging_station"]


@dataclass
class Edge:
    """道路边 - 使用整数ID"""
    from_node: int
    to_node: int
    distance: float  # 单位：km


@dataclass
class Vehicle:
    """车辆 - 节点ID使用整数"""
    id: str
    current_node: int          # 当前所在节点ID
    battery: float             # 当前电量 (kWh)
    load: float                # 当前载重 (kg)
    status: VehicleStatus
    target_node: int           # 目标节点ID（0表示无目标）
    path: List[int]            # 剩余路径节点ID列表

    # 扩展字段
    current_task_id: Optional[str] = None    # 当前执行任务ID
    saved_task_id: Optional[str] = None      # 中断暂存任务ID
    charging_target: Optional[int] = None    # 目标充电站
    is_going_to_charge: bool = False         # 前往充电站标记
    is_in_charge_queue: bool = False         # 充电站排队标记


@dataclass
class Task:
    """任务 - 节点ID使用整数"""
    id: str
    node_id: int               # 任务所在节点
    weight: float              # 货物重量 (kg)
    release_time: float        # 产生时间（仿真时间）
    deadline: float            # 截止时间
    status: TaskStatus


@dataclass
class ChargingStation:
    """充电站 - 节点ID使用整数"""
    node_id: int
    queue_length: int          # 排队车辆数
    charging_count: int        # 充电中车辆数


@dataclass
class Metrics:
    """运行指标"""
    current_time: float
    scale: str                 # "small" / "medium" / "large"
    strategy: str              # "nearest" / "largest"
    total_score: float
    completed_tasks: int
    timeout_tasks: int
    total_distance: float      # 所有车辆累计行驶距离 (km)
    charging_times: int        # 累计充电次数
    low_battery_events: int = 0
    charging_requests: int = 0
    charging_queue_events: int = 0
    total_charging_wait_time: float = 0.0
    max_queue_length: int = 0
