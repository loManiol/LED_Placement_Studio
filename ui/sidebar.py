"""
Left-hand control panel for LED Placement Studio.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.engine import PAPER_SIZES_MM


class Sidebar(QWidget):
    """All user inputs live here."""

    generate_clicked = pyqtSignal()
    export_clicked = pyqtSignal()
    auto_tile_clicked = pyqtSignal()
    add_tile_clicked = pyqtSignal()
    clear_tiles_clicked = pyqtSignal()
    simulate_clicked = pyqtSignal()
    stop_simulate_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(380)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # ---- Text & Font ----
        g_text = QGroupBox("Text & Font")
        fl = QFormLayout(g_text)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Enter text… (Farsi / English / …)")
        self.text_edit.setMaximumHeight(80)
        self.text_edit.setPlainText("ظروف چوبی")
        fl.addRow(self.text_edit)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["RTL (Farsi / Arabic)", "LTR (English / Latin)"])
        fl.addRow("Direction", self.lang_combo)

        self.font_combo = QComboBox()
        self._populate_fonts()
        fl.addRow("System Font", self.font_combo)

        self.font_path_edit = QLineEdit()
        self.font_path_edit.setPlaceholderText("Or browse a .ttf / .otf file…")
        btn_browse_font = QPushButton("Browse…")
        btn_browse_font.clicked.connect(self._browse_font)
        font_row = QHBoxLayout()
        font_row.addWidget(self.font_path_edit)
        font_row.addWidget(btn_browse_font)
        fl.addRow("Custom Font", font_row)

        layout.addWidget(g_text)

        # ---- Physical Size ----
        g_size = QGroupBox("Physical Size (mm)")
        fl = QFormLayout(g_size)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0, 5000)
        self.width_spin.setValue(600)
        self.width_spin.setSuffix(" mm")
        fl.addRow("Desired Width", self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0, 5000)
        self.height_spin.setValue(0)
        self.height_spin.setSuffix(" mm")
        self.height_spin.setToolTip("Set > 0 only if Width is 0 (height-driven)")
        fl.addRow("Desired Height", self.height_spin)

        layout.addWidget(g_size)

        # ---- LED Settings ----
        g_led = QGroupBox("LED Placement")
        fl = QFormLayout(g_led)

        self.mode_edges = QRadioButton("Edges (outline)")
        self.mode_center = QRadioButton("Centerline (skeleton)")
        self.mode_edges.setChecked(True)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.mode_edges)
        mode_row.addWidget(self.mode_center)
        fl.addRow("Mode", mode_row)

        self.max_leds_spin = QSpinBox()
        self.max_leds_spin.setRange(0, 5000)
        self.max_leds_spin.setValue(400)
        self.max_leds_spin.setSpecialValueText("No limit")
        self.max_leds_spin.setToolTip("0 = use fixed pitch instead of max-LED targeting")
        fl.addRow("Max LEDs", self.max_leds_spin)

        self.pitch_spin = QDoubleSpinBox()
        self.pitch_spin.setRange(2.0, 50.0)
        self.pitch_spin.setValue(6.0)
        self.pitch_spin.setSingleStep(0.5)
        self.pitch_spin.setSuffix(" mm")
        self.pitch_spin.setToolTip("Used when Max LEDs = 0")
        fl.addRow("Fixed Pitch", self.pitch_spin)

        self.led_dia_spin = QDoubleSpinBox()
        self.led_dia_spin.setRange(1.0, 20.0)
        self.led_dia_spin.setValue(5.0)
        self.led_dia_spin.setSuffix(" mm")
        fl.addRow("LED Diameter", self.led_dia_spin)

        self.pin_spacing_spin = QDoubleSpinBox()
        self.pin_spacing_spin.setRange(0.5, 10.0)
        self.pin_spacing_spin.setValue(2.54)
        self.pin_spacing_spin.setSuffix(" mm")
        fl.addRow("Pin Spacing", self.pin_spacing_spin)

        layout.addWidget(g_led)

        # ---- Tiling ----
        g_tile = QGroupBox("Tiling")
        fl = QFormLayout(g_tile)

        self.paper_combo = QComboBox()
        self.paper_combo.addItems(list(PAPER_SIZES_MM.keys()))
        self.paper_combo.setCurrentText("A4")
        fl.addRow("Paper", self.paper_combo)

        self.orient_combo = QComboBox()
        self.orient_combo.addItems(["portrait", "landscape"])
        fl.addRow("Orientation", self.orient_combo)

        self.overlap_spin = QDoubleSpinBox()
        self.overlap_spin.setRange(0, 100)
        self.overlap_spin.setValue(20.0)
        self.overlap_spin.setSuffix(" mm")
        fl.addRow("Overlap", self.overlap_spin)

        self.smart_tile_check = QCheckBox("Smart (skip empty regions)")
        self.smart_tile_check.setChecked(True)
        fl.addRow(self.smart_tile_check)

        tile_btns = QHBoxLayout()
        self.btn_auto_tile = QPushButton("Auto Tile")
        self.btn_add_tile = QPushButton("Add Tile")
        self.btn_clear_tiles = QPushButton("Clear Tiles")
        self.btn_auto_tile.clicked.connect(self.auto_tile_clicked.emit)
        self.btn_add_tile.clicked.connect(self.add_tile_clicked.emit)
        self.btn_clear_tiles.clicked.connect(self.clear_tiles_clicked.emit)
        tile_btns.addWidget(self.btn_auto_tile)
        tile_btns.addWidget(self.btn_add_tile)
        tile_btns.addWidget(self.btn_clear_tiles)
        fl.addRow(tile_btns)

        layout.addWidget(g_tile)

        # ---- Output ----
        g_out = QGroupBox("Output")
        fl = QFormLayout(g_out)

        self.out_path_edit = QLineEdit()
        default_out = str(Path.home() / "LED_Placement_Output")
        self.out_path_edit.setText(default_out)
        btn_browse_out = QPushButton("…")
        btn_browse_out.setFixedWidth(36)
        btn_browse_out.clicked.connect(self._browse_output)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_path_edit)
        out_row.addWidget(btn_browse_out)
        fl.addRow("Folder", out_row)

        layout.addWidget(g_out)

        # ---- Action buttons ----
        self.btn_generate = QPushButton("Generate Placement")
        self.btn_generate.setObjectName("generateBtn")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.clicked.connect(self.generate_clicked.emit)
        layout.addWidget(self.btn_generate)

        # Simulate row
        sim_row = QHBoxLayout()
        self.btn_simulate = QPushButton("▶ Simulate")
        self.btn_simulate.setObjectName("simulateBtn")
        self.btn_simulate.setMinimumHeight(36)
        self.btn_simulate.clicked.connect(self.simulate_clicked.emit)
        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.setMinimumHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_simulate_clicked.emit)
        sim_row.addWidget(self.btn_simulate)
        sim_row.addWidget(self.btn_stop)
        layout.addLayout(sim_row)

        self.btn_export = QPushButton("Export All")
        self.btn_export.setObjectName("exportBtn")
        self.btn_export.setMinimumHeight(36)
        self.btn_export.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self.btn_export)

        layout.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    def _populate_fonts(self):
        families = QFontDatabase.families()
        # Prefer common useful fonts first
        preferred = [
            "Arial", "Segoe UI", "Tahoma", "Times New Roman",
            "IranNastaliq", "Vazir", "Vazirmatn", "Noto Naskh Arabic",
            "Noto Sans Arabic", "DejaVu Sans",
        ]
        seen = set()
        for f in preferred:
            if f in families and f not in seen:
                self.font_combo.addItem(f)
                seen.add(f)
        for f in sorted(families):
            if f not in seen:
                self.font_combo.addItem(f)

    def _browse_font(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Font File",
            str(Path.home()),
            "Font Files (*.ttf *.otf *.ttc);;All Files (*)",
        )
        if path:
            self.font_path_edit.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", self.out_path_edit.text()
        )
        if path:
            self.out_path_edit.setText(path)

    # ------------------------------------------------------------------
    # Getters used by MainWindow
    # ------------------------------------------------------------------
    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def get_language_dir(self) -> str:
        return "RTL" if self.lang_combo.currentIndex() == 0 else "LTR"

    def get_font_path(self) -> Optional[str]:
        """Return custom font file path if the user browsed one."""
        custom = self.font_path_edit.text().strip()
        if custom and Path(custom).is_file():
            return custom
        return None

    def get_font_family(self) -> str:
        """Return the selected system font family name."""
        return self.font_combo.currentText()

    def get_desired_width(self) -> float:
        return self.width_spin.value()

    def get_desired_height(self) -> float:
        return self.height_spin.value()

    def get_placement_mode(self) -> str:
        return "centerline" if self.mode_center.isChecked() else "edges"

    def get_max_leds(self) -> Optional[int]:
        v = self.max_leds_spin.value()
        return v if v > 0 else None

    def get_pitch(self) -> float:
        return self.pitch_spin.value()

    def get_led_dia(self) -> float:
        return self.led_dia_spin.value()

    def get_pin_spacing(self) -> float:
        return self.pin_spacing_spin.value()

    def get_paper(self) -> str:
        return self.paper_combo.currentText()

    def get_orientation(self) -> str:
        return self.orient_combo.currentText()

    def get_overlap(self) -> float:
        return self.overlap_spin.value()

    def get_smart_tiling(self) -> bool:
        return self.smart_tile_check.isChecked()

    def get_output_dir(self) -> Path:
        return Path(self.out_path_edit.text().strip() or ".")
