"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║          YT Downloader Pro  ·  v4.0  ·  Professional Desktop Edition           ║
║──────────────────────────────────────────────────────────────────────────────────║
║  Install :  pip install yt-dlp PyQt6 requests                                   ║
║  FFmpeg  :  https://ffmpeg.org  (needed for merging & subtitles)                 ║
║  Run     :  python youtube_downloader_pro.py                                     ║
╚══════════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

# ─── stdlib ───────────────────────────────────────────────────────────────────────
import json, logging, os, platform, re, shutil, subprocess, sys, time
import traceback, urllib.parse, uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

# ─── third-party guards ───────────────────────────────────────────────────────────
try:
    import yt_dlp
    from yt_dlp.utils import DownloadError
except ImportError:
    print("ERROR: yt-dlp not found.\n  pip install yt-dlp", file=sys.stderr)
    sys.exit(1)

try:
    import requests as _req
except ImportError:
    _req = None  # type: ignore[assignment]

try:
    from PyQt6.QtCore import (
        QObject, QRunnable, Qt, QThread, QThreadPool, QTimer,
        pyqtSignal, pyqtSlot,
    )
    from PyQt6.QtGui import (
        QCloseEvent, QColor, QCursor, QFont, QPalette, QPixmap,
    )
    from PyQt6.QtWidgets import (
        QAbstractItemView, QApplication, QCheckBox, QComboBox,
        QDialog, QDialogButtonBox, QFileDialog, QFrame,
        QGraphicsDropShadowEffect, QHBoxLayout, QHeaderView,
        QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
        QPushButton, QScrollArea, QSizePolicy, QSplitter,
        QStackedWidget, QStatusBar, QTableWidget, QTableWidgetItem,
        QTabWidget, QTextEdit, QTreeWidget, QTreeWidgetItem,
        QVBoxLayout, QWidget,
    )
except ImportError:
    print("ERROR: PyQt6 not found.\n  pip install PyQt6", file=sys.stderr)
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════════
#  §1  PATHS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════════

APP_NAME    = "YT Downloader Pro"
APP_VER     = "4.0"
BASE_DIR    = Path(__file__).resolve().parent
LOGS_DIR    = BASE_DIR / "logs"
DL_DIR      = Path.home() / "Downloads" / "YTDownloaderPro"
HIST_FILE   = LOGS_DIR / "history.json"
CFG_FILE    = LOGS_DIR / "config.json"
LOG_FILE    = LOGS_DIR / "ytdpro.log"

for _d in (LOGS_DIR, DL_DIR):
    _d.mkdir(parents=True, exist_ok=True)

QUALITY_PRESETS: List[str] = [
    "Best Available", "4K (2160p)", "1440p", "1080p",
    "720p", "480p", "360p", "240p", "144p",
]
QUALITY_H: Dict[str, int] = {
    "Best Available": 9999, "4K (2160p)": 2160, "1440p": 1440,
    "1080p": 1080, "720p": 720,  "480p": 480,
    "360p":  360,  "240p": 240,  "144p": 144,
}
VIDEO_CONTAINERS : List[str] = ["mp4", "mkv", "webm", "avi", "mov"]
AUDIO_FORMATS    : List[str] = ["mp3", "m4a", "aac", "opus", "flac", "wav"]
SUB_LANG_PRESETS : List[str] = ["en", "fr", "de", "es", "it", "pt",
                                  "ja", "ko", "zh", "ar", "ru", "hi"]
MAX_CONCURRENT   : int = 3
THUMB_W: int = 284
THUMB_H: int = 160
HIST_LIMIT       : int = 1000

DEFAULT_CFG: Dict[str, Any] = {
    "output_dir":       str(DL_DIR),
    "default_quality":  "1080p",
    "default_vfmt":     "mp4",
    "default_afmt":     "mp3",
    "max_concurrent":   3,
    "write_subs":       False,
    "sub_langs":        "en",
    "embed_subs":       True,
    "auto_clip":        True,
    "speed_limit_kb":   0,
}


# ══════════════════════════════════════════════════════════════════════════════════
#  §2  LOGGING
# ══════════════════════════════════════════════════════════════════════════════════

def _init_log() -> logging.Logger:
    root = logging.getLogger()
    if root.handlers:
        return logging.getLogger("ytd")
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-14s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024,
                                  backupCount=3, encoding="utf-8")
        fh.setLevel(logging.DEBUG); fh.setFormatter(fmt); root.addHandler(fh)
    except OSError:
        pass
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO); ch.setFormatter(fmt); root.addHandler(ch)
    return logging.getLogger("ytd")

log = _init_log()


# ══════════════════════════════════════════════════════════════════════════════════
#  §3  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════════

class Config:
    """Thread-safe JSON configuration store with defaults."""
    _d: Dict[str, Any] = {}

    @classmethod
    def load(cls) -> None:
        try:
            if CFG_FILE.exists():
                loaded = json.loads(CFG_FILE.read_text("utf-8"))
                cls._d = {**DEFAULT_CFG, **loaded}
            else:
                cls._d = dict(DEFAULT_CFG)
        except Exception:
            cls._d = dict(DEFAULT_CFG)

    @classmethod
    def save(cls) -> None:
        try:
            CFG_FILE.write_text(json.dumps(cls._d, indent=2, ensure_ascii=False), "utf-8")
        except Exception:
            pass

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return cls._d.get(key, DEFAULT_CFG.get(key, default))

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        cls._d[key] = value; cls.save()

Config.load()


# ══════════════════════════════════════════════════════════════════════════════════
#  §4  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════════

def fmt_bytes(n: Optional[float]) -> str:
    if n is None or n < 0: return "—"
    units = ("B", "KB", "MB", "GB", "TB")
    v = float(n); i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024; i += 1
    return f"{int(v)} {units[i]}" if i == 0 else f"{v:.1f} {units[i]}"

def fmt_dur(s: Optional[float]) -> str:
    if not s or s < 0: return "0:00"
    s = int(s); h, r = divmod(s, 3600); m, sc = divmod(r, 60)
    return f"{h}:{m:02d}:{sc:02d}" if h else f"{m}:{sc:02d}"

def fmt_speed(b: Optional[float]) -> str:
    return "—" if not b else f"{fmt_bytes(int(b))}/s"

def fmt_eta(s: Optional[float]) -> str:
    return "—" if s is None or s <= 0 else fmt_dur(s)

def fmt_views(n: int) -> str:
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:     return f"{n/1_000_000:.1f}M"
    if n >= 1_000:         return f"{n/1_000:.1f}K"
    return str(n)

def clip(t: str, n: int = 72) -> str:
    return t if len(t) <= n else t[:n - 1] + "…"

def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def sanitize(name: str, mx: int = 180) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "_", name)
    return re.sub(r"\s+", " ", s).strip()[:mx]

def ffmpeg_ok() -> bool:
    return shutil.which("ffmpeg") is not None

def open_path(p: Path) -> None:
    target = p if p.is_dir() else p.parent
    try:
        sys_name = platform.system()
        if sys_name == "Windows":  os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys_name == "Darwin": subprocess.Popen(["open", str(target)])
        else:                      subprocess.Popen(["xdg-open", str(target)])
    except Exception as exc:
        log.error("open_path: %s", exc)

def format_date(d: str) -> str:
    if len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d or "—"

def _yt_patterns() -> list:
    return [re.compile(p, re.I) for p in [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?(?:.*&)?v=([\w\-]{11})",
        r"(?:https?://)?youtu\.be/([\w\-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?(?:.*&)?list=([\w\-]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([\w\-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/@[\w\-]+",
    ]]

_YT_PATS  = _yt_patterns()
_PL_PAT   = re.compile(r"youtube\.com/playlist\?(?:.*&)?list=([\w\-]+)", re.I)

def valid_yt(url: str) -> Tuple[bool, str]:
    url = url.strip()
    if not url: return False, "URL is empty"
    for p in _YT_PATS:
        if p.search(url): return True, ""
    return False, "Not a recognised YouTube URL"

def clean_url(url: str) -> Tuple[str, bool]:
    """Strip YouTube Mix / Watch-Later / Radio params. Returns (clean, was_mix)."""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        vid = (params.get("v") or [""])[0]
        lst = (params.get("list") or [""])[0]
        is_mix = bool(lst.startswith("RD") or "start_radio" in params
                      or lst.startswith("WL") or lst.startswith("LL"))
        if vid:   return f"https://www.youtube.com/watch?v={vid}", is_mix
        if lst and not is_mix:
            return f"https://www.youtube.com/playlist?list={lst}", False
    except Exception:
        pass
    return url, False

def load_hist() -> List[Dict[str, Any]]:
    try:
        if HIST_FILE.exists():
            d = json.loads(HIST_FILE.read_text("utf-8"))
            if isinstance(d, list): return d
    except Exception:
        pass
    return []

def save_hist(h: List[Dict[str, Any]]) -> None:
    try:
        HIST_FILE.write_text(json.dumps(h[-HIST_LIMIT:], indent=2, ensure_ascii=False), "utf-8")
    except Exception:
        pass

def push_hist(e: Dict[str, Any]) -> None:
    h = load_hist(); h.append(e); save_hist(h)


# ══════════════════════════════════════════════════════════════════════════════════
#  §5  PROFESSIONAL LIGHT THEME  (clean, modern, YTD-inspired)
# ══════════════════════════════════════════════════════════════════════════════════

# ── Palette ─────────────────────────────────────────────────────────────────────
W0  = "#FBFCFD"   # window background (off-white)
W1  = "#FFFFFF"   # card / surface
W2  = "#F5F6F8"   # subtle raised area
W3  = "#ECEEF2"   # hover tint
W4  = "#E1E4EA"   # border light
W5  = "#C8CDD8"   # border medium

TX0 = "#111318"   # primary text
TX1 = "#3A3F4A"   # secondary text
TX2 = "#6B7180"   # muted text
TX3 = "#A0A8BA"   # placeholder / disabled

RD  = "#CC0000"   # brand red
RDH = "#A50000"   # brand red hover
RDL = "#FFF0F0"   # brand red light bg
RDB = "#CC000022" # brand red border alpha

BL  = "#1971C2"   # accent blue
BLH = "#155EA3"   # accent blue hover
BLL = "#EDF4FF"   # accent blue light bg

GN  = "#2F9E44"   # success green
GNH = "#23782F"   # success hover
GNL = "#EDFBF0"   # success light

OR  = "#D9730D"   # warning orange
ORL = "#FFF3E8"   # warning light

PU  = "#7048E8"   # paused purple
PUL = "#F3F0FF"   # paused light

STATUS_FG: Dict[str, str] = {
    "QUEUED": TX2, "PREPARING": BL,  "DOWNLOADING": BL,
    "MERGING": OR, "PAUSED":    PU,
    "COMPLETED": GN, "FAILED": RD,  "CANCELLED": TX3,
}
STATUS_BG_CLR: Dict[str, str] = {
    "QUEUED": W2,  "PREPARING": BLL, "DOWNLOADING": BLL,
    "MERGING": ORL, "PAUSED":   PUL,
    "COMPLETED": GNL, "FAILED": RDL, "CANCELLED": W2,
}

