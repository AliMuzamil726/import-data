"""
=============================================================================
  SCIENTIFIC CALCULATOR — Production-Ready Desktop Application
  Stack   : Python 3.11+ | PyQt6 | MVC Architecture
  Version : 4.0.0  — v3 bug-free code  +  v1 light theme
=============================================================================
  Install:  pip install PyQt6
  Run    :  python scientific_calculator.py
=============================================================================
"""
import sys
import json
import math
import re
from pathlib import Path
from datetime import datetime


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QScrollArea, QFrame,
    QSizePolicy, QSplitter,
)
from PyQt6.QtCore  import Qt, QTimer, pyqtSignal
from PyQt6.QtGui   import (
    QKeySequence, QShortcut, QColor, QPalette, QMouseEvent, QKeyEvent,
)


# ─────────────────────────────────────────────────────────────────────────────
#  LIGHT COLOUR PALETTE  (from v1)
# ─────────────────────────────────────────────────────────────────────────────

CLR_BG              = "#F0F2F5"
CLR_DISPLAY_BG      = "#FFFFFF"
CLR_DISPLAY_FG      = "#1A1A2E"
CLR_EXPR_FG         = "#6B7280"
CLR_BTN_NUM         = "#FFFFFF"
CLR_BTN_NUM_HV      = "#EEF2FF"
CLR_BTN_OP          = "#E8F4FD"
CLR_BTN_OP_HV       = "#BFDBFE"
CLR_BTN_FUNC        = "#F3F4F6"
CLR_BTN_FUNC_HV     = "#E5E7EB"
CLR_BTN_ACTION      = "#3B82F6"
CLR_BTN_ACTION_HV   = "#2563EB"
CLR_BTN_DANGER      = "#FEE2E2"
CLR_BTN_DANGER_HV   = "#FCA5A5"
CLR_BTN_MEM         = "#E8F5E9"
CLR_BTN_MEM_HV      = "#C8E6C9"
CLR_BTN_MODE        = "#EDE9FE"
CLR_BTN_MODE_HV     = "#DDD6FE"
CLR_SIDEBAR_BG      = "#FAFAFA"
CLR_HIST_ITEM       = "#F9FAFB"
CLR_HIST_ITEM_HV    = "#EFF6FF"
CLR_BORDER          = "#E5E7EB"
CLR_MEM_BADGE       = "#10B981"
CLR_TEXT_PRIMARY    = "#111827"
CLR_TEXT_MUTED      = "#9CA3AF"

APP_NAME            = "ScientificCalc"
APP_VERSION         = "4.0.0"
HISTORY_FILE        = Path(__file__).parent / "data" / "history.json"


# ─────────────────────────────────────────────────────────────────────────────
#  MODEL — CalculatorEngine
# ─────────────────────────────────────────────────────────────────────────────

