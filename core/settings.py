"""Persist user preferences between sessions."""
from __future__ import annotations

from PyQt6.QtCore import QSettings

from core.version import APP_NAME, APP_ORG


def settings() -> QSettings:
    return QSettings(APP_ORG, APP_NAME)


def save_setup(page) -> None:
    s = settings()
    s.setValue("text", page.get_text())
    s.setValue("lang_index", page.lang_combo.currentIndex())
    s.setValue("font_family", page.get_font_family())
    s.setValue("font_path", page.font_path_edit.text())
    s.setValue("width_mm", page.get_desired_width())
    s.setValue("height_mm", page.get_desired_height())
    s.setValue("method_domino", page.method_domino.isChecked())
    if page.path_center.isChecked():
        path = "center"
    elif page.path_both.isChecked():
        path = "both"
    else:
        path = "edge"
    s.setValue("path", path)
    s.setValue("space_gap", page.space_gap.isChecked())
    s.setValue("max_leds", page.max_leds_spin.value())
    s.setValue("gap_mm", page.get_gap())
    s.setValue("led_dia", page.get_led_dia())
    s.setValue("pin_spacing", page.get_pin_spacing())
    s.setValue("output_dir", str(page.get_output_dir()))


def load_setup(page) -> None:
    s = settings()
    if s.contains("text"):
        page.text_edit.setPlainText(s.value("text", ""))
    page.lang_combo.setCurrentIndex(int(s.value("lang_index", 0)))
    family = s.value("font_family", "")
    if family:
        idx = page.font_combo.findText(family)
        if idx >= 0:
            page.font_combo.setCurrentIndex(idx)
        else:
            page.font_combo.setEditText(family)
    page.font_path_edit.setText(s.value("font_path", ""))
    page.width_spin.setValue(float(s.value("width_mm", 600)))
    page.height_spin.setValue(float(s.value("height_mm", 0)))

    if s.value("method_domino", True) in (True, "true", "1"):
        page.method_domino.setChecked(True)
    else:
        page.method_classic.setChecked(True)

    path = s.value("path", "edge")
    if path == "center":
        page.path_center.setChecked(True)
    elif path == "both":
        page.path_both.setChecked(True)
    else:
        page.path_edge.setChecked(True)

    if s.value("space_gap", True) in (True, "true", "1"):
        page.space_gap.setChecked(True)
    else:
        page.space_count.setChecked(True)
    page.max_leds_spin.setValue(int(s.value("max_leds", 300)))
    page.gap_spin.setValue(float(s.value("gap_mm", 1.0)))
    page.led_dia_spin.setValue(float(s.value("led_dia", 5.0)))
    page.pin_spacing_spin.setValue(float(s.value("pin_spacing", 2.54)))
    page.out_path_edit.setText(s.value("output_dir", str(page.get_output_dir())))
    page._on_space_mode(page.space_gap.isChecked())
    page._update_gap_label()


def save_geometry(window) -> None:
    s = settings()
    s.setValue("geometry", window.saveGeometry())
    s.setValue("windowState", window.saveState())


def load_geometry(window) -> None:
    s = settings()
    geo = s.value("geometry")
    if geo is not None:
        window.restoreGeometry(geo)
    st = s.value("windowState")
    if st is not None:
        window.restoreState(st)