STYLESHEET = f"""
/* ══ Global ══════════════════════════════════════════════════ */
* {{ outline: none; }}
QWidget {{
    background: {W0};
    color: {TX0};
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: {BLL};
    selection-color: {TX0};
}}
QMainWindow  {{ background: {W0}; }}
QDialog      {{ background: {W1}; }}

/* ══ Scrollbars ═══════════════════════════════════════════════ */
QScrollBar:vertical {{
    background: transparent; width: 9px; margin: 3px 1px;
}}
QScrollBar::handle:vertical {{
    background: {W5}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TX2}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{
    background: transparent; height: 9px; margin: 1px 3px;
}}
QScrollBar::handle:horizontal {{
    background: {W5}; border-radius: 4px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {TX2}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ══ QLineEdit ════════════════════════════════════════════════ */
QLineEdit {{
    background: {W1};
    border: 1.5px solid {W4};
    border-radius: 7px;
    padding: 8px 12px;
    color: {TX0};
    font-size: 13px;
}}
QLineEdit:hover  {{ border-color: {W5}; }}
QLineEdit:focus  {{ border-color: {BL}; background: {W1}; }}
QLineEdit:disabled {{ background: {W2}; color: {TX3}; border-color: {W3}; }}
QLineEdit[readOnly="true"] {{ background: {W2}; color: {TX1}; }}

/* ══ QTextEdit ════════════════════════════════════════════════ */
QTextEdit {{
    background: {W1};
    border: 1.5px solid {W4};
    border-radius: 7px;
    padding: 10px 12px;
    color: {TX1};
    font-family: "Cascadia Code","Consolas","JetBrains Mono",monospace;
    font-size: 11.5px;
}}

/* ══ QComboBox ════════════════════════════════════════════════ */
QComboBox {{
    background: {W1};
    border: 1.5px solid {W4};
    border-radius: 7px;
    padding: 7px 34px 7px 12px;
    color: {TX0};
    min-height: 36px;
    font-size: 13px;
}}
QComboBox:hover {{ border-color: {W5}; }}
QComboBox:focus {{ border-color: {BL}; }}
QComboBox:on    {{ border-color: {BL}; }}
QComboBox::drop-down {{
    width: 32px; border: none;
    border-left: 1px solid {W4};
    border-radius: 0 7px 7px 0;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: none;
    border-left:  5px solid transparent;
    border-right: 5px solid transparent;
    border-top:   5px solid {TX2};
    margin: 0 8px;
}}
QComboBox QAbstractItemView {{
    background: {W1};
    border: 1.5px solid {W5};
    border-radius: 7px;
    selection-background-color: {BLL};
    selection-color: {TX0};
    padding: 4px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 8px 14px;
    min-height: 30px;
    border-radius: 5px;
    margin: 1px 3px;
    color: {TX0};
}}
QComboBox QAbstractItemView::item:hover {{ background: {W3}; }}

/* ══ QPushButton (base) ═══════════════════════════════════════ */
QPushButton {{
    background: {W1};
    color: {TX0};
    border: 1.5px solid {W4};
    border-radius: 7px;
    padding: 8px 18px;
    font-weight: 500;
    font-size: 13px;
    min-height: 36px;
}}
QPushButton:hover   {{ background: {W2}; border-color: {W5}; }}
QPushButton:pressed {{ background: {W3}; }}
QPushButton:disabled {{ color: {TX3}; background: {W2}; border-color: {W3}; }}

/* Brand Red — primary action */
QPushButton#pBrand {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #E50000, stop:1 {RD});
    color: white; border: none;
    font-weight: 700; font-size: 14px;
    letter-spacing: 0.2px; border-radius: 8px;
}}
QPushButton#pBrand:hover   {{ background: {RDH}; }}
QPushButton#pBrand:pressed {{ background: #8A0000; }}
QPushButton#pBrand:disabled {{ background: {W5}; color: {TX3}; }}

/* Accent Blue — secondary action */
QPushButton#pBlue {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #228BE6, stop:1 {BL});
    color: white; border: none;
    font-weight: 700; border-radius: 8px;
}}
QPushButton#pBlue:hover   {{ background: {BLH}; }}
QPushButton#pBlue:disabled {{ background: {W5}; color: {TX3}; }}

/* Success Green */
QPushButton#pGreen {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #40C057, stop:1 {GN});
    color: white; border: none;
    font-weight: 700; border-radius: 8px;
}}
QPushButton#pGreen:hover   {{ background: {GNH}; }}
QPushButton#pGreen:disabled {{ background: {W5}; color: {TX3}; }}

/* Danger outline — cancel / warning */
QPushButton#pDanger {{
    background: transparent;
    color: {RD};
    border: 1.5px solid {RD};
    font-weight: 600;
    border-radius: 7px;
}}
QPushButton#pDanger:hover   {{ background: {RD}; color: white; }}
QPushButton#pDanger:pressed {{ background: {RDH}; color: white; }}

/* Ghost — secondary neutral */
QPushButton#pGhost {{
    background: transparent;
    color: {TX1};
    border: 1.5px solid {W4};
    font-size: 12px;
    padding: 5px 14px;
    min-height: 30px;
    border-radius: 6px;
}}
QPushButton#pGhost:hover   {{ background: {W2}; border-color: {W5}; }}
QPushButton#pGhost:pressed {{ background: {W3}; }}

/* Link-style */
QPushButton#pLink {{
    background: transparent; color: {BL};
    border: none; font-size: 12px; font-weight: 500;
    padding: 2px 4px; min-height: 20px;
}}
QPushButton#pLink:hover {{ color: {BLH}; }}

/* Icon square button (small) */
QPushButton#pIcon {{
    background: {W1};
    color: {TX1};
    border: 1.5px solid {W4};
    border-radius: 6px;
    padding: 0;
    min-width: 30px; max-width: 30px;
    min-height: 30px; max-height: 30px;
    font-size: 13px;
}}
QPushButton#pIcon:hover   {{ background: {W2}; border-color: {W5}; }}
QPushButton#pIcon:pressed {{ background: {W3}; }}

/* Cancel download icon */
QPushButton#pCancelDl {{
    background: {RDL};
    color: {RD};
    border: 1.5px solid {RDB};
    border-radius: 6px;
    padding: 0;
    font-size: 12px; font-weight: 700;
    min-width: 30px; max-width: 30px;
    min-height: 30px; max-height: 30px;
}}
QPushButton#pCancelDl:hover   {{ background: {RD}; color: white; border-color: {RD}; }}
QPushButton#pCancelDl:pressed {{ background: {RDH}; color: white; }}

/* ══ QProgressBar ═════════════════════════════════════════════ */
QProgressBar {{
    background: {W4};
    border: none;
    border-radius: 4px;
    height: 7px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #339AF0, stop:1 {BL});
    border-radius: 4px;
}}
QProgressBar#pbGreen::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #51CF66, stop:1 {GN});
    border-radius: 4px;
}}
QProgressBar#pbRed::chunk {{ background: {RD}; border-radius: 4px; }}
QProgressBar#pbOrange::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #FFA94D, stop:1 {OR});
    border-radius: 4px;
}}

/* ══ Tables & Trees ══════════════════════════════════════════ */
QTableWidget, QTreeWidget {{
    background: {W1};
    alternate-background-color: {W2};
    gridline-color: {W4};
    border: 1.5px solid {W4};
    border-radius: 8px;
    selection-background-color: {BLL};
    outline: none;
    font-size: 13px;
    color: {TX0};
}}
QHeaderView::section {{
    background: {W2};
    color: {TX2};
    border: none;
    border-bottom: 1.5px solid {W4};
    border-right: 1px solid {W4};
    padding: 9px 14px;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.7px;
}}
QHeaderView::section:last {{ border-right: none; }}
QTableWidget::item, QTreeWidget::item {{
    padding: 7px 12px; border: none; color: {TX0};
}}
QTableWidget::item:selected, QTreeWidget::item:selected {{
    background: {BLL}; color: {TX0};
}}
QTreeWidget::item:hover {{ background: {W3}; }}

/* ══ QTabWidget ══════════════════════════════════════════════ */
QTabWidget::pane {{
    border: 1.5px solid {W4};
    border-radius: 0 9px 9px 9px;
    background: {W1};
    top: -1px;
}}
QTabBar::tab {{
    background: {W3};
    color: {TX1};
    padding: 10px 26px;
    border: 1.5px solid {W4};
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    font-weight: 500; font-size: 13px;
    margin-right: 3px;
    min-width: 100px;
}}
QTabBar::tab:hover    {{ background: {W1}; color: {TX0}; }}
QTabBar::tab:selected {{
    background: {W1}; color: {RD};
    font-weight: 700;
    border-bottom: 2.5px solid {RD};
}}

/* ══ QCheckBox ════════════════════════════════════════════════ */
QCheckBox {{ color: {TX0}; spacing: 9px; font-size: 13px; }}
QCheckBox::indicator {{
    width: 17px; height: 17px;
    border: 1.5px solid {W5}; border-radius: 4px; background: {W1};
}}
QCheckBox::indicator:hover   {{ border-color: {BL}; }}
QCheckBox::indicator:checked {{ background: {BL}; border-color: {BL}; }}

/* ══ QStatusBar ═══════════════════════════════════════════════ */
QStatusBar {{
    background: {W1}; color: {TX1};
    border-top: 1px solid {W4};
    font-size: 12px; padding: 0 14px; min-height: 28px;
}}
QStatusBar::item {{ border: none; }}

/* ══ QToolTip ═════════════════════════════════════════════════ */
QToolTip {{
    background: {TX0}; color: white;
    border: none; border-radius: 5px;
    padding: 6px 11px; font-size: 12px;
}}

/* ══ Splitter ═════════════════════════════════════════════════ */
QSplitter::handle           {{ background: {W4}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ══ Misc ═════════════════════════════════════════════════════ */
QScrollArea {{ border: none; background: transparent; }}
QFrame[frameShape="4"] {{ background: {W4}; max-height: 1px; border: none; }}
QFrame[frameShape="5"] {{ background: {W4}; max-width:  1px; border: none; }}
QMessageBox {{ background: {W1}; }}
QMessageBox QPushButton {{ min-width: 90px; }}
QDialogButtonBox QPushButton {{ min-width: 100px; }}
"""


# ══════════════════════════════════════════════════════════════════════════════════
#  §6  DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════════

class DLStatus(Enum):
    QUEUED      = auto()
    PREPARING   = auto()
    DOWNLOADING = auto()
    MERGING     = auto()
    PAUSED      = auto()
    COMPLETED   = auto()
    FAILED      = auto()
    CANCELLED   = auto()

    @property
    def is_terminal(self) -> bool:
        return self in (DLStatus.COMPLETED, DLStatus.FAILED, DLStatus.CANCELLED)

    @property
    def is_active(self) -> bool:
        return self in (DLStatus.PREPARING, DLStatus.DOWNLOADING, DLStatus.MERGING)


@dataclass
class FormatInfo:
    format_id : str
    ext       : str
    height    : Optional[int]
    fps       : Optional[float]
    vcodec    : str
    acodec    : str
    filesize  : Optional[int]
    abr       : Optional[float]
    tbr       : Optional[float]
    label     : str
    note      : str = ""

    @property
    def is_video(self) -> bool:
        return self.vcodec not in ("none", "", None)

    @property
    def resolution(self) -> str:
        return f"{self.height}p" if self.height else "audio"


@dataclass
class VideoMeta:
    url          : str
    vid_id       : str
    title        : str
    channel      : str
    duration     : int
    view_count   : int
    upload_date  : str
    description  : str
    thumbnail_url: str
    formats      : List[FormatInfo]  = field(default_factory=list)
    is_playlist  : bool              = False
    entries      : List["VideoMeta"] = field(default_factory=list)
    like_count   : int               = 0

    @property
    def video_formats(self) -> List[FormatInfo]:
        return [f for f in self.formats if f.is_video]

    @property
    def audio_formats(self) -> List[FormatInfo]:
        return [f for f in self.formats if not f.is_video]


@dataclass
class DLTask:
    url            : str
    title          : str
    output_dir     : Path
    quality        : str  = "Best Available"
    container      : str  = "mp4"
    audio_only     : bool = False
    audio_fmt      : str  = "mp3"
    write_subs     : bool = False
    sub_langs      : str  = "en"
    embed_subs     : bool = True
    speed_limit_kb : int  = 0
    thumbnail_url  : str  = ""
    task_id        : str  = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class TaskState:
    task      : DLTask
    status    : DLStatus = DLStatus.QUEUED
    pct       : float    = 0.0
    dl_bytes  : int      = 0
    tot_bytes : int      = 0
    speed     : float    = 0.0
    eta       : float    = 0.0
    out_path  : Optional[str] = None
    err       : Optional[str] = None
    started   : float = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════════════════════
