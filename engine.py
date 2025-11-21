from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import random
import math
import heapq


@dataclass
class Post:
    id: int
    source_id: int
    created_at: float


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
        u = random.random()
        return -math.log(1 - u) / self.lambd if self.lambd > 0 else 0.0


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
            if s.post and s.enqueued_at < oldest_t:
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
            if s.post and s.enqueued_at > newest_t:
                newest_t = s.enqueued_at
                newest_idx = i
        if newest_idx == -1:
            return None
        post = self.slots[newest_idx].post
        self.slots[newest_idx] = BufferSlot()
        self.size -= 1
        return post

    def list_state(self):
        return [(i, s.post.id if s.post else None, s.enqueued_at) for i, s in enumerate(self.slots)]


class Device:
    def __init__(self, id: int, service_law: ServiceLaw):
        self.id = id
        self.service_law = service_law
        self.busy = False
        self.current_post: Optional[Post] = None

    def is_free(self) -> bool:
        return not self.busy

    def start_process(self, post: Post) -> float:
        self.busy = True
        self.current_post = post
        return self.service_law.next_service_time()

    def complete(self) -> Optional[Post]:
        self.busy = False
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


class SimulationCore:
    def __init__(self, params: Dict[str, Any]):
        random.seed(params["seed"])

        self.current_time: float = 0.0
        self.calendar: List[Event] = []

        self.buffer = Buffer(params["buffer"])
        self.pool = DevicePool([Device(i, ExponentialService(params["lambda"]))
                                for i in range(params["devices"])])

        self.inter_arrival = UniformInterarrival(*params["i32"])
        self.service = ExponentialService(params["lambda"])

        self.params = params
        self.next_post_id = 1

        self.stats: Dict[str, float] = dict(
            generated=0,
            queued=0,
            served=0,
            evicted=0,
            direct=0,
        )

        self.log_output: List[Any] = []

        self.placement = PlacementDispatcher(self.buffer, self.pool,
                                             direct_assign=params["direct"],
                                             sim=self)
        self.selection = SelectionDispatcher(self.buffer, self.pool, sim=self)

    def log(self, evtype: str, data: Dict[str, Any]):
        self.log_output.append((evtype, self.current_time, data))

    def schedule(self, ev: "Event"):
        heapq.heappush(self.calendar, ev)

    def bootstrap(self):
        for s in range(1, self.params["sources"] + 1):
            self.schedule(ArrivalEvent(0.0, s))

    def step(self) -> bool:
        if not self.calendar:
            return False
        ev = heapq.heappop(self.calendar)
        ev.process(self)
        return True


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
    def __init__(self, buffer: Buffer, pool: DevicePool, direct_assign: bool, sim: SimulationCore):
        self._buffer = buffer
        self._pool = pool
        self._direct = direct_assign
        self._sim = sim

    def handle_publish(self, post: Post, now: float) -> AcceptedResult:
        if self._direct:
            dev = self._pool.pick_cyclic_d2p2()
            if dev:
                dev.start_process(post)
                self._sim.log("ASSIGN_TO_DEVICE", {
                    "post": post.id,
                    "source": post.source_id,
                    "device": dev.id,
                    "action": f"Заявка {post.id} сразу направлена на прибор D{dev.id} (минуя буфер)",
                })
                return AcceptedResult(202, False, assigned_device_id=dev.id)

        evicted_id: Optional[int] = None
        if self._buffer.is_full():
            dropped = self._buffer.drop_oldest_d10o3()
            if dropped:
                evicted_id = dropped.id
                self._sim.stats["evicted"] += 1
                self._sim.log("BUFFER_EVICT", {
                    "post": dropped.id,
                    "source": dropped.source_id,
                    "action": f"Буфер полон: выбита самая старая заявка {dropped.id} (D10O3)",
                })

        ok = self._buffer.enqueue_d1031(post, now)
        if ok:
            self._sim.log("BUFFER_ENQUEUE", {
                "post": post.id,
                "source": post.source_id,
                "action": f"Заявка {post.id} поставлена в буфер по кольцу (D1031), last_index={self._buffer.last_index}",
            })
        return AcceptedResult(202 if ok else 500, ok, evicted_post_id=evicted_id)


