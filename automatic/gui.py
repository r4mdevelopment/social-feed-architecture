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
        root.title("Симулятор новостной ленты соцсети - Автоматический режим")

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
        ttk.Checkbutton(params_frame, text="Прямая постановка на прибор",
                        variable=self.chk_direct).pack(anchor="w", pady=3)

        # Кнопка запуска
        ttk.Button(main, text="Запустить автоматический режим",
                   command=self.run_auto).pack(pady=10)

        # Сводка
        summary_frame = ttk.LabelFrame(main, text="Сводка результатов")
        summary_frame.pack(fill="both", expand=True)

        cols = ("param", "value")
        self.summary_table = ttk.Treeview(summary_frame, columns=cols, show="headings", height=12)
        self.summary_table.heading("param", text="Параметр")
        self.summary_table.heading("value", text="Значение")

        self.summary_table.column("param", width=220, anchor="w")
        self.summary_table.column("value", width=130, anchor="center")

        self.summary_table.pack(fill="both", expand=True)

    # Параметры

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

    # Запуск автоматического режима

    def run_auto(self):
        if not self.read_params():
            return

        self.sim = SimulationCore(self.params)
        self.sim.bootstrap()

        result = self.sim.run_automatic(
            max_steps=self.params["steps"],
            max_time=9999.0,
        )

        for row in self.summary_table.get_children():
            self.summary_table.delete(row)

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

        for k, v in result.items():
            rus = names.get(k, k)
            self.summary_table.insert("", "end", values=(rus, f"{v}"))

        messagebox.showinfo("Готово", "Автоматическое моделирование завершено!")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