class CalculatorEngine:
    """Pure business logic — zero UI dependency."""

    def __init__(self) -> None:
        self._expression      : str         = ""
        self._result          : float | None = None
        self._memory          : float       = 0.0
        self._angle_mode      : str         = "DEG"
        self._last_was_result : bool        = False

    @property
    def expression(self)  -> str:          return self._expression
    @property
    def result(self)       -> float | None: return self._result
    @property
    def angle_mode(self)   -> str:          return self._angle_mode
    @property
    def has_memory(self)   -> bool:         return self._memory != 0.0

    # ── Editing ───────────────────────────────────────────────────────────────
    def append(self, token: str) -> None:
        if self._last_was_result and token not in ("+","-","*","/","**","%",")"):
            self._expression = ""
        self._last_was_result = False
        self._expression += token

    def backspace(self) -> None:
        self._expression = self._expression[:-1] if self._expression else ""
        self._last_was_result = False

    def clear_entry(self) -> None:
        self._expression = ""; self._result = None; self._last_was_result = False

    def all_clear(self) -> None:
        self._expression = ""; self._result = None; self._last_was_result = False

    # ── Evaluate ──────────────────────────────────────────────────────────────
    def evaluate(self) -> tuple[float | None, str | None]:
        raw = self._expression.strip()
        if not raw:
            return None, "Empty expression"
        try:
            ns   = self._build_ns()
            expr = self._preprocess(raw)
            res  = float(eval(expr, {"__builtins__": {}}, ns))   # noqa: S307
            if math.isnan(res): return None, "Not a number"
            if math.isinf(res): return None, "Result is infinite"
            self._result = res; self._last_was_result = True
            return res, None
        except ZeroDivisionError:
            return None, "Division by zero"
        except (ValueError, OverflowError) as exc:
            return None, str(exc).capitalize()
        except Exception:
            return None, "Invalid expression"

    def _build_ns(self) -> dict:
        d = self._angle_mode == "DEG"
        return {
            "sin"  : lambda x: math.sin(math.radians(x) if d else x),
            "cos"  : lambda x: math.cos(math.radians(x) if d else x),
            "tan"  : lambda x: math.tan(math.radians(x) if d else x),
            "asin" : lambda x: math.degrees(math.asin(x)) if d else math.asin(x),
            "acos" : lambda x: math.degrees(math.acos(x)) if d else math.acos(x),
            "atan" : lambda x: math.degrees(math.atan(x)) if d else math.atan(x),
            "log"  : math.log10,
            "ln"   : math.log,
            "sqrt" : math.sqrt,
            "fact" : lambda x: float(math.factorial(int(x))),
            "abs"  : abs,
            "pi"   : math.pi,
            "e"    : math.e,
            "pow"  : pow,
            "round": round,
        }

    @staticmethod
    def _preprocess(expr: str) -> str:
        for old, new in [("×","*"),("÷","/"),("π","pi"),("√(","sqrt("),("−","-"),("^","**")]:
            expr = expr.replace(old, new)
        expr = re.sub(r'(\d)(pi|e\b|sqrt|sin|cos|tan|log|ln|fact|abs)', r'\1*\2', expr)
        expr = re.sub(r'\)\(', r')*(', expr)
        expr = re.sub(r'(\d)\(', r'\1*(', expr)
        return expr

    # ── Memory ────────────────────────────────────────────────────────────────
    def memory_store(self)    -> None:
        if self._result is not None: self._memory  = self._result
    def memory_add(self)      -> None:
        if self._result is not None: self._memory += self._result
    def memory_subtract(self) -> None:
        if self._result is not None: self._memory -= self._result
    def memory_recall(self)   -> str:  return self._fmt(self._memory)
    def memory_clear(self)    -> None: self._memory = 0.0

    def toggle_angle_mode(self) -> str:
        self._angle_mode = "RAD" if self._angle_mode == "DEG" else "DEG"
        return self._angle_mode

    @staticmethod
    def _fmt(n: float) -> str:
        if n == int(n) and abs(n) < 1e15:
            return str(int(n))
        return f"{n:.10g}"

    def format_result(self) -> str:
        return self._fmt(self._result) if self._result is not None else "0"


# ─────────────────────────────────────────────────────────────────────────────
#  SERVICE — HistoryManager
# ─────────────────────────────────────────────────────────────────────────────

class HistoryManager:
    MAX_HISTORY = 200

    def __init__(self) -> None:
        self._entries: list[dict] = []
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def add(self, expression: str, result: str) -> None:
        self._entries.append({
            "expression": expression,
            "result"    : result,
            "timestamp" : datetime.now().isoformat(timespec="seconds"),
        })
        self._entries = self._entries[-self.MAX_HISTORY:]
        self._save()

    def get_all(self)  -> list[dict]: return list(reversed(self._entries))
    def clear(self)    -> None:       self._entries.clear(); self._save()

    def _load(self) -> None:
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._entries = data
        except Exception:
            self._entries = []

    def _save(self) -> None:
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, ensure_ascii=False)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  VIEW — Display Screen
# ─────────────────────────────────────────────────────────────────────────────