#  §7  FORMAT STRING BUILDER
# ══════════════════════════════════════════════════════════════════════════════════

def build_format_str(quality: str, container: str, audio_only: bool,
                     audio_fmt: str, has_ff: bool) -> str:
    """Build a robust yt-dlp format selector with full fallback chain."""
    if audio_only:
        if audio_fmt in ("m4a", "aac"):
            return "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
        if audio_fmt == "opus":
            return "bestaudio[ext=webm]/bestaudio/best"
        return "bestaudio/best"

    max_h = QUALITY_H.get(quality, 9999)

    if not has_ff:
        if max_h >= 9999: return "best[ext=mp4]/best"
        return f"best[ext=mp4][height<={max_h}]/best[height<={max_h}]/best"

    if max_h >= 9999:
        return ("bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                "/bestvideo[ext=mp4]+bestaudio"
                "/bestvideo[vcodec^=avc]+bestaudio[ext=m4a]"
                "/bestvideo+bestaudio[ext=m4a]"
                "/bestvideo+bestaudio/best[ext=mp4]/best")

    hf = f"[height<={max_h}]"
    return (f"bestvideo[ext=mp4]{hf}+bestaudio[ext=m4a]"
            f"/bestvideo[ext=mp4]{hf}+bestaudio"
            f"/bestvideo[vcodec^=avc]{hf}+bestaudio[ext=m4a]"
            f"/bestvideo{hf}+bestaudio[ext=m4a]"
            f"/bestvideo{hf}+bestaudio"
            f"/best[ext=mp4]{hf}/best{hf}/best")


# ══════════════════════════════════════════════════════════════════════════════════
#  §8  yt-dlp LOGGER BRIDGE
# ══════════════════════════════════════════════════════════════════════════════════

class YDLLogger:
    _PASS = ("[download]","[ffmpeg]","[Merger]","[VideoConvertor]",
              "[ExtractAudio]","[EmbedSubtitle]","[Fixup")

    def __init__(self, tid: str, sig: "DLSig") -> None:
        self._tid = tid; self._sig = sig

    def debug(self, m: str) -> None:
        if any(t in m for t in self._PASS):
            self._sig.log_line.emit(self._tid, m.strip())

    def info(self, m: str) -> None:
        self._sig.log_line.emit(self._tid, m.strip())

    def warning(self, m: str) -> None:
        log.warning("[yt-dlp] %s", m)

    def error(self, m: str) -> None:
        log.error("[yt-dlp] %s", m)


# ══════════════════════════════════════════════════════════════════════════════════
#  §9  DOWNLOAD WORKER
# ══════════════════════════════════════════════════════════════════════════════════

class DLCancelled(Exception):
    pass


class DLSig(QObject):
    progress = pyqtSignal(str, float, int, int, float, float)
    status   = pyqtSignal(str, object)
    done     = pyqtSignal(str, str)
    error    = pyqtSignal(str, str)
    log_line = pyqtSignal(str, str)


class DLWorker(QRunnable):
    def __init__(self, task: DLTask) -> None:
        super().__init__()
        self.task    = task
        self.sig     = DLSig()
        self._cancel = False
        self._pause  = False
        self._last_b = 0
        self._last_t = 0.0
        self.setAutoDelete(True)

    def request_cancel(self) -> None: self._cancel = True
    def request_pause(self)  -> None: self._pause  = True
    def request_resume(self) -> None: self._pause  = False

    @pyqtSlot()
    def run(self) -> None:
        tid  = self.task.task_id
        task = self.task
        self._emit(DLStatus.PREPARING)

        has_ff  = ffmpeg_ok()
        c_url, _ = clean_url(task.url)
        fmt     = build_format_str(task.quality, task.container,
                                    task.audio_only, task.audio_fmt, has_ff)
        log.debug("Worker %s | fmt=%s", tid[:8], fmt)

        pp: List[Dict[str, Any]] = []
        if task.audio_only and has_ff:
            pp.append({"key": "FFmpegExtractAudio",
                        "preferredcodec": task.audio_fmt,
                        "preferredquality": "192",
                        "nopostoverwrites": False})

        if task.write_subs and has_ff and task.embed_subs and not task.audio_only:
            pp.append({"key": "FFmpegEmbedSubtitle",
                        "already_have_subtitle": False})

        opts: Dict[str, Any] = {
            "quiet":           True,  "no_warnings":    True,
            "noprogress":      False, "format":         fmt,
            "outtmpl":         str(task.output_dir / "%(title)s.%(ext)s"),
            "restrictfilenames": False,
            "windowsfilenames": platform.system() == "Windows",
            "retries":          10,   "fragment_retries": 10,
            "skip_unavailable_fragments": True,
            "ignoreerrors":     False, "nocheckcertificate": False,
            "socket_timeout":   30,
            "http_chunk_size":  10 * 1024 * 1024,
            "noplaylist":       True,
            "progress_hooks":   [self._hook],
            "postprocessors":   pp,
            "writethumbnail":   False, "writeinfojson": False,
            "no_color":         True,
            "logger":           YDLLogger(tid, self.sig),
            "concurrent_fragment_downloads": 4,
        }

        if not task.audio_only and has_ff:
            opts["merge_output_format"] = task.container

        if task.write_subs:
            langs = [l.strip() for l in task.sub_langs.split(",") if l.strip()] or ["en"]
            opts.update({
                "writesubtitles":    True,
                "writeautomaticsub": True,
                "subtitleslangs":    langs,
                "subtitlesformat":   "srt/vtt/best",
            })

        if task.speed_limit_kb > 0:
            opts["ratelimit"] = task.speed_limit_kb * 1024

        self._emit(DLStatus.DOWNLOADING)
        try:
            ydl_opts: Any = opts
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ret = ydl.download([c_url])
            if ret not in (0, None):
                raise DownloadError(f"yt-dlp exit code {ret}")

            out = self._find_output(task)
            self._emit(DLStatus.COMPLETED)
            self.sig.done.emit(tid, str(out))
            push_hist({
                "task_id":   tid,   "title":     task.title,
                "url":       task.url, "output":  str(out),
                "format":    task.audio_fmt if task.audio_only else task.container,
                "quality":   task.quality,  "timestamp": now_ts(),
                "size":      out.stat().st_size if out.exists() else 0,
            })

        except DLCancelled:
            self._emit(DLStatus.CANCELLED)
            self.sig.log_line.emit(tid, "Cancelled by user.")
        except DownloadError as e:
            msg = str(e).replace("ERROR: ", "", 1)
            log.error("DL error %s: %s", tid[:8], msg)
            self._emit(DLStatus.FAILED); self.sig.error.emit(tid, msg)
        except Exception as e:
            msg = str(e)
            log.error("DL fail %s: %s\n%s", tid[:8], msg, traceback.format_exc())
            self._emit(DLStatus.FAILED); self.sig.error.emit(tid, msg)

    def _hook(self, d: Dict[str, Any]) -> None:
        if self._cancel: raise DLCancelled()
        while self._pause and not self._cancel: time.sleep(0.15)
        if self._cancel: raise DLCancelled()

        s = d.get("status", "")
        if s == "downloading":
            dl    = d.get("downloaded_bytes") or 0
            tot   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            speed = d.get("speed") or self._spd(dl)
            eta   = d.get("eta") or 0.0
            pct   = dl / tot * 100.0 if tot else 0.0
            self.sig.progress.emit(self.task.task_id, pct, dl, tot,
                                    float(speed or 0), float(eta))
        elif s == "finished":
            self._emit(DLStatus.MERGING)
            self.sig.log_line.emit(self.task.task_id, "Merging streams with FFmpeg…")

    def _spd(self, dl: int) -> float:
        now = time.monotonic(); el = now - self._last_t
        v   = (dl - self._last_b) / el if el > 0 and self._last_b else 0.0
        self._last_b = dl; self._last_t = now
        return max(0.0, v)

    def _emit(self, s: DLStatus) -> None:
        self.sig.status.emit(self.task.task_id, s)

    def _find_output(self, task: DLTask) -> Path:
        try:
            skip = {".part",".ytdl",".json",".vtt",".srt",".ass",".temp"}
            files = sorted(
                [f for f in task.output_dir.iterdir()
                 if f.is_file() and f.suffix.lower() not in skip],
                key=lambda f: f.stat().st_mtime, reverse=True,
            )
            if files: return files[0]
        except Exception: pass
        ext = task.audio_fmt if task.audio_only else task.container
        return task.output_dir / f"{sanitize(task.title)}.{ext}"


# ══════════════════════════════════════════════════════════════════════════════════
#  §10  DOWNLOAD MANAGER
# ══════════════════════════════════════════════════════════════════════════════════

class DLManager(QObject):
    sig_progress  = pyqtSignal(str, float, int, int, float, float)
    sig_status    = pyqtSignal(str, object)
    sig_done      = pyqtSignal(str, str)
    sig_error     = pyqtSignal(str, str)
    sig_log       = pyqtSignal(str, str)
    sig_qchanged  = pyqtSignal(int, int)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        pool = QThreadPool.globalInstance()
        if pool is None: raise RuntimeError("No QThreadPool")
        self._pool    = pool
        self._pool.setMaxThreadCount(Config.get("max_concurrent", MAX_CONCURRENT))
        self._active:  Dict[str, DLWorker] = {}
        self._pending: Deque[DLTask]       = deque()

    def set_max(self, n: int) -> None:
        self._pool.setMaxThreadCount(max(1, min(n, 8)))

    def enqueue(self, t: DLTask) -> None:
        self._pending.append(t); self._qc(); self._dispatch()

    def cancel(self, tid: str) -> None:
        if tid in self._active:
            self._active[tid].request_cancel()
        else:
            self._pending = deque(t for t in self._pending if t.task_id != tid)
            self.sig_status.emit(tid, DLStatus.CANCELLED); self._qc()

    def pause(self, tid: str) -> None:
        if tid in self._active:
            self._active[tid].request_pause()
            self.sig_status.emit(tid, DLStatus.PAUSED)

    def resume(self, tid: str) -> None:
        if tid in self._active:
            self._active[tid].request_resume()
            self.sig_status.emit(tid, DLStatus.DOWNLOADING)

    def cancel_all(self) -> None:
        for tid in list(self._active): self._active[tid].request_cancel()
        self._pending.clear(); self._qc()

    @property
    def active_count(self)  -> int: return len(self._active)
    @property
    def pending_count(self) -> int: return len(self._pending)

    def _dispatch(self) -> None:
        while self._pending and len(self._active) < self._pool.maxThreadCount():
            t = self._pending.popleft(); self._qc()
            w = DLWorker(t); self._active[t.task_id] = w
            w.sig.progress.connect(self.sig_progress)
            w.sig.status.connect(self.sig_status)
            w.sig.done.connect(self._on_done)
            w.sig.error.connect(self._on_error)
            w.sig.log_line.connect(self.sig_log)
            self._pool.start(w)
            log.info("Dispatched: %s", t.title[:55])

    def _on_done(self, tid: str, path: str) -> None:
        self._active.pop(tid, None); self.sig_done.emit(tid, path); self._dispatch()

    def _on_error(self, tid: str, msg: str) -> None:
        self._active.pop(tid, None); self.sig_error.emit(tid, msg); self._dispatch()

    def _qc(self) -> None:
        self.sig_qchanged.emit(len(self._active), len(self._pending))


# ══════════════════════════════════════════════════════════════════════════════════
#  §11  EXTRACTOR WORKER  (fast flat playlist + single video)
# ══════════════════════════════════════════════════════════════════════════════════

