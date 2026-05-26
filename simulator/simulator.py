"""仿真引擎 完整版
路网扩容为10节点，能耗微调为0.5 kWh/km，参数合理贴近实车
调度、行驶、任务、电量、充电全套逻辑完整
"""
from typing import Dict, List, Any, Optional, Tuple
import random
import math
from .models import (
    Node, Edge, Vehicle, Task, ChargingStation, Metrics,
    VehicleStatus, TaskStatus
)

from core.graph import CityGraph, Node as ANode
from strategy import Dispatcher


class Simulator:
    # 工况参数：小幅调高能耗，整体仍符合现实新能源物流车
    VEHICLE_SPEED = 50.0                # km/h
    VEHICLE_BATTERY_CAPACITY = 100.0    # 电池总电量 kWh
    VEHICLE_LOAD_CAPACITY = 1000.0      # 最大载重 kg
    ENERGY_PER_KM = 0.5                 # 每公里耗电 0.5 kWh（小幅上调，合理范围）
    CHARGING_RATE = 60.0                # 充电功率 kWh/h
    CHARGING_PORTS = 2                  # 单充电站充电桩数量
    LOW_BATTERY_THRESHOLD = 20.0        # 低于20kWh触发充电（保持原阈值）

    SCORE_DIST_PENALTY = 0.3
    TASK_GEN_INTERVAL = 6
    TASK_GEN_PROB = 0.9
    PENALTY_OVERLOAD = 50
    PENALTY_TIMEOUT = 100

    def __init__(self, graph_data: dict, scale: str, strategy: str):
        self.nodes: Dict[int, Node] = {}
        self.edges: Dict[str, Edge] = {}

        for nd in graph_data.get("nodes", []):
            node = Node(**nd)
            self.nodes[node.id] = node
        for ed in graph_data.get("edges", []):
            edge = Edge(**ed)
            key = f"{edge.from_node}->{edge.to_node}"
            self.edges[key] = edge

        type_map = {"depot": "warehouse", "task_point": "task", "charging_station": "charging"}
        self.city_graph = CityGraph()
        for n in self.nodes.values():
            self.city_graph.add_node(ANode(id=n.id, x=n.x, y=n.y, type=type_map[n.type]))
        for e in self.edges.values():
            self.city_graph.add_edge(e.from_node, e.to_node, e.distance, bidirectional=True)

        print(f"[Simulator] 底层图加载完成: {len(self.nodes)} 节点, {len(self.edges)} 边")

        self.vehicle_segment_traveled: Dict[str, float] = {}
        self.vehicles: Dict[str, Vehicle] = {}
        self._init_vehicles()

        self.tasks: Dict[str, Task] = {}
        self.charging_stations: Dict[int, ChargingStation] = {}
        self._init_charging_stations()

        self.task_travel_dist: Dict[str, float] = {}

        self.metrics = Metrics(
            current_time=0.0, scale=scale, strategy=strategy,
            total_score=0.0, completed_tasks=0, timeout_tasks=0,
            total_distance=0.0, charging_times=0
        )
        self.current_time = 0.0
        self.task_id_counter = 1
        self.task_gen_timer = 0

        self.dispatcher = Dispatcher(self.city_graph, strategy)
        print(f"[Simulator] 加载调度器: {strategy}")
        print(f"[Simulator] 仿真初始化完成 | 规模: {scale}")
        print(f"[Simulator] 车辆数: {len(self.vehicles)} | 电池容量: {self.VEHICLE_BATTERY_CAPACITY}kWh")
        print(f"[Simulator] 理论续航: {self.VEHICLE_BATTERY_CAPACITY / self.ENERGY_PER_KM:.0f}km | 低电量阈值: {self.LOW_BATTERY_THRESHOLD}kWh")

    def _init_vehicles(self):
        depot_list = [n for n in self.nodes.values() if n.type == "depot"]
        start_id = depot_list[0].id if depot_list else next(iter(self.nodes.keys()))
        for i in range(1, 4):
            vid = f"v{i}"
            car = Vehicle(
                id=vid, current_node=start_id, battery=self.VEHICLE_BATTERY_CAPACITY,
                load=0.0, status=VehicleStatus.IDLE, target_node=0, path=[]
            )
            self.vehicles[vid] = car
            self.vehicle_segment_traveled[vid] = 0.0

    def _init_charging_stations(self):
        for n in self.nodes.values():
            if n.type == "charging_station":
                self.charging_stations[n.id] = ChargingStation(
                    node_id=n.id, queue_length=0, charging_count=0
                )

    def get_state(self) -> dict:
        veh_state = []
        for v in self.vehicles.values():
            veh_state.append({
                "id": v.id, "current_node": v.current_node, "battery": round(v.battery, 1),
                "load": round(v.load, 1), "status": v.status.value, "target_node": v.target_node,
                "path": v.path.copy(), "current_task_id": v.current_task_id
            })
        task_state = []
        for t in self.tasks.values():
            task_state.append({
                "id": t.id, "node_id": t.node_id, "weight": t.weight,
                "release_time": round(t.release_time, 1), "deadline": round(t.deadline, 1),
                "status": t.status.value
            })
        node_state = [{"id": n.id, "x": n.x, "y": n.y, "type": n.type} for n in self.nodes.values()]
        edge_state = [{"from_node": e.from_node, "to_node": e.to_node, "distance": e.distance} for e in self.edges.values()]
        cs_state = [{"node_id": cs.node_id, "queue_length": cs.queue_length, "charging_count": cs.charging_count} for cs in self.charging_stations.values()]

        return {
            "nodes": node_state, "edges": edge_state, "vehicles": veh_state,
            "tasks": task_state, "charging_stations": cs_state,
            "metrics": {
                "current_time": round(self.metrics.current_time, 1),
                "scale": self.metrics.scale, "strategy": self.metrics.strategy,
                "total_score": round(self.metrics.total_score, 1),
                "completed_tasks": self.metrics.completed_tasks,
                "timeout_tasks": self.metrics.timeout_tasks,
                "total_distance": round(self.metrics.total_distance, 1),
                "charging_times": self.metrics.charging_times
            }
        }

    def update(self, dt: float):
        self.current_time += dt
        self.metrics.current_time = self.current_time

        self._generate_tasks(dt)
        self._dispatch_tasks()
        self._move_vehicles(dt)
        self._handle_charging(dt)
        self._check_vehicle_battery()
        self._check_task_status()

    def _move_vehicles(self, dt: float):
        dt_h = dt / 60.0
        step_dist = self.VEHICLE_SPEED * dt_h

        for car in self.vehicles.values():
            vid = car.id
            if car.status == VehicleStatus.CHARGING or car.is_in_charge_queue:
                self.vehicle_segment_traveled[vid] = 0.0
                continue
            if car.status != VehicleStatus.MOVING:
                self.vehicle_segment_traveled[vid] = 0.0
                continue

            if car.battery < self.LOW_BATTERY_THRESHOLD and not car.is_going_to_charge:
                nearest_cs = self._find_nearest_charging_station(car.current_node)
                if nearest_cs and nearest_cs != car.current_node:
                    print(f"[Simulator] {vid} 电量不足({car.battery:.1f}kWh)，中断任务前往充电站")
                    car.saved_task_id = car.current_task_id
                    car.current_task_id = None
                    car.is_going_to_charge = True
                    car.charging_target = nearest_cs
                    try:
                        path, _ = self.city_graph.shortest_path(car.current_node, nearest_cs)
                        car.path = path[1:] if len(path) > 1 else []
                    except:
                        car.path = [nearest_cs]
                    self.vehicle_segment_traveled[vid] = 0.0
                    continue

            if not car.path:
                car.status = VehicleStatus.IDLE
                car.target_node = 0
                self.vehicle_segment_traveled[vid] = 0.0

                if car.is_going_to_charge:
                    cs = self.charging_stations.get(car.current_node)
                    if cs:
                        if cs.charging_count < self.CHARGING_PORTS:
                            car.status = VehicleStatus.CHARGING
                            cs.charging_count += 1
                            self.metrics.charging_times += 1
                            print(f"[Simulator] {vid} 抵达充电站，开始充电")
                        else:
                            car.is_in_charge_queue = True
                            cs.queue_length += 1
                            print(f"[Simulator] {vid} 充电站已满，进入排队")
                    car.is_going_to_charge = False
                    car.charging_target = None
                    continue

                if car.saved_task_id:
                    task = self.tasks.get(car.saved_task_id)
                    if task and task.status == TaskStatus.ASSIGNED:
                        car.current_task_id = car.saved_task_id
                        car.saved_task_id = None
                        car.target_node = task.node_id
                        car.status = VehicleStatus.MOVING
                        try:
                            p, _ = self.city_graph.shortest_path(car.current_node, task.node_id)
                            car.path = p[1:] if len(p) > 1 else []
                        except:
                            car.path = [task.node_id]
                continue

            next_n = car.path[0]
            seg_len = self._get_distance(car.current_node, next_n)
            if seg_len <= 0:
                car.path.pop(0)
                self.vehicle_segment_traveled[vid] = 0.0
                continue

            traveled = self.vehicle_segment_traveled[vid]
            remain = seg_len - traveled

            if step_dist < remain:
                add_d = step_dist
                traveled += add_d
                self.vehicle_segment_traveled[vid] = traveled
                car.battery -= add_d * self.ENERGY_PER_KM
                self.metrics.total_distance += add_d
            else:
                add_d = remain
                car.battery -= add_d * self.ENERGY_PER_KM
                self.metrics.total_distance += add_d

                old_n = car.current_node
                car.current_node = next_n
                car.path.pop(0)
                self.vehicle_segment_traveled[vid] = 0.0
                print(f"[Simulator] {vid} {old_n} → {next_n}，剩余电量 {car.battery:.1f}kWh")

    def _handle_charging(self, dt: float):
        dt_h = dt / 60.0
        charge_add = self.CHARGING_RATE * dt_h

        for car in self.vehicles.values():
            if car.status != VehicleStatus.CHARGING:
                continue
            car.battery += charge_add
            if car.battery >= self.VEHICLE_BATTERY_CAPACITY:
                car.battery = self.VEHICLE_BATTERY_CAPACITY
                car.status = VehicleStatus.IDLE
                cs = self.charging_stations.get(car.current_node)
                if cs:
                    cs.charging_count -= 1
                print(f"[Simulator] {car.id} 充电完成，电量已满")

        for cs in self.charging_stations.values():
            while cs.queue_length > 0 and cs.charging_count < self.CHARGING_PORTS:
                wake_car = None
                for car in self.vehicles.values():
                    if car.is_in_charge_queue and car.current_node == cs.node_id:
                        wake_car = car
                        break
                if not wake_car:
                    break
                wake_car.is_in_charge_queue = False
                wake_car.status = VehicleStatus.CHARGING
                cs.queue_length -= 1
                cs.charging_count += 1
                self.metrics.charging_times += 1
                print(f"[Simulator] {wake_car.id} 结束排队，开始充电")

    def _check_vehicle_battery(self):
        for car in self.vehicles.values():
            if car.status != VehicleStatus.IDLE or car.is_going_to_charge or car.is_in_charge_queue:
                continue
            if car.battery < self.LOW_BATTERY_THRESHOLD:
                cs = self._find_nearest_charging_station(car.current_node)
                if cs and cs != car.current_node:
                    print(f"[Simulator] {car.id} 空闲低电量，自动前往充电站")
                    car.is_going_to_charge = True
                    car.charging_target = cs
                    try:
                        path, _ = self.city_graph.shortest_path(car.current_node, cs)
                        car.path = path[1:] if len(path) > 1 else []
                    except:
                        car.path = [cs]
                    car.target_node = cs
                    car.status = VehicleStatus.MOVING

    def _check_task_status(self):
        finished: List[Tuple[Task, Vehicle]] = []
        for car in self.vehicles.values():
            tid = car.current_task_id
            if not tid:
                continue
            task = self.tasks.get(tid)
            if not task or task.status != TaskStatus.ASSIGNED:
                continue
            if car.current_node == task.node_id and car.status == VehicleStatus.IDLE:
                finished.append((task, car))

        for task, car in finished:
            task.status = TaskStatus.COMPLETED
            car.current_task_id = None
            car.load = max(0.0, car.load - task.weight)

            ahead = max(0.0, self.current_time - task.release_time)
            dist = self.task_travel_dist.get(task.id, 0.0)
            score = 100.0 + ahead * 2.0 - dist * self.SCORE_DIST_PENALTY
            score = max(score, 0.0)
            self.metrics.total_score += score
            self.metrics.completed_tasks += 1
            print(f"[Simulator] 任务{task.id}完成 | 得分:{score:.1f} | 距离惩罚:{dist*self.SCORE_DIST_PENALTY:.1f}")

        for task in self.tasks.values():
            if task.status in (TaskStatus.WAITING, TaskStatus.ASSIGNED):
                if self.current_time > task.deadline:
                    task.status = TaskStatus.TIMEOUT
                    self.metrics.total_score -= self.PENALTY_TIMEOUT
                    self.metrics.timeout_tasks += 1
                    for car in self.vehicles.values():
                        if car.current_task_id == task.id:
                            car.current_task_id = None
                            car.status = VehicleStatus.IDLE
                            car.path = []
                            car.target_node = 0
                    print(f"[Simulator] 任务{task.id}超时，扣{self.PENALTY_TIMEOUT}分")

    def _generate_tasks(self, dt: float):
        self.task_gen_timer += dt
        if self.task_gen_timer < self.TASK_GEN_INTERVAL:
            return
        self.task_gen_timer = 0
        if random.random() >= self.TASK_GEN_PROB:
            return

        points = [n.id for n in self.nodes.values() if n.type == "task_point"]
        if not points:
            return
        nid = random.choice(points)
        w = random.randint(50, 500)
        dl = self.current_time + random.randint(80, 150)
        tid = f"t{self.task_id_counter}"
        self.task_id_counter += 1
        new_task = Task(
            id=tid, node_id=nid, weight=w,
            release_time=self.current_time, deadline=dl,
            status=TaskStatus.WAITING
        )
        self.tasks[tid] = new_task
        print(f"[Simulator] 新建任务{tid} | 重量:{w}kg | 截止时间:{dl:.1f}min")

    def _dispatch_tasks(self):
        acts = self.dispatcher.dispatch(self.get_state())
        for act in acts:
            if act.get("action") != "assign":
                continue
            vid = act.get("vehicle_id")
            tid = act.get("task_id")
            car = self.vehicles.get(vid)
            task = self.tasks.get(tid)
            if not car or not task:
                continue
            if car.status != VehicleStatus.IDLE or task.status != TaskStatus.WAITING:
                continue

            task.status = TaskStatus.ASSIGNED
            car.current_task_id = tid
            car.target_node = task.node_id
            car.status = VehicleStatus.MOVING
            self.task_travel_dist[tid] = self.metrics.total_distance
            try:
                path, _ = self.city_graph.shortest_path(car.current_node, task.node_id)
                car.path = path[1:] if len(path) > 1 else []
            except:
                car.path = [task.node_id]
            print(f"[Simulator] 分配任务{tid} → {vid} | 路径:{car.path}")

        idle_vehicles = [v for v in self.vehicles.values() if v.status == VehicleStatus.IDLE]
        pending_tasks = [t for t in self.tasks.values() if t.status == TaskStatus.WAITING]

        while idle_vehicles and pending_tasks:
            car = idle_vehicles.pop(0)
            task = pending_tasks.pop(0)
            if car.status != VehicleStatus.IDLE or task.status != TaskStatus.WAITING:
                continue

            task.status = TaskStatus.ASSIGNED
            car.current_task_id = task.id
            car.target_node = task.node_id
            car.status = VehicleStatus.MOVING
            self.task_travel_dist[task.id] = self.metrics.total_distance
            try:
                path, _ = self.city_graph.shortest_path(car.current_node, task.node_id)
                car.path = path[1:] if len(path) > 1 else []
            except:
                car.path = [task.node_id]
            print(f"[Simulator] 补充分配任务{task.id} → {car.id} | 路径:{car.path}")

    def _find_nearest_charging_station(self, start: int) -> Optional[int]:
        try:
            cs_id, _ = self.city_graph.nearest_node(start, "charging")
            return cs_id
        except:
            cs_list = [n.id for n in self.nodes.values() if n.type == "charging_station"]
            if not cs_list:
                return None
            min_d = float("inf")
            res = None
            sx, sy = self.nodes[start].x, self.nodes[start].y
            for cid in cs_list:
                cx, cy = self.nodes[cid].x, self.nodes[cid].y
                d = math.hypot(sx - cx, sy - cy)
                if d < min_d:
                    min_d = d
                    res = cid
            return res

    def _get_distance(self, u: int, v: int) -> float:
        try:
            _, dist = self.city_graph.shortest_path(u, v)
            return dist
        except:
            if u not in self.nodes or v not in self.nodes:
                return 100.0
            return math.hypot(self.nodes[u].x - self.nodes[v].x, self.nodes[u].y - self.nodes[v].y)

    def add_test_task(self, tid: str, nid: int, w: float, rt: float, dt: float):
        t = Task(id=tid, node_id=nid, weight=w, release_time=rt, deadline=dt, status=TaskStatus.WAITING)
        self.tasks[tid] = t
        print(f"[Simulator] 手动添加测试任务: {tid}")