class DisplayScreen(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DisplayScreen")
        self._build()

    def _build(self) -> None:
        self.setMinimumHeight(130)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)

        # Badge row
        top_row = QHBoxLayout()
        self.angle_label = QLabel("DEG")
        self.angle_label.setObjectName("AngleLabel")
        self.mem_label = QLabel("M")
        self.mem_label.setObjectName("MemLabel")
        self.mem_label.setVisible(False)
        top_row.addWidget(self.angle_label)
        top_row.addStretch()
        top_row.addWidget(self.mem_label)
        layout.addLayout(top_row)
        layout.addStretch()

        # Expression (small / muted)
        self.expr_label = QLabel("")
        self.expr_label.setObjectName("ExprLabel")
        self.expr_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.expr_label.setWordWrap(False)
        layout.addWidget(self.expr_label)

        # Result (large)
        self.result_label = QLabel("0")
        self.result_label.setObjectName("ResultLabel")
        self.result_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.result_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.result_label)

    # ── Public API ────────────────────────────────────────────────────────────
    def set_expression(self, text: str) -> None:
        self.expr_label.setText(text if len(text) <= 40 else "…" + text[-39:])

    def set_result(self, text: str) -> None:
        font_size = 36 if len(text) <= 14 else max(18, 36 - (len(text) - 14) * 2)
        self.result_label.setStyleSheet(f"font-size: {font_size}px;")
        self.result_label.setText(text)

    def set_angle_mode(self, mode: str) -> None:
        self.angle_label.setText(mode)

    def set_memory_visible(self, visible: bool) -> None:
        self.mem_label.setVisible(visible)

    def flash_error(self) -> None:
        self.setStyleSheet(f"#DisplayScreen {{ background: #FEE2E2; }}")
        QTimer.singleShot(350, lambda: self.setStyleSheet(
            f"#DisplayScreen {{ background: {CLR_DISPLAY_BG}; }}"
        ))


# ─────────────────────────────────────────────────────────────────────────────
#  VIEW — CalcButton
#  NOTE: Qt does NOT support 'transform' in stylesheets — never include it.
# ─────────────────────────────────────────────────────────────────────────────

# role → (bg, hover, pressed, fg)
_ROLES: dict[str, tuple[str, str, str, str]] = {
    "number"  : (CLR_BTN_NUM,    CLR_BTN_NUM_HV,    "#D1D5DB",       CLR_TEXT_PRIMARY),
    "operator": (CLR_BTN_OP,     CLR_BTN_OP_HV,     "#93C5FD",       "#1D4ED8"),
    "function": (CLR_BTN_FUNC,   CLR_BTN_FUNC_HV,   "#D1D5DB",       "#374151"),
    "action"  : (CLR_BTN_ACTION, CLR_BTN_ACTION_HV, "#1D4ED8",       "#FFFFFF"),
    "danger"  : (CLR_BTN_DANGER, CLR_BTN_DANGER_HV, "#FCA5A5",       "#DC2626"),
    "memory"  : (CLR_BTN_MEM,    CLR_BTN_MEM_HV,    "#A7F3D0",       "#166534"),
    "mode"    : (CLR_BTN_MODE,   CLR_BTN_MODE_HV,   "#C4B5FD",       "#5B21B6"),
}