class ExtSig(QObject):
    done     = pyqtSignal(object)
    error    = pyqtSignal(str)
    msg      = pyqtSignal(str)
    progress = pyqtSignal(int, int)


class ExtWorker(QRunnable):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.url     = url
        self.sig     = ExtSig()
        self._cancel = False
        self.setAutoDelete(True)

    def cancel(self) -> None: self._cancel = True

    @pyqtSlot()
    def run(self) -> None:
        try:
            c_url, is_mix = clean_url(self.url)
            is_pl = bool(_PL_PAT.search(self.url) and "watch?v=" not in self.url)
            if is_mix:
                self.sig.msg.emit("YouTube Mix detected — treating as single video…")
            elif is_pl:
                self.sig.msg.emit("Playlist URL — starting fast scan…")
            else:
                self.sig.msg.emit("Fetching video info…")

            if self._cancel: return
            meta = self._fetch_pl(c_url) if is_pl else self._fetch_vid(c_url)
            if not self._cancel: self.sig.done.emit(meta)

        except Exception as e:
            if not self._cancel:
                log.error("ExtWorker: %s", traceback.format_exc())
                self.sig.error.emit(str(e).replace("ERROR: ", "", 1))

    def _fetch_vid(self, url: str) -> VideoMeta:
        opts: Any = {"quiet": True, "no_warnings": True,
                      "skip_download": True, "noplaylist": True,
                      "socket_timeout": 12, "extractor_retries": 2}
        with yt_dlp.YoutubeDL(opts) as ydl:
            raw: Any = ydl.extract_info(url, download=False)
        if not raw: raise ValueError("YouTube returned no data")
        return self._build(url, raw)

    def _fetch_pl(self, url: str) -> VideoMeta:
        self.sig.msg.emit("Flat-scanning playlist (no per-video requests)…")
        opts: Any = {"quiet": True, "no_warnings": True,
                      "skip_download": True, "extract_flat": True,
                      "playlistend": 500, "socket_timeout": 12}
        with yt_dlp.YoutubeDL(opts) as ydl:
            raw: Any = ydl.extract_info(url, download=False)
        if not raw: raise ValueError("Playlist returned no data")

        flat  = raw.get("entries") or []
        total = len(flat)
        self.sig.msg.emit(f"Found {total} videos — building entry list…")
        self.sig.progress.emit(0, total)

        entries: List[VideoMeta] = []
        for i, e in enumerate(flat):
            if not e or self._cancel: break
            vid_url = (e.get("url") or e.get("webpage_url")
                       or f"https://www.youtube.com/watch?v={e.get('id','')}")
            entries.append(VideoMeta(
                url=vid_url, vid_id=e.get("id",""),
                title=e.get("title","Unknown"),
                channel=e.get("uploader", raw.get("uploader","")),
                duration=e.get("duration",0) or 0,
                view_count=e.get("view_count",0) or 0,
                upload_date=e.get("upload_date",""),
                description="", thumbnail_url=e.get("thumbnail",""),
            ))
            if (i + 1) % 50 == 0: self.sig.progress.emit(i+1, total)

        self.sig.progress.emit(total, total)
        return VideoMeta(
            url=url, vid_id=raw.get("id",""),
            title=raw.get("title","Playlist"),
            channel=raw.get("uploader",""),
            duration=sum(e.duration for e in entries),
            view_count=0, upload_date="", description="",
            thumbnail_url=flat[0].get("thumbnail","") if flat else "",
            is_playlist=True, entries=entries,
        )

    def _build(self, url: str, raw: Any) -> VideoMeta:
        fmts = self._parse_fmts(raw.get("formats") or [])
        return VideoMeta(
            url=url or raw.get("webpage_url",""),
            vid_id=raw.get("id",""),
            title=raw.get("title","Unknown"),
            channel=raw.get("uploader", raw.get("channel","Unknown")),
            duration=raw.get("duration",0) or 0,
            view_count=raw.get("view_count",0) or 0,
            upload_date=raw.get("upload_date",""),
            description=raw.get("description",""),
            thumbnail_url=raw.get("thumbnail",""),
            formats=fmts,
            like_count=raw.get("like_count",0) or 0,
        )

    @staticmethod
    def _parse_fmts(raws: List[Any]) -> List[FormatInfo]:
        result: List[FormatInfo] = []; seen: set = set()
        for f in raws:
            ext = f.get("ext","") or ""; vc = f.get("vcodec","none") or "none"
            ac  = f.get("acodec","none") or "none"; h = f.get("height"); fps = f.get("fps")
            if ext in ("mhtml","none"): continue
            if vc == "none" and ac == "none": continue
            fps_s = f"@{int(fps)}fps" if fps and fps > 1 else ""
            if h: lbl = f"{h}p{fps_s}  [{ext.upper()}]"
            else:
                abr = f.get("abr")
                lbl = (f"Audio {int(abr)}kbps [{ext.upper()}]" if abr
                        else f"Audio [{ext.upper()}]")
            base, n = lbl, 1
            while lbl in seen: lbl = f"{base} ({n})"; n += 1
            seen.add(lbl)
            result.append(FormatInfo(
                format_id=f.get("format_id",""), ext=ext, height=h, fps=fps,
                vcodec=vc, acodec=ac,
                filesize=f.get("filesize") or f.get("filesize_approx"),
                abr=f.get("abr"), tbr=f.get("tbr"), label=lbl,
                note=f.get("format_note",""),
            ))
        result.sort(key=lambda x: (x.height is None, -(x.height or 0), -(x.tbr or 0)))
        return result


# ══════════════════════════════════════════════════════════════════════════════════
#  §12  THUMBNAIL LOADER
# ══════════════════════════════════════════════════════════════════════════════════

class ThumbLoader(QThread):
    loaded = pyqtSignal(bytes)
    failed = pyqtSignal()

    def __init__(self, url: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent); self.url = url

    def run(self) -> None:
        if _req is None: self.failed.emit(); return
        try:
            r = _req.get(self.url, timeout=8); r.raise_for_status()
            self.loaded.emit(r.content)
        except Exception: self.failed.emit()


# ══════════════════════════════════════════════════════════════════════════════════
#  §13  GUI HELPERS — reusable widgets
# ══════════════════════════════════════════════════════════════════════════════════

def _lbl(text: str = "", size: int = 13, bold: bool = False,
          color: str = TX0, wrap: bool = False) -> QLabel:
    w = QLabel(text); w.setWordWrap(wrap)
    w.setStyleSheet(
        f"color:{color}; font-size:{size}px; "
        f"font-weight:{'700' if bold else '400'};"
        "background:transparent; border:none;"
    )
    return w

def _sep(vert: bool = False) -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine if vert else QFrame.Shape.HLine)
    f.setStyleSheet(
        f"background:{W4}; border:none; "
        f"{'max-width:1px;' if vert else 'max-height:1px;'}"
    )
    return f

def _section_lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color:{TX2}; font-size:10px; font-weight:700; "
        "letter-spacing:1.1px; background:transparent; border:none;"
    )
    return l

def _card_frame(radius: int = 9) -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:{W1}; border:1.5px solid {W4}; border-radius:{radius}px;}}"
    )
    return f

def _pill(text: str, fg: str, bg: str, border: str = "") -> QLabel:
    l = QLabel(text); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
    bd = border or f"{fg}33"
    l.setStyleSheet(
        f"color:{fg}; background:{bg}; border:1px solid {bd};"
        "border-radius:4px; padding:2px 9px; font-size:10px;"
        "font-weight:700; letter-spacing:0.5px;"
    )
    return l

def _icon_btn(sym: str, tip: str = "", obj: str = "pIcon", sz: int = 30) -> QPushButton:
    b = QPushButton(sym); b.setObjectName(obj); b.setFixedSize(sz, sz)
    if tip: b.setToolTip(tip)
    return b


