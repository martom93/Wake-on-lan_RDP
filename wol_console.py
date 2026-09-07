#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WOL Console — zdalne wybudzanie komputerów (Wake-on-LAN) z podglądem stanu.

Następca skryptu tkinter: PySide6, lista komputerów zapisywana w JSON,
monitorowanie dostępności w tle, pulpit zdalny, log zdarzeń, tray.

Autor pierwowzoru: Marcin Tomaszewski (github.com/martom93)

Uruchomienie:
    pip install PySide6
    python wol_console.py
    python wol_console.py --demo     # wypełnia listę przykładowymi maszynami
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, QObject, QPointF, QRect, QRectF,
    QRunnable, QSettings, QSize, QSortFilterProxyModel, QThreadPool, QTimer,
    Qt, Signal, Slot,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QSizePolicy, QSpinBox, QSplitter, QStyle, QStyledItemDelegate,
    QStyleOptionViewItem, QSystemTrayIcon, QTableView, QTextEdit, QToolButton,
    QVBoxLayout, QWidget,
)

APP_NAME = "WOL Console"
APP_VERSION = "2.0"
ORG_NAME = "martom93"

IS_WINDOWS = sys.platform.startswith("win")

# --------------------------------------------------------------------------
# Paleta i style
# --------------------------------------------------------------------------
# Ciemny błękitno-grafitowy "kolor serwerowni"; bursztyn zarezerwowany
# wyłącznie dla akcji włączania zasilania, zieleń dla stanu online.
C = {
    "bg":        "#151A23",
    "panel":     "#1C222E",
    "panel_alt": "#222937",
    "line":      "#2E3746",
    "line_soft": "#262E3B",
    "text":      "#E4E9F2",
    "text_dim":  "#8B98AE",
    "text_faint":"#63708A",
    "amber":     "#E2A24A",
    "amber_dk":  "#C4883A",
    "online":    "#4FB286",
    "offline":   "#5D6A80",
    "error":     "#CE5F58",
    "info":      "#5C8FD6",
}

STYLESHEET = f"""
QWidget {{
    background: {C['bg']};
    color: {C['text']};
    font-size: 13px;
}}
QLabel, QCheckBox {{
    background: transparent;
}}
QFrame#Panel {{
    background: {C['panel']};
    border: 1px solid {C['line']};
    border-radius: 8px;
}}
QFrame#Header {{
    background: {C['panel']};
    border: none;
    border-bottom: 1px solid {C['line']};
    border-radius: 0px;
}}
QLabel#AppTitle {{
    font-size: 17px;
    font-weight: 600;
    color: {C['text']};
}}
QLabel#AppSubtitle  {{ color: {C['text_faint']}; font-size: 12px; }}
QLabel#SectionLabel {{ color: {C['text_dim']}; font-size: 12px; }}
QLabel#DetailName   {{ font-size: 16px; font-weight: 600; }}
QLabel#FieldKey     {{ color: {C['text_faint']}; font-size: 12px; }}
QLabel#FieldValue   {{ color: {C['text']}; font-size: 12px; }}
QLabel#EmptyTitle   {{ color: {C['text_dim']}; font-size: 15px; }}
QLabel#EmptyBody    {{ color: {C['text_faint']}; font-size: 13px; }}

QPushButton {{
    background: {C['panel_alt']};
    border: 1px solid {C['line']};
    border-radius: 6px;
    padding: 7px 14px;
    color: {C['text']};
}}
QPushButton:hover  {{ background: #29313F; border-color: #3B475A; }}
QPushButton:pressed{{ background: #202634; }}
QPushButton:disabled {{ color: {C['text_faint']}; background: {C['panel']}; border-color: {C['line_soft']}; }}
QPushButton#Primary {{
    background: {C['amber']};
    border: 1px solid {C['amber']};
    color: #1A1206;
    font-weight: 600;
}}
QPushButton#Primary:hover   {{ background: #EDAE58; border-color: #EDAE58; }}
QPushButton#Primary:pressed {{ background: {C['amber_dk']}; }}
QPushButton#Primary:disabled {{ background: #3A3223; border-color: #3A3223; color: #7A6B4E; }}
QPushButton#Compact {{ padding: 6px 8px; font-size: 12px; }}
QPushButton#Danger:hover {{ background: #3A2422; border-color: {C['error']}; color: #F0B2AE; }}

QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 10px;
    color: {C['text']};
}}
QToolButton:hover  {{ background: {C['panel_alt']}; border-color: {C['line']}; }}
QToolButton:pressed{{ background: #202634; }}
QToolButton:disabled {{ color: {C['text_faint']}; }}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {C['bg']};
    border: 1px solid {C['line']};
    border-radius: 6px;
    padding: 6px 9px;
    selection-background-color: {C['info']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {C['info']}; }}
QLineEdit[invalid="true"] {{ border-color: {C['error']}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    background: transparent; border: none; width: 16px;
}}
QComboBox QAbstractItemView {{
    background: {C['panel']};
    border: 1px solid {C['line']};
    selection-background-color: {C['panel_alt']};
    outline: none;
}}

QTableView {{
    background: {C['panel']};
    alternate-background-color: {C['panel']};
    border: 1px solid {C['line']};
    border-radius: 8px;
    gridline-color: {C['line_soft']};
    selection-background-color: #2A3away;
    outline: none;
}}
QTableView::item {{ border-bottom: 1px solid {C['line_soft']}; padding-left: 4px; }}
QTableView::item:selected {{ background: #2B3purple; }}
QHeaderView::section {{
    background: {C['panel']};
    color: {C['text_dim']};
    border: none;
    border-bottom: 1px solid {C['line']};
    padding: 8px 6px;
    font-size: 12px;
}}
QTableCornerButton::section {{ background: {C['panel']}; border: none; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:vertical {{ height: 8px; }}
QSplitter::handle:horizontal {{ width: 8px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #38425380; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #46536A; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #38425380; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QProgressBar {{
    background: {C['bg']};
    border: 1px solid {C['line']};
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {C['amber']}; border-radius: 5px; }}

QMenu {{ background: {C['panel']}; border: 1px solid {C['line']}; padding: 5px; }}
QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {C['panel_alt']}; }}
QMenu::separator {{ height: 1px; background: {C['line']}; margin: 5px 8px; }}

QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {C['line']};
    border-radius: 4px;
    background: {C['bg']};
}}
QCheckBox::indicator:checked {{ background: {C['info']}; border-color: {C['info']}; }}
QToolTip {{
    background: {C['panel_alt']}; color: {C['text']};
    border: 1px solid {C['line']}; padding: 5px;
}}
"""
# drobna korekta: usuwamy literówki w selektorach kolorów zaznaczenia
STYLESHEET = STYLESHEET.replace("#2A3away", "#2A3446").replace("#2B3purple", "#2A3446")


def ui_font(size: int = 13, weight: int = QFont.Normal) -> QFont:
    f = QFont()
    f.setFamilies(["Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", "Sans Serif"])
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


def mono_font(size: int = 12) -> QFont:
    f = QFont()
    f.setFamilies(["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Monospace"])
    f.setPixelSize(size)
    return f