class SelectionDispatcher:
    def __init__(self, buffer: Buffer, pool: DevicePool, sim: SimulationCore):
        self._buffer = buffer
        self._pool = pool
        self._packet: Optional[Packet] = None
        self._sim = sim

    def on_device_freed(self, now: float):
        if self._packet is None or not self._packet.posts:
            first = self._buffer.pick_lifo_d2b2()
            if first is None:
                return

            self._sim.log("BUFFER_PICK", {
                "post": first.id,
                "source": first.source_id,
                "action": f"Выбрана последняя по времени заявка {first.id} из буфера (LIFO D2B2)",
            })

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
                self._sim.log("BUFFER_ENQUEUE", {
                    "post": p.id,
                    "source": p.source_id,
                    "action": f"Заявка {p.id} возвращена в буфер (не входит в пакет источника {src})",
                })
                t += 1e-6

            self._packet = Packet(src, same)
            self._sim.log("PACKET_FORMED", {
                "source": src,
                "post": same[-1].id if same else None,
                "packet_size": len(same),
                "action": f"Сформирован пакет из {len(same)} заявок источника {src}",
            })

        while self._packet and self._packet.posts:
            dev = self._pool.pick_cyclic_d2p2()
            if dev is None:
                break
            post = self._packet.posts.pop()
            dev.start_process(post)
            self._sim.log("SERVICE_START", {
                "post": post.id,
                "source": post.source_id,
                "device": dev.id,
                "action": f"Заявка {post.id} из пакета источника {post.source_id} передана на прибор D{dev.id}",
            })

        if self._packet and not self._packet.posts:
            self._packet = None


class Event:
    def __init__(self, time: float):
        self.time = time

    def __lt__(self, other: "Event"):
        return self.time < other.time

    def process(self, sim: SimulationCore):
        raise NotImplementedError


class ArrivalEvent(Event):
    def __init__(self, time: float, source: int):
        super().__init__(time)
        self.source = source

    def process(self, sim: SimulationCore):
        sim.current_time = self.time

        post = Post(sim.next_post_id, self.source, self.time)
        sim.next_post_id += 1
        sim.stats["generated"] += 1

        sim.log("ARRIVAL", {
            "post": post.id,
            "source": post.source_id,
            "action": f"Источник {self.source} сгенерировал заявку {post.id}",
        })

        res = sim.placement.handle_publish(post, self.time)

        if res.queued:
            sim.stats["queued"] += 1

        delay = sim.inter_arrival.next_delay()
        sim.schedule(ArrivalEvent(self.time + delay, self.source))

        if res.assigned_device_id is not None:
            device = sim.pool.devices[res.assigned_device_id]
            t = sim.service.next_service_time()
            sim.schedule(CompletionEvent(self.time + t, device.id))

        if (not sim.placement._direct) and (not sim.buffer.is_empty()) and sim.pool.any_free():
            sim.selection.on_device_freed(self.time)
            for d in sim.pool.devices:
                if d.busy:
                    need = True
                    for ev in sim.calendar:
                        if isinstance(ev, CompletionEvent) and ev.dev_id == d.id:
                            need = False
                            break
                    if need:
                        t_serv = sim.service.next_service_time()
                        sim.schedule(CompletionEvent(self.time + t_serv, d.id))


class CompletionEvent(Event):
    def __init__(self, time: float, dev_id: int):
        super().__init__(time)
        self.dev_id = dev_id

    def process(self, sim: SimulationCore):
        sim.current_time = self.time
        dev = sim.pool.devices[self.dev_id]
        post = dev.complete()

        if post:
            sim.stats["served"] += 1

        sim.log("SERVICE_COMPLETE", {
            "post": post.id if post else None,
            "source": post.source_id if post else None,
            "device": self.dev_id,
            "action": f"Прибор D{self.dev_id} завершил обработку заявки {post.id if post else '—'}",
        })

        sim.selection.on_device_freed(self.time)

        for d in sim.pool.devices:
            if d.busy:
                need = True
                for ev in sim.calendar:
                    if isinstance(ev, CompletionEvent) and ev.dev_id == d.id:
                        need = False
                        break
                if need:
                    t_serv = sim.service.next_service_time()
                    sim.schedule(CompletionEvent(self.time + t_serv, d.id))
