from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import random
import math
import heapq
import statistics


@dataclass
class Post:
    id: int
    source_id: int
    created_at: float
    service_start: Optional[float] = None
    service_end: Optional[float] = None


class InterarrivalLaw:
    def next_delay(self) -> float:
        raise NotImplementedError


class UniformInterarrival(InterarrivalLaw):
    def __init__(self, a: float, b: float):
        self.a = a
        self.b = b

    def next_delay(self) -> float:
        return random.uniform(self.a, self.b)


class ServiceLaw:
    def next_service_time(self) -> float:
        raise NotImplementedError


class ExponentialService(ServiceLaw):
    def __init__(self, lambd: float):
        self.lambd = lambd

    def next_service_time(self) -> float:
        r = random.random()
        return -math.log(r) / self.lambd if self.lambd > 0 else 0.0


@dataclass
class BufferSlot:
    post: Optional[Post] = None
    enqueued_at: float = 0.0


class Buffer:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.slots: List[BufferSlot] = [BufferSlot() for _ in range(capacity)]
        self.last_index: int = -1
        self.size: int = 0

    def is_full(self) -> bool:
        return self.size == self.capacity

    def is_empty(self) -> bool:
        return self.size == 0

    def enqueue_d1031(self, post: Post, now: float) -> bool:
        if self.is_full():
            return False
        start = (self.last_index + 1) % self.capacity
        idx = start
        for _ in range(self.capacity):
            if self.slots[idx].post is None:
                self.slots[idx].post = post
                self.slots[idx].enqueued_at = now
                self.last_index = idx
                self.size += 1
                return True
            idx = (idx + 1) % self.capacity
        return False

    def drop_oldest_d10o3(self) -> Optional[Post]:
        oldest_t = float("inf")
        oldest_idx = -1
        for i, s in enumerate(self.slots):
            if s.post is not None and s.enqueued_at < oldest_t:
                oldest_t = s.enqueued_at
                oldest_idx = i
        if oldest_idx == -1:
            return None
        dropped = self.slots[oldest_idx].post
        self.slots[oldest_idx] = BufferSlot()
        self.size -= 1
        return dropped

    def pick_lifo_d2b2(self) -> Optional[Post]:
        newest_t = -1.0
        newest_idx = -1
        for i, s in enumerate(self.slots):
            if s.post is not None and s.enqueued_at > newest_t:
                newest_t = s.enqueued_at
                newest_idx = i
        if newest_idx == -1:
            return None
        post = self.slots[newest_idx].post
        self.slots[newest_idx] = BufferSlot()
        self.size -= 1
        return post


class Device:
    def __init__(self, id: int, service_law: ServiceLaw):
        self.id = id
        self.service_law = service_law
        self.busy = False
        self.current_post: Optional[Post] = None

        self.work_time: float = 0.0
        self._last_start: Optional[float] = None

    def is_free(self) -> bool:
        return not self.busy

    def start_process(self, post: Post, now: float) -> float:
        self.busy = True
        self.current_post = post
        self._last_start = now
        return self.service_law.next_service_time()

    def complete(self, now: float) -> Optional[Post]:
        if self.busy and self._last_start is not None:
            self.work_time += max(0.0, now - self._last_start)

        self.busy = False
        self._last_start = None

        p = self.current_post
        self.current_post = None
        return p


class DevicePool:
    def __init__(self, devices: List[Device]):
        self.devices = devices
        self.cursor = 0

    def pick_cyclic_d2p2(self) -> Optional[Device]:
        n = len(self.devices)
        for k in range(n):
            i = (self.cursor + k) % n
            if self.devices[i].is_free():
                self.cursor = (i + 1) % n
                return self.devices[i]
        return None

    def any_free(self) -> bool:
        return any(d.is_free() for d in self.devices)


@dataclass
class AcceptedResult:
    status: int
    queued: bool
    evicted_post_id: Optional[int] = None
    assigned_device_id: Optional[int] = None


@dataclass
class Packet:
    source_id: int
    posts: List[Post]