# --------------------------------------------------------------------------
# Ikony rysowane w kodzie (brak zewnętrznych plików = jeden plik aplikacji)
# --------------------------------------------------------------------------
def _pix(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    return pm


def make_icon(kind: str, color: str = C["text"], size: int = 40) -> QIcon:
    pm = _pix(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = size
    pen = QPen(QColor(color))
    pen.setWidthF(s * 0.075)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    m = s * 0.22          # margines

    if kind == "power":
        r = QRectF(m, m, s - 2 * m, s - 2 * m)
        p.drawArc(r, int(-55 * 16), int(290 * 16))
        p.drawLine(QPointF(s / 2, m - s * 0.06), QPointF(s / 2, s * 0.46))
    elif kind == "monitor":
        p.drawRoundedRect(QRectF(m, m * 1.1, s - 2 * m, (s - 2 * m) * 0.72), s * 0.05, s * 0.05)
        p.drawLine(QPointF(s * 0.38, s - m * 0.9), QPointF(s * 0.62, s - m * 0.9))
        p.drawLine(QPointF(s / 2, m * 1.1 + (s - 2 * m) * 0.72), QPointF(s / 2, s - m * 0.9))
    elif kind == "plus":
        p.drawLine(QPointF(s / 2, m * 0.9), QPointF(s / 2, s - m * 0.9))
        p.drawLine(QPointF(m * 0.9, s / 2), QPointF(s - m * 0.9, s / 2))
    elif kind == "pencil":
        path = QPainterPath()
        path.moveTo(m * 0.9, s - m * 0.9)
        path.lineTo(m * 1.35, s * 0.72)
        path.lineTo(s * 0.72, m * 0.75)
        path.lineTo(s - m * 0.85, m * 1.25)
        path.lineTo(s * 0.78, s * 0.62)
        path.lineTo(m * 1.55, s - m * 1.3)
        path.closeSubpath()
        p.drawPath(path)
    elif kind == "trash":
        p.drawLine(QPointF(m * 0.7, s * 0.3), QPointF(s - m * 0.7, s * 0.3))
        p.drawLine(QPointF(s * 0.4, s * 0.22), QPointF(s * 0.6, s * 0.22))
        path = QPainterPath()
        path.moveTo(s * 0.28, s * 0.34)
        path.lineTo(s * 0.33, s * 0.8)
        path.lineTo(s * 0.67, s * 0.8)
        path.lineTo(s * 0.72, s * 0.34)
        p.drawPath(path)
    elif kind == "refresh":
        r = QRectF(m, m, s - 2 * m, s - 2 * m)
        p.drawArc(r, int(30 * 16), int(280 * 16))
        tri = QPolygonF([
            QPointF(s * 0.76, s * 0.20), QPointF(s * 0.86, s * 0.40), QPointF(s * 0.64, s * 0.38)])
        p.setBrush(QColor(color))
        p.setPen(Qt.NoPen)
        p.drawPolygon(tri)
    elif kind == "gear":
        p.save()
        p.translate(s / 2, s / 2)
        p.setBrush(QColor(color))
        p.setPen(Qt.NoPen)
        for i in range(8):
            p.save()
            p.rotate(i * 45)
            p.drawRoundedRect(QRectF(-s * 0.05, -s * 0.36, s * 0.10, s * 0.16), 2, 2)
            p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)
        p.drawEllipse(QPointF(0, 0), s * 0.20, s * 0.20)
        p.drawEllipse(QPointF(0, 0), s * 0.07, s * 0.07)
        p.restore()
    elif kind in ("import", "export"):
        p.drawLine(QPointF(m * 0.8, s * 0.76), QPointF(s - m * 0.8, s * 0.76))
        if kind == "import":
            p.drawLine(QPointF(s / 2, s * 0.20), QPointF(s / 2, s * 0.60))
            p.drawPolyline(QPolygonF([QPointF(s * 0.36, s * 0.46), QPointF(s / 2, s * 0.61),
                                      QPointF(s * 0.64, s * 0.46)]))
        else:
            p.drawLine(QPointF(s / 2, s * 0.20), QPointF(s / 2, s * 0.60))
            p.drawPolyline(QPolygonF([QPointF(s * 0.36, s * 0.34), QPointF(s / 2, s * 0.19),
                                      QPointF(s * 0.64, s * 0.34)]))
    elif kind == "search":
        p.drawEllipse(QPointF(s * 0.44, s * 0.44), s * 0.20, s * 0.20)
        p.drawLine(QPointF(s * 0.59, s * 0.59), QPointF(s * 0.78, s * 0.78))
    elif kind == "info":
        p.drawEllipse(QPointF(s / 2, s / 2), s * 0.30, s * 0.30)
        p.drawLine(QPointF(s / 2, s * 0.46), QPointF(s / 2, s * 0.68))
        p.drawPoint(QPointF(s / 2, s * 0.34))
    elif kind == "app":
        # logo: sygnał sieciowy + przycisk zasilania w środku
        p.setPen(QPen(QColor(C["amber"]), s * 0.075, Qt.SolidLine, Qt.RoundCap))
        r = QRectF(s * 0.30, s * 0.30, s * 0.40, s * 0.40)
        p.drawArc(r, int(-55 * 16), int(290 * 16))
        p.drawLine(QPointF(s / 2, s * 0.22), QPointF(s / 2, s * 0.47))
        p.setPen(QPen(QColor(C["info"]), s * 0.06, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72), int(200 * 16), int(50 * 16))
        p.drawArc(QRectF(s * 0.14, s * 0.14, s * 0.72, s * 0.72), int(290 * 16), int(50 * 16))
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------
# Model danych
# --------------------------------------------------------------------------
UNKNOWN, ONLINE, OFFLINE, CHECKING = "unknown", "online", "offline", "checking"

STATUS_LABEL = {UNKNOWN: "nieznany", ONLINE: "online", OFFLINE: "offline", CHECKING: "sprawdzanie"}
STATUS_COLOR = {UNKNOWN: C["text_faint"], ONLINE: C["online"], OFFLINE: C["offline"], CHECKING: C["info"]}

MAC_RE = re.compile(r"^[0-9A-Fa-f]{12}$")


def normalize_mac(raw: str) -> str:
    """Przyjmuje AA:BB:CC:DD:EE:FF, AA-BB-..., aabb.ccdd.eeff lub 12 znaków."""
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", raw or "")
    if not MAC_RE.match(cleaned):
        raise ValueError("Adres MAC musi mieć 12 znaków szesnastkowych, np. 1A:2B:3C:4D:5E:6F")
    return cleaned.upper()


def pretty_mac(mac: str) -> str:
    mac = re.sub(r"[^0-9A-Fa-f]", "", mac or "").upper()
    return ":".join(mac[i:i + 2] for i in range(0, len(mac), 2)) if len(mac) == 12 else mac


@dataclass
class Host:
    name: str = ""
    mac: str = ""
    address: str = ""            # nazwa DNS / IP do pingu i pulpitu zdalnego
    wol_target: str = "255.255.255.255"   # broadcast LAN lub publiczny IP (WOL przez WAN)
    wol_port: int = 9
    rdp_port: int = 3389
    group: str = "Ogólne"
    check_mode: str = "auto"     # auto | tcp | ping
    check_port: int = 0          # 0 → użyj rdp_port
    note: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def probe_port(self) -> int:
        return self.check_port or self.rdp_port or 3389

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Host":
        known = {f for f in Host.__dataclass_fields__}
        return Host(**{k: v for k, v in d.items() if k in known})


def config_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "WOLConsole"
    d.mkdir(parents=True, exist_ok=True)
    return d


HOSTS_FILE = config_dir() / "hosts.json"


def load_hosts(path: Path = HOSTS_FILE) -> list[Host]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Host.from_dict(d) for d in data.get("hosts", [])]
    except Exception:
        return []