class StatCard(QWidget):
    """Heading + large value stat block."""
    def __init__(self, heading: str, value: str = "—",
                  parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        l = QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(2)
        self._val = _lbl(value, 17, bold=True, color=TX0)
        self._hdg = _lbl(heading, 9, color=TX2)
        l.addWidget(self._val); l.addWidget(self._hdg)

    def set_value(self, v: str) -> None: self._val.setText(v)


class StatusBadge(QLabel):
    """Coloured status pill that updates its own style."""
    def __init__(self, status: str = "QUEUED",
                  parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(110)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        fg = STATUS_FG.get(status, TX2)
        bg = STATUS_BG_CLR.get(status, W2)
        self.setText(status)
        self.setStyleSheet(
            f"color:{fg}; background:{bg}; border:1.5px solid {fg}44;"
            "border-radius:5px; padding:3px 10px; font-size:10px;"
            "font-weight:700; letter-spacing:0.8px;"
        )


# ══════════════════════════════════════════════════════════════════════════════════
#  §14  PLAYLIST PICKER DIALOG
# ══════════════════════════════════════════════════════════════════════════════════

class PlaylistDialog(QDialog):
    """Professional playlist selection dialog with search, bulk actions, totals."""

    def __init__(self, meta: VideoMeta, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._meta    = meta
        self._entries = meta.entries
        self.setWindowTitle(f"Select Videos — {clip(meta.title, 50)}")
        self.setMinimumSize(820, 580); self.resize(920, 640)
        self.setStyleSheet(f"QDialog{{background:{W1};}}")
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20); root.setSpacing(14)

        # ── header ─────────────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(14)
        ico = _lbl("☰", 24, color=RD); ico.setFixedWidth(32)
        hdr.addWidget(ico)
        col = QVBoxLayout(); col.setSpacing(3)
        col.addWidget(_lbl(clip(self._meta.title, 68), 15, bold=True))
        col.addWidget(_lbl(
            f"{self._meta.channel}  ·  {len(self._entries)} videos  ·  "
            f"Total runtime: {fmt_dur(self._meta.duration)}",
            12, color=TX1
        ))
        hdr.addLayout(col, 1)
        root.addLayout(hdr)
        root.addWidget(_sep())

        # ── search + bulk ───────────────────────────────────────────────────
        tb = QHBoxLayout(); tb.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search videos in this playlist…")
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._filter)
        tb.addWidget(self._search, 1)
        for label, fn in [("Select All",  self._sel_all),
                           ("Select None", self._sel_none),
                           ("Invert",      self._invert),
                           ("First 10",    self._first10)]:
            b = QPushButton(label); b.setObjectName("pGhost")
            b.setFixedHeight(32); b.clicked.connect(fn)
            tb.addWidget(b)
        root.addLayout(tb)

        # ── tree ────────────────────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["#", "Title", "Duration", "Channel", "Views"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hh = self._tree.header()
        if hh:
            for i, m in [(0, QHeaderView.ResizeMode.ResizeToContents),
                          (1, QHeaderView.ResizeMode.Stretch),
                          (2, QHeaderView.ResizeMode.ResizeToContents),
                          (3, QHeaderView.ResizeMode.ResizeToContents),
                          (4, QHeaderView.ResizeMode.ResizeToContents)]:
                hh.setSectionResizeMode(i, m)

        for i, e in enumerate(self._entries, 1):
            item = QTreeWidgetItem([
                str(i), e.title, fmt_dur(e.duration),
                e.channel, fmt_views(e.view_count) if e.view_count else "—",
            ])
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setToolTip(1, e.url)
            item.setData(0, Qt.ItemDataRole.UserRole, i - 1)
            self._tree.addTopLevelItem(item)

        self._tree.itemChanged.connect(lambda _: self._update_count())
        root.addWidget(self._tree, 1)

        # ── footer ──────────────────────────────────────────────────────────
        self._dur_lbl   = _lbl("", 12, color=TX1)
        self._count_lbl = _lbl("", 12, color=TX1)
        root.addWidget(self._dur_lbl)
        root.addWidget(_sep())

        foot = QHBoxLayout(); foot.setSpacing(10)
        foot.addWidget(self._count_lbl); foot.addStretch()
        cancel_b = QPushButton("Cancel"); cancel_b.setObjectName("pGhost")
        cancel_b.setFixedSize(100, 38); cancel_b.clicked.connect(self.reject)
        ok_b = QPushButton("⬇  Download Selected")
        ok_b.setObjectName("pBrand"); ok_b.setFixedSize(210, 38)
        ok_b.clicked.connect(self.accept)
        foot.addWidget(cancel_b); foot.addWidget(ok_b)
        root.addLayout(foot)

        self._update_count()

    # ── helpers ─────────────────────────────────────────────────────────────
    def _set_all_visible(self, state: Qt.CheckState) -> None:
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and not item.isHidden():
                item.setCheckState(0, state)

    def _sel_all(self)  -> None: self._set_all_visible(Qt.CheckState.Checked)
    def _sel_none(self) -> None: self._set_all_visible(Qt.CheckState.Unchecked)
    def _invert(self)   -> None:
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and not item.isHidden():
                c = item.checkState(0)
                item.setCheckState(0, Qt.CheckState.Unchecked
                                    if c == Qt.CheckState.Checked
                                    else Qt.CheckState.Checked)

    def _first10(self) -> None:
        shown = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and not item.isHidden():
                item.setCheckState(0, Qt.CheckState.Checked if shown < 10
                                    else Qt.CheckState.Unchecked)
                shown += 1

    def _filter(self, text: str) -> None:
        t = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item: item.setHidden(bool(t and t not in item.text(1).lower()))
        self._update_count()

    def _update_count(self) -> None:
        n = dur = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.checkState(0) == Qt.CheckState.Checked:
                n += 1
                idx = item.data(0, Qt.ItemDataRole.UserRole)
                if idx is not None and 0 <= idx < len(self._entries):
                    dur += self._entries[idx].duration
        self._count_lbl.setText(f"<b>{n}</b> of {len(self._entries)} videos selected")
        self._dur_lbl.setText(f"Total duration of selection:  {fmt_dur(dur)}")

    def selected_entries(self) -> List[VideoMeta]:
        result: List[VideoMeta] = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.checkState(0) == Qt.CheckState.Checked:
                idx = item.data(0, Qt.ItemDataRole.UserRole)
                if idx is not None and 0 <= idx < len(self._entries):
                    result.append(self._entries[idx])
        return result


# ══════════════════════════════════════════════════════════════════════════════════
#  §15  SETTINGS DIALOG
# ══════════════════════════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings — YT Downloader Pro")
        self.setFixedSize(540, 500)
        self.setStyleSheet(f"QDialog{{background:{W1};}}")
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20); root.setSpacing(14)
        root.addWidget(_lbl("Settings", 18, bold=True))
        root.addWidget(_sep())

        def _row(lbl_text: str, widget: QWidget) -> QHBoxLayout:
            h = QHBoxLayout(); h.setSpacing(14)
            l = _lbl(lbl_text, 13, color=TX1); l.setFixedWidth(185)
            h.addWidget(l); h.addWidget(widget, 1)
            return h

        # Output dir
        dr = QHBoxLayout(); dr.setSpacing(8)
        self._dir = QLineEdit(Config.get("output_dir")); self._dir.setReadOnly(True)
        self._dir.setFixedHeight(34)
        bb = QPushButton("Browse"); bb.setObjectName("pGhost"); bb.setFixedSize(80,34)
        bb.clicked.connect(self._browse)
        dr.addWidget(self._dir,1); dr.addWidget(bb)
        rl = QHBoxLayout(); rl.setSpacing(14)
        ll = _lbl("Output folder", 13, color=TX1); ll.setFixedWidth(185)
        rl.addWidget(ll); rl.addLayout(dr, 1)
        root.addLayout(rl)

        self._q  = QComboBox(); self._q.addItems(QUALITY_PRESETS)
        self._q.setCurrentText(Config.get("default_quality","1080p")); self._q.setFixedHeight(34)
        root.addLayout(_row("Default quality", self._q))

        self._vf = QComboBox(); self._vf.addItems([f.upper() for f in VIDEO_CONTAINERS])
        self._vf.setCurrentText(Config.get("default_vfmt","mp4").upper()); self._vf.setFixedHeight(34)
        root.addLayout(_row("Default video format", self._vf))

        self._af = QComboBox(); self._af.addItems([f.upper() for f in AUDIO_FORMATS])
        self._af.setCurrentText(Config.get("default_afmt","mp3").upper()); self._af.setFixedHeight(34)
        root.addLayout(_row("Default audio format", self._af))

        self._mc = QComboBox()
        for n in range(1,9): self._mc.addItem(str(n))
        self._mc.setCurrentText(str(Config.get("max_concurrent",3))); self._mc.setFixedHeight(34)
        root.addLayout(_row("Concurrent downloads", self._mc))

        sp_row = QHBoxLayout(); sp_row.setSpacing(8)
        self._spd = QLineEdit(str(Config.get("speed_limit_kb",0)))
        self._spd.setFixedSize(100,34); sp_row.addWidget(self._spd)
        sp_row.addWidget(_lbl("KB/s  (0 = unlimited)",12,color=TX2)); sp_row.addStretch()
        sr = QHBoxLayout(); sr.setSpacing(14)
        sl = _lbl("Speed limit",13,color=TX1); sl.setFixedWidth(185)
        sr.addWidget(sl); sr.addLayout(sp_row,1)
        root.addLayout(sr)

        self._clip  = QCheckBox("Auto-detect YouTube URLs from clipboard")
        self._clip.setChecked(Config.get("auto_clip",True)); root.addWidget(self._clip)
        self._embed = QCheckBox("Embed subtitles into video file (requires FFmpeg)")
        self._embed.setChecked(Config.get("embed_subs",True)); root.addWidget(self._embed)

        root.addStretch()
        root.addWidget(_sep())

        foot = QHBoxLayout(); foot.setSpacing(10); foot.addStretch()
        cb = QPushButton("Cancel"); cb.setObjectName("pGhost"); cb.setFixedSize(100,38)
        cb.clicked.connect(self.reject)
        sb = QPushButton("Save Settings"); sb.setObjectName("pBlue"); sb.setFixedSize(150,38)
        sb.clicked.connect(self._save)
        foot.addWidget(cb); foot.addWidget(sb)
        root.addLayout(foot)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self,"Output Folder",self._dir.text())
        if d: self._dir.setText(d)

    def _save(self) -> None:
        try: spd = int(self._spd.text() or "0")
        except ValueError: spd = 0
        Config.set("output_dir",       self._dir.text())
        Config.set("default_quality",  self._q.currentText())
        Config.set("default_vfmt",     self._vf.currentText().lower())
        Config.set("default_afmt",     self._af.currentText().lower())
        Config.set("max_concurrent",   int(self._mc.currentText()))
        Config.set("speed_limit_kb",   spd)
        Config.set("auto_clip",        self._clip.isChecked())
        Config.set("embed_subs",       self._embed.isChecked())
        self.accept()


# ══════════════════════════════════════════════════════════════════════════════════
#  §16  DOWNLOAD CARD  (per-task row in the queue)
# ══════════════════════════════════════════════════════════════════════════════════

class DLCard(QFrame):
    sig_pause  = pyqtSignal(str)
    sig_resume = pyqtSignal(str)
    sig_cancel = pyqtSignal(str)
    sig_folder = pyqtSignal(str)

    def __init__(self, task_id: str, title: str,
                  parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self._paused = False
        self._out:   Optional[str] = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QFrame{{background:{W1}; border:1.5px solid {W4}; border-radius:10px;}}"
            f"QFrame:hover{{border-color:{W5};}}"
        )
        self._build(title)

    def _build(self, title: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 13, 16, 13); root.setSpacing(9)

        # Row 1: title icon + title text + status badge
        r1 = QHBoxLayout(); r1.setSpacing(10)
        self._ico = QLabel("▶")
        self._ico.setFixedWidth(20)
        self._ico.setStyleSheet(f"color:{RD}; font-size:13px; font-weight:900; background:transparent;")
        r1.addWidget(self._ico)
        self._title_lbl = _lbl(clip(title, 80), 13, bold=True)
        self._title_lbl.setWordWrap(False)
        r1.addWidget(self._title_lbl, 1)
        self._badge = StatusBadge("QUEUED")
        r1.addWidget(self._badge)
        root.addLayout(r1)

        # Row 2: progress bar
        self._pbar = QProgressBar()
        self._pbar.setRange(0, 100); self._pbar.setValue(0)
        self._pbar.setFixedHeight(7); self._pbar.setTextVisible(False)
        root.addWidget(self._pbar)

        # Row 3: stats + buttons
        r3 = QHBoxLayout(); r3.setSpacing(22)
        self._l_pct   = _lbl("0%",    11, color=TX1)
        self._l_size  = _lbl("—",     11, color=TX2)
        self._l_speed = _lbl("—",     11, color=TX2)
        self._l_eta   = _lbl("—",     11, color=TX2)
        for lbl in (self._l_pct, self._l_size, self._l_speed, self._l_eta):
            r3.addWidget(lbl)
        r3.addStretch()

        self._b_pause  = _icon_btn("⏸", "Pause",         "pIcon")
        self._b_cancel = _icon_btn("✕", "Cancel download","pCancelDl")
        self._b_folder = _icon_btn("📂","Open folder",    "pIcon")
        self._b_folder.setVisible(False)

        self._b_pause.clicked.connect(self._toggle_pause)
        self._b_cancel.clicked.connect(lambda: self.sig_cancel.emit(self.task_id))
        self._b_folder.clicked.connect(self._do_open)

        for b in (self._b_pause, self._b_cancel, self._b_folder):
            r3.addWidget(b)
        root.addLayout(r3)

    # ── public ─────────────────────────────────────────────────────────────
    def update_progress(self, pct: float, dl: int, tot: int,
                         spd: float, eta: float) -> None:
        self._pbar.setValue(int(min(pct, 100)))
        self._l_pct.setText(f"{pct:.1f}%")
        self._l_size.setText(f"{fmt_bytes(dl)} / {fmt_bytes(tot)}" if tot else fmt_bytes(dl))
        self._l_speed.setText(fmt_speed(spd))
        self._l_eta.setText(f"ETA {fmt_eta(eta)}" if eta else "—")

    def update_status(self, s: DLStatus) -> None:
        self._badge.set_status(s.name)
        active = not s.is_terminal
        self._b_pause.setVisible(active)
        self._b_cancel.setVisible(active)

        if s == DLStatus.COMPLETED:
            self._pbar.setValue(100); self._l_pct.setText("100%")
            self._b_folder.setVisible(True)
            self._ico.setStyleSheet(f"color:{GN}; font-size:13px; background:transparent;")
            self._ico.setText("✓")
            self._pbar.setStyleSheet(
                f"QProgressBar{{background:{W4};border:none;border-radius:4px;}}"
                f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 #51CF66,stop:1 {GN});border-radius:4px;}}"
            )
        elif s == DLStatus.FAILED:
            self._ico.setStyleSheet(f"color:{RD}; font-size:13px; background:transparent;")
            self._ico.setText("✗")
            self._pbar.setStyleSheet(
                f"QProgressBar{{background:{W4};border:none;border-radius:4px;}}"
                f"QProgressBar::chunk{{background:{RD};border-radius:4px;}}"
            )
        elif s == DLStatus.MERGING:
            self._pbar.setStyleSheet(
                f"QProgressBar{{background:{W4};border:none;border-radius:4px;}}"
                f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 #FFA94D,stop:1 {OR});border-radius:4px;}}"
            )
        elif s == DLStatus.PAUSED:
            self._b_pause.setText("▶"); self._b_pause.setToolTip("Resume")
            self._ico.setStyleSheet(f"color:{PU}; font-size:13px; background:transparent;")
        elif s == DLStatus.DOWNLOADING:
            self._b_pause.setText("⏸"); self._b_pause.setToolTip("Pause")
            self._ico.setStyleSheet(f"color:{RD}; font-size:13px; background:transparent;")

    def set_output(self, path: str) -> None:
        self._out = path; self._b_folder.setVisible(True)

    def _toggle_pause(self) -> None:
        if self._paused:
            self._paused = False; self.sig_resume.emit(self.task_id)
        else:
            self._paused = True;  self.sig_pause.emit(self.task_id)

    def _do_open(self) -> None:
        if self._out: self.sig_folder.emit(self._out)