class PlacementDispatcher:
    def __init__(self, buffer: Buffer, pool: DevicePool, direct_assign: bool, sim: "SimulationCore"):
        self._buffer = buffer
        self._pool = pool
        self._direct = direct_assign
        self._sim = sim

    def handle_publish(self, post: Post, now: float) -> AcceptedResult:
        if self._direct:
            dev = self._pool.pick_cyclic_d2p2()
            if dev is not None:
                post.service_start = now
                dur = dev.start_process(post, now)
                self._sim.stats["direct"] += 1
                self._sim.source_stats[post.source_id]["direct"] += 1
                self._sim.log("ASSIGN_TO_DEVICE", {"post": post.id, "source": post.source_id, "device": dev.id})
                self._sim.schedule(CompletionEvent(now + dur, dev.id))
                return AcceptedResult(202, False, assigned_device_id=dev.id)

        if self._buffer.is_full():
            dropped = self._buffer.drop_oldest_d10o3()
            if dropped is not None:
                self._sim.stats["evicted"] += 1
                self._sim.source_stats[dropped.source_id]["evicted"] += 1
                self._sim.log("BUFFER_EVICT", {"post": dropped.id, "source": dropped.source_id})

        ok = self._buffer.enqueue_d1031(post, now)
        if ok:
            self._sim.stats["queued"] += 1
            self._sim.source_stats[post.source_id]["queued"] += 1
            self._sim.log("BUFFER_ENQUEUE", {"post": post.id, "source": post.source_id})
        return AcceptedResult(202 if ok else 500, ok)


class SelectionDispatcher:
    def __init__(self, buffer: Buffer, pool: DevicePool, sim: "SimulationCore"):
        self._buffer = buffer
        self._pool = pool
        self._packet: Optional[Packet] = None
        self._sim = sim

    def on_device_freed(self, now: float):
        if self._packet is None or not self._packet.posts:
            first = self._buffer.pick_lifo_d2b2()
            if first is None:
                return

            self._sim.log("BUFFER_PICK", {"post": first.id, "source": first.source_id})

            src = first.source_id
            pulled = [first]
            while not self._buffer.is_empty():
                p = self._buffer.pick_lifo_d2b2()
                if p is None:
                    break
                pulled.append(p)

            same = [p for p in pulled if p.source_id == src]
            other = [p for p in pulled if p.source_id != src]

            t = now
            for p in reversed(other):
                self._buffer.enqueue_d1031(p, t)
                self._sim.log("BUFFER_ENQUEUE", {"post": p.id, "source": p.source_id})
                t += 1e-6

            self._packet = Packet(src, same)
            self._sim.log("PACKET_FORMED", {"source": src, "packet_size": len(same)})

        while self._packet is not None and self._packet.posts:
            dev = self._pool.pick_cyclic_d2p2()
            if dev is None:
                break

            post = self._packet.posts.pop()
            post.service_start = now
            dur = dev.start_process(post, now)

            self._sim.log("SERVICE_START", {"post": post.id, "source": post.source_id, "device": dev.id})
            self._sim.schedule(CompletionEvent(now + dur, dev.id))

        if self._packet is not None and not self._packet.posts:
            self._packet = None


class Event:
    def __init__(self, time: float):
        self.time = time

    def __lt__(self, other: "Event"):
        return self.time < other.time

    def process(self, sim: "SimulationCore"):
        raise NotImplementedError


class ArrivalEvent(Event):
    def __init__(self, time: float, source: int):
        super().__init__(time)
        self.source = source

    def process(self, sim: "SimulationCore"):
        sim.current_time = self.time

        post = Post(sim.next_post_id, self.source, self.time)
        sim.next_post_id += 1

        sim.stats["generated"] += 1
        sim.source_stats[self.source]["generated"] += 1

        sim.log("ARRIVAL", {"post": post.id, "source": post.source_id})

        sim.placement.handle_publish(post, self.time)

        delay = sim.inter_arrival.next_delay()
        sim.schedule(ArrivalEvent(self.time + delay, self.source))

        if (not sim.placement._direct) and (not sim.buffer.is_empty()) and sim.pool.any_free():
            sim.selection.on_device_freed(self.time)


