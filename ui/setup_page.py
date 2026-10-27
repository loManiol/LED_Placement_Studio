"""
Setup page – clean single-screen settings (no scroll).
User fills this in, hits Generate, then moves to the View page.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SetupPage(QWidget):
    generate_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 28, 40, 28)
        root.setSpacing(18)

        # ---- Header ----
        title = QLabel("LED Placement Studio")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Design · Place · Preview · Export")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        root.addSpacing(8)

        # ---- Two-column card layout ----
        cards = QHBoxLayout()
        cards.setSpacing(20)

        # LEFT card: Text & Font + Size
        left = QFrame()
        left.setObjectName("card")
        left_l = QVBoxLayout(left)
        left_l.setSpacing(14)
        left_l.setContentsMargins(20, 18, 20, 18)

        left_l.addWidget(self._section_label("1  ·  Text & Font"))

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Type your text here…\n(Persian, Arabic, English, …)")
        self.text_edit.setFixedHeight(90)
        self.text_edit.setPlainText("ظروف چوبی")
        left_l.addWidget(self.text_edit)

        row = QHBoxLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["RTL – Farsi / Arabic", "LTR – English / Latin"])
        row.addWidget(QLabel("Direction"))
        row.addWidget(self.lang_combo, 1)
        left_l.addLayout(row)

        row = QHBoxLayout()
        self.font_combo = QComboBox()
        self._populate_fonts()
        row.addWidget(QLabel("System font"))
        row.addWidget(self.font_combo, 1)
        left_l.addLayout(row)

        row = QHBoxLayout()
        self.font_path_edit = QLineEdit()
        self.font_path_edit.setPlaceholderText("Optional: path to .ttf / .otf")
        btn_font = QPushButton("Browse…")
        btn_font.setFixedWidth(90)
        btn_font.clicked.connect(self._browse_font)
        row.addWidget(self.font_path_edit, 1)
        row.addWidget(btn_font)
        left_l.addLayout(row)

        left_l.addSpacing(6)
        left_l.addWidget(self._section_label("2  ·  Physical size"))

        size_grid = QGridLayout()
        size_grid.setHorizontalSpacing(12)
        size_grid.setVerticalSpacing(8)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0, 5000)
        self.width_spin.setValue(600)
        self.width_spin.setSuffix("  mm")
        self.width_spin.setDecimals(1)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0, 5000)
        self.height_spin.setValue(0)
        self.height_spin.setSuffix("  mm")
        self.height_spin.setDecimals(1)
        self.height_spin.setToolTip("Leave 0 to size by width only")

        size_grid.addWidget(QLabel("Width"), 0, 0)
        size_grid.addWidget(self.width_spin, 0, 1)
        size_grid.addWidget(QLabel("Height (optional)"), 1, 0)
        size_grid.addWidget(self.height_spin, 1, 1)
        left_l.addLayout(size_grid)

        left_l.addStretch()
        cards.addWidget(left, 1)

        # RIGHT card: LED strategy + extras
        right = QFrame()
        right.setObjectName("card")
        right_l = QVBoxLayout(right)
        right_l.setSpacing(14)
        right_l.setContentsMargins(20, 18, 20, 18)

        right_l.addWidget(self._section_label("3  ·  LED strategy"))

        # Mode
        mode_row = QHBoxLayout()
        self.mode_edges = QRadioButton("Edges (outline)")
        self.mode_center = QRadioButton("Centerline")
        self.mode_edges.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.mode_edges)
        self._mode_group.addButton(self.mode_center)
        mode_row.addWidget(self.mode_edges)
        mode_row.addWidget(self.mode_center)
        mode_row.addStretch()
        right_l.addLayout(mode_row)

        # Pitch strategy – clearer UX
        hint = QLabel(
            "Choose how LEDs are spaced:\n"
            "• Target count → app finds the best pitch automatically\n"
            "• Fixed pitch → exact millimetre spacing"
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        right_l.addWidget(hint)

        self.strategy_target = QRadioButton("Target LED count")
        self.strategy_pitch = QRadioButton("Fixed pitch")
        self.strategy_target.setChecked(True)
        self._strat_group = QButtonGroup(self)
        self._strat_group.addButton(self.strategy_target)
        self._strat_group.addButton(self.strategy_pitch)
        right_l.addWidget(self.strategy_target)
        right_l.addWidget(self.strategy_pitch)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        self.max_leds_spin = QSpinBox()
        self.max_leds_spin.setRange(10, 5000)
        self.max_leds_spin.setValue(300)
        self.max_leds_spin.setSuffix("  LEDs")

        self.pitch_spin = QDoubleSpinBox()
        self.pitch_spin.setRange(2.5, 40.0)
        self.pitch_spin.setValue(6.0)
        self.pitch_spin.setSingleStep(0.5)
        self.pitch_spin.setSuffix("  mm")
        self.pitch_spin.setEnabled(False)

        grid.addWidget(QLabel("Max LEDs"), 0, 0)
        grid.addWidget(self.max_leds_spin, 0, 1)
        grid.addWidget(QLabel("Pitch"), 1, 0)
        grid.addWidget(self.pitch_spin, 1, 1)
        right_l.addLayout(grid)

        self.strategy_target.toggled.connect(self._on_strategy_changed)

        # Fine details (compact)
        right_l.addSpacing(4)
        right_l.addWidget(self._section_label("4  ·  Hardware"))

        hw = QGridLayout()
        hw.setHorizontalSpacing(12)
        self.led_dia_spin = QDoubleSpinBox()
        self.led_dia_spin.setRange(1.0, 20.0)
        self.led_dia_spin.setValue(5.0)
        self.led_dia_spin.setSuffix("  mm")
        self.pin_spacing_spin = QDoubleSpinBox()
        self.pin_spacing_spin.setRange(0.5, 10.0)
        self.pin_spacing_spin.setValue(2.54)
        self.pin_spacing_spin.setSuffix("  mm")
        hw.addWidget(QLabel("LED Ø"), 0, 0)
        hw.addWidget(self.led_dia_spin, 0, 1)
        hw.addWidget(QLabel("Pin spacing"), 1, 0)
        hw.addWidget(self.pin_spacing_spin, 1, 1)
        right_l.addLayout(hw)

        right_l.addSpacing(4)
        right_l.addWidget(self._section_label("5  ·  Output folder"))

        out_row = QHBoxLayout()
        self.out_path_edit = QLineEdit()
        self.out_path_edit.setText(str(Path.home() / "LED_Placement_Output"))
        btn_out = QPushButton("…")
        btn_out.setFixedWidth(40)
        btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.out_path_edit, 1)
        out_row.addWidget(btn_out)
        right_l.addLayout(out_row)

        right_l.addStretch()
        cards.addWidget(right, 1)

        root.addLayout(cards, 1)

        # ---- Big Generate CTA ----
        self.btn_generate = QPushButton("Generate placement  →")
        self.btn_generate.setObjectName("generateBtn")
        self.btn_generate.setMinimumHeight(52)
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.clicked.connect(self.generate_clicked.emit)
        root.addWidget(self.btn_generate)

        tip = QLabel("Tip: after generating you can move, add or delete LEDs on the View page.")
        tip.setObjectName("pageSubtitle")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(tip)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _on_strategy_changed(self, target_on: bool):
        self.max_leds_spin.setEnabled(target_on)
        self.pitch_spin.setEnabled(not target_on)

    def _populate_fonts(self):
        families = QFontDatabase.families()
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
            self, "Select Font File", str(Path.home()),
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

    # ---- getters ----
    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def get_language_dir(self) -> str:
        return "RTL" if self.lang_combo.currentIndex() == 0 else "LTR"

    def get_font_path(self) -> Optional[str]:
        custom = self.font_path_edit.text().strip()
        return custom if custom and Path(custom).is_file() else None

    def get_font_family(self) -> str:
        return self.font_combo.currentText()

    def get_desired_width(self) -> float:
        return self.width_spin.value()

    def get_desired_height(self) -> float:
        return self.height_spin.value()

    def get_placement_mode(self) -> str:
        return "centerline" if self.mode_center.isChecked() else "edges"

    def get_max_leds(self) -> Optional[int]:
        if self.strategy_target.isChecked():
            return self.max_leds_spin.value()
        return None

    def get_pitch(self) -> float:
        return self.pitch_spin.value()

    def get_led_dia(self) -> float:
        return self.led_dia_spin.value()

    def get_pin_spacing(self) -> float:
        return self.pin_spacing_spin.value()

    def get_output_dir(self) -> Path:
        return Path(self.out_path_edit.text().strip() or ".")

    def set_busy(self, busy: bool):
        self.btn_generate.setEnabled(not busy)
        self.btn_generate.setText("Working…" if busy else "Generate placement  →")
