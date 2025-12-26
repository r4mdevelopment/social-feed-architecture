from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from engine import SimulationCore


# Дефолтные параметры

DEFAULT_PARAMS = {
    "buffer": 12,  # Очередь постов соцсети
    "devices": 3,  # Серверы соцсети
    "sources": 4,  # Пользователи
    "i32": (0.8, 2.2),  # Интервал генерации
    "lambda": 1.0,  # Интенсивность Exp
    "steps": 50000,  # Количество шагов по кнопке "N шагов"
    "direct": False,  # Прямая постановка
    "seed": 42,  # Сид для воспроизведения тех же результатов в любое время
}


# Оболочка приложения

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Симулятор новостной ленты соцсети — Автоматический режим")

        self.params = DEFAULT_PARAMS.copy()
        self.sim: Optional[SimulationCore] = None

        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)

        # Параметры UI интерфейса

        params_frame = ttk.LabelFrame(main, text="Параметры моделирования")
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
        ttk.Checkbutton(params_frame, text="Прямая постановка на прибор", variable=self.chk_direct).pack(
            anchor="w", pady=3
        )

        ttk.Button(main, text="Запустить автоматический режим", command=self.run_auto).pack(pady=10)

        # Результаты

        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True)

        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="Сводка")

        self.summary_table = ttk.Treeview(summary_frame, columns=("param", "value"), show="headings", height=10)
        self.summary_table.heading("param", text="Параметр")
        self.summary_table.heading("value", text="Значение")
        self.summary_table.column("param", width=260, anchor="w")
        self.summary_table.column("value", width=160, anchor="center")
        self.summary_table.pack(fill="both", expand=True)

        # Таблица 1
        sources_frame = ttk.Frame(notebook)
        notebook.add(sources_frame, text="Таблица 1 — Источники")

        cols1 = ("source", "requests", "p_rej", "t_stay", "t_buff", "t_serv", "d_buff", "d_serv")
        self.tbl_sources = ttk.Treeview(sources_frame, columns=cols1, show="headings", height=12)

        self.tbl_sources.heading("source", text="Источник")
        self.tbl_sources.heading("requests", text="Заявок")
        self.tbl_sources.heading("p_rej", text="P отказа")
        self.tbl_sources.heading("t_stay", text="T в системе")
        self.tbl_sources.heading("t_buff", text="T буфера")
        self.tbl_sources.heading("t_serv", text="T обслуживания")
        self.tbl_sources.heading("d_buff", text="Доля буфера")
        self.tbl_sources.heading("d_serv", text="Доля обслуж.")

        self.tbl_sources.column("source", width=80, anchor="center")
        self.tbl_sources.column("requests", width=80, anchor="center")
        self.tbl_sources.column("p_rej", width=90, anchor="center")
        self.tbl_sources.column("t_stay", width=95, anchor="center")
        self.tbl_sources.column("t_buff", width=95, anchor="center")
        self.tbl_sources.column("t_serv", width=105, anchor="center")
        self.tbl_sources.column("d_buff", width=95, anchor="center")
        self.tbl_sources.column("d_serv", width=95, anchor="center")

        self.tbl_sources.pack(fill="both", expand=True)

        # Таблица 2
        devices_frame = ttk.Frame(notebook)
        notebook.add(devices_frame, text="Таблица 2 — Приборы")

        cols2 = ("device", "coefficient", "work_time")
        self.tbl_devices = ttk.Treeview(devices_frame, columns=cols2, show="headings", height=12)

        self.tbl_devices.heading("device", text="Прибор")
        self.tbl_devices.heading("coefficient", text="Коэфф. загрузки")
        self.tbl_devices.heading("work_time", text="Рабочее время")

        self.tbl_devices.column("device", width=100, anchor="center")
        self.tbl_devices.column("coefficient", width=140, anchor="center")
        self.tbl_devices.column("work_time", width=140, anchor="center")

        self.tbl_devices.pack(fill="both", expand=True)

    def read_params(self) -> bool:
        try:
            buffer_size = int(self.inputs["buffer"].get())
            devices = int(self.inputs["devices"].get())
            sources = int(self.inputs["sources"].get())

            raw_range = self.inputs["i32_range"].get()
            parts = raw_range.split(",")
            if len(parts) != 2:
                raise ValueError("Интервал генерации должен быть вида min,max")

            i_min = float(parts[0].strip())
            i_max = float(parts[1].strip())
            if i_min <= 0 or i_max <= 0 or i_min >= i_max:
                raise ValueError("Интервал генерации: 0 < min < max")

            lam = float(self.inputs["lambda"].get())
            steps = int(self.inputs["steps"].get())
            if steps <= 0:
                raise ValueError("Число шагов должно быть > 0")

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
            messagebox.showerror("Ошибка", str(e))
            return False


    def run_auto(self):
        if not self.read_params():
            return

        self.sim = SimulationCore(self.params)
        self.sim.bootstrap()

        result = self.sim.run_automatic(max_steps=self.params["steps"], max_time=9999.0)

        for row in self.summary_table.get_children():
            self.summary_table.delete(row)
        for row in self.tbl_sources.get_children():
            self.tbl_sources.delete(row)
        for row in self.tbl_devices.get_children():
            self.tbl_devices.delete(row)

        summary = result["summary"]
        names = {
            "generated": "Сгенерировано заявок",
            "queued": "Поставлено в буфер",
            "served": "Обслужено",
            "evicted": "Выбито из буфера",
            "direct": "Прямо на прибор",
            "reject_pct": "% отказов",
            "final_time": "Финальное время",
            "buffer_capacity": "Вместимость буфера",
        }
        order = ["generated", "queued", "served", "evicted", "direct", "reject_pct", "final_time", "buffer_capacity"]

        for k in order:
            v = summary.get(k, "")
            if k in ("reject_pct",):
                self.summary_table.insert("", "end", values=(names[k], f"{float(v):.6f}"))
            elif k in ("final_time",):
                self.summary_table.insert("", "end", values=(names[k], f"{float(v):.6f}"))
            else:
                self.summary_table.insert("", "end", values=(names[k], f"{v}"))

        for r in result["table_sources"]:
            self.tbl_sources.insert(
                "",
                "end",
                values=(
                    r["source"],
                    r["requests"],
                    f"{r['p_rej']:.3f}",
                    f"{r['t_stay']:.2f}",
                    f"{r['t_buff']:.2f}",
                    f"{r['t_serv']:.2f}",
                    f"{r['d_buff']:.2f}",
                    f"{r['d_serv']:.2f}",
                ),
            )

        for r in result["table_devices"]:
            self.tbl_devices.insert(
                "",
                "end",
                values=(
                    r["device"],
                    f"{r['coefficient']:.3f}",
                    f"{r['work_time']:.2f}",
                ),
            )

        messagebox.showinfo("Готово", "Автоматическое моделирование завершено!")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