def save_hosts(hosts: list[Host], path: Path = HOSTS_FILE) -> None:
    payload = {"version": 1, "hosts": [h.to_dict() for h in hosts]}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------
# Sieć: magic packet + sondy dostępności
# --------------------------------------------------------------------------
def send_magic_packet(mac: str, target: str, port: int = 9, repeats: int = 3) -> None:
    """Wysyła Magic Packet. Ponawia kilka razy — pakiety UDP bywają gubione."""
    mac_bytes = bytes.fromhex(normalize_mac(mac))
    packet = b"\xFF" * 6 + mac_bytes * 16
    target = (target or "255.255.255.255").strip()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for _ in range(max(1, repeats)):
            sock.sendto(packet, (target, int(port)))
            time.sleep(0.08)
    finally:
        sock.close()


def tcp_probe(address: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((address, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def icmp_probe(address: str, timeout: float) -> bool:
    if IS_WINDOWS:
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), address]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout))), address]
        flags = 0
    try:
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=timeout + 2, creationflags=flags)
        return r.returncode == 0
    except Exception:
        return False


def probe_host(host: Host, timeout: float = 1.5) -> bool:
    if not host.address:
        return False
    if host.check_mode == "ping":
        return icmp_probe(host.address, timeout)
    if host.check_mode == "tcp":
        return tcp_probe(host.address, host.probe_port, timeout)
    return tcp_probe(host.address, host.probe_port, timeout) or icmp_probe(host.address, timeout)


class ProbeSignals(QObject):
    finished = Signal(str, bool, float)   # host_id, online, czas_odpowiedzi_ms


class ProbeTask(QRunnable):
    """Pojedyncze sprawdzenie hosta wykonywane w puli wątków."""

    def __init__(self, host: Host, timeout: float, signals: "ProbeSignals | None" = None):
        super().__init__()
        self.host = host
        self.timeout = timeout
        # sygnały mogą być współdzielone z obiektem żyjącym dłużej niż zadanie
        self.signals = signals or ProbeSignals()

    @Slot()
    def run(self) -> None:
        t0 = time.perf_counter()
        ok = probe_host(self.host, self.timeout)
        self.signals.finished.emit(self.host.id, ok, (time.perf_counter() - t0) * 1000)


# --------------------------------------------------------------------------
# Model tabeli
# --------------------------------------------------------------------------
COL_STATUS, COL_NAME, COL_GROUP, COL_ADDRESS, COL_MAC, COL_SEEN = range(6)
HEADERS = ["Stan", "Nazwa", "Grupa", "Adres", "MAC", "Ostatnio online"]
StatusRole = Qt.UserRole + 1
HostIdRole = Qt.UserRole + 2
SortRole = Qt.UserRole + 3


class HostTableModel(QAbstractTableModel):
    def __init__(self, hosts: list[Host] | None = None):
        super().__init__()
        self.hosts: list[Host] = hosts or []
        self.status: dict[str, str] = {}
        self.latency: dict[str, float] = {}
        self.last_seen: dict[str, float] = {}

    # --- podstawy modelu ---
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.hosts)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        h = self.hosts[index.row()]
        col = index.column()
        st = self.status.get(h.id, UNKNOWN)

        if role == Qt.DisplayRole:
            if col == COL_STATUS:
                return STATUS_LABEL[st]
            if col == COL_NAME:
                return h.name
            if col == COL_GROUP:
                return h.group
            if col == COL_ADDRESS:
                return h.address
            if col == COL_MAC:
                return pretty_mac(h.mac)
            if col == COL_SEEN:
                ts = self.last_seen.get(h.id)
                if st == ONLINE:
                    lat = self.latency.get(h.id)
                    return f"teraz · {lat:.0f} ms" if lat else "teraz"
                return humanize_since(ts) if ts else "—"
        if role == Qt.FontRole and col in (COL_ADDRESS, COL_MAC):
            return mono_font(12)
        if role == Qt.ForegroundRole and col in (COL_GROUP, COL_ADDRESS, COL_MAC, COL_SEEN):
            return QColor(C["text_dim"])
        if role == StatusRole:
            return st
        if role == HostIdRole:
            return h.id
        if role == SortRole:
            if col == COL_STATUS:
                return {ONLINE: 0, CHECKING: 1, UNKNOWN: 2, OFFLINE: 3}[st]
            if col == COL_SEEN:
                return -(self.last_seen.get(h.id) or 0)
            return self.data(index, Qt.DisplayRole)
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignVCenter | Qt.AlignLeft)
        return None

    # --- operacje na liście ---
    def set_hosts(self, hosts: list[Host]) -> None:
        self.beginResetModel()
        self.hosts = hosts
        self.endResetModel()

    def add_host(self, host: Host) -> None:
        self.beginInsertRows(QModelIndex(), len(self.hosts), len(self.hosts))
        self.hosts.append(host)
        self.endInsertRows()

    def update_host(self, row: int, host: Host) -> None:
        self.hosts[row] = host
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(HEADERS) - 1))

    def remove_host(self, row: int) -> None:
        self.beginRemoveRows(QModelIndex(), row, row)
        h = self.hosts.pop(row)
        self.endRemoveRows()
        self.status.pop(h.id, None)

    def row_of(self, host_id: str) -> int:
        for i, h in enumerate(self.hosts):
            if h.id == host_id:
                return i
        return -1

    def set_status(self, host_id: str, st: str, latency: float | None = None) -> None:
        row = self.row_of(host_id)
        if row < 0:
            return
        self.status[host_id] = st
        if st == ONLINE:
            self.last_seen[host_id] = time.time()
            if latency is not None:
                self.latency[host_id] = latency
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(HEADERS) - 1))

    def counts(self) -> tuple[int, int]:
        online = sum(1 for h in self.hosts if self.status.get(h.id) == ONLINE)
        return online, len(self.hosts)


def humanize_since(ts: float) -> str:
    d = int(time.time() - ts)
    if d < 60:
        return f"{d} s temu"
    if d < 3600:
        return f"{d // 60} min temu"
    if d < 86400:
        return f"{d // 3600} godz. temu"
    return datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")


class HostFilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.setSortRole(SortRole)
        self.text = ""
        self.only_online = False

    def set_text(self, t: str) -> None:
        self.text = t.strip().lower()
        self.invalidateFilter()

    def set_only_online(self, v: bool) -> None:
        self.only_online = v
        self.invalidateFilter()

    def filterAcceptsRow(self, row: int, parent: QModelIndex) -> bool:
        m: HostTableModel = self.sourceModel()
        h = m.hosts[row]
        if self.only_online and m.status.get(h.id) != ONLINE:
            return False
        if not self.text:
            return True
        hay = " ".join([h.name, h.group, h.address, pretty_mac(h.mac), h.note]).lower()
        return self.text in hay


# --------------------------------------------------------------------------
# Delegat rysujący kropkę stanu
# --------------------------------------------------------------------------
class StatusDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        st = index.data(StatusRole) or UNKNOWN
        painter.save()
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#2A3446"))
        painter.setRenderHint(QPainter.Antialiasing, True)
        r: QRect = option.rect
        cy = r.center().y() + 1
        cx = r.left() + 16
        col = QColor(STATUS_COLOR[st])
        if st == ONLINE:
            halo = QColor(col)
            halo.setAlpha(45)
            painter.setBrush(halo)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx, cy), 8.5, 8.5)
        painter.setBrush(col)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 4.0, 4.0)
        painter.setPen(QColor(C["text"] if st == ONLINE else C["text_dim"]))
        painter.setFont(ui_font(12))
        painter.drawText(QRect(r.left() + 28, r.top(), r.width() - 30, r.height()),
                         int(Qt.AlignVCenter | Qt.AlignLeft), STATUS_LABEL[st])
        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        return QSize(110, 34)


