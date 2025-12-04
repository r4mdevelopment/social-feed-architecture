from __future__ import annotations

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional

from engine import SimulationCore

# Дефолтные параметры

DEFAULT_PARAMS = {
    "buffer": 12,  # Очередь постов соцсети
    "devices": 3,  # Серверы соцсети
    "sources": 4,  # Пользователи
    "i32": (0.8, 2.2),  # Интервал генерации
    "lambda": 1.0,  # Интенсивность Exp
    "steps": 40,  # Количество шагов по кнопке "N шагов"
    "direct": False,  # Прямая постановка
    "seed": 42,  # Сид для воспроизведения тех же результатов в любое время
}


# Оболочка приложения

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Симулятор новостной ленты соцсети — Пошаговый режим")

        self.params = DEFAULT_PARAMS.copy()
        self.sim: Optional[SimulationCore] = None
        self.last_log_index: int = 0

        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)

        # Параметры UI интерфейса

        params_frame = ttk.Frame(main)
        params_frame.pack(fill="x")

        self.inputs: dict[str, tk.Entry] = {}

        def add_field(label: str, key: str):
            row = ttk.Frame(params_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label).pack(side="left")
            ent = tk.Entry(row, width=25)
            ent.pack(side="right")
            self.inputs[key] = ent

        add_field("Очередь постов соцсети (буфер):", "buffer")
        add_field("Серверы соцсети:", "devices")
        add_field("Пользователи:", "sources")
        add_field("Интервал генерации (min,max):", "i32_range")
        add_field("Интенсивность λ (Exp):", "lambda")
        add_field("Число шагов (N):", "steps")

        self.inputs["buffer"].insert(0, str(self.params["buffer"]))
        self.inputs["devices"].insert(0, str(self.params["devices"]))
        self.inputs["sources"].insert(0, str(self.params["sources"]))
        self.inputs["i32_range"].insert(0, f"{self.params['i32'][0]}, {self.params['i32'][1]}")
        self.inputs["lambda"].insert(0, str(self.params["lambda"]))
        self.inputs["steps"].insert(0, str(self.params["steps"]))

        self.chk_direct = tk.BooleanVar(value=self.params["direct"])
        ttk.Checkbutton(params_frame, text="Прямая постановка на прибор",
                        variable=self.chk_direct).pack(anchor="w", pady=3)

        # Кнопки

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=5)

        ttk.Button(buttons, text="Запустить моделирование",
                   command=self.start_sim).pack(side="left", padx=5)
        ttk.Button(buttons, text="Следующий шаг",
                   command=self.next_step).pack(side="left", padx=5)
        ttk.Button(buttons, text="Запустить N шагов",
                   command=self.run_n_steps).pack(side="left", padx=5)

        # Календарь

        calendar_frame = ttk.LabelFrame(main, text="Календарь событий (пошаговый режим)")
        calendar_frame.pack(fill="both", expand=True, pady=5)

        columns = (
            "time", "etype", "post", "source", "device",
            "action", "buf_size", "cursor", "last_idx", "reject_pct",
        )

        self.calendar = ttk.Treeview(calendar_frame, columns=columns, show="headings", height=15)

        self.calendar.heading("time", text="t")
        self.calendar.heading("etype", text="Тип")
        self.calendar.heading("post", text="Заявка")
        self.calendar.heading("source", text="Источник")
        self.calendar.heading("device", text="Прибор")
        self.calendar.heading("action", text="Действие")
        self.calendar.heading("buf_size", text="Буфер (занято)")
        self.calendar.heading("cursor", text="cursor (D2P2)")
        self.calendar.heading("last_idx", text="last_index (D1031)")
        self.calendar.heading("reject_pct", text="% отказов")

        self.calendar.column("time", width=60, anchor="center")
        self.calendar.column("etype", width=90, anchor="center")
        self.calendar.column("post", width=60, anchor="center")
        self.calendar.column("source", width=70, anchor="center")
        self.calendar.column("device", width=70, anchor="center")
        self.calendar.column("action", width=380, anchor="w")
        self.calendar.column("buf_size", width=90, anchor="center")
        self.calendar.column("cursor", width=90, anchor="center")
        self.calendar.column("last_idx", width=110, anchor="center")
        self.calendar.column("reject_pct", width=90, anchor="center")

        cal_scroll = ttk.Scrollbar(calendar_frame, orient="vertical", command=self.calendar.yview)
        self.calendar.configure(yscrollcommand=cal_scroll.set)

        self.calendar.pack(side="left", fill="both", expand=True)
        cal_scroll.pack(side="right", fill="y")

        # Логи

        self.out = scrolledtext.ScrolledText(main, width=120, height=15)
        self.out.pack(fill="both", expand=True, pady=5)

    # Параметры

    def read_params(self) -> bool:
        try:
            buffer_size = int(self.inputs["buffer"].get())
            devices = int(self.inputs["devices"].get())
            sources = int(self.inputs["sources"].get())

            raw_range = self.inputs["i32_range"].get()
            parts = raw_range.split(",")
            if len(parts) != 2:
                raise ValueError("Интервал генерации: min,max")

            i_min = float(parts[0].strip())
            i_max = float(parts[1].strip())
            if i_min <= 0 or i_max <= 0 or i_min >= i_max:
                raise ValueError("Интервал генерации: 0 < min < max")

            lam = float(self.inputs["lambda"].get())
            steps = int(self.inputs["steps"].get())

            self.params = {
                "buffer": buffer_size,
                "devices": devices,
                "sources": sources,
                "i32": (i_min, i_max),
                "lambda": lam,
                "steps": steps,
                "direct": self.chk_direct.get(),
                "seed": DEFAULT_PARAMS["seed"],
            }
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Проверьте корректность введённых данных.\n{e}")
            return False

    # Симуляция

    def start_sim(self):
        if not self.read_params():
            return
        self.sim = SimulationCore(self.params)
        self.sim.bootstrap()
        self.last_log_index = 0

        self.out.delete(1.0, tk.END)
        for row in self.calendar.get_children():
            self.calendar.delete(row)

        self.out.insert(tk.END, "Симуляция запущена\n")

    def next_step(self):
        if not self.sim:
            return
        if not self.sim.step():
            self.out.insert(tk.END, "\n--- Нет событий в календаре ---\n")
        self.print_new_logs()

    def run_n_steps(self):
        if not self.sim:
            return
        for _ in range(self.params["steps"]):
            if not self.sim.step():
                break
        self.print_new_logs()

    # Логи

    def print_new_logs(self):
        if not self.sim:
            return

        for i in range(self.last_log_index, len(self.sim.log_output)):
            evtype, time, data = self.sim.log_output[i]

            st = self.sim.stats
            reject_pct = (st["evicted"] / st["generated"] * 100.0) if st["generated"] > 0 else 0.0

            row = (
                f"{time:.3f}",
                evtype,
                data.get("post", ""),
                data.get("source", ""),
                data.get("device", ""),
                data.get("action", ""),
                self.sim.buffer.size,
                self.sim.pool.cursor,
                self.sim.buffer.last_index,
                f"{reject_pct:.1f}",
            )
            self.calendar.insert("", "end", values=row)

            self.out.insert(tk.END, f"\n=== Событие: {evtype} (t={time:.3f}) ===\n")
            for k, v in data.items():
                self.out.insert(tk.END, f"  {k}: {v}\n")

            buf_state = self.sim.buffer.list_state()
            self.out.insert(tk.END, f"Буфер (индекс, заявка, t): {buf_state}\n")

            devs = [
                f"D{d.id}={'FREE' if d.is_free() else f'BUSY({d.current_post.id})'}"
                for d in self.sim.pool.devices
            ]
            self.out.insert(
                tk.END,
                f"Приборы: {devs}, cursor={self.sim.pool.cursor}, "
                f"last_index={self.sim.buffer.last_index}\n",
            )

            self.out.insert(
                tk.END,
                f"Статистика: gen={st['generated']} queued={st['queued']} "
                f"served={st['served']} evicted={st['evicted']} direct={st['direct']} "
                f"({reject_pct:.1f}% отказов)\n",
            )

        self.last_log_index = len(self.sim.log_output)
        self.out.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