class CalcButton(QPushButton):
    def __init__(self, label: str, role: str = "number",
                 parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self._role = role
        self._apply_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(54, 48)

    def _apply_style(self) -> None:
        bg, hv, pr, fg = _ROLES.get(self._role, _ROLES["number"])
        # ── Qt stylesheet does NOT support 'transform' — intentionally omitted
        self.setStyleSheet(f"""
            QPushButton {{
                background-color : {bg};
                color            : {fg};
                border           : 1px solid {CLR_BORDER};
                border-radius    : 10px;
                font-size        : 15px;
                font-weight      : 500;
                padding          : 6px 4px;
            }}
            QPushButton:hover {{
                background-color : {hv};
                border-color     : #CBD5E1;
            }}
            QPushButton:pressed {{
                background-color : {pr};
                border-color     : #93C5FD;
            }}
        """)


# ─────────────────────────────────────────────────────────────────────────────
#  VIEW — Button Panel
# ─────────────────────────────────────────────────────────────────────────────

_BUTTON_DEFS: list[tuple[str, str, str, int, int, int, int]] = [
    # label      role        action    row col  rs  cs
    # ── Row 0 : Memory ───────────────────────────────────────────────────────
    ("MC",       "memory",   "MC",      0,  0,  1,  1),
    ("MR",       "memory",   "MR",      0,  1,  1,  1),
    ("M+",       "memory",   "M+",      0,  2,  1,  1),
    ("M-",       "memory",   "M-",      0,  3,  1,  1),
    ("DEG",      "mode",     "MODE",    0,  4,  1,  1),
    # ── Row 1 : Trig ─────────────────────────────────────────────────────────
    ("sin",      "function", "sin(",    1,  0,  1,  1),
    ("cos",      "function", "cos(",    1,  1,  1,  1),
    ("tan",      "function", "tan(",    1,  2,  1,  1),
    ("π",        "function", "pi",      1,  3,  1,  1),
    ("e",        "function", "e",       1,  4,  1,  1),
    # ── Row 2 : Powers / Roots ───────────────────────────────────────────────
    ("x²",       "function", "**2",     2,  0,  1,  1),
    ("xʸ",       "function", "**",      2,  1,  1,  1),
    ("√",        "function", "sqrt(",   2,  2,  1,  1),
    ("log",      "function", "log(",    2,  3,  1,  1),
    ("ln",       "function", "ln(",     2,  4,  1,  1),
    # ── Row 3 : Misc ─────────────────────────────────────────────────────────
    ("n!",       "function", "fact(",   3,  0,  1,  1),
    ("(",        "function", "(",       3,  1,  1,  1),
    (")",        "function", ")",       3,  2,  1,  1),
    ("%",        "operator", "%",       3,  3,  1,  1),
    ("AC",       "danger",   "AC",      3,  4,  1,  1),
    # ── Row 4 ─────────────────────────────────────────────────────────────────
    ("7",        "number",   "7",       4,  0,  1,  1),
    ("8",        "number",   "8",       4,  1,  1,  1),
    ("9",        "number",   "9",       4,  2,  1,  1),
    ("÷",        "operator", "/",       4,  3,  1,  1),
    ("⌫",        "danger",   "BS",      4,  4,  1,  1),
    # ── Row 5 ─────────────────────────────────────────────────────────────────
    ("4",        "number",   "4",       5,  0,  1,  1),
    ("5",        "number",   "5",       5,  1,  1,  1),
    ("6",        "number",   "6",       5,  2,  1,  1),
    ("×",        "operator", "*",       5,  3,  1,  1),
    ("C",        "function", "C",       5,  4,  1,  1),
    # ── Row 6 ─────────────────────────────────────────────────────────────────
    ("1",        "number",   "1",       6,  0,  1,  1),
    ("2",        "number",   "2",       6,  1,  1,  1),
    ("3",        "number",   "3",       6,  2,  1,  1),
    ("−",        "operator", "-",       6,  3,  1,  1),
    ("=",        "action",   "=",       6,  4,  2,  1),  # rowspan=2
    # ── Row 7 ─────────────────────────────────────────────────────────────────
    ("0",        "number",   "0",       7,  0,  1,  2),  # colspan=2
    (".",        "number",   ".",       7,  2,  1,  1),
    ("+",        "operator", "+",       7,  3,  1,  1),
]


class ButtonPanel(QWidget):
    button_pressed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._btn_map: dict[str, CalcButton] = {}
        self._build()

    def _build(self) -> None:
        grid = QGridLayout(self)
        grid.setSpacing(6)
        grid.setContentsMargins(12, 8, 12, 12)
        for label, role, action, row, col, rs, cs in _BUTTON_DEFS:
            btn = CalcButton(label, role)
            self._btn_map[action] = btn
            grid.addWidget(btn, row, col, rs, cs)
            btn.clicked.connect(lambda _checked, a=action: self.button_pressed.emit(a))
        for i in range(8): grid.setRowStretch(i, 1)
        for j in range(5): grid.setColumnStretch(j, 1)

    def update_mode_button(self, mode: str) -> None:
        btn = self._btn_map.get("MODE")
        if btn is not None:      # ← guard: .get() can return None
            btn.setText(mode)


# ─────────────────────────────────────────────────────────────────────────────
#  VIEW — HistoryItemFrame
#  Proper QFrame subclass — avoids Pylance monkey-patch error on mousePressEvent
# ─────────────────────────────────────────────────────────────────────────────

class HistoryItemFrame(QFrame):
    """Clickable history card — subclasses QFrame with correct override."""
    clicked = pyqtSignal(str)

    def __init__(self, expression: str, result: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expression = expression
        self.setObjectName("HistoryItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)

        expr_lbl = QLabel(expression)
        expr_lbl.setObjectName("HistExpr")
        expr_lbl.setWordWrap(True)

        res_lbl = QLabel(f"= {result}")
        res_lbl.setObjectName("HistResult")

        lay.addWidget(expr_lbl)
        lay.addWidget(res_lbl)

        # Inline hover style per card (v1 approach)
        self.setStyleSheet(f"""
            QFrame#HistoryItem {{
                background    : {CLR_HIST_ITEM};
                border        : 1px solid {CLR_BORDER};
                border-radius : 8px;
            }}
            QFrame#HistoryItem:hover {{
                background    : {CLR_HIST_ITEM_HV};
                border-color  : #BFDBFE;
            }}
        """)

    # Correct Qt override: parameter name must be 'a0', not 'event'
    def mousePressEvent(self, a0: QMouseEvent | None) -> None:  # type: ignore[override]
        self.clicked.emit(self._expression)
        super().mousePressEvent(a0)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
#  VIEW — History Panel
# ─────────────────────────────────────────────────────────────────────────────

class HistoryPanel(QWidget):
    history_clicked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HistoryPanel")
        self.setMinimumWidth(210)
        self.setMaximumWidth(300)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("HistoryHeader")
        header.setFixedHeight(48)
        hdr_layout = QHBoxLayout(header)
        hdr_layout.setContentsMargins(16, 0, 8, 0)

        title = QLabel("History")
        title.setObjectName("HistoryTitle")

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("ClearHistBtn")
        clear_btn.setFixedSize(56, 28)
        clear_btn.clicked.connect(self._on_clear)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        hdr_layout.addWidget(title)
        hdr_layout.addStretch()
        hdr_layout.addWidget(clear_btn)
        root.addWidget(header)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setObjectName("Divider")
        root.addWidget(div)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setObjectName("HistoryScroll")

        self._container = QWidget()
        self._container.setObjectName("HistoryContainer")
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(8, 8, 8, 8)
        self._vbox.setSpacing(4)
        self._vbox.addStretch()

        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, 1)

        # Empty state
        self._empty_label = QLabel("No history yet.\nStart calculating!")
        self._empty_label.setObjectName("EmptyLabel")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vbox.insertWidget(0, self._empty_label)

    # ── Public API ────────────────────────────────────────────────────────────
    def add_entry(self, expression: str, result: str) -> None:
        self._empty_label.hide()
        item = HistoryItemFrame(expression, result)
        item.clicked.connect(self.history_clicked)
        self._vbox.insertWidget(0, item)

    def clear_display(self) -> None:
        while self._vbox.count() > 2:
            layout_item = self._vbox.takeAt(0)
            if layout_item is not None:          # ← guard: takeAt() can return None
                widget = layout_item.widget()
                if widget is not None:           # ← guard: widget() can return None
                    widget.deleteLater()
        self._empty_label.show()

    def load_history(self, entries: list[dict]) -> None:
        for entry in reversed(entries):
            self.add_entry(entry["expression"], entry["result"])

    def _on_clear(self) -> None:
        self.clear_display()
        self.history_clicked.emit("__CLEAR__")


# ─────────────────────────────────────────────────────────────────────────────
#  CONTROLLER
# ─────────────────────────────────────────────────────────────────────────────

class MainController:
    def __init__(self, display: DisplayScreen, buttons: ButtonPanel,
                 history_panel: HistoryPanel) -> None:
        self._engine    = CalculatorEngine()
        self._history   = HistoryManager()
        self._display   = display
        self._buttons   = buttons
        self._hist_panel = history_panel

        self._buttons.button_pressed.connect(self._on_button)
        self._hist_panel.history_clicked.connect(self._on_history_item)
        self._hist_panel.load_history(self._history.get_all())
        self._refresh_display()

    def _on_button(self, action: str) -> None:
        e = self._engine
        if   action == "AC"  : e.all_clear()
        elif action == "C"   : e.clear_entry()
        elif action == "BS"  : e.backspace()
        elif action == "="   : self._do_evaluate(); return
        elif action == "MODE":
            mode = e.toggle_angle_mode()
            self._buttons.update_mode_button(mode)
            self._display.set_angle_mode(mode)
            return
        elif action == "MC"  : e.memory_clear();    self._display.set_memory_visible(e.has_memory)
        elif action == "MR"  : e.append(e.memory_recall())
        elif action == "M+"  : e.memory_add();      self._display.set_memory_visible(e.has_memory)
        elif action == "M-"  : e.memory_subtract(); self._display.set_memory_visible(e.has_memory)
        else                 : e.append(action)
        self._refresh_display()

    def _do_evaluate(self) -> None:
        expr = self._engine.expression.strip()
        if not expr:
            return
        result, error = self._engine.evaluate()
        if error:
            self._display.set_expression(expr)
            self._display.set_result(error)
            self._display.flash_error()
        else:
            result_str = self._engine.format_result()
            self._display.set_expression(f"{expr} =")
            self._display.set_result(result_str)
            self._history.add(expr, result_str)
            self._hist_panel.add_entry(expr, result_str)
        self._display.set_memory_visible(self._engine.has_memory)

    def _refresh_display(self) -> None:
        expr = self._engine.expression
        self._display.set_expression(expr)
        self._display.set_result(expr if expr else "0")

    def _on_history_item(self, expression: str) -> None:
        if expression == "__CLEAR__":
            self._history.clear()
            return
        self._engine.all_clear()
        for ch in expression:
            self._engine.append(ch)
        self._refresh_display()

    def handle_key(self, key_text: str, key: int) -> None:
        from PyQt6.QtCore import Qt as _Qt
        mapping = {
            "0":"0","1":"1","2":"2","3":"3","4":"4",
            "5":"5","6":"6","7":"7","8":"8","9":"9",
            "+":"+","-":"-","*":"*","/":"/",
            "(":"(",")":")",".":" .","%":"%",
        }
        if key_text in mapping:
            self._on_button(key_text)
        elif key in (_Qt.Key.Key_Return, _Qt.Key.Key_Enter):
            self._on_button("=")
        elif key == _Qt.Key.Key_Backspace:
            self._on_button("BS")
        elif key == _Qt.Key.Key_Escape:
            self._on_button("AC")
        elif key_text.lower() == "c":
            self._on_button("C")

    def copy_result(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._display.result_label.text())


# ─────────────────────────────────────────────────────────────────────────────
#  GLOBAL STYLESHEET  — v1 Light Theme (clean white + soft blue accents)
# ─────────────────────────────────────────────────────────────────────────────

_STYLE = f"""
/* ── Global ────────────────────────────────────────────────────── */
QMainWindow, QWidget {{
    background-color : {CLR_BG};
    font-family      : 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif;
}}

/* ── Splitter ───────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color : {CLR_BORDER};
    width            : 1px;
}}

/* ── Display ────────────────────────────────────────────────────── */
#DisplayScreen {{
    background-color : {CLR_DISPLAY_BG};
    border-bottom    : 1px solid {CLR_BORDER};
}}
#AngleLabel {{
    font-size     : 11px;
    font-weight   : 600;
    color         : {CLR_BTN_ACTION};
    background    : #EFF6FF;
    border        : 1px solid #BFDBFE;
    border-radius : 4px;
    padding       : 2px 7px;
}}
#MemLabel {{
    font-size     : 11px;
    font-weight   : 700;
    color         : #FFFFFF;
    background    : {CLR_MEM_BADGE};
    border-radius : 4px;
    padding       : 2px 7px;
}}
#ExprLabel {{
    font-size   : 14px;
    color       : {CLR_EXPR_FG};
    font-weight : 400;
}}
#ResultLabel {{
    font-size      : 36px;
    font-weight    : 300;
    color          : {CLR_DISPLAY_FG};
    letter-spacing : -1px;
}}

/* ── History Panel ──────────────────────────────────────────────── */
#HistoryPanel {{
    background-color : {CLR_SIDEBAR_BG};
    border-left      : 1px solid {CLR_BORDER};
}}
#HistoryHeader {{
    background    : {CLR_SIDEBAR_BG};
    border-bottom : 1px solid {CLR_BORDER};
}}
#HistoryTitle {{
    font-size   : 13px;
    font-weight : 600;
    color       : {CLR_TEXT_PRIMARY};
}}
#ClearHistBtn {{
    background    : transparent;
    color         : {CLR_BTN_ACTION};
    border        : 1px solid #BFDBFE;
    border-radius : 6px;
    font-size     : 12px;
    font-weight   : 500;
}}
#ClearHistBtn:hover {{
    background : #EFF6FF;
}}
#Divider {{
    color            : {CLR_BORDER};
    background-color : {CLR_BORDER};
    max-height       : 1px;
}}
#HistoryScroll {{
    background : {CLR_SIDEBAR_BG};
    border     : none;
}}
#HistoryContainer {{
    background : {CLR_SIDEBAR_BG};
}}
#HistExpr {{
    font-size   : 12px;
    color       : {CLR_EXPR_FG};
    font-weight : 400;
}}
#HistResult {{
    font-size   : 14px;
    font-weight : 600;
    color       : {CLR_TEXT_PRIMARY};
}}
#EmptyLabel {{
    font-size : 13px;
    color     : {CLR_TEXT_MUTED};
    padding   : 40px 16px;
}}

/* ── Scrollbar ──────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background : transparent;
    width      : 6px;
    margin     : 0;
}}
QScrollBar::handle:vertical {{
    background    : #D1D5DB;
    border-radius : 3px;
    min-height    : 20px;
}}
QScrollBar::handle:vertical:hover {{
    background : #9CA3AF;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height : 0px;
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  {APP_VERSION}")
        self.setMinimumSize(720, 620)
        self.resize(860, 680)
        self._build_ui()
        self.setStyleSheet(_STYLE)
        # Ctrl+C → copy result to clipboard
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(
            self._controller.copy_result
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Calculator pane
        calc_widget = QWidget()
        calc_widget.setObjectName("CalcWidget")
        calc_layout = QVBoxLayout(calc_widget)
        calc_layout.setContentsMargins(0, 0, 0, 0)
        calc_layout.setSpacing(0)

        self.display = DisplayScreen()
        self.buttons = ButtonPanel()
        calc_layout.addWidget(self.display, 0)
        calc_layout.addWidget(self.buttons, 1)

        # History sidebar
        self.history_panel = HistoryPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("MainSplitter")
        splitter.addWidget(calc_widget)
        splitter.addWidget(self.history_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([580, 280])
        splitter.setHandleWidth(1)
        root.addWidget(splitter)

        self._controller = MainController(
            self.display, self.buttons, self.history_panel
        )

    # FIX: parameter name must match Qt base class — 'a0', not 'event'
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:   # type: ignore[override]
        if a0 is not None:
            self._controller.handle_key(a0.text(), a0.key())


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ScientificCalc")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,     QColor(CLR_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(CLR_TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base,       QColor(CLR_DISPLAY_BG))
    palette.setColor(QPalette.ColorRole.Text,       QColor(CLR_TEXT_PRIMARY))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# =============================================================================
#  ALL FIXES APPLIED (v4.0)
#  ─────────────────────────────────────────────────────────────────────────
#  [1] mousePressEvent monkey-patch → replaced with HistoryItemFrame subclass
#      using correct Qt signature: mousePressEvent(self, a0: QMouseEvent|None)
#  [2] layout.takeAt().widget() → guarded with `if widget is not None`
#  [3] self._btn_map.get("MODE") → guarded with `if btn is not None`
#  [4] keyPressEvent parameter renamed 'event' → 'a0: QKeyEvent|None'
#  [*] transform: scale() removed from all QPushButton stylesheets (Qt invalid)
#
#  KEYBOARD SHORTCUTS
#  ─────────────────────────────────────────────────────────────────────────
#  0–9  .  +  -  *  /  (  )  %   →  append to expression
#  Enter / Return                  →  evaluate  ( = )
#  Backspace                       →  delete last character
#  Escape                          →  All Clear (AC)
#  Ctrl+C                          →  Copy result to clipboard
#
#  BUILD EXE  (Windows)
#  ─────────────────────────────────────────────────────────────────────────
#  pip install pyinstaller
#  pyinstaller --onefile --windowed --name ScientificCalc scientific_calculator.py
#  Output: dist/ScientificCalc.exe
#
#  HISTORY FILE
#  ─────────────────────────────────────────────────────────────────────────
#  Saved automatically to:  data/history.json  (next to this script)
# =============================================================================