# --------------------------------------------------------------------------
# Dialogi
# --------------------------------------------------------------------------
class HostDialog(QDialog):
    """Dodawanie i edycja komputera."""

    def __init__(self, parent=None, host: Host | None = None, groups: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edytuj komputer" if host else "Nowy komputer")
        self.setMinimumWidth(460)
        self.host = host or Host()

        self.name = QLineEdit(self.host.name)
        self.name.setPlaceholderText("np. Stacja robocza — biuro")
        self.mac = QLineEdit(pretty_mac(self.host.mac))
        self.mac.setPlaceholderText("1A:2B:3C:4D:5E:6F")
        self.mac.setFont(mono_font(12))
        self.address = QLineEdit(self.host.address)
        self.address.setPlaceholderText("192.168.1.20 lub pc-biuro.local")
        self.address.setFont(mono_font(12))
        self.wol_target = QLineEdit(self.host.wol_target)
        self.wol_target.setPlaceholderText("255.255.255.255 (LAN) lub publiczny IP")
        self.wol_target.setFont(mono_font(12))
        self.wol_port = QSpinBox(); self.wol_port.setRange(1, 65535); self.wol_port.setValue(self.host.wol_port)
        self.rdp_port = QSpinBox(); self.rdp_port.setRange(1, 65535); self.rdp_port.setValue(self.host.rdp_port)
        self.group = QComboBox(); self.group.setEditable(True)
        self.group.addItems(sorted(set((groups or []) + ["Ogólne"])))
        self.group.setCurrentText(self.host.group or "Ogólne")
        self.check_mode = QComboBox()
        for label, val in [("Automatycznie (port, potem ping)", "auto"),
                           ("Tylko port TCP", "tcp"), ("Tylko ping ICMP", "ping")]:
            self.check_mode.addItem(label, val)
        self.check_mode.setCurrentIndex(max(0, self.check_mode.findData(self.host.check_mode)))
        self.check_port = QSpinBox(); self.check_port.setRange(0, 65535)
        self.check_port.setValue(self.host.check_port)
        self.check_port.setSpecialValueText("jak pulpit zdalny")
        self.note = QLineEdit(self.host.note)
        self.note.setPlaceholderText("Notatka widoczna w panelu szczegółów")

        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.addRow("Nazwa", self.name)
        form.addRow("Adres MAC", self.mac)
        form.addRow("Adres komputera", self.address)
        form.addRow(self._separator())
        form.addRow("Cel pakietu WOL", self.wol_target)
        for sb in (self.wol_port, self.rdp_port, self.check_port):
            sb.setFixedWidth(210)
        form.addRow("Port WOL", self.wol_port)
        form.addRow("Port pulpitu zdalnego", self.rdp_port)
        form.addRow(self._separator())
        form.addRow("Grupa", self.group)
        form.addRow("Sprawdzanie stanu", self.check_mode)
        form.addRow("Port sondy", self.check_port)
        form.addRow("Notatka", self.note)

        self.hint = QLabel("Pakiet magiczny wysyłany jest rozgłoszeniowo w sieci lokalnej. "
                           "Do wybudzania przez internet podaj publiczny adres i port "
                           "przekierowany na router.")
        self.hint.setObjectName("EmptyBody")
        self.hint.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Zapisz")
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Anuluj")
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(14)
        lay.addLayout(form)
        lay.addWidget(self.hint)
        lay.addWidget(buttons)

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background: {C['line_soft']}; max-height: 1px; border: none;")
        return line

    def on_accept(self) -> None:
        if not self.name.text().strip():
            self._mark(self.name, "Nazwa nie może być pusta.")
            return
        try:
            mac = normalize_mac(self.mac.text())
        except ValueError as e:
            self._mark(self.mac, str(e))
            return
        if not self.address.text().strip():
            self._mark(self.address, "Podaj adres IP lub nazwę hosta — bez niego nie sprawdzę stanu.")
            return
        h = self.host
        h.name = self.name.text().strip()
        h.mac = mac
        h.address = self.address.text().strip()
        h.wol_target = self.wol_target.text().strip() or "255.255.255.255"
        h.wol_port = self.wol_port.value()
        h.rdp_port = self.rdp_port.value()
        h.group = self.group.currentText().strip() or "Ogólne"
        h.check_mode = self.check_mode.currentData()
        h.check_port = self.check_port.value()
        h.note = self.note.text().strip()
        self.accept()

    def _mark(self, widget: QLineEdit, msg: str) -> None:
        widget.setProperty("invalid", "true")
        widget.style().unpolish(widget); widget.style().polish(widget)
        widget.setFocus()
        self.hint.setText(msg)
        self.hint.setStyleSheet(f"color: {C['error']};")


class SettingsDialog(QDialog):
    def __init__(self, parent, cfg: QSettings):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Ustawienia")
        self.setMinimumWidth(470)

        self.interval = QSpinBox(); self.interval.setRange(5, 3600); self.interval.setSuffix(" s")
        self.interval.setValue(int(cfg.value("monitor/interval", 20)))
        self.timeout = QSpinBox(); self.timeout.setRange(1, 15); self.timeout.setSuffix(" s")
        self.timeout.setValue(int(cfg.value("monitor/timeout", 2)))
        self.repeats = QSpinBox(); self.repeats.setRange(1, 10)
        self.repeats.setValue(int(cfg.value("wol/repeats", 3)))
        self.boot_wait = QSpinBox(); self.boot_wait.setRange(15, 600); self.boot_wait.setSuffix(" s")
        self.boot_wait.setValue(int(cfg.value("wol/boot_wait", 120)))
        self.auto_rdp = QCheckBox("Zaproponuj pulpit zdalny, gdy komputer się zgłosi")
        self.auto_rdp.setChecked(cfg.value("wol/auto_rdp", True, type=bool))
        self.tray = QCheckBox("Zwijaj do zasobnika systemowego zamiast zamykać")
        self.tray.setChecked(cfg.value("ui/minimize_to_tray", True, type=bool))
        self.notify = QCheckBox("Powiadamiaj o zmianie stanu komputerów")
        self.notify.setChecked(cfg.value("ui/notify", True, type=bool))
        self.rdp_cmd = QLineEdit(cfg.value("rdp/command", "", type=str))
        self.rdp_cmd.setPlaceholderText("puste = mstsc (Windows) / xfreerdp / remmina")
        self.rdp_cmd.setFont(mono_font(12))

        for sb in (self.interval, self.timeout, self.repeats, self.boot_wait):
            sb.setFixedWidth(150)
        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.addRow("Odstęp sprawdzania", self.interval)
        form.addRow("Limit czasu sondy", self.timeout)
        form.addRow("Powtórzenia pakietu WOL", self.repeats)
        form.addRow("Czas oczekiwania na start", self.boot_wait)
        form.addRow(self.auto_rdp)
        form.addRow(self.tray)
        form.addRow(self.notify)
        form.addRow("Klient pulpitu zdalnego", self.rdp_cmd)

        info = QLabel(f"Lista komputerów: {HOSTS_FILE}")
        info.setObjectName("EmptyBody")
        info.setWordWrap(True)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Zapisz")
        bb.button(QDialogButtonBox.Save).setObjectName("Primary")
        bb.button(QDialogButtonBox.Cancel).setText("Anuluj")
        bb.accepted.connect(self.save); bb.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16); lay.setSpacing(14)
        lay.addLayout(form); lay.addWidget(info); lay.addWidget(bb)

    def save(self) -> None:
        c = self.cfg
        c.setValue("monitor/interval", self.interval.value())
        c.setValue("monitor/timeout", self.timeout.value())
        c.setValue("wol/repeats", self.repeats.value())
        c.setValue("wol/boot_wait", self.boot_wait.value())
        c.setValue("wol/auto_rdp", self.auto_rdp.isChecked())
        c.setValue("ui/minimize_to_tray", self.tray.isChecked())
        c.setValue("ui/notify", self.notify.isChecked())
        c.setValue("rdp/command", self.rdp_cmd.text().strip())
        self.accept()