class CompletionEvent(Event):
    def __init__(self, time: float, dev_id: int):
        super().__init__(time)
        self.dev_id = dev_id

    def process(self, sim: "SimulationCore"):
        sim.current_time = self.time
        dev = sim.pool.devices[self.dev_id]
        post = dev.complete(self.time)

        if post is not None:
            post.service_end = self.time
            sim.stats["served"] += 1
            st = sim.source_stats[post.source_id]
            st["served"] += 1

            if post.service_start is not None:
                st["system_times"].append(post.service_end - post.created_at)
                st["service_times"].append(post.service_end - post.service_start)
                st["buffer_times"].append(post.service_start - post.created_at)

        sim.log(
            "SERVICE_COMPLETE",
            {
                "post": post.id if post else None,
                "source": post.source_id if post else None,
                "device": self.dev_id,
            },
        )

        sim.selection.on_device_freed(self.time)


class SimulationCore:
    def __init__(self, params: Dict[str, Any]):
        random.seed(params["seed"])

        self.params = params
        self.current_time: float = 0.0
        self.calendar: List[Event] = []

        self.buffer = Buffer(params["buffer"])
        self.pool = DevicePool([Device(i, ExponentialService(params["lambda"])) for i in range(params["devices"])])

        self.inter_arrival = UniformInterarrival(*params["i32"])

        self.next_post_id = 1

        self.stats: Dict[str, float] = dict(
            generated=0,
            queued=0,
            served=0,
            evicted=0,
            direct=0,
        )

        self.source_stats: Dict[int, Dict[str, Any]] = {
            s: dict(
                generated=0,
                queued=0,
                served=0,
                evicted=0,
                direct=0,
                system_times=[],
                buffer_times=[],
                service_times=[],
            )
            for s in range(1, params["sources"] + 1)
        }

        self.log_output: List[Any] = []

        self.placement = PlacementDispatcher(self.buffer, self.pool, direct_assign=params["direct"], sim=self)
        self.selection = SelectionDispatcher(self.buffer, self.pool, sim=self)

    def log(self, evtype: str, data: Dict[str, Any]):
        self.log_output.append((evtype, self.current_time, data))

    def schedule(self, ev: Event):
        heapq.heappush(self.calendar, ev)

    def bootstrap(self):
        for s in range(1, self.params["sources"] + 1):
            self.schedule(ArrivalEvent(0.0, s))

    def run_automatic(self, max_steps: int = 100000, max_time: float = 9999.0) -> Dict[str, Any]:
        self.log_output.clear()

        steps = 0
        while self.calendar and steps < max_steps:
            ev = heapq.heappop(self.calendar)
            if ev.time > max_time:
                break
            ev.process(self)
            steps += 1

        return {
            "summary": self.summary(),
            "table_sources": self.table_sources(),
            "table_devices": self.table_devices(),
        }

    def summary(self) -> Dict[str, float]:
        st = self.stats
        reject_pct = (st["evicted"] / st["generated"] * 100.0) if st["generated"] > 0 else 0.0
        return dict(
            generated=st["generated"],
            queued=st["queued"],
            served=st["served"],
            evicted=st["evicted"],
            direct=st["direct"],
            reject_pct=reject_pct,
            final_time=self.current_time,
            buffer_capacity=self.buffer.capacity,
        )

    def table_sources(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for s in range(1, self.params["sources"] + 1):
            st = self.source_stats[s]
            gen = st["generated"]

            p_rej = (st["evicted"] / gen) if gen > 0 else 0.0

            t_sys = statistics.mean(st["system_times"]) if st["system_times"] else 0.0
            t_buf = statistics.mean(st["buffer_times"]) if st["buffer_times"] else 0.0
            t_srv = statistics.mean(st["service_times"]) if st["service_times"] else 0.0

            d_buf = statistics.pvariance(st["buffer_times"]) if len(st["buffer_times"]) > 1 else 0.0
            d_srv = statistics.pvariance(st["service_times"]) if len(st["service_times"]) > 1 else 0.0

            rows.append(
                dict(
                    source=s,
                    requests=int(gen),
                    p_rej=p_rej,
                    t_stay=t_sys,
                    t_buff=t_buf,
                    t_serv=t_srv,
                    d_buff=d_buf,
                    d_serv=d_srv,
                )
            )
        return rows

    def table_devices(self) -> List[Dict[str, Any]]:
        total_time = self.current_time
        rows: List[Dict[str, Any]] = []
        for d in self.pool.devices:
            coeff = (d.work_time / total_time) if total_time > 0 else 0.0
            rows.append(dict(device=f"D{d.id}", coefficient=coeff, work_time=d.work_time))
        return rows
