"""
converter.py — Конвертер валют с GUI (tkinter + requests)
Флаги нарисованы через Canvas (работают на любом Windows без эмодзи).
История курса через fxapi.app (один запрос на 7 дней).
"""

import threading
import tkinter as tk
from tkinter import ttk
import requests
from datetime import date, timedelta

# ── API ──────────────────────────────────────────────────────────────────────
RATE_URL    = "https://open.er-api.com/v6/latest/{base}"
HISTORY_URL = "https://fxapi.app/api/history/{base}/{target}.json?from={frm}&to={to}"

# ── Валюты ───────────────────────────────────────────────────────────────────
POPULAR = ["USD", "EUR", "RUB", "CNY", "GBP", "JPY", "KZT", "BYN", "UAH", "TRY", "CHF", "CAD"]

# Флаги: список горизонтальных полос (цвет, доля высоты)
# Для сложных флагов — упрощённые до 2–3 полос + при необходимости крест/круг
FLAG_STRIPES = {
    "USD": [("#B22234", 0.5), ("#FFFFFF", 0.5)],          # красно-белый упрощённо
    "EUR": [("#003399", 1.0)],                              # синий (флаг ЕС)
    "RUB": [("#FFFFFF", 0.333), ("#0033A0", 0.333), ("#DA291C", 0.334)],
    "CNY": [("#DE2910", 1.0)],                              # красный
    "GBP": [("#012169", 0.5), ("#C8102E", 0.5)],           # синий+красный
    "JPY": [("#FFFFFF", 1.0)],                              # белый
    "KZT": [("#00AFCA", 1.0)],                              # голубой
    "BYN": [("#CF101A", 0.667), ("#009A44", 0.333)],
    "UAH": [("#005BBB", 0.5), ("#FFD500", 0.5)],
    "TRY": [("#E30A17", 1.0)],                              # красный
    "CHF": [("#FF0000", 1.0)],                              # красный
    "CAD": [("#FF0000", 0.25), ("#FFFFFF", 0.5), ("#FF0000", 0.25)],
}

# ── Цвета UI ─────────────────────────────────────────────────────────────────
BG         = "#0f0f17"
SURFACE    = "#1a1a2a"
BORDER     = "#2e2e46"
ACCENT     = "#7c6af7"
ACCENT2    = "#56cfb2"
TEXT       = "#e8e8f0"
MUTED      = "#6c6c8a"
CHART_UP   = "#56cfb2"
CHART_DOWN = "#f07070"
GRID_COL   = "#1e1e30"

FW, FH = 22, 14   # размер флага в пикселях


def fmt_number(value: float) -> str:
    """1 234 567,89  — пробел=тысячи, запятая=дробная часть."""
    s = f"{value:,.2f}"
    s = s.replace(",", "\u2009")   # thin space для тысяч
    s = s.replace(".", ",")
    return s