# ══════════════════════════════════════════════════════════════════════════════════
#  §17  VIDEO INFO PANEL
# ══════════════════════════════════════════════════════════════════════════════════

class InfoPanel(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loader: Optional[ThumbLoader] = None
        self.setStyleSheet(
            f"QFrame{{background:{W1}; border:1.5px solid {W4}; border-radius:10px;}}"
        )
        self._build(); self.clear()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16); root.setSpacing(18)

        self._thumb = QLabel("No Preview")
        self._thumb.setFixedSize(THUMB_W, THUMB_H)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            f"background:{W0}; border-radius:8px; border:1.5px solid {W4};"
            f"color:{TX2}; font-size:12px;"
        )
        root.addWidget(self._thumb)

        col = QVBoxLayout(); col.setSpacing(8); col.setContentsMargins(0,0,0,0)
        self._title_lbl = _lbl("—", 15, bold=True, wrap=True)
        col.addWidget(self._title_lbl)
        self._chan_lbl = _lbl("—", 12, color=TX1)
        col.addWidget(self._chan_lbl)
        col.addWidget(_sep())

        stats = QHBoxLayout(); stats.setSpacing(30)
        self._s_dur   = StatCard("DURATION")
        self._s_views = StatCard("VIEWS")
        self._s_date  = StatCard("UPLOADED")
        self._s_fmts  = StatCard("FORMATS")
        self._s_size  = StatCard("EST. SIZE")
        for sc in (self._s_dur, self._s_views, self._s_date, self._s_fmts, self._s_size):
            stats.addWidget(sc)
        stats.addStretch()
        col.addLayout(stats)

        self._pl_badge = _pill("", OR, ORL)
        self._pl_badge.setVisible(False)
        col.addWidget(self._pl_badge)
        col.addStretch()
        root.addLayout(col, 1)

    def show_meta(self, meta: VideoMeta) -> None:
        self._title_lbl.setText(meta.title or "—")
        self._chan_lbl.setText(f"   {meta.channel}")
        self._s_dur.set_value(fmt_dur(meta.duration))
        self._s_views.set_value(fmt_views(meta.view_count) if meta.view_count else "—")
        self._s_date.set_value(format_date(meta.upload_date))
        vf = len(meta.video_formats); af = len(meta.audio_formats)
        self._s_fmts.set_value(f"{vf}V / {af}A")
        best_sz: Optional[int] = next(
            (f.filesize for f in meta.video_formats if f.filesize), None
        )
        self._s_size.set_value(fmt_bytes(best_sz) if best_sz else "—")
        if meta.is_playlist:
            n = len(meta.entries)
            self._pl_badge.setText(f"  PLAYLIST  ·  {n} video{'s' if n!=1 else ''}")
            self._pl_badge.setVisible(True)
        else:
            self._pl_badge.setVisible(False)
        if meta.thumbnail_url: self._load_thumb(meta.thumbnail_url)

    def clear(self) -> None:
        self._title_lbl.setText("—"); self._chan_lbl.setText("—")
        for sc in (self._s_dur, self._s_views, self._s_date, self._s_fmts, self._s_size):
            sc.set_value("—")
        self._thumb.clear(); self._thumb.setText("No Preview")
        self._pl_badge.setVisible(False)

    def _load_thumb(self, url: str) -> None:
        if self._loader and self._loader.isRunning():
            self._loader.terminate(); self._loader.wait()
        self._thumb.setText("Loading…")
        self._loader = ThumbLoader(url, self)
        self._loader.loaded.connect(self._on_thumb)
        self._loader.failed.connect(lambda: self._thumb.setText("No Preview"))
        self._loader.start()

    def _on_thumb(self, data: bytes) -> None:
        px = QPixmap()
        if px.loadFromData(data):
            self._thumb.setPixmap(px.scaled(
                THUMB_W, THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            self._thumb.setText("No Preview")


# ══════════════════════════════════════════════════════════════════════════════════
#  §18  CONTROL PANEL  (URL input + options + download buttons)
# ══════════════════════════════════════════════════════════════════════════════════

class ControlPanel(QFrame):
    sig_fetch        = pyqtSignal(str)
    sig_cancel_fetch = pyqtSignal()
    sig_download     = pyqtSignal(str, str, str, bool, str, str, bool, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._out_dir = Path(Config.get("output_dir", str(DL_DIR)))
        self.setStyleSheet(
            f"QFrame{{background:{W1}; border:1.5px solid {W4}; border-radius:10px;}}"
        )
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18); root.setSpacing(13)

        # ── URL row ────────────────────────────────────────────────────────
        root.addWidget(_section_lbl("YOUTUBE URL"))
        url_row = QHBoxLayout(); url_row.setSpacing(8)
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText(
            "Paste a YouTube video, playlist or Shorts URL and press Enter…"
        )
        self._url_edit.setClearButtonEnabled(True)
        self._url_edit.setFixedHeight(42)
        self._url_edit.returnPressed.connect(self._do_fetch)
        url_row.addWidget(self._url_edit, 1)

        self._btn_analyze = QPushButton("  🔍  Analyze")
        self._btn_analyze.setObjectName("pBrand")
        self._btn_analyze.setFixedSize(132, 42)
        self._btn_analyze.clicked.connect(self._do_fetch)
        url_row.addWidget(self._btn_analyze)

        self._btn_stop = QPushButton("✕  Stop")
        self._btn_stop.setObjectName("pDanger")
        self._btn_stop.setFixedSize(90, 42)
        self._btn_stop.setVisible(False)
        self._btn_stop.clicked.connect(self._do_cancel)
        url_row.addWidget(self._btn_stop)
        root.addLayout(url_row)

        root.addWidget(_sep())

        # ── Quality / format row ───────────────────────────────────────────
        def _opt(heading: str, widget: QWidget) -> QVBoxLayout:
            c = QVBoxLayout(); c.setSpacing(5)
            c.addWidget(_section_lbl(heading)); c.addWidget(widget)
            return c

        self._q_box = QComboBox()
        self._q_box.addItems(QUALITY_PRESETS)
        self._q_box.setCurrentText(Config.get("default_quality","1080p"))
        self._q_box.setFixedHeight(36)

        self._vfmt_box = QComboBox()
        self._vfmt_box.addItems([f.upper() for f in VIDEO_CONTAINERS])
        self._vfmt_box.setCurrentText(Config.get("default_vfmt","mp4").upper())
        self._vfmt_box.setFixedHeight(36)

        self._afmt_box = QComboBox()
        self._afmt_box.addItems([f.upper() for f in AUDIO_FORMATS])
        self._afmt_box.setCurrentText(Config.get("default_afmt","mp3").upper())
        self._afmt_box.setFixedHeight(36)

        opt_row = QHBoxLayout(); opt_row.setSpacing(12)
        opt_row.addLayout(_opt("QUALITY",       self._q_box),    2)
        opt_row.addLayout(_opt("VIDEO FORMAT",  self._vfmt_box), 1)
        opt_row.addLayout(_opt("AUDIO FORMAT",  self._afmt_box), 1)
        root.addLayout(opt_row)

        # ── Output folder ──────────────────────────────────────────────────
        root.addWidget(_section_lbl("SAVE TO FOLDER"))
        dir_row = QHBoxLayout(); dir_row.setSpacing(8)
        self._dir_edit = QLineEdit(str(self._out_dir))
        self._dir_edit.setReadOnly(True); self._dir_edit.setFixedHeight(34)
        dir_row.addWidget(self._dir_edit, 1)
        btn_br = QPushButton("Browse"); btn_br.setObjectName("pGhost")
        btn_br.setFixedSize(80, 34); btn_br.clicked.connect(self._browse)
        dir_row.addWidget(btn_br)
        root.addLayout(dir_row)

        root.addWidget(_sep())

        # ── Subtitles row ──────────────────────────────────────────────────
        sub_row = QHBoxLayout(); sub_row.setSpacing(16)
        self._subs_chk = QCheckBox("Download Subtitles")
        self._subs_chk.setChecked(Config.get("write_subs", False))
        sub_row.addWidget(self._subs_chk)
        sub_row.addWidget(_lbl("Languages:", 12, color=TX1))
        self._lang_edit = QLineEdit(Config.get("sub_langs","en"))
        self._lang_edit.setFixedSize(130, 28)
        self._lang_edit.setPlaceholderText("en,fr,ja…")
        self._lang_edit.setToolTip(
            "Comma-separated ISO language codes.\n"
            "Examples: en  |  en,fr  |  ja  |  zh-Hans,en"
        )
        sub_row.addWidget(self._lang_edit)
        sub_row.addStretch()
        root.addLayout(sub_row)

        # ── Download buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self._btn_dl = QPushButton("⬇   Download Video")
        self._btn_dl.setObjectName("pBrand")
        self._btn_dl.setFixedHeight(44)
        self._btn_dl.setEnabled(False)
        self._btn_dl.clicked.connect(lambda: self._emit_dl(False))

        self._btn_audio = QPushButton("🎵   Audio Only")
        self._btn_audio.setObjectName("pGreen")
        self._btn_audio.setFixedHeight(44)
        self._btn_audio.setEnabled(False)
        self._btn_audio.clicked.connect(lambda: self._emit_dl(True))

        btn_row.addWidget(self._btn_dl, 2)
        btn_row.addWidget(self._btn_audio, 1)
        root.addLayout(btn_row)

    # ── public ─────────────────────────────────────────────────────────────
    def get_url(self)            -> str:  return self._url_edit.text().strip()
    def set_url(self, u: str)    -> None: self._url_edit.setText(u)

    def set_fetching(self, v: bool) -> None:
        self._btn_analyze.setEnabled(not v)
        self._btn_analyze.setText("Analyzing…" if v else "  🔍  Analyze")
        self._btn_stop.setVisible(v)
        self._url_edit.setEnabled(not v)

    def set_dl_enabled(self, v: bool) -> None:
        self._btn_dl.setEnabled(v); self._btn_audio.setEnabled(v)

    def update_output_dir(self, path: str) -> None:
        self._out_dir = Path(path); self._dir_edit.setText(path)

    # ── private ────────────────────────────────────────────────────────────
    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Output Folder", str(self._out_dir))
        if d: self._out_dir = Path(d); self._dir_edit.setText(d)

    def _do_fetch(self) -> None:
        u = self.get_url()
        if u: self.sig_fetch.emit(u)

    def _do_cancel(self) -> None:
        self.sig_cancel_fetch.emit(); self.set_fetching(False)

    def _emit_dl(self, audio_only: bool) -> None:
        u = self.get_url()
        if not u: return
        self.sig_download.emit(
            u, self._q_box.currentText(),
            self._vfmt_box.currentText().lower(),
            audio_only,
            self._afmt_box.currentText().lower(),
            str(self._out_dir),
            self._subs_chk.isChecked(),
            self._lang_edit.text().strip() or "en",
        )


# ══════════════════════════════════════════════════════════════════════════════════
#  §19  ACTIVITY LOG CONSOLE
# ══════════════════════════════════════════════════════════════════════════════════

class LogConsole(QTextEdit):
    MAX_LINES = 600

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Cascadia Code", 11))
        self.setStyleSheet(
            f"QTextEdit{{background:{W1}; color:{TX1}; "
            f"border:1.5px solid {W4}; border-radius:8px; "
            "padding:10px 12px; font-family:'Cascadia Code','Consolas',"
            "'JetBrains Mono',monospace; font-size:12px;}}"
        )
        self.setMaximumHeight(155)
        self._n = 0
        self._log("System", f"YT Downloader Pro v{APP_VER} — ready", TX0, bold=True)
        ff = "FFmpeg ✓" if ffmpeg_ok() else "FFmpeg ✗  —  install for merging"
        self._log("System", ff, GN if ffmpeg_ok() else RD)

    def _log(self, prefix: str, msg: str, color: str = TX1,
              bold: bool = False) -> None:
        if self._n >= self.MAX_LINES: self.clear(); self._n = 0
        ts = time.strftime("%H:%M:%S")
        w  = "font-weight:700;" if bold else ""
        self.append(
            f'<span style="color:{TX3};">[{ts}]</span> '
            f'<span style="color:{BL};font-size:10px;font-weight:700;">{prefix}</span> '
            f'<span style="color:{color};{w}">{msg}</span>'
        )
        sb = self.verticalScrollBar()
        if sb: sb.setValue(sb.maximum())
        self._n += 1

    def info(self, m: str) -> None: self._log("INFO ", m, TX0)
    def warn(self, m: str) -> None: self._log("WARN ", m, OR)
    def err(self,  m: str) -> None: self._log("ERROR", m, RD)
    def dl(self,   m: str) -> None: self._log("DL   ", m, BL)
    def ok(self,   m: str) -> None: self._log("DONE ", m, GN)


# ══════════════════════════════════════════════════════════════════════════════════
#  §20  HEADER BAR
# ══════════════════════════════════════════════════════════════════════════════════

class HeaderBar(QWidget):
    sig_settings = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(62)
        self.setStyleSheet(f"background:{RD};")
        self._build()

    def _build(self) -> None:
        l = QHBoxLayout(self)
        l.setContentsMargins(22, 0, 18, 0); l.setSpacing(12)

        # Logo + name block
        logo = QLabel("▶")
        logo.setStyleSheet("color:white; font-size:26px; font-weight:900; background:transparent;")
        l.addWidget(logo)

        name_col = QVBoxLayout(); name_col.setSpacing(0)
        name_col.addWidget(_lbl(APP_NAME, 17, bold=True, color="white"))
        tagline = _lbl("The Professional YouTube Downloader", 10, color="rgba(255,255,255,0.65)")
        name_col.addWidget(tagline)
        l.addLayout(name_col)
        l.addStretch()

        # Status pills
        self._p_active  = self._pill("0 active")
        self._p_pending = self._pill("0 queued", dim=True)
        self._p_ff      = self._pill(
            "FFmpeg ✓" if ffmpeg_ok() else "FFmpeg ✗",
            warn=not ffmpeg_ok(),
        )
        for p in (self._p_active, self._p_pending, self._p_ff):
            l.addWidget(p)

        vl = QFrame(); vl.setFrameShape(QFrame.Shape.VLine); vl.setFixedHeight(30)
        vl.setStyleSheet("background:rgba(255,255,255,0.25); border:none; max-width:1px;")
        l.addWidget(vl)

        btn_s = QPushButton("⚙  Settings")
        btn_s.setStyleSheet(
            "background:rgba(255,255,255,0.15); color:white;"
            "border:1.5px solid rgba(255,255,255,0.35); border-radius:6px;"
            "padding:6px 16px; font-size:12px; font-weight:600;"
        )
        btn_s.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_s.clicked.connect(self.sig_settings)
        l.addWidget(btn_s)

    def update_queue(self, active: int, pending: int) -> None:
        self._p_active.setText(f"{active} active")
        self._p_pending.setText(f"{pending} queued")

    @staticmethod
    def _pill(text: str, dim: bool = False, warn: bool = False) -> QLabel:
        if warn:
            st = "background:rgba(255,235,0,0.22); color:#FFE066; border:1px solid rgba(255,235,0,0.4);"
        elif dim:
            st = "background:rgba(255,255,255,0.1); color:rgba(255,255,255,0.7); border:1px solid rgba(255,255,255,0.15);"
        else:
            st = "background:rgba(255,255,255,0.2); color:white; border:1px solid rgba(255,255,255,0.35);"
        lab = QLabel(text)
        lab.setStyleSheet(st + "border-radius:12px; padding:4px 13px; font-size:11px; font-weight:700; letter-spacing:0.4px;")
        return lab


# ══════════════════════════════════════════════════════════════════════════════════
#  §21  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._meta:       Optional[VideoMeta]  = None
        self._cards:      Dict[str, DLCard]    = {}
        self._states:     Dict[str, TaskState] = {}
        self._ext_worker: Optional[ExtWorker]  = None
        self._clip_prev   = ""
        self._mgr         = DLManager(self)

        self._init_window()
        self._build_ui()
        self._wire()

        self._clip_timer = QTimer(self)
        self._clip_timer.timeout.connect(self._check_clipboard)
        if Config.get("auto_clip", True):
            self._clip_timer.start(800)

        log.info("%s v%s started", APP_NAME, APP_VER)

    # ══ window init ═══════════════════════════════════════════════════════════
    def _init_window(self) -> None:
        self.setWindowTitle(f"{APP_NAME}  v{APP_VER}")
        self.setMinimumSize(1120, 720); self.resize(1340, 860)
        self.setStyleSheet(STYLESHEET)
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window,        QColor(W0))
        pal.setColor(QPalette.ColorRole.WindowText,    QColor(TX0))
        pal.setColor(QPalette.ColorRole.Base,          QColor(W1))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(W2))
        self.setPalette(pal)

    # ══ build UI ══════════════════════════════════════════════════════════════
    def _build_ui(self) -> None:
        cw = QWidget(); self.setCentralWidget(cw)
        ml = QVBoxLayout(cw); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)

        self._hdr = HeaderBar()
        self._hdr.sig_settings.connect(self._open_settings)
        ml.addWidget(self._hdr)

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.setChildrenCollapsible(False); sp.setHandleWidth(1)
        sp.addWidget(self._build_left()); sp.addWidget(self._build_right())
        sp.setSizes([468, 832])
        ml.addWidget(sp, 1)

        self._sb = QStatusBar(); self.setStatusBar(self._sb)
        self._sb.showMessage(
            "Ready  ·  " + ("FFmpeg detected ✓" if ffmpeg_ok()
                             else "⚠ FFmpeg not found — install for merging")
        )

    def _build_left(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w); l.setContentsMargins(14,14,7,14); l.setSpacing(10)
        self._ctrl = ControlPanel();  l.addWidget(self._ctrl)
        self._info = InfoPanel();     l.addWidget(self._info)
        hdr_lbl = _section_lbl("ACTIVITY LOG"); hdr_lbl.setContentsMargins(0,4,0,2)
        l.addWidget(hdr_lbl)
        self._console = LogConsole(); l.addWidget(self._console)
        return w

    def _build_right(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w); l.setContentsMargins(7,14,14,14); l.setSpacing(0)
        self._tabs = QTabWidget(); self._tabs.setDocumentMode(True)
        self._tabs.addTab(self._build_queue_tab(),   "  ⬇  Downloads  ")
        self._tabs.addTab(self._build_history_tab(), "  🕒  History  ")
        l.addWidget(self._tabs, 1)
        return w

    def _build_queue_tab(self) -> QWidget:
        outer = QWidget()
        l = QVBoxLayout(outer); l.setContentsMargins(0,10,0,0); l.setSpacing(8)

        tb = QHBoxLayout(); tb.setSpacing(8)
        self._q_stat_lbl = _lbl("", 12, color=TX1)
        tb.addWidget(self._q_stat_lbl); tb.addStretch()
        self._btn_cancel_all = QPushButton("Cancel All")
        self._btn_cancel_all.setObjectName("pDanger")
        self._btn_cancel_all.setFixedHeight(30)
        self._btn_cancel_all.setVisible(False)
        self._btn_cancel_all.clicked.connect(self._do_cancel_all)
        self._btn_clear = QPushButton("Clear Completed")
        self._btn_clear.setObjectName("pGhost")
        self._btn_clear.setFixedHeight(30)
        self._btn_clear.clicked.connect(self._clear_done)
        tb.addWidget(self._btn_cancel_all); tb.addWidget(self._btn_clear)
        l.addLayout(tb)

        sc = QScrollArea(); sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        sc.setStyleSheet(f"QScrollArea{{background:{W0}; border:none;}}")
        self._q_inner = QWidget(); self._q_inner.setStyleSheet(f"background:{W0};")
        self._q_lay   = QVBoxLayout(self._q_inner)
        self._q_lay.setContentsMargins(0,0,6,0); self._q_lay.setSpacing(7)
        self._q_lay.addStretch()
        sc.setWidget(self._q_inner); l.addWidget(sc, 1)

        self._empty_lbl = QLabel(
            "No downloads yet\n\nPaste a YouTube URL above and click Analyze"
        )
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color:{TX3}; font-size:13px; background:transparent;")
        l.addWidget(self._empty_lbl)
        return outer

    def _build_history_tab(self) -> QWidget:
        outer = QWidget()
        l = QVBoxLayout(outer); l.setContentsMargins(0,10,0,0); l.setSpacing(8)

        sr = QHBoxLayout(); sr.setSpacing(8)
        self._hist_srch = QLineEdit()
        self._hist_srch.setPlaceholderText("🔍  Search history…")
        self._hist_srch.setFixedHeight(32)
        self._hist_srch.textChanged.connect(self._reload_hist)
        sr.addWidget(self._hist_srch, 1)
        l.addLayout(sr)

        self._hist_tbl = QTableWidget(0, 6)
        self._hist_tbl.setHorizontalHeaderLabels(
            ["Title", "Format", "Quality", "Size", "Date", ""]
        )
        hh = self._hist_tbl.horizontalHeader()
        if hh:
            hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for i in (1,2,3,4): hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed); hh.resizeSection(5, 72)
        self._hist_tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._hist_tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._hist_tbl.setAlternatingRowColors(True)
        self._hist_tbl.setShowGrid(False)
        vh = self._hist_tbl.verticalHeader()
        if vh: vh.setVisible(False)
        self._hist_tbl.doubleClicked.connect(self._hist_open)
        l.addWidget(self._hist_tbl, 1)

        br = QHBoxLayout(); br.setSpacing(8)
        self._hist_cnt = _lbl("", 12, color=TX2); br.addWidget(self._hist_cnt)
        br.addStretch()
        rb = QPushButton("↻  Refresh"); rb.setObjectName("pGhost"); rb.setFixedHeight(30)
        rb.clicked.connect(self._reload_hist)
        cb = QPushButton("🗑  Clear All"); cb.setObjectName("pDanger"); cb.setFixedHeight(30)
        cb.clicked.connect(self._clear_hist)
        br.addWidget(rb); br.addWidget(cb)
        l.addLayout(br)
        self._reload_hist()
        return outer

    # ══ signal wiring ═════════════════════════════════════════════════════════
    def _wire(self) -> None:
        c = self._ctrl
        c.sig_fetch.connect(self._on_fetch)
        c.sig_cancel_fetch.connect(self._on_cancel_fetch)
        c.sig_download.connect(self._on_download)

        m = self._mgr
        m.sig_progress.connect(self._on_progress)
        m.sig_status.connect(self._on_status)
        m.sig_done.connect(self._on_done)
        m.sig_error.connect(self._on_error)
        m.sig_log.connect(lambda _, msg: self._console.dl(msg) if msg.strip() else None)
        m.sig_qchanged.connect(self._on_qchanged)

    # ══ slots — fetch ══════════════════════════════════════════════════════════
    @pyqtSlot(str)
    def _on_fetch(self, url: str) -> None:
        ok, msg = valid_yt(url)
        if not ok:
            self._sb.showMessage(f"⚠  {msg}"); self._console.warn(f"Invalid URL: {msg}"); return
        self._ctrl.set_fetching(True); self._ctrl.set_dl_enabled(False)
        self._info.clear(); self._sb.showMessage("Analyzing URL…")
        self._console.info(f"Fetching: {url[:90]}")
        w = ExtWorker(url); self._ext_worker = w
        w.sig.done.connect(self._on_meta)
        w.sig.error.connect(self._on_fetch_err)
        w.sig.msg.connect(lambda m: self._console.info(m))
        w.sig.progress.connect(
            lambda cur, tot: self._sb.showMessage(
                f"Scanning playlist: {cur}/{tot}…" if tot else "Scanning…"
            )
        )
        pool = QThreadPool.globalInstance()
        if pool: pool.start(w)

    @pyqtSlot()
    def _on_cancel_fetch(self) -> None:
        if self._ext_worker: self._ext_worker.cancel(); self._ext_worker = None
        self._sb.showMessage("Fetch cancelled"); self._console.warn("Fetch cancelled by user")

    @pyqtSlot(object)
    def _on_meta(self, meta: VideoMeta) -> None:
        self._meta = meta; self._info.show_meta(meta)
        self._ctrl.set_fetching(False); self._ctrl.set_dl_enabled(True)
        if meta.is_playlist:
            n = len(meta.entries)
            self._sb.showMessage(f"Playlist ready  ·  {meta.title}  ·  {n} videos")
            self._console.info(f"Playlist loaded: \"{meta.title}\" — {n} videos")
        else:
            self._sb.showMessage(
                f"Ready  ·  {clip(meta.title,55)}  ·  {fmt_dur(meta.duration)}"
            )
            self._console.info(
                f"Loaded: \"{meta.title}\"  [{fmt_dur(meta.duration)}]  "
                f"{len(meta.video_formats)}V / {len(meta.audio_formats)}A formats"
            )

    @pyqtSlot(str)
    def _on_fetch_err(self, msg: str) -> None:
        self._ctrl.set_fetching(False)
        self._sb.showMessage(f"Error: {msg[:80]}"); self._console.err(f"Fetch failed: {msg}")
        QMessageBox.warning(
            self, "Fetch Error",
            f"Could not fetch video info:\n\n{msg}\n\n"
            "• Check the URL is valid\n"
            "• Check your internet connection\n"
            "• Try:  pip install -U yt-dlp"
        )

    # ══ slots — download ═══════════════════════════════════════════════════════
    @pyqtSlot(str, str, str, bool, str, str, bool, str)
    def _on_download(self, url: str, quality: str, container: str,
                      audio_only: bool, audio_fmt: str, out_dir: str,
                      subs: bool, sub_langs: str) -> None:
        if not self._meta:
            self._sb.showMessage("Please analyze a URL first."); return
        if not ffmpeg_ok() and not audio_only:
            self._console.warn(
                "FFmpeg not found — using single-stream (no merge). "
                "Install FFmpeg for best quality."
            )
        meta       = self._meta
        embed      = Config.get("embed_subs", True)
        spd_limit  = Config.get("speed_limit_kb", 0)

        if meta.is_playlist:
            dlg = PlaylistDialog(meta, self)
            if dlg.exec() != QDialog.DialogCode.Accepted: return
            chosen = dlg.selected_entries()
            if not chosen:
                self._sb.showMessage("No videos selected."); return
            pl_dir = Path(out_dir) / sanitize(meta.title or "Playlist")
            pl_dir.mkdir(parents=True, exist_ok=True)
            for e in chosen:
                self._enqueue(DLTask(
                    url=e.url, title=e.title, output_dir=pl_dir,
                    quality=quality, container=container,
                    audio_only=audio_only, audio_fmt=audio_fmt,
                    write_subs=subs, sub_langs=sub_langs,
                    embed_subs=embed, speed_limit_kb=spd_limit,
                    thumbnail_url=e.thumbnail_url,
                ))
            self._console.info(
                f"Queued {len(chosen)} videos → {pl_dir.name}/"
            )
        else:
            self._enqueue(DLTask(
                url=meta.url, title=meta.title, output_dir=Path(out_dir),
                quality=quality, container=container,
                audio_only=audio_only, audio_fmt=audio_fmt,
                write_subs=subs, sub_langs=sub_langs,
                embed_subs=embed, speed_limit_kb=spd_limit,
                thumbnail_url=meta.thumbnail_url,
            ))

    def _enqueue(self, task: DLTask) -> None:
        card = DLCard(task.task_id, task.title)
        card.sig_pause.connect(self._mgr.pause)
        card.sig_resume.connect(self._mgr.resume)
        card.sig_cancel.connect(self._mgr.cancel)
        card.sig_folder.connect(lambda p: open_path(Path(p)))
        self._cards[task.task_id]  = card
        self._states[task.task_id] = TaskState(task=task)
        self._q_lay.insertWidget(self._q_lay.count() - 1, card)
        self._empty_lbl.setVisible(False)
        self._tabs.setCurrentIndex(0)
        self._mgr.enqueue(task)
        self._console.dl(f"Queued: {clip(task.title, 60)}")
        self._update_q_label()

    # ══ slots — progress / status ══════════════════════════════════════════════
    @pyqtSlot(str, float, int, int, float, float)
    def _on_progress(self, tid: str, pct: float, dl: int,
                      tot: int, spd: float, eta: float) -> None:
        s = self._states.get(tid)
        if s: s.pct=pct; s.dl_bytes=dl; s.tot_bytes=tot; s.speed=spd; s.eta=eta
        c = self._cards.get(tid)
        if c: c.update_progress(pct, dl, tot, spd, eta)

    @pyqtSlot(str, object)
    def _on_status(self, tid: str, status: DLStatus) -> None:
        s = self._states.get(tid)
        if s: s.status = status
        c = self._cards.get(tid)
        if c: c.update_status(status)

    @pyqtSlot(str, str)
    def _on_done(self, tid: str, path: str) -> None:
        s = self._states.get(tid)
        if s: s.status=DLStatus.COMPLETED; s.out_path=path
        c = self._cards.get(tid)
        if c: c.set_output(path); c.update_status(DLStatus.COMPLETED)
        self._sb.showMessage(f"✓  Complete: {Path(path).name}")
        self._console.ok(f"Saved: {Path(path).name}")
        self._reload_hist(); self._update_q_label()

    @pyqtSlot(str, str)
    def _on_error(self, tid: str, msg: str) -> None:
        s = self._states.get(tid)
        if s: s.status=DLStatus.FAILED; s.err=msg
        c = self._cards.get(tid)
        if c: c.update_status(DLStatus.FAILED)
        self._sb.showMessage(f"✗  Error: {msg[:80]}")
        self._console.err(f"Failed: {msg}")
        self._update_q_label()

    @pyqtSlot(int, int)
    def _on_qchanged(self, active: int, pending: int) -> None:
        self._hdr.update_queue(active, pending)
        self._btn_cancel_all.setVisible(active + pending > 0)
        self._update_q_label()

    # ══ queue helpers ══════════════════════════════════════════════════════════
    def _update_q_label(self) -> None:
        active = sum(1 for s in self._states.values() if s.status.is_active)
        done   = sum(1 for s in self._states.values() if s.status == DLStatus.COMPLETED)
        total  = len(self._states)
        if total:
            self._q_stat_lbl.setText(
                f"{active} downloading  ·  {done} completed  ·  {total} total"
            )
        else:
            self._q_stat_lbl.setText("")

    def _clear_done(self) -> None:
        to_rm = [tid for tid,s in self._states.items() if s.status.is_terminal]
        for tid in to_rm:
            c = self._cards.pop(tid, None)
            if c: self._q_lay.removeWidget(c); c.deleteLater()
            self._states.pop(tid, None)
        if not self._cards: self._empty_lbl.setVisible(True)
        self._update_q_label()

    def _do_cancel_all(self) -> None:
        if QMessageBox.question(
            self, "Cancel All",
            "Cancel all active and pending downloads?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._mgr.cancel_all()

    # ══ clipboard ══════════════════════════════════════════════════════════════
    def _check_clipboard(self) -> None:
        cb = QApplication.clipboard()
        if not cb: return
        text = (cb.text() or "").strip()
        if text and text != self._clip_prev:
            self._clip_prev = text
            ok, _ = valid_yt(text)
            if ok and self._ctrl.get_url() != text:
                self._ctrl.set_url(text)
                self._sb.showMessage("YouTube URL detected from clipboard  ·  Press Analyze")
                self._console.info(f"Clipboard: {text[:70]}")

    # ══ history ════════════════════════════════════════════════════════════════
    def _reload_hist(self, _: str = "") -> None:
        h = load_hist(); self._hist_tbl.setRowCount(0)
        query = self._hist_srch.text().lower(); shown = 0
        for e in reversed(h):
            title = e.get("title","")
            if query and query not in title.lower(): continue
            r = self._hist_tbl.rowCount(); self._hist_tbl.insertRow(r)
            sz = "—"
            try:
                p = Path(e.get("output",""))
                if p.exists(): sz = fmt_bytes(p.stat().st_size)
            except Exception: pass
            items = [
                QTableWidgetItem(clip(title, 65)),
                QTableWidgetItem((e.get("format") or "").upper()),
                QTableWidgetItem(e.get("quality","")),
                QTableWidgetItem(sz),
                QTableWidgetItem(e.get("timestamp","")[:16]),
            ]
            items[0].setData(Qt.ItemDataRole.UserRole, e.get("output",""))
            for col, item in enumerate(items):
                self._hist_tbl.setItem(r, col, item)
            ob = QPushButton("📂 Open"); ob.setObjectName("pLink"); ob.setFixedHeight(28)
            out_path = e.get("output","")
            ob.clicked.connect(lambda _, p=out_path: open_path(Path(p)) if p else None)
            self._hist_tbl.setCellWidget(r, 5, ob)
            shown += 1
        self._hist_cnt.setText(f"{shown} entries")

    def _clear_hist(self) -> None:
        if QMessageBox.question(
            self, "Clear History",
            "Permanently clear all download history?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            save_hist([]); self._reload_hist()

    def _hist_open(self, idx: Any) -> None:
        item = self._hist_tbl.item(idx.row(), 0)
        if item:
            p = item.data(Qt.ItemDataRole.UserRole)
            if p: open_path(Path(p))

    # ══ settings ═══════════════════════════════════════════════════════════════
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._mgr.set_max(Config.get("max_concurrent", MAX_CONCURRENT))
            self._ctrl.update_output_dir(Config.get("output_dir", str(DL_DIR)))
            if Config.get("auto_clip", True):
                if not self._clip_timer.isActive(): self._clip_timer.start(800)
            else:
                self._clip_timer.stop()
            self._console.info("Settings saved and applied")

    # ══ close ══════════════════════════════════════════════════════════════════
    def closeEvent(self, a0: Optional[QCloseEvent]) -> None:
        if a0 is None: return
        if self._mgr.active_count:
            r = QMessageBox.question(
                self, "Downloads Running",
                f"{self._mgr.active_count} download(s) still active.\nCancel them and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r == QMessageBox.StandardButton.Yes: self._mgr.cancel_all(); a0.accept()
            else: a0.ignore()
        else:
            a0.accept()


# ══════════════════════════════════════════════════════════════════════════════════
#  §22  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════════

def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VER)
    app.setFont(QFont("Segoe UI", 10))

    win = MainWindow()
    win.show()

    if not ffmpeg_ok():
        win._console.warn("FFmpeg not found on PATH — merging disabled")
        win._console.warn("  Windows → https://ffmpeg.org/download.html")
        win._console.warn("  macOS   → brew install ffmpeg")
        win._console.warn("  Linux   → sudo apt install ffmpeg")
        win._sb.showMessage(
            "⚠  FFmpeg not found — download from ffmpeg.org and add to PATH"
        )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())