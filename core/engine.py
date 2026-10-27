"""
Core processing engine for LED Placement Studio.
Extracted & extended from the original LED_placer.py script.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LEDPad:
    """One LED pad in millimetres (centre + tangent direction)."""
    x_mm: float
    y_mm: float
    tx: float = 1.0
    ty: float = 0.0

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x_mm, self.y_mm, self.tx, self.ty)


@dataclass
class TileRect:
    """A tile rectangle in millimetres (scene coordinates)."""
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    label: str = ""


@dataclass
class PlacementResult:
    """Everything the UI needs after a generation run."""
    pads: List[LEDPad]
    mask: np.ndarray                 # binary mask at PX_PER_MM resolution
    final_w_mm: float
    final_h_mm: float
    pitch_mm: float
    scale: float
    underlay: Optional[np.ndarray] = None  # high-res grayscale for preview


# ---------------------------------------------------------------------------
# Paper sizes
# ---------------------------------------------------------------------------

PAPER_SIZES_MM = {
    "A2": (420.0, 594.0),
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "B2": (500.0, 707.0),
    "B3": (353.0, 500.0),
    "B4": (250.0, 353.0),
    "B5": (176.0, 250.0),
}


def get_paper_dims(paper: str, orientation: str) -> Tuple[float, float]:
    w, h = PAPER_SIZES_MM[paper]
    return (w, h) if orientation == "portrait" else (h, w)


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class CoreEngine:
    """
    Stateless processing engine.
    All heavy work lives here so it can be run on a QThread.
    """

    def __init__(
        self,
        px_per_mm: float = 5.0,
        print_dpi: float = 300.0,
        led_dia_mm: float = 5.0,
        pin_spacing_mm: float = 2.54,
        pin_drill_mm: float = 1.0,
    ):
        self.px_per_mm = px_per_mm
        self.print_dpi = print_dpi
        self.led_dia_mm = led_dia_mm
        self.pin_spacing_mm = pin_spacing_mm
        self.pin_drill_mm = pin_drill_mm

    # ------------------------------------------------------------------
    # 1. Text → binary mask (PyQt6 native rendering)
    # ------------------------------------------------------------------
    def render_text_mask(
        self,
        text: str,
        font_path: Optional[str] = None,
        font_family: Optional[str] = None,
        language_dir: str = "LTR",
        font_size_pt: int = 300,
    ) -> np.ndarray:
        """
        Render text into a grayscale mask.
        Prefer font_path (custom .ttf/.otf). If missing, use font_family
        from the system font list (works for any installed family).
        """
        import sys
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import (
            QColor,
            QFont,
            QFontDatabase,
            QFontMetrics,
            QImage,
            QPainter,
        )
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        family = None

        if font_path:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id == -1:
                raise RuntimeError(f"Could not load font file: {font_path}")
            families = QFontDatabase.applicationFontFamilies(font_id)
            if not families:
                raise RuntimeError(f"No font families found in: {font_path}")
            family = families[0]
        elif font_family:
            family = font_family
        else:
            raise RuntimeError("Either font_path or font_family must be provided")

        font = QFont(family, font_size_pt)
        # Ensure complex-script shaping works
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)

        metrics = QFontMetrics(font)
        rect = metrics.boundingRect(text)

        w = max(rect.width() + 100, 50)
        h = max(rect.height() + 100, 50)

        img = QImage(w, h, QImage.Format.Format_Grayscale8)
        img.fill(Qt.GlobalColor.black)

        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(50 - rect.left(), 50 - rect.top(), text)
        painter.end()

        ptr = img.bits()
        ptr.setsize(img.sizeInBytes())
        bpl = img.bytesPerLine()
        arr = np.array(ptr, copy=True).reshape(h, bpl)
        arr = arr[:, :w]
        return arr

    # ------------------------------------------------------------------
    # 2. Skeletonization
    # ------------------------------------------------------------------
    @staticmethod
    def get_skeleton(img: np.ndarray) -> np.ndarray:
        skel = np.zeros(img.shape, np.uint8)
        img_copy = img.copy()
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        while True:
            eroded = cv2.erode(img_copy, element)
            temp = cv2.dilate(eroded, element)
            temp = cv2.subtract(img_copy, temp)
            skel = cv2.bitwise_or(skel, temp)
            img_copy = eroded.copy()
            if cv2.countNonZero(img_copy) == 0:
                break
        return skel

    # ------------------------------------------------------------------
    # 3. LED placement along contours
    # ------------------------------------------------------------------
    def place_leds(
        self,
        routing_mask: np.ndarray,
        check_mask: np.ndarray,
        pitch_mm: float,
    ) -> List[LEDPad]:
        spacing_px = pitch_mm * self.px_per_mm
        pads_native: List[Tuple[float, float, float, float]] = []

        contours, _ = cv2.findContours(
            routing_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE
        )

        for c in contours:
            if cv2.arcLength(c, True) < spacing_px:
                continue

            epsilon = 0.015 * cv2.arcLength(c, True)
            approx_corners = cv2.approxPolyDP(c, epsilon, True)
            corner_pts = {tuple(pt[0]) for pt in approx_corners}

            c_pts = c.reshape(-1, 2)
            closed = np.vstack([c_pts, c_pts[:1]])

            current_dist = spacing_px  # force placement at start
            for i in range(len(closed) - 1):
                p1, p2 = closed[i], closed[i + 1]
                dist = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))

                is_corner = tuple(p1) in corner_pts

                if is_corner or current_dist >= spacing_px:
                    step = min(5, len(closed) // 8)
                    p_prev = closed[max(0, i - step)]
                    p_next = closed[min(len(closed) - 1, i + step)]
                    dx = p_next[0] - p_prev[0]
                    dy = p_next[1] - p_prev[1]
                    L = float(np.hypot(dx, dy))
                    tx, ty = (1.0, 0.0) if L < 1e-6 else (dx / L, dy / L)

                    cx_mm = p1[0] / self.px_per_mm
                    cy_mm = p1[1] / self.px_per_mm

                    p1x = cx_mm + tx * (self.pin_spacing_mm / 2)
                    p1y = cy_mm + ty * (self.pin_spacing_mm / 2)
                    p2x = cx_mm - tx * (self.pin_spacing_mm / 2)
                    p2y = cy_mm - ty * (self.pin_spacing_mm / 2)

                    if self._is_on_mask(p1x, p1y, check_mask) and self._is_on_mask(
                        p2x, p2y, check_mask
                    ):
                        pads_native.append((cx_mm, cy_mm, tx, ty))
                        current_dist = 0.0

                current_dist += dist

        # Strict deduplication
        final: List[LEDPad] = []
        min_d2 = (pitch_mm * 0.7) ** 2
        for r in pads_native:
            if all(
                (r[0] - q.x_mm) ** 2 + (r[1] - q.y_mm) ** 2 >= min_d2 for q in final
            ):
                final.append(LEDPad(*r))
        return final

    def _is_on_mask(self, px_mm: float, py_mm: float, mask: np.ndarray) -> bool:
        x_px = int(round(px_mm * self.px_per_mm))
        y_px = int(round(py_mm * self.px_per_mm))
        if y_px < 0 or y_px >= mask.shape[0] or x_px < 0 or x_px >= mask.shape[1]:
            return False
        return bool(mask[y_px, x_px] > 0)

    # ------------------------------------------------------------------
    # 4. Binary search for max-LED pitch
    # ------------------------------------------------------------------
    def find_pitch_for_max_leds(
        self,
        routing_mask: np.ndarray,
        check_mask: np.ndarray,
        max_leds: int,
        pitch_min: float = 3.0,
        pitch_max: float = 30.0,
        tol: int = 2,
    ) -> Tuple[float, List[LEDPad]]:
        """
        Binary search over pitch so that len(pads) ≈ max_leds.
        Returns (best_pitch, pads).
        """
        lo, hi = pitch_min, pitch_max
        best_pads: List[LEDPad] = []
        best_pitch = pitch_max

        for _ in range(18):  # enough iterations for float precision
            mid = (lo + hi) / 2.0
            pads = self.place_leds(routing_mask, check_mask, mid)
            n = len(pads)
            if n > max_leds + tol:
                lo = mid  # too many → increase pitch
            elif n < max_leds - tol:
                hi = mid  # too few → decrease pitch
            else:
                return mid, pads
            if n <= max_leds and (not best_pads or n > len(best_pads)):
                best_pads = pads
                best_pitch = mid

        # final run with best_pitch
        if not best_pads:
            best_pads = self.place_leds(routing_mask, check_mask, best_pitch)
        return best_pitch, best_pads

    # ------------------------------------------------------------------
    # 5. Full generation pipeline
    # ------------------------------------------------------------------
    def generate(
        self,
        text: str,
        font_path: Optional[str] = None,
        font_family: Optional[str] = None,
        language_dir: str = "LTR",
        desired_width_mm: float = 600.0,
        desired_height_mm: float = 0.0,
        placement_mode: str = "edges",  # "edges" | "centerline"
        max_leds: Optional[int] = None,
        pitch_mm: float = 6.0,
        pitch_min: float = 3.0,
        pitch_max: float = 25.0,
    ) -> PlacementResult:
        """
        Full pipeline: render → scale → route → place LEDs.
        If max_leds is given, pitch is adapted via binary search.
        Provide font_path and/or font_family (family is used when path is missing).
        """
        raw_mask = self.render_text_mask(
            text,
            font_path=font_path,
            font_family=font_family,
            language_dir=language_dir,
        )

        # Crop to content
        x, y, w, h = cv2.boundingRect(raw_mask)
        cropped = raw_mask[y : y + h, x : x + w]

        current_w_mm = w / self.px_per_mm
        current_h_mm = h / self.px_per_mm

        if desired_width_mm > 0:
            scale = desired_width_mm / current_w_mm
        elif desired_height_mm > 0:
            scale = desired_height_mm / current_h_mm
        else:
            scale = 1.0

        final_w_px = max(1, int(w * scale))
        final_h_px = max(1, int(h * scale))
        final_w_mm = final_w_px / self.px_per_mm
        final_h_mm = final_h_px / self.px_per_mm

        thick_mask = cv2.resize(
            cropped, (final_w_px, final_h_px), interpolation=cv2.INTER_NEAREST
        )

        if placement_mode == "centerline":
            routing_mask = self.get_skeleton(thick_mask)
            check_mask = thick_mask
        else:
            routing_mask = thick_mask
            check_mask = cv2.dilate(thick_mask, np.ones((3, 3), np.uint8))

        if max_leds is not None and max_leds > 0:
            used_pitch, pads = self.find_pitch_for_max_leds(
                routing_mask, check_mask, max_leds, pitch_min, pitch_max
            )
        else:
            used_pitch = pitch_mm
            pads = self.place_leds(routing_mask, check_mask, used_pitch)

        return PlacementResult(
            pads=pads,
            mask=thick_mask,
            final_w_mm=final_w_mm,
            final_h_mm=final_h_mm,
            pitch_mm=used_pitch,
            scale=scale,
            underlay=thick_mask,
        )

    # ------------------------------------------------------------------
    # 6. High-resolution canvas rendering (for export)
    # ------------------------------------------------------------------
    def render_master_jpg(
        self,
        result: PlacementResult,
        pads: Optional[List[LEDPad]] = None,
        output_path: Optional[Path] = None,
    ) -> np.ndarray:
        """
        Draw the classic FULL_VIEW_Master style image.
        Uses the (possibly edited) pad list if provided.
        """
        pads = pads if pads is not None else result.pads
        canvas_w = int(result.final_w_mm * self.print_dpi / 25.4)
        canvas_h = int(result.final_h_mm * self.print_dpi / 25.4)
        canvas = np.full((canvas_h, canvas_w, 3), 255, np.uint8)

        underlay = cv2.resize(
            result.mask, (canvas_w, canvas_h), interpolation=cv2.INTER_AREA
        )
        canvas[underlay > 128] = (230, 230, 230)

        r_led = max(1, int(round(self.led_dia_mm / 2 * self.print_dpi / 25.4)))
        r_drill = max(1, int(round(self.pin_drill_mm / 2 * self.print_dpi / 25.4)))

        for i, pad in enumerate(pads):
            cx = int(pad.x_mm * self.print_dpi / 25.4)
            cy = int(pad.y_mm * self.print_dpi / 25.4)
            c1x = int((pad.x_mm + pad.tx * self.pin_spacing_mm / 2) * self.print_dpi / 25.4)
            c1y = int((pad.y_mm + pad.ty * self.pin_spacing_mm / 2) * self.print_dpi / 25.4)
            c2x = int((pad.x_mm - pad.tx * self.pin_spacing_mm / 2) * self.print_dpi / 25.4)
            c2y = int((pad.y_mm - pad.ty * self.pin_spacing_mm / 2) * self.print_dpi / 25.4)

            cv2.circle(canvas, (cx, cy), r_led, (0, 0, 0), 2, cv2.LINE_AA)
            cv2.circle(canvas, (c1x, c1y), r_drill, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, (c2x, c2y), r_drill, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.putText(
                canvas,
                str(i),
                (cx - 15, cy + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2,
                cv2.LINE_AA,
            )

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(
                str(output_path), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 92]
            )
        return canvas

    # ------------------------------------------------------------------
    # 7. Smart / Manual tiling
    # ------------------------------------------------------------------
    def auto_tiles(
        self,
        result: PlacementResult,
        paper: str = "A4",
        orientation: str = "portrait",
        overlap_mm: float = 20.0,
        smart: bool = True,
    ) -> List[TileRect]:
        """Generate a list of TileRect covering the design."""
        part_w, part_h = get_paper_dims(paper, orientation)
        canvas_w_px = int(result.final_w_mm * self.print_dpi / 25.4)
        canvas_h_px = int(result.final_h_mm * self.print_dpi / 25.4)

        underlay = cv2.resize(
            result.mask, (canvas_w_px, canvas_h_px), interpolation=cv2.INTER_AREA
        )

        if smart:
            ys, xs = np.where(underlay > 128)
            if len(xs) and len(ys):
                min_x = max(0, int(np.min(xs)) - 50)
                max_x = min(canvas_w_px, int(np.max(xs)) + 50)
                min_y = max(0, int(np.min(ys)) - 50)
                max_y = min(canvas_h_px, int(np.max(ys)) + 50)
            else:
                min_x, max_x, min_y, max_y = 0, canvas_w_px, 0, canvas_h_px
        else:
            min_x, max_x, min_y, max_y = 0, canvas_w_px, 0, canvas_h_px

        part_w_px = int(part_w * self.print_dpi / 25.4)
        part_h_px = int(part_h * self.print_dpi / 25.4)
        overlap_px = int(overlap_mm * self.print_dpi / 25.4)

        work_w = max_x - min_x
        work_h = max_y - min_y
        cols = math.ceil(work_w / (part_w_px - overlap_px)) if work_w > 0 else 1
        rows = math.ceil(work_h / (part_h_px - overlap_px)) if work_h > 0 else 1

        tiles: List[TileRect] = []
        idx = 1
        for row in range(rows):
            for col in range(cols):
                start_x = min_x + col * (part_w_px - overlap_px)
                start_y = min_y + row * (part_h_px - overlap_px)
                end_x = min(start_x + part_w_px, canvas_w_px)
                end_y = min(start_y + part_h_px, canvas_h_px)

                if smart:
                    slice_mask = underlay[start_y:end_y, start_x:end_x]
                    if not np.any(slice_mask > 128):
                        continue

                # convert to mm
                x_mm = start_x * 25.4 / self.print_dpi
                y_mm = start_y * 25.4 / self.print_dpi
                w_mm = (end_x - start_x) * 25.4 / self.print_dpi
                h_mm = (end_y - start_y) * 25.4 / self.print_dpi
                tiles.append(
                    TileRect(x_mm, y_mm, w_mm, h_mm, label=f"P{idx}")
                )
                idx += 1
        return tiles

    def export_tiles(
        self,
        result: PlacementResult,
        tiles: List[TileRect],
        pads: Optional[List[LEDPad]] = None,
        output_dir: Path = Path("."),
        paper: str = "A4",
        orientation: str = "portrait",
    ) -> List[Path]:
        """Crop the master canvas according to the given tiles and save JPGs."""
        master = self.render_master_jpg(result, pads=pads)
        part_w, part_h = get_paper_dims(paper, orientation)
        part_w_px = int(part_w * self.print_dpi / 25.4)
        part_h_px = int(part_h * self.print_dpi / 25.4)

        out_dir = Path(output_dir) / "Parts_To_Print"
        out_dir.mkdir(parents=True, exist_ok=True)
        saved: List[Path] = []

        for i, t in enumerate(tiles, 1):
            sx = int(t.x_mm * self.print_dpi / 25.4)
            sy = int(t.y_mm * self.print_dpi / 25.4)
            ex = int((t.x_mm + t.w_mm) * self.print_dpi / 25.4)
            ey = int((t.y_mm + t.h_mm) * self.print_dpi / 25.4)

            sx = max(0, sx)
            sy = max(0, sy)
            ex = min(master.shape[1], ex)
            ey = min(master.shape[0], ey)

            slice_img = master[sy:ey, sx:ex]
            page = np.full((part_h_px, part_w_px, 3), 255, np.uint8)
            page[0 : slice_img.shape[0], 0 : slice_img.shape[1]] = slice_img

            cv2.rectangle(
                page,
                (0, 0),
                (slice_img.shape[1], slice_img.shape[0]),
                (200, 200, 200),
                2,
            )
            label = t.label or f"PART {i}"
            cv2.putText(
                page,
                f"{label} - Align edges to overlap",
                (40, 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 0),
                2,
            )

            path = out_dir / f"Piece_{i:02d}_{paper}_{orientation}.jpg"
            cv2.imwrite(str(path), page, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            saved.append(path)
        return saved

    def export_csv(
        self,
        pads: List[LEDPad],
        output_path: Path,
    ) -> Path:
        """Write LED centres + tangent to CSV."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            import csv

            writer = csv.writer(f)
            writer.writerow(["index", "x_mm", "y_mm", "tx", "ty"])
            for i, p in enumerate(pads):
                writer.writerow([i, f"{p.x_mm:.4f}", f"{p.y_mm:.4f}", f"{p.tx:.6f}", f"{p.ty:.6f}"])
        return output_path