# ── Флаг-виджет ──────────────────────────────────────────────────────────────
class FlagCanvas(tk.Canvas):
    def __init__(self, parent, code: str, **kw):
        super().__init__(parent, width=FW, height=FH,
                         highlightthickness=1, highlightbackground=BORDER,
                         **kw)
        self._draw(code)

    def _draw(self, code: str) -> None:
        self.delete("all")
        stripes = FLAG_STRIPES.get(code, [("#888888", 1.0)])
        y = 0
        for color, frac in stripes:
            h = max(1, round(FH * frac))
            self.create_rectangle(0, y, FW, y + h, fill=color, outline="")
            y += h

        # Особые символы поверх
        if code == "JPY":   # красный круг
            cx, cy, r = FW // 2, FH // 2, FH // 3
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             fill="#BC002D", outline="")
        elif code == "CHF":  # белый крест
            cx, cy = FW // 2, FH // 2
            self.create_rectangle(cx - 1, cy - 4, cx + 2, cy + 5,
                                  fill="white", outline="")
            self.create_rectangle(cx - 4, cy - 1, cx + 5, cy + 2,
                                  fill="white", outline="")
        elif code == "EUR":  # жёлтый круг из точек (упрощённо — кольцо)
            cx, cy, r = FW // 2, FH // 2, FH // 3
            self.create_oval(cx - r, cy - r, cx + r, cy + r,
                             outline="#FFCC00", width=2)
        elif code == "GBP":  # белый крест
            self.create_line(0, 0, FW, FH, fill="white", width=1)
            self.create_line(FW, 0, 0, FH, fill="white", width=1)
            self.create_line(FW // 2, 0, FW // 2, FH, fill="white", width=2)
            self.create_line(0, FH // 2, FW, FH // 2, fill="white", width=2)
        elif code == "USD":  # горизонтальные полосы
            for i in range(13):
                c = "#B22234" if i % 2 == 0 else "#FFFFFF"
                y0 = round(FH * i / 13)
                y1 = round(FH * (i + 1) / 13)
                self.create_rectangle(0, y0, FW, y1, fill=c, outline="")
            self.create_rectangle(0, 0, FW // 2, FH // 2,
                                  fill="#3C3B6E", outline="")
        elif code == "CNY":  # жёлтая звезда
            cx, cy = FW // 4, FH // 3
            self.create_text(cx, cy, text="★", fill="#FFDE00",
                             font=("Arial", 6))
        elif code == "KZT":  # солнце упрощённо
            self.create_oval(FW // 2 - 3, FH // 2 - 3,
                             FW // 2 + 3, FH // 2 + 3,
                             fill="#FFC800", outline="")
        elif code == "TRY":  # полумесяц + звезда
            cx, cy = FW // 2 + 1, FH // 2
            self.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                             fill="white", outline="")
            self.create_oval(cx - 2, cy - 4, cx + 5, cy + 4,
                             fill="#E30A17", outline="")
        elif code == "CAD":  # кленовый лист (упрощённо — красный ромб)
            pts = [FW // 2, 2, FW - 3, FH // 2, FW // 2, FH - 2, 3, FH // 2]
            self.create_polygon(pts, fill="#FF0000", outline="")


# ── Комбобокс с флагом ───────────────────────────────────────────────────────
class FlagCombo(tk.Frame):
    """Frame = [флаг][код валюты ▾] с выпадающим меню через Toplevel."""

    def __init__(self, parent, codes: list[str], initial: str,
                 on_change=None, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._codes = codes
        self._value = initial
        self._on_change = on_change

        self._flag_cv = FlagCanvas(self, initial, bg=SURFACE)
        self._flag_cv.grid(row=0, column=0, padx=(6, 4), pady=6)

        self._label = tk.Label(self, text=initial, bg=SURFACE, fg=TEXT,
                               font=("Segoe UI", 12), cursor="hand2",
                               padx=4, pady=4)
        self._label.grid(row=0, column=1, sticky="ew")

        arrow = tk.Label(self, text="▾", bg=SURFACE, fg=ACCENT,
                         font=("Segoe UI", 10), cursor="hand2", padx=4)
        arrow.grid(row=0, column=2, padx=(0, 6))

        self.configure(highlightthickness=1, highlightbackground=BORDER)
        self.columnconfigure(1, weight=1)

        for w in (self, self._flag_cv, self._label, arrow):
            w.bind("<Button-1>", self._open_menu)

    def get(self) -> str:
        return self._value

    def set(self, code: str) -> None:
        self._value = code
        self._label.config(text=code)
        self._flag_cv._draw(code)

    def _open_menu(self, event=None) -> None:
        top = tk.Toplevel(self)
        top.overrideredirect(True)
        top.configure(bg=BORDER)

        # Позиция под виджетом
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        top.geometry(f"+{x}+{y}")

        canvas = tk.Canvas(top, bg=SURFACE, highlightthickness=0,
                           width=160, height=min(len(self._codes) * 30, 300))
        sb = tk.Scrollbar(top, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        inner = tk.Frame(canvas, bg=SURFACE)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        for code in self._codes:
            row = tk.Frame(inner, bg=SURFACE, cursor="hand2")
            row.pack(fill="x")
            FlagCanvas(row, code, bg=SURFACE).pack(side="left",
                                                    padx=(6, 4), pady=3)
            lbl = tk.Label(row, text=code, bg=SURFACE, fg=TEXT,
                           font=("Segoe UI", 11), cursor="hand2",
                           anchor="w", padx=4)
            lbl.pack(side="left", fill="x", expand=True)

            def pick(c=code, t=top):
                self.set(c)
                if self._on_change:
                    self._on_change(c)
                t.destroy()

            row.bind("<Button-1>", lambda e, p=pick: p())
            lbl.bind("<Button-1>", lambda e, p=pick: p())
            row.bind("<Enter>", lambda e, r=row: r.config(bg=BORDER))
            row.bind("<Leave>", lambda e, r=row: r.config(bg=SURFACE))

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        # Закрыть по клику вне
        top.bind("<FocusOut>", lambda e: top.destroy())
        top.focus_set()


# ── Мини-график ──────────────────────────────────────────────────────────────
class MiniChart(tk.Canvas):
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 14, 14, 26

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=SURFACE, highlightthickness=0, **kw)
        self._data: list[tuple[str, float]] = []

    def set_data(self, data: list[tuple[str, float]]) -> None:
        self._data = data
        self.after(10, self._draw)

    def _draw(self) -> None:
        self.delete("all")
        W = self.winfo_width() or int(self["width"])
        H = self.winfo_height() or int(self["height"])
        pl, pr, pt, pb = self.PAD_L, self.PAD_R, self.PAD_T, self.PAD_B

        if len(self._data) < 2:
            self.create_text(W // 2, H // 2,
                             text="Нет данных для этой пары валют",
                             fill=MUTED, font=("Segoe UI", 9))
            return

        values = [v for _, v in self._data]
        labels = [l for l, _ in self._data]
        mn, mx = min(values), max(values)
        span = (mx - mn) if mx != mn else (mn * 0.02 or 0.01)
        mn -= span * 0.15
        mx += span * 0.15
        span = mx - mn

        def cx(i): return pl + (W - pl - pr) * i / (len(values) - 1)
        def cy(v): return pt + (H - pt - pb) * (1 - (v - mn) / span)

        # Сетка
        for k in range(5):
            yg = pt + (H - pt - pb) * k / 4
            vg = mx - (span * k / 4)
            self.create_line(pl, yg, W - pr, yg, fill=GRID_COL, width=1)
            self.create_text(pl - 4, yg, text=f"{vg:.4f}",
                             fill=MUTED, font=("Consolas", 7), anchor="e")

        pts = [(cx(i), cy(v)) for i, v in enumerate(values)]
        is_up = values[-1] >= values[0]
        line_col = CHART_UP if is_up else CHART_DOWN

        # Заливка под кривой (полигон)
        poly = []
        for px, py in pts:
            poly += [px, py]
        poly += [pts[-1][0], H - pb, pts[0][0], H - pb]
        # Рисуем полупрозрачный эффект несколькими прямоугольниками
        fill_col = "#1a3d35" if is_up else "#3d1a1a"
        if len(poly) >= 6:
            self.create_polygon(poly, fill=fill_col, outline="")

        # Линия
        for i in range(len(pts) - 1):
            self.create_line(pts[i][0], pts[i][1],
                             pts[i+1][0], pts[i+1][1],
                             fill=line_col, width=2)

        # Точки
        for px, py in pts:
            self.create_oval(px - 3, py - 3, px + 3, py + 3,
                             fill=line_col, outline=SURFACE, width=1)

        # Подписи X
        step = max(1, len(labels) // 7)
        for i, lbl in enumerate(labels):
            if i % step == 0 or i == len(labels) - 1:
                self.create_text(cx(i), H - pb + 10, text=lbl,
                                 fill=MUTED, font=("Consolas", 7))

        # Тренд
        pct = ((values[-1] - values[0]) / values[0] * 100) if values[0] else 0
        arrow = "▲" if is_up else "▼"
        self.create_text(W - pr, pt,
                         text=f"{arrow} {pct:+.2f}%",
                         fill=line_col, font=("Segoe UI", 8, "bold"),
                         anchor="ne")


# ── API ──────────────────────────────────────────────────────────────────────
def get_exchange_rate(base: str, target: str) -> float:
    url = RATE_URL.format(base=base.upper())
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    data = r.json()
    if data.get("result") != "success":
        raise ValueError(data.get("error-type", "ошибка API"))
    rates = data.get("rates", {})
    if target.upper() not in rates:
        raise KeyError(f"Валюта «{target.upper()}» не найдена")
    return rates[target.upper()]


def get_rate_history(base: str, target: str, days: int = 7) -> list[tuple[str, float]]:
    today = date.today()
    frm = (today - timedelta(days=days - 1)).isoformat()
    to = today.isoformat()
    url = HISTORY_URL.format(base=base.upper(), target=target.upper(),
                             frm=frm, to=to)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    result = []
    for item in data.get("rates", []):
        d = item.get("date", "")
        rate = item.get("rate")
        if d and rate is not None:
            label = d[8:10] + "." + d[5:7]   # dd.mm
            result.append((label, float(rate)))
    return result


# ── Приложение ───────────────────────────────────────────────────────────────
class ConverterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._build_window()
        self._build_ui()

    def _build_window(self) -> None:
        self.root.title("Конвертер валют")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        w, h = 430, 610
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _lbl(self, parent, text, size=9, color=MUTED, bold=False):
        return tk.Label(parent, text=text, bg=BG, fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"))

    def _entry(self, parent, textvariable=None):
        return tk.Entry(parent, textvariable=textvariable,
                        bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                        relief="flat", bd=0, font=("Segoe UI", 13),
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT)

    def _build_ui(self) -> None:
        pad = dict(padx=24)

        tk.Frame(self.root, bg=ACCENT, height=4).pack(fill="x")
        self._lbl(self.root, "💱  КОНВЕРТЕР ВАЛЮТ", size=15,
                  color=TEXT, bold=True).pack(pady=(18, 3))
        self._lbl(self.root, "Курсы: open.er-api.com · История: fxapi.app",
                  size=8).pack(pady=(0, 12))

        # ── Исходная + сумма ─────────────────────
        row1 = tk.Frame(self.root, bg=BG)
        row1.pack(fill="x", **pad)

        col_l = tk.Frame(row1, bg=BG)
        col_l.pack(side="left", expand=True, fill="x", padx=(0, 10))
        self._lbl(col_l, "ИСХОДНАЯ ВАЛЮТА").pack(anchor="w")
        self.base_combo = FlagCombo(col_l, POPULAR, "USD")
        self.base_combo.pack(fill="x", pady=(4, 0))

        col_r = tk.Frame(row1, bg=BG)
        col_r.pack(side="left", expand=True, fill="x")
        self._lbl(col_r, "СУММА").pack(anchor="w")
        self.amount_var = tk.StringVar(value="100")
        e = self._entry(col_r, self.amount_var)
        e.pack(fill="x", pady=(4, 0), ipady=9)

        # ── Swap ─────────────────────────────────
        tk.Button(self.root, text="⇅  поменять",
                  command=self._swap,
                  bg=BG, fg=ACCENT, font=("Segoe UI", 9),
                  relief="flat", bd=0, cursor="hand2",
                  activebackground=BG, activeforeground=ACCENT2
                  ).pack(pady=8)

        # ── Целевая ──────────────────────────────
        row2 = tk.Frame(self.root, bg=BG)
        row2.pack(fill="x", **pad)
        self._lbl(row2, "ЦЕЛЕВАЯ ВАЛЮТА").pack(anchor="w")
        self.target_combo = FlagCombo(row2, POPULAR, "RUB")
        self.target_combo.pack(anchor="w", pady=(4, 0), fill="x")

        # ── Конвертировать ───────────────────────
        self.conv_btn = tk.Button(
            self.root, text="Конвертировать",
            command=self._start_convert,
            bg=ACCENT, fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
            relief="flat", bd=0, cursor="hand2",
            activebackground="#6a58e0", activeforeground="#ffffff",
            padx=20, pady=10,
        )
        self.conv_btn.pack(fill="x", padx=24, pady=14)

        # ── Результат ─────────────────────────────
        rf = tk.Frame(self.root, bg=SURFACE,
                      highlightthickness=1, highlightbackground=BORDER)
        rf.pack(fill="x", padx=24)
        self.result_var = tk.StringVar(value="—")
        tk.Label(rf, textvariable=self.result_var,
                 bg=SURFACE, fg=ACCENT2,
                 font=("Segoe UI", 15, "bold"),
                 pady=12, wraplength=370).pack()
        self.rate_var = tk.StringVar(value="")
        tk.Label(rf, textvariable=self.rate_var,
                 bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9), pady=6).pack()

        # ── График ───────────────────────────────
        cf = tk.Frame(self.root, bg=BG)
        cf.pack(fill="x", padx=24, pady=(12, 2))
        self._lbl(cf, "КУРС ЗА 7 ДНЕЙ").pack(side="left")
        self.chart_status = tk.Label(cf, text="", bg=BG, fg=MUTED,
                                     font=("Segoe UI", 8))
        self.chart_status.pack(side="right")

        self.chart = MiniChart(self.root, width=382, height=120)
        self.chart.pack(padx=24, fill="x")

        # ── Статус ────────────────────────────────
        self.status_var = tk.StringVar(value="Готов к работе")
        tk.Label(self.root, textvariable=self.status_var,
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), pady=8).pack()

    def _swap(self) -> None:
        b, t = self.base_combo.get(), self.target_combo.get()
        self.base_combo.set(t)
        self.target_combo.set(b)

    def _start_convert(self) -> None:
        raw = self.amount_var.get().replace(",", ".").replace("\u2009", "").replace(" ", "").strip()
        try:
            amount = float(raw)
            if amount < 0:
                raise ValueError
        except ValueError:
            self.result_var.set("⚠  Введите корректную сумму (число ≥ 0)")
            return

        base, target = self.base_combo.get(), self.target_combo.get()
        self.conv_btn.config(state="disabled", text="Загрузка...")
        self.status_var.set("Запрашиваю курс...")
        self.result_var.set("…")
        self.rate_var.set("")
        self.chart_status.config(text="загрузка графика…")
        self.root.update()

        threading.Thread(target=self._fetch, args=(base, target, amount),
                         daemon=True).start()

    def _fetch(self, base, target, amount) -> None:
        try:
            rate = get_exchange_rate(base, target)
            result = amount * rate
            self.root.after(0, self._show_result, amount, base, result, target, rate)
            threading.Thread(target=self._fetch_history, args=(base, target),
                             daemon=True).start()
        except KeyError as e:
            self.root.after(0, self.result_var.set, f"⚠  {e}")
        except requests.exceptions.ConnectionError:
            self.root.after(0, self.result_var.set, "⚠  Нет интернета")
        except requests.exceptions.Timeout:
            self.root.after(0, self.result_var.set, "⚠  Сервер не отвечает")
        except Exception as e:
            self.root.after(0, self.result_var.set, f"⚠  {e}")
        finally:
            self.root.after(0, self._reset_btn)

    def _fetch_history(self, base, target) -> None:
        try:
            history = get_rate_history(base, target, days=7)
            self.root.after(0, self._show_chart, history)
        except Exception as e:
            self.root.after(0, self.chart_status.config,
                            {"text": f"график недоступен: {e}"})

    def _show_result(self, amount, base, result, target, rate) -> None:
        self.result_var.set(
            f"{fmt_number(amount)} {base}  =  {fmt_number(result)} {target}")
        self.rate_var.set(f"1 {base} = {rate:.6f} {target}")
        self.status_var.set("✓ Готово")

    def _show_chart(self, history) -> None:
        self.chart.set_data(history)
        n = len(history)
        self.chart_status.config(
            text=f"{n} дней" if n else "нет данных для этой пары")

    def _reset_btn(self) -> None:
        self.conv_btn.config(state="normal", text="Конвертировать")


def main() -> None:
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
