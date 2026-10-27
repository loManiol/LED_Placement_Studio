"""
View / Editor page – canvas + tools after generation.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.engine import PAPER_SIZES_MM
from ui.canvas import LEDCanvas


class ViewPage(QWidget):
    back_clicked = pyqtSignal()
    simulate_clicked = pyqtSignal()
    stop_simulate_clicked = pyqtSignal()
    export_clicked = pyqtSignal()
    auto_tile_clicked = pyqtSignal()
    add_tile_clicked = pyqtSignal()
    clear_tiles_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ---- Top bar ----
        top = QHBoxLayout()
        top.setSpacing(10)

        self.btn_back = QPushButton("←  Setup")
        self.btn_back.setObjectName("ghostBtn")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.back_clicked.emit)
        top.addWidget(self.btn_back)

        top.addSpacing(8)

        # Live metrics (big & friendly)
        self.lbl_leds = QLabel("0")
        self.lbl_leds.setObjectName("metricBig")
        self.lbl_leds_cap = QLabel("LEDs")
        self.lbl_leds_cap.setObjectName("metricCap")

        self.lbl_pitch = QLabel("—")
        self.lbl_pitch.setObjectName("metricBig")
        self.lbl_pitch_cap = QLabel("Pitch mm")
        self.lbl_pitch_cap.setObjectName("metricCap")

        self.lbl_size = QLabel("—")
        self.lbl_size.setObjectName("metricBig")
        self.lbl_size_cap = QLabel("Size mm")
        self.lbl_size_cap.setObjectName("metricCap")

        for big, cap in (
            (self.lbl_leds, self.lbl_leds_cap),
            (self.lbl_pitch, self.lbl_pitch_cap),
            (self.lbl_size, self.lbl_size_cap),
        ):
            box = QVBoxLayout()
            box.setSpacing(0)
            box.addWidget(big, alignment=Qt.AlignmentFlag.AlignCenter)
            box.addWidget(cap, alignment=Qt.AlignmentFlag.AlignCenter)
            wrap = QFrame()
            wrap.setObjectName("metricCard")
            wrap.setLayout(box)
            wrap.setMinimumWidth(110)
            top.addWidget(wrap)

        top.addStretch()

        # Simulate
        self.btn_simulate = QPushButton("▶  Simulate")
        self.btn_simulate.setObjectName("simulateBtn")
        self.btn_simulate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_simulate.clicked.connect(self.simulate_clicked.emit)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.clicked.connect(self.stop_simulate_clicked.emit)

        top.addWidget(self.btn_simulate)
        top.addWidget(self.btn_stop)

        self.btn_export = QPushButton("Export all")
        self.btn_export.setObjectName("exportBtn")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self.export_clicked.emit)
        top.addWidget(self.btn_export)

        root.addLayout(top)

        # ---- Body: canvas + right tool strip ----
        body = QHBoxLayout()
        body.setSpacing(10)

        self.canvas = LEDCanvas()
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body.addWidget(self.canvas, 1)

        # Right tool strip (tiling + edit tips)
        tools = QFrame()
        tools.setObjectName("card")
        tools.setFixedWidth(200)
        tl = QVBoxLayout(tools)
        tl.setContentsMargins(14, 14, 14, 14)
        tl.setSpacing(10)

        tl.addWidget(self._label("Edit LEDs"))
        tip = QLabel(
            "• Drag a pad to move\n"
            "• Double-click to add\n"
            "• Delete key to remove\n"
            "• Right-click for menu\n"
            "• Ctrl+Z / Ctrl+Y undo"
        )
        tip.setObjectName("hintLabel")
        tip.setWordWrap(True)
        tl.addWidget(tip)

        tl.addSpacing(6)
        tl.addWidget(self._label("Tiling"))

        self.paper_combo = QComboBox()
        self.paper_combo.addItems(list(PAPER_SIZES_MM.keys()))
        self.paper_combo.setCurrentText("A4")
        tl.addWidget(QLabel("Paper"))
        tl.addWidget(self.paper_combo)

        self.orient_combo = QComboBox()
        self.orient_combo.addItems(["portrait", "landscape"])
        tl.addWidget(QLabel("Orientation"))
        tl.addWidget(self.orient_combo)

        self.overlap_spin = QDoubleSpinBox()
        self.overlap_spin.setRange(0, 80)
        self.overlap_spin.setValue(20)
        self.overlap_spin.setSuffix(" mm")
        tl.addWidget(QLabel("Overlap"))
        tl.addWidget(self.overlap_spin)

        self.smart_tile_check = QCheckBox("Smart (skip empty)")
        self.smart_tile_check.setChecked(True)
        tl.addWidget(self.smart_tile_check)

        self.btn_auto_tile = QPushButton("Auto tile")
        self.btn_auto_tile.clicked.connect(self.auto_tile_clicked.emit)
        tl.addWidget(self.btn_auto_tile)

        self.btn_add_tile = QPushButton("Add tile")
        self.btn_add_tile.clicked.connect(self.add_tile_clicked.emit)
        tl.addWidget(self.btn_add_tile)

        self.btn_clear_tiles = QPushButton("Clear tiles")
        self.btn_clear_tiles.clicked.connect(self.clear_tiles_clicked.emit)
        tl.addWidget(self.btn_clear_tiles)

        tl.addStretch()
        body.addWidget(tools)

        root.addLayout(body, 1)

        # ---- Bottom status line ----
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setObjectName("hintLabel")
        root.addWidget(self.lbl_status)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    # ---- public helpers used by MainWindow ----
    def set_metrics(self, leds: int, pitch: float, w_mm: float, h_mm: float, target: int | None = None):
        if target:
            self.lbl_leds.setText(f"{leds} / {target}")
        else:
            self.lbl_leds.setText(str(leds))
        self.lbl_pitch.setText(f"{pitch:.2f}")
        self.lbl_size.setText(f"{w_mm:.0f}×{h_mm:.0f}")

    def set_led_count(self, n: int, target: int | None = None):
        if target:
            self.lbl_leds.setText(f"{n} / {target}")
        else:
            self.lbl_leds.setText(str(n))

    def set_simulating(self, on: bool):
        self.btn_simulate.setEnabled(not on)
        self.btn_stop.setEnabled(on)

    def get_paper(self) -> str:
        return self.paper_combo.currentText()

    def get_orientation(self) -> str:
        return self.orient_combo.currentText()

    def get_overlap(self) -> float:
        return self.overlap_spin.value()

    def get_smart_tiling(self) -> bool:
        return self.smart_tile_check.isChecked()

    def show_status(self, msg: str):
        self.lbl_status.setText(msg)