class WakeDialog(QDialog):
    """Okno startu: wysyła pakiet i czeka, aż komputer odpowie."""

    connect_requested = Signal(str)   # host_id

    def __init__(self, parent, host: Host, cfg: QSettings):
        super().__init__(parent)
        self.host = host
        self.cfg = cfg
        self.pool = QThreadPool.globalInstance()
        self.signals = ProbeSignals()
        self.signals.finished.connect(self._probe_result)
        self.total = int(cfg.value("wol/boot_wait", 120))
        self.elapsed = 0
        self.online = False
        self.setWindowTitle(f"Wybudzanie — {host.name}")
        self.setMinimumWidth(430)

        self.title = QLabel(host.name)
        self.title.setObjectName("DetailName")
        self.state = QLabel("Wysyłam pakiet magiczny…")
        self.state.setObjectName("SectionLabel")
        self.bar = QProgressBar(); self.bar.setRange(0, self.total); self.bar.setTextVisible(False)
        self.detail = QLabel("")
        self.detail.setObjectName("FieldKey")
        self.detail.setFont(mono_font(12))

        self.rdp_btn = QPushButton("Połącz pulpitem zdalnym")
        self.rdp_btn.setObjectName("Primary")
        self.rdp_btn.setEnabled(False)
        self.rdp_btn.clicked.connect(self._connect)
        self.close_btn = QPushButton("Zamknij")
        self.close_btn.clicked.connect(self.reject)

        row = QHBoxLayout(); row.addStretch(1)
        row.addWidget(self.close_btn); row.addWidget(self.rdp_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18); lay.setSpacing(10)
        lay.addWidget(self.title); lay.addWidget(self.state)
        lay.addWidget(self.bar); lay.addWidget(self.detail)
        lay.addSpacing(6); lay.addLayout(row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        QTimer.singleShot(0, self._send)

    def _send(self) -> None:
        if self.online:      # host odpowiedział, zanim pakiet poszedł w świat
            return
        try:
            send_magic_packet(self.host.mac, self.host.wol_target, self.host.wol_port,
                              int(self.cfg.value("wol/repeats", 3)))
            self.state.setText("Pakiet wysłany. Czekam, aż komputer się zgłosi…")
            self.detail.setText(f"{pretty_mac(self.host.mac)} → {self.host.wol_target}:{self.host.wol_port}")
        except Exception as e:
            self.timer.stop()
            self.state.setText(f"Nie udało się wysłać pakietu: {e}")
            self.state.setStyleSheet(f"color: {C['error']};")

    def _tick(self) -> None:
        self.elapsed += 1
        self.bar.setValue(min(self.elapsed, self.total))
        if self.elapsed % 3 == 0 and not self.online:
            self.pool.start(ProbeTask(self.host, float(self.cfg.value("monitor/timeout", 2)),
                                      self.signals))
        if self.elapsed >= self.total and not self.online:
            self.timer.stop()
            self.state.setText("Komputer nadal nie odpowiada. Sprawdź, czy WOL jest włączony w BIOS-ie "
                               "i karcie sieciowej.")
            self.rdp_btn.setEnabled(True)
            self.rdp_btn.setText("Spróbuj mimo to")

    @Slot(str, bool, float)
    def _probe_result(self, host_id: str, ok: bool, ms: float) -> None:
        if not ok or self.online:
            return
        self.online = True
        self.timer.stop()
        self.bar.setValue(self.total)
        self.state.setText(f"Komputer jest online po {self.elapsed} s.")
        self.state.setStyleSheet(f"color: {C['online']};")
        self.detail.setText(f"{self.host.address}:{self.host.probe_port} · {ms:.0f} ms")
        self.rdp_btn.setEnabled(True)
        if self.cfg.value("wol/auto_rdp", True, type=bool):
            self.rdp_btn.setDefault(True)
            self.rdp_btn.setFocus()

    def _connect(self) -> None:
        self.connect_requested.emit(self.host.id)
        self.accept()


class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("O programie")
        self.setFixedWidth(400)
        logo = QLabel()
        logo.setPixmap(make_icon("app", size=64).pixmap(64, 64))
        title = QLabel(f"{APP_NAME} {APP_VERSION}")
        title.setObjectName("DetailName")
        body = QLabel(
            "Wybudzanie komputerów przez Wake-on-LAN, podgląd dostępności "
            "i szybkie łączenie pulpitem zdalnym.\n\n"
            "Autor: Marcin Tomaszewski\n"
            "tomaszewsky.marcin@gmail.com\n"
            "github.com/martom93"
        )
        body.setObjectName("EmptyBody")
        body.setWordWrap(True)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("Zamknij")
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)

        head = QHBoxLayout(); head.addWidget(logo); head.addSpacing(12)
        col = QVBoxLayout(); col.addWidget(title); col.addStretch(1)
        head.addLayout(col); head.addStretch(1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 16); lay.setSpacing(12)
        lay.addLayout(head); lay.addWidget(body); lay.addWidget(bb)


