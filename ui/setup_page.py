"""
Setup page – three-column layout, clearer strategy controls.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SetupPage(QWidget):
    generate_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_fonts: list[str] = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        title = QLabel("LED Placement Studio")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Design  ·  Place  ·  Preview  ·  Export")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        cols = QHBoxLayout()
        cols.setSpacing(14)

        # ========== COL 1 – Text & Font (wider) ==========
        c1 = QFrame()
        c1.setObjectName("card")
        c1.setMinimumWidth(320)
        l1 = QVBoxLayout(c1)
        l1.setContentsMargins(16, 14, 16, 14)
        l1.setSpacing(10)

        l1.addWidget(self._section_label("Text & font"))

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Type your text…")
        self.text_edit.setFixedHeight(88)
        self.text_edit.setPlainText("ظروف چوبی")
        l1.addWidget(self.text_edit)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["RTL – Farsi / Arabic", "LTR – English / Latin"])
        l1.addWidget(QLabel("Direction"))
        l1.addWidget(self.lang_combo)

        l1.addWidget(QLabel("Font  (type to search)"))
        self.font_combo = QComboBox()
        self.font_combo.setEditable(True)
        self.font_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.font_combo.setMaxVisibleItems(16)
        self.font_combo.setCompleter(None)  # we filter manually
        self._populate_fonts()
        # Filter as user types in the line edit
        le = self.font_combo.lineEdit()
        if le is not None:
            le.textEdited.connect(self._on_font_typed)
            le.editingFinished.connect(self._on_font_edit_finished)
        l1.addWidget(self.font_combo)

        row = QHBoxLayout()
        self.font_path_edit = QLineEdit()
        self.font_path_edit.setPlaceholderText("Or browse a .ttf / .otf file")
        btn_font = QPushButton("Browse…")
        btn_font.setFixedWidth(88)
        btn_font.clicked.connect(self._browse_font)
        row.addWidget(self.font_path_edit, 1)
        row.addWidget(btn_font)
        l1.addLayout(row)

        l1.addSpacing(6)
        l1.addWidget(self._section_label("Physical size"))

        sg = QGridLayout()
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0, 5000)
        self.width_spin.setValue(600)
        self.width_spin.setSuffix(" mm")
        self.width_spin.setDecimals(1)
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0, 5000)
        self.height_spin.setValue(0)
        self.height_spin.setSuffix(" mm")
        self.height_spin.setDecimals(1)
        self.height_spin.setToolTip(
            "0 = size by width only. Both set → fit inside the box."
        )
        sg.addWidget(QLabel("Width"), 0, 0)
        sg.addWidget(self.width_spin, 0, 1)
        sg.addWidget(QLabel("Height"), 1, 0)
        sg.addWidget(self.height_spin, 1, 1)
        l1.addLayout(sg)

        l1.addStretch()
        cols.addWidget(c1, 3)

        # ========== COL 2 – Strategy ==========
        c2 = QFrame()
        c2.setObjectName("card")
        c2.setMinimumWidth(260)
        l2 = QVBoxLayout(c2)
        l2.setContentsMargins(16, 14, 16, 14)
        l2.setSpacing(10)

        l2.addWidget(self._section_label("Method"))
        self.method_domino = QRadioButton("Domino")
        self.method_classic = QRadioButton("Classic")
        self.method_domino.setChecked(True)
        self.method_domino.setToolTip(
            "Centre-to-centre chain: place → step D → place.\n"
            "Gap value = distance between centres."
        )
        self.method_classic.setToolTip(
            "Original contour walk with corner preference.\n"
            "Gap value = body-to-body clearance."
        )
        self._method_group = QButtonGroup(self)
        self._method_group.addButton(self.method_domino)
        self._method_group.addButton(self.method_classic)
        l2.addWidget(self.method_domino)
        l2.addWidget(self.method_classic)

        l2.addSpacing(4)
        l2.addWidget(self._section_label("Path"))
        self.path_edge = QRadioButton("Edge (outline)")
        self.path_center = QRadioButton("Centerline")
        self.path_both = QRadioButton("Both (outline + fill)")
        self.path_edge.setChecked(True)
        self.path_edge.setToolTip("Follow the outer outline of the letters")
        self.path_center.setToolTip(
            "Follow the middle of strokes — best for filled / small fonts"
        )
        self.path_both.setToolTip("Outline first, then fill the interior")
        self._path_group = QButtonGroup(self)
        for b in (self.path_edge, self.path_center, self.path_both):
            self._path_group.addButton(b)
            l2.addWidget(b)

        l2.addSpacing(4)
        l2.addWidget(self._section_label("Spacing control"))
        self.space_gap = QRadioButton("By gap")
        self.space_count = QRadioButton("By LED count")
        self.space_gap.setChecked(True)
        self._space_group = QButtonGroup(self)
        self._space_group.addButton(self.space_gap)
        self._space_group.addButton(self.space_count)
        l2.addWidget(self.space_gap)
        l2.addWidget(self.space_count)

        self.gap_spin = QDoubleSpinBox()
        self.gap_spin.setRange(0.3, 40.0)
        self.gap_spin.setValue(1.0)
        self.gap_spin.setSingleStep(0.5)
        self.gap_spin.setSuffix(" mm")
        self.gap_spin.setToolTip(
            "Domino: centre-to-centre D.\nClassic: body-to-body clearance."
        )

        self.max_leds_spin = QSpinBox()
        self.max_leds_spin.setRange(10, 8000)
        self.max_leds_spin.setValue(300)
        self.max_leds_spin.setSuffix(" LEDs")
        self.max_leds_spin.setEnabled(False)

        g = QGridLayout()
        g.addWidget(QLabel("Gap"), 0, 0)
        g.addWidget(self.gap_spin, 0, 1)
        g.addWidget(QLabel("Target count"), 1, 0)
        g.addWidget(self.max_leds_spin, 1, 1)
        l2.addLayout(g)

        self.space_gap.toggled.connect(self._on_space_mode)
        self.method_domino.toggled.connect(self._update_gap_label)
        self._gap_label_hint = QLabel("")
        self._gap_label_hint.setObjectName("hintLabel")
        self._gap_label_hint.setWordWrap(True)
        l2.addWidget(self._gap_label_hint)
        self._update_gap_label()

        l2.addStretch()
        cols.addWidget(c2, 2)

        # ========== COL 3 – Hardware & output (narrower) ==========
        c3 = QFrame()
        c3.setObjectName("card")
        c3.setMinimumWidth(220)
        l3 = QVBoxLayout(c3)
        l3.setContentsMargins(16, 14, 16, 14)
        l3.setSpacing(10)

        l3.addWidget(self._section_label("Hardware"))
        self.led_dia_spin = QDoubleSpinBox()
        self.led_dia_spin.setRange(1.0, 20.0)
        self.led_dia_spin.setValue(5.0)
        self.led_dia_spin.setSuffix(" mm")
        self.pin_spacing_spin = QDoubleSpinBox()
        self.pin_spacing_spin.setRange(0.5, 10.0)
        self.pin_spacing_spin.setValue(2.54)
        self.pin_spacing_spin.setSuffix(" mm")
        h = QGridLayout()
        h.addWidget(QLabel("LED Ø"), 0, 0)
        h.addWidget(self.led_dia_spin, 0, 1)
        h.addWidget(QLabel("Pin spacing"), 1, 0)
        h.addWidget(self.pin_spacing_spin, 1, 1)
        l3.addLayout(h)

        l3.addSpacing(6)
        l3.addWidget(self._section_label("Output folder"))
        out_row = QHBoxLayout()
        self.out_path_edit = QLineEdit()
        self.out_path_edit.setText(str(Path.home() / "LED_Placement_Output"))
        btn_out = QPushButton("…")
        btn_out.setFixedWidth(36)
        btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.out_path_edit, 1)
        out_row.addWidget(btn_out)
        l3.addLayout(out_row)

        tip = QLabel(
            "After Generate you can move, add or delete LEDs on the View page."
        )
        tip.setObjectName("hintLabel")
        tip.setWordWrap(True)
        l3.addWidget(tip)

        l3.addStretch()
        cols.addWidget(c3, 2)

        root.addLayout(cols, 1)

        self.btn_generate = QPushButton("Generate placement  →")
        self.btn_generate.setObjectName("generateBtn")
        self.btn_generate.setMinimumHeight(48)
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.clicked.connect(self.generate_clicked.emit)
        root.addWidget(self.btn_generate)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    def _on_space_mode(self, gap_on: bool):
        self.gap_spin.setEnabled(gap_on)
        self.max_leds_spin.setEnabled(not gap_on)

    def _update_gap_label(self):
        if self.method_domino.isChecked():
            self._gap_label_hint.setText(
                "Domino gap = centre-to-centre distance D."
            )
        else:
            self._gap_label_hint.setText(
                "Classic gap = body-to-body clearance "
                "(centres ≈ LED Ø + gap)."
            )

    # ---- fonts ----
    def _populate_fonts(self):
        families = list(QFontDatabase.families())
        preferred = [
            "Arial", "Segoe UI", "Tahoma", "Times New Roman",
            "IranNastaliq", "Vazir", "Vazirmatn", "Noto Naskh Arabic",
            "Noto Sans Arabic", "DejaVu Sans",
        ]
        ordered, seen = [], set()
        for f in preferred:
            if f in families and f not in seen:
                ordered.append(f)
                seen.add(f)
        for f in sorted(families):
            if f not in seen:
                ordered.append(f)
        self._all_fonts = ordered
        self.font_combo.clear()
        self.font_combo.addItems(ordered)

    def _on_font_typed(self, text: str):
        q = text.strip().lower()
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        if not q:
            self.font_combo.addItems(self._all_fonts)
        else:
            matches = [f for f in self._all_fonts if q in f.lower()]
            self.font_combo.addItems(matches if matches else self._all_fonts)
        # Keep typed text in the line edit
        le = self.font_combo.lineEdit()
        if le is not None:
            le.setText(text)
            le.setCursorPosition(len(text))
        self.font_combo.blockSignals(False)
        if self.font_combo.count() > 0:
            self.font_combo.showPopup()

    def _on_font_edit_finished(self):
        le = self.font_combo.lineEdit()
        if le is None:
            return
        typed = le.text().strip()
        # If exact match exists, select it; else keep first match / typed
        idx = self.font_combo.findText(typed, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        elif self.font_combo.count() > 0:
            # try case-insensitive
            for i in range(self.font_combo.count()):
                if self.font_combo.itemText(i).lower() == typed.lower():
                    self.font_combo.setCurrentIndex(i)
                    return

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

    # ---- getters ----
    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def get_language_dir(self) -> str:
        return "RTL" if self.lang_combo.currentIndex() == 0 else "LTR"

    def get_font_path(self) -> Optional[str]:
        custom = self.font_path_edit.text().strip()
        return custom if custom and Path(custom).is_file() else None

    def get_font_family(self) -> str:
        return self.font_combo.currentText().strip()

    def get_desired_width(self) -> float:
        return self.width_spin.value()

    def get_desired_height(self) -> float:
        return self.height_spin.value()

    def get_placement_mode(self) -> str:
        """Map Method × Path → engine mode string."""
        domino = self.method_domino.isChecked()
        if self.path_both.isChecked():
            return "fill"  # outline+interior (uses domino outline)
        if self.path_center.isChecked():
            return "domino_centerline" if domino else "centerline"
        # edge
        return "domino" if domino else "edges"

    def get_max_leds(self) -> Optional[int]:
        if self.space_count.isChecked():
            return self.max_leds_spin.value()
        return None

    def get_gap(self) -> float:
        return self.gap_spin.value()

    def get_led_dia(self) -> float:
        return self.led_dia_spin.value()

    def get_pin_spacing(self) -> float:
        return self.pin_spacing_spin.value()

    def get_output_dir(self) -> Path:
        return Path(self.out_path_edit.text().strip() or ".")

    def set_busy(self, busy: bool):
        self.btn_generate.setEnabled(not busy)
        self.btn_generate.setText(
            "Working…" if busy else "Generate placement  →"
        )
