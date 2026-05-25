"""数据类定义 - 与UI接口严格对齐"""
from dataclasses import dataclass
from typing import List, Literal
from enum import Enum


class VehicleStatus(Enum):
    """车辆状态枚举"""
    IDLE = "idle"           # 空闲
    MOVING = "moving"       # 移动中
    CHARGING = "charging"   # 充电中


class TaskStatus(Enum):
    """任务状态枚举"""
    WAITING = "waiting"         # 未分配
    ASSIGNED = "assigned"       # 已分配未完成
    COMPLETED = "completed"     # 已完成
    TIMEOUT = "timeout"         # 超时


@dataclass
class Node:
    """道路节点"""
    id: str
    x: float
    y: float
    type: Literal["depot", "task_point", "charging_station"]


@dataclass
class Edge:
    """道路边"""
    from_node: str
    to_node: str
    distance: float  # 单位：km


@dataclass
class Vehicle:
    """车辆"""
    id: str
    current_node: str          # 当前所在节点ID
    battery: float             # 当前电量 (kWh)
    load: float                # 当前载重 (kg)
    status: VehicleStatus
    target_node: str           # 目标节点ID（无则为空字符串）
    path: List[str]            # 剩余路径节点ID列表


@dataclass
class Task:
    """任务"""
    id: str
    node_id: str               # 任务所在节点
    weight: float              # 货物重量 (kg)
    release_time: float        # 产生时间（仿真时间）
    deadline: float            # 截止时间
    status: TaskStatus


@dataclass
class ChargingStation:
    """充电站"""
    node_id: str
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