# --------------------------------------------------------------------------
# Panel szczegółów
# --------------------------------------------------------------------------
class DetailPanel(QFrame):
    wake = Signal(); rdp = Signal(); check = Signal(); edit = Signal(); remove = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setFixedWidth(292)

        self.name = QLabel("—"); self.name.setObjectName("DetailName"); self.name.setWordWrap(True)
        self.badge = QLabel("nieznany")
        self.badge.setFixedHeight(22)
        self._set_badge(UNKNOWN)

        self.fields: dict[str, QLabel] = {}
        grid = QGridLayout(); grid.setVerticalSpacing(7); grid.setHorizontalSpacing(10)
        for r, key in enumerate(["Adres", "MAC", "Cel WOL", "Port WOL", "Pulpit zdalny",
                                 "Grupa", "Ostatnio online"]):
            k = QLabel(key); k.setObjectName("FieldKey")
            v = QLabel("—"); v.setObjectName("FieldValue"); v.setFont(mono_font(12))
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(k, r, 0, Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(v, r, 1, Qt.AlignRight | Qt.AlignVCenter)
            self.fields[key] = v
        grid.setColumnStretch(1, 1)

        self.note = QLabel(""); self.note.setObjectName("EmptyBody"); self.note.setWordWrap(True)

        self.btn_wake = QPushButton("  Wybudź komputer")
        self.btn_wake.setObjectName("Primary")
        self.btn_wake.setIcon(make_icon("power", "#1A1206"))
        self.btn_wake.setIconSize(QSize(16, 16))
        self.btn_wake.clicked.connect(self.wake)
        self.btn_rdp = QPushButton("  Pulpit zdalny")
        self.btn_rdp.setIcon(make_icon("monitor")); self.btn_rdp.setIconSize(QSize(16, 16))
        self.btn_rdp.clicked.connect(self.rdp)
        self.btn_check = QPushButton("Sprawdź"); self.btn_check.setObjectName("Compact")
        self.btn_check.setToolTip("Sprawdź stan teraz")
        self.btn_check.clicked.connect(self.check)
        self.btn_edit = QPushButton("Edytuj"); self.btn_edit.setObjectName("Compact")
        self.btn_edit.clicked.connect(self.edit)
        self.btn_del = QPushButton("Usuń"); self.btn_del.setObjectName("Danger")
        self.btn_del.setProperty("class", "compact")
        self.btn_del.setStyleSheet("padding: 6px 8px; font-size: 12px;")
        self.btn_del.clicked.connect(self.remove)

        row1 = QHBoxLayout(); row1.setSpacing(8)
        row1.addWidget(self.btn_check); row1.addWidget(self.btn_edit); row1.addWidget(self.btn_del)

        head = QHBoxLayout(); head.addWidget(self.name, 1); head.addWidget(self.badge, 0, Qt.AlignTop)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 15, 16, 15); lay.setSpacing(12)
        lay.addLayout(head)
        lay.addLayout(grid)
        lay.addWidget(self.note)
        lay.addStretch(1)
        lay.addWidget(self.btn_wake)
        lay.addWidget(self.btn_rdp)
        lay.addLayout(row1)
        self.set_host(None, UNKNOWN, None, None)

    def _set_badge(self, st: str) -> None:
        col = STATUS_COLOR[st]
        self.badge.setText(f"  {STATUS_LABEL[st]}  ")
        self.badge.setStyleSheet(
            f"color: {col}; border: 1px solid {col}55; background: {col}1A;"
            f"border-radius: 11px; font-size: 12px; padding: 0 4px;")

    def set_host(self, host: Optional[Host], st: str, last_seen: float | None, latency: float | None):
        enabled = host is not None
        for b in (self.btn_wake, self.btn_rdp, self.btn_check, self.btn_edit, self.btn_del):
            b.setEnabled(enabled)
        self.badge.setVisible(host is not None)
        if not host:
            self.name.setText("Nie wybrano komputera")
            for v in self.fields.values():
                v.setText("—")
            self.note.setText("Wybierz pozycję z listy, aby zobaczyć szczegóły i akcje.")
            return
        self.name.setText(host.name)
        self._set_badge(st)
        self.fields["Adres"].setText(host.address or "—")
        self.fields["MAC"].setText(pretty_mac(host.mac))
        self.fields["Cel WOL"].setText(host.wol_target)
        self.fields["Port WOL"].setText(str(host.wol_port))
        self.fields["Pulpit zdalny"].setText(f"{host.address}:{host.rdp_port}")
        self.fields["Grupa"].setText(host.group)
        if st == ONLINE:
            self.fields["Ostatnio online"].setText(f"teraz · {latency:.0f} ms" if latency else "teraz")
        else:
            self.fields["Ostatnio online"].setText(humanize_since(last_seen) if last_seen else "—")
        self.note.setText(host.note)
        self.btn_rdp.setEnabled(st == ONLINE)
        self.btn_rdp.setToolTip("" if st == ONLINE else "Komputer nie odpowiada — najpierw go wybudź.")


# --------------------------------------------------------------------------
# Okno główne
# --------------------------------------------------------------------------
class MainWindow(QWidget):
    def __init__(self, demo: bool = False):
        super().__init__()
        self.cfg = QSettings(ORG_NAME, APP_NAME)
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(16)
        self.probe_signals = ProbeSignals()
        self.probe_signals.finished.connect(self._probe_done)
        self.model = HostTableModel(demo_hosts() if demo else load_hosts())
        self.proxy = HostFilterProxy()
        self.proxy.setSourceModel(self.model)
        self._quitting = False

        self.setWindowTitle(f"{APP_NAME} — wybudzanie i podgląd komputerów")
        self.setWindowIcon(make_icon("app", size=64))
        self.resize(1080, 660)
        self.setMinimumSize(880, 520)

        self._build_ui()
        self._build_tray()
        self._connect_actions()

        self.monitor = QTimer(self)
        self.monitor.timeout.connect(self.check_all)
        self.monitor.start(int(self.cfg.value("monitor/interval", 20)) * 1000)
        QTimer.singleShot(400, self.check_all)
        self._refresh_footer()

    # ---------------- budowa interfejsu ----------------
    def _build_ui(self) -> None:
        header = QFrame(); header.setObjectName("Header"); header.setFixedHeight(62)
        logo = QLabel(); logo.setPixmap(make_icon("app", size=30).pixmap(30, 30))
        title = QLabel(APP_NAME); title.setObjectName("AppTitle")
        subtitle = QLabel("wybudzanie przez sieć i podgląd dostępności")
        subtitle.setObjectName("AppSubtitle")
        tcol = QVBoxLayout(); tcol.setSpacing(0); tcol.addWidget(title); tcol.addWidget(subtitle)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Szukaj po nazwie, adresie, grupie…   (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(290)
        self.search.addAction(make_icon("search", C["text_faint"]), QLineEdit.LeadingPosition)

        self.only_online = QCheckBox("Tylko online")

        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 0, 18, 0); hl.setSpacing(12)
        hl.addWidget(logo); hl.addLayout(tcol); hl.addStretch(1)
        hl.addWidget(self.only_online); hl.addWidget(self.search)

        # pasek narzędzi
        bar = QHBoxLayout(); bar.setSpacing(4)
        self.tb_add = self._tool("Dodaj komputer", "plus", "Ctrl+N")
        self.tb_wake = self._tool("Wybudź", "power", "Ctrl+W", accent=True)
        self.tb_rdp = self._tool("Pulpit zdalny", "monitor", "Ctrl+R")
        self.tb_check = self._tool("Sprawdź wszystkie", "refresh", "F5")
        self.tb_import = self._tool("Importuj", "import")
        self.tb_export = self._tool("Eksportuj", "export")
        self.tb_settings = self._tool("Ustawienia", "gear")
        self.tb_about = self._tool("O programie", "info")
        for b in (self.tb_add, self.tb_wake, self.tb_rdp, self.tb_check):
            bar.addWidget(b)
        bar.addStretch(1)
        for b in (self.tb_import, self.tb_export, self.tb_settings, self.tb_about):
            bar.addWidget(b)

        # tabela
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(COL_STATUS, StatusDelegate(self.table))
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(COL_STATUS, Qt.AscendingOrder)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.setFont(ui_font(13))
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(COL_STATUS, QHeaderView.Fixed)
        hh.resizeSection(COL_STATUS, 118)
        hh.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        hh.setSectionResizeMode(COL_GROUP, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_ADDRESS, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_MAC, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_SEEN, QHeaderView.ResizeToContents)

        self.empty = QLabel(self.table)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setObjectName("EmptyTitle")
        self.empty.setText("Lista jest pusta.\n\nDodaj pierwszy komputer, aby wybudzać go zdalnie.")
        self.empty.hide()

        self.detail = DetailPanel()

        center = QHBoxLayout(); center.setSpacing(12)
        center.addWidget(self.table, 1)
        center.addWidget(self.detail, 0)
        center_w = QWidget(); center_w.setLayout(center)

        # log zdarzeń
        log_wrap = QFrame(); log_wrap.setObjectName("Panel")
        log_head = QLabel("Dziennik zdarzeń"); log_head.setObjectName("SectionLabel")
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setFont(mono_font(12))
        self.log.setFrameShape(QFrame.NoFrame)
        self.log.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log.setMaximumBlockCount(500)
        self.log.setStyleSheet(f"background: transparent; border: none; color: {C['text_dim']};")
        ll = QVBoxLayout(log_wrap); ll.setContentsMargins(14, 10, 12, 10); ll.setSpacing(6)
        ll.addWidget(log_head); ll.addWidget(self.log)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(center_w); splitter.addWidget(log_wrap)
        splitter.setStretchFactor(0, 4); splitter.setStretchFactor(1, 1)
        splitter.setSizes([440, 150])
        splitter.setHandleWidth(8)

        # stopka
        self.footer = QLabel("")
        self.footer.setObjectName("EmptyBody")
        self.scan_bar = QProgressBar(); self.scan_bar.setFixedWidth(130)
        self.scan_bar.setRange(0, 0); self.scan_bar.hide()
        foot = QHBoxLayout(); foot.addWidget(self.footer); foot.addStretch(1); foot.addWidget(self.scan_bar)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(header)
        body = QVBoxLayout(); body.setContentsMargins(16, 12, 16, 12); body.setSpacing(12)
        body.addLayout(bar); body.addWidget(splitter, 1); body.addLayout(foot)
        root.addLayout(body)

        self._update_empty()

    def _tool(self, text: str, icon: str, shortcut: str = "", accent: bool = False) -> QToolButton:
        b = QToolButton()
        b.setText("  " + text)
        b.setIcon(make_icon(icon, C["amber"] if accent else C["text"]))
        b.setIconSize(QSize(17, 17))
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setCursor(Qt.PointingHandCursor)
        fm = b.fontMetrics()
        b.setMinimumWidth(fm.horizontalAdvance(b.text()) + 44)
        if shortcut:
            act = QAction(self)
            act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(b.click)
            self.addAction(act)
            b.setToolTip(f"{text} ({shortcut})")
        return b

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(make_icon("app", size=64), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        a_show = menu.addAction("Pokaż okno")
        a_check = menu.addAction("Sprawdź wszystkie")
        menu.addSeparator()
        a_quit = menu.addAction("Zakończ")
        a_show.triggered.connect(self._restore)
        a_check.triggered.connect(self.check_all)
        a_quit.triggered.connect(self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self._restore() if r == QSystemTrayIcon.Trigger else None)
        try:
            self.tray.show()
        except Exception:
            pass

    def _connect_actions(self) -> None:
        self.tb_add.clicked.connect(self.add_host)
        self.tb_wake.clicked.connect(self.wake_selected)
        self.tb_rdp.clicked.connect(self.rdp_selected)
        self.tb_check.clicked.connect(self.check_all)
        self.tb_import.clicked.connect(self.import_hosts)
        self.tb_export.clicked.connect(self.export_hosts)
        self.tb_settings.clicked.connect(self.open_settings)
        self.tb_about.clicked.connect(lambda: AboutDialog(self).exec())

        self.search.textChanged.connect(self.proxy.set_text)
        self.only_online.toggled.connect(self.proxy.set_only_online)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(lambda _: self.rdp_selected())
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.model.dataChanged.connect(lambda *_: (self._selection_changed(), self._refresh_footer()))
        self.model.modelReset.connect(self._update_empty)
        self.model.rowsInserted.connect(self._update_empty)
        self.model.rowsRemoved.connect(self._update_empty)

        self.detail.wake.connect(self.wake_selected)
        self.detail.rdp.connect(self.rdp_selected)
        self.detail.check.connect(self.check_selected)
        self.detail.edit.connect(self.edit_selected)
        self.detail.remove.connect(self.delete_selected)

        act_find = QAction(self); act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(self.search.setFocus); self.addAction(act_find)
        act_del = QAction(self); act_del.setShortcut(QKeySequence.Delete)
        act_del.triggered.connect(self.delete_selected); self.addAction(act_del)

    # ---------------- pomocnicze ----------------
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.empty.setGeometry(0, 0, self.table.width(), self.table.height())

    def _update_empty(self) -> None:
        self.empty.setVisible(self.model.rowCount() == 0)
        self.empty.setGeometry(0, 0, self.table.width(), self.table.height())
        self._refresh_footer()

    def selected_host(self) -> Optional[Host]:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        row = self.proxy.mapToSource(idx).row()
        return self.model.hosts[row] if 0 <= row < len(self.model.hosts) else None

    def _selection_changed(self, *_):
        h = self.selected_host()
        if h:
            self.detail.set_host(h, self.model.status.get(h.id, UNKNOWN),
                                 self.model.last_seen.get(h.id), self.model.latency.get(h.id))
        else:
            self.detail.set_host(None, UNKNOWN, None, None)
        online = h is not None and self.model.status.get(h.id) == ONLINE
        self.tb_rdp.setEnabled(online)
        self.tb_wake.setEnabled(h is not None)

    def _refresh_footer(self) -> None:
        online, total = self.model.counts()
        interval = int(self.cfg.value("monitor/interval", 20))
        self.footer.setText(f"{online} z {total} komputerów online · sprawdzanie co {interval} s")

    def log_line(self, msg: str, kind: str = "info") -> None:
        color = {"info": C["text_dim"], "ok": C["online"], "warn": C["amber"], "err": C["error"]}[kind]
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.appendHtml(
            f'<span style="color:{C["text_faint"]}">{ts}</span>&nbsp;&nbsp;'
            f'<span style="color:{color}">{msg}</span>')

    # ---------------- akcje ----------------
    def add_host(self) -> None:
        dlg = HostDialog(self, None, self._groups())
        if dlg.exec() == QDialog.Accepted:
            self.model.add_host(dlg.host)
            self._persist()
            self.log_line(f"Dodano komputer {dlg.host.name}.", "ok")
            self.check_one(dlg.host)

    def edit_selected(self) -> None:
        h = self.selected_host()
        if not h:
            return
        dlg = HostDialog(self, h, self._groups())
        if dlg.exec() == QDialog.Accepted:
            self.model.update_host(self.model.row_of(h.id), dlg.host)
            self._persist()
            self.log_line(f"Zaktualizowano {dlg.host.name}.", "ok")

    def delete_selected(self) -> None:
        h = self.selected_host()
        if not h:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Usunąć komputer?")
        box.setText(f"Usunąć „{h.name}” z listy?")
        box.setInformativeText("Ta pozycja zniknie z listy. Samego komputera to nie dotyczy.")
        yes = box.addButton("Usuń", QMessageBox.DestructiveRole)
        box.addButton("Anuluj", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            self.model.remove_host(self.model.row_of(h.id))
            self._persist()
            self.log_line(f"Usunięto {h.name}.", "warn")

    def wake_selected(self) -> None:
        h = self.selected_host()
        if not h:
            QMessageBox.information(self, "Wybierz komputer", "Zaznacz komputer na liście.")
            return
        self.log_line(f"Wysyłam pakiet magiczny do {h.name} ({pretty_mac(h.mac)}).")
        dlg = WakeDialog(self, h, self.cfg)
        dlg.connect_requested.connect(lambda hid: self.open_rdp(h))
        dlg.exec()
        self.check_one(h)

    def rdp_selected(self) -> None:
        h = self.selected_host()
        if h:
            self.open_rdp(h)

    def open_rdp(self, host: Host) -> None:
        custom = self.cfg.value("rdp/command", "", type=str)
        target = f"{host.address}:{host.rdp_port}"
        try:
            if custom:
                subprocess.Popen(custom.replace("{host}", host.address)
                                 .replace("{port}", str(host.rdp_port))
                                 .replace("{target}", target), shell=True)
            elif IS_WINDOWS:
                path = Path(os.environ.get("TEMP", ".")) / f"wol_{host.id}.rdp"
                path.write_text(
                    f"full address:s:{target}\n"
                    "screen mode id:i:2\n"
                    "authentication level:i:2\n"
                    "redirectclipboard:i:1\n", encoding="utf-8")
                subprocess.Popen(["mstsc", str(path)])
                QTimer.singleShot(15000, lambda: path.unlink(missing_ok=True))
            else:
                for candidate in (["xfreerdp", f"/v:{target}"], ["remmina", "-c", f"rdp://{target}"]):
                    try:
                        subprocess.Popen(candidate)
                        break
                    except FileNotFoundError:
                        continue
                else:
                    raise FileNotFoundError("Nie znaleziono klienta RDP (xfreerdp / remmina).")
            self.log_line(f"Otwieram pulpit zdalny: {target}.", "ok")
        except Exception as e:
            self.log_line(f"Pulpit zdalny nieudany: {e}", "err")
            QMessageBox.warning(self, "Nie udało się otworzyć pulpitu zdalnego",
                                f"{e}\n\nMożesz wskazać własnego klienta w Ustawieniach.")

    # ---------------- monitoring ----------------
    def check_all(self) -> None:
        if not self.model.hosts:
            return
        self.scan_bar.show()
        self._pending = len(self.model.hosts)
        for h in self.model.hosts:
            self.check_one(h, silent=True)

    def check_selected(self) -> None:
        h = self.selected_host()
        if h:
            self.check_one(h)

    def check_one(self, host: Host, silent: bool = False) -> None:
        self.pool.start(ProbeTask(host, float(self.cfg.value("monitor/timeout", 2)),
                                  self.probe_signals))

    @Slot(str, bool, float)
    def _probe_done(self, host_id: str, ok: bool, ms: float) -> None:
        prev = self.model.status.get(host_id, UNKNOWN)
        new = ONLINE if ok else OFFLINE
        self.model.set_status(host_id, new, ms if ok else None)
        row = self.model.row_of(host_id)
        if row >= 0 and prev != new and prev != UNKNOWN:
            name = self.model.hosts[row].name
            if new == ONLINE:
                self.log_line(f"{name} jest online ({ms:.0f} ms).", "ok")
            else:
                self.log_line(f"{name} przestał odpowiadać.", "warn")
            if self.cfg.value("ui/notify", True, type=bool) and self.tray.isVisible():
                self.tray.showMessage(APP_NAME, f"{name}: {STATUS_LABEL[new]}",
                                      QSystemTrayIcon.Information, 4000)
        self._pending = max(0, getattr(self, "_pending", 1) - 1)
        if self._pending == 0:
            self.scan_bar.hide()
        self._refresh_footer()
        self._selection_changed()

    # ---------------- dane ----------------
    def _groups(self) -> list[str]:
        return sorted({h.group for h in self.model.hosts if h.group})

    def _persist(self) -> None:
        try:
            save_hosts(self.model.hosts)
        except Exception as e:
            self.log_line(f"Nie udało się zapisać listy: {e}", "err")

    def import_hosts(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importuj listę komputerów", "", "JSON (*.json)")
        if not path:
            return
        new = load_hosts(Path(path))
        if not new:
            QMessageBox.warning(self, "Pusty plik", "W tym pliku nie ma komputerów do zaimportowania.")
            return
        existing = {h.mac for h in self.model.hosts}
        added = 0
        for h in new:
            if h.mac not in existing:
                h.id = uuid.uuid4().hex[:12]
                self.model.add_host(h)
                added += 1
        self._persist()
        self.log_line(f"Zaimportowano {added} z {len(new)} pozycji.", "ok")
        self.check_all()

    def export_hosts(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Eksportuj listę komputerów",
                                              "komputery.json", "JSON (*.json)")
        if path:
            save_hosts(self.model.hosts, Path(path))
            self.log_line(f"Wyeksportowano listę do {path}.", "ok")

    def open_settings(self) -> None:
        dlg = SettingsDialog(self, self.cfg)
        if dlg.exec() == QDialog.Accepted:
            self.monitor.setInterval(int(self.cfg.value("monitor/interval", 20)) * 1000)
            self._refresh_footer()
            self.log_line("Zapisano ustawienia.", "ok")

    def _context_menu(self, pos) -> None:
        h = self.selected_host()
        if not h:
            return
        m = QMenu(self)
        a_wake = m.addAction("Wybudź komputer")
        a_rdp = m.addAction("Pulpit zdalny")
        a_check = m.addAction("Sprawdź teraz")
        m.addSeparator()
        a_mac = m.addAction("Kopiuj adres MAC")
        a_addr = m.addAction("Kopiuj adres")
        m.addSeparator()
        a_edit = m.addAction("Edytuj")
        a_del = m.addAction("Usuń")
        chosen = m.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is a_wake:
            self.wake_selected()
        elif chosen is a_rdp:
            self.open_rdp(h)
        elif chosen is a_check:
            self.check_one(h)
        elif chosen is a_mac:
            QApplication.clipboard().setText(pretty_mac(h.mac))
        elif chosen is a_addr:
            QApplication.clipboard().setText(h.address)
        elif chosen is a_edit:
            self.edit_selected()
        elif chosen is a_del:
            self.delete_selected()

    # ---------------- okno / tray ----------------
    def _restore(self) -> None:
        self.showNormal(); self.raise_(); self.activateWindow()

    def _quit(self) -> None:
        self._quitting = True
        self.close()
        QApplication.quit()

    def closeEvent(self, e):
        if (not self._quitting and self.cfg.value("ui/minimize_to_tray", True, type=bool)
                and self.tray.isVisible()):
            e.ignore()
            self.hide()
            self.tray.showMessage(APP_NAME, "Program działa dalej w zasobniku systemowym.",
                                  QSystemTrayIcon.Information, 3000)
            return
        self._persist()
        self.monitor.stop()
        self.pool.waitForDone(3000)
        e.accept()


def demo_hosts() -> list[Host]:
    return [
        Host(name="Serwerownia — NAS", mac="1A2B3C4D5E6F", address="192.168.1.10",
             wol_target="192.168.1.255", group="Serwery", note="Kopie zapasowe co noc o 2:00.",
             rdp_port=3389),
        Host(name="Stacja robocza — biuro", mac="A0B1C2D3E4F5", address="192.168.1.21",
             wol_target="192.168.1.255", group="Biuro", note="Główny komputer projektowy."),
        Host(name="Laptop księgowość", mac="0C1D2E3F4A5B", address="192.168.1.34",
             wol_target="192.168.1.255", group="Biuro"),
        Host(name="Komputer w warsztacie", mac="F0E1D2C3B4A5", address="192.168.1.42",
             wol_target="192.168.1.255", group="Warsztat", check_mode="ping"),
        Host(name="Dom — pecet", mac="9A8B7C6D5E4F", address="dom.example.net",
             wol_target="203.0.113.55", wol_port=9999, rdp_port=3390, group="Zdalne",
             note="Wybudzanie przez internet — przekierowanie portu na routerze."),
    ]


def main() -> int:
    QApplication.setAttribute(Qt.AA_DontShowIconsInMenus, False)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")
    app.setFont(ui_font(13))
    app.setStyleSheet(STYLESHEET)
    app.setQuitOnLastWindowClosed(False)
    w = MainWindow(demo="--demo" in sys.argv)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
