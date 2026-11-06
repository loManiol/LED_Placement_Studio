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
    gap_mm: float                    # edge-to-edge gap between LED bodies
    spacing_mm: float                # center-to-center = led_dia + gap
    scale: float
    led_dia_mm: float = 5.0          # physical LED body diameter
    underlay: Optional[np.ndarray] = None  # high-res grayscale for preview

    # backward-friendly alias
    @property
    def pitch_mm(self) -> float:
        return self.spacing_mm


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
    def center_spacing_mm(self, gap_mm: float) -> float:
        """Center-to-center distance for a given edge-to-edge body gap."""
        return float(self.led_dia_mm) + float(gap_mm)

    def place_leds(
        self,
        routing_mask: np.ndarray,
        check_mask: np.ndarray,
        gap_mm: float,
    ) -> List[LEDPad]:
        """
        Classic contour placement (corners preferred) with a hard minimum
        centre-to-centre distance of (led_dia + gap). Overlaps are rejected
        in a final pass — spacing is never allowed to collapse.
        """
        spacing_mm = max(self.center_spacing_mm(gap_mm), self.led_dia_mm * 0.5)
        spacing_px = spacing_mm * self.px_per_mm
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

            current_dist = spacing_px  # force a first candidate at the start
            for i in range(len(closed) - 1):
                p1, p2 = closed[i], closed[i + 1]
                dist = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))

                is_corner = tuple(p1) in corner_pts

                if is_corner or current_dist >= spacing_px:
                    step = min(5, max(1, len(closed) // 8))
                    p_prev = closed[max(0, i - step)]
                    p_next = closed[min(len(closed) - 1, i + step)]
                    dx = float(p_next[0] - p_prev[0])
                    dy = float(p_next[1] - p_prev[1])
                    L = float(np.hypot(dx, dy))
                    tx, ty = (1.0, 0.0) if L < 1e-6 else (dx / L, dy / L)

                    cx_mm = float(p1[0]) / self.px_per_mm
                    cy_mm = float(p1[1]) / self.px_per_mm

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

        # Hard overlap guard — full body spacing, no 0.7 fudge
        final: List[LEDPad] = []
        min_d2 = spacing_mm ** 2
        for r in pads_native:
            if all(
                (r[0] - q.x_mm) ** 2 + (r[1] - q.y_mm) ** 2 >= min_d2 for q in final
            ):
                final.append(LEDPad(*r))
        return final

    def place_interior_fill(

        self,
        fill_mask: np.ndarray,
        gap_mm: float,
        existing: Optional[List[LEDPad]] = None,
    ) -> List[LEDPad]:
        """
        Fill the *inside* of the glyph with a hexagonal-ish grid of LEDs,
        respecting centre spacing = led_dia + gap, and staying clear of
        any already-placed edge pads.
        """
        spacing_mm = max(self.center_spacing_mm(gap_mm), self.led_dia_mm * 0.5)
        spacing_px = spacing_mm * self.px_per_mm

        # Shrink mask so fill stays away from the outline by ~half spacing
        erode_r = max(1, int(round(spacing_px * 0.45)))
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (erode_r * 2 + 1, erode_r * 2 + 1)
        )
        inner = cv2.erode(fill_mask, kernel)
        if cv2.countNonZero(inner) == 0:
            return []

        h, w = inner.shape
        existing = existing or []
        min_d2 = spacing_mm ** 2
        pads: List[LEDPad] = []

        # Offset every other row for denser hexagonal packing still ≥ spacing
        row_step = spacing_px
        col_step = spacing_px
        y = float(spacing_px * 0.5)
        row = 0
        while y < h:
            x_off = (spacing_px * 0.5) if (row % 2) else 0.0
            x = float(spacing_px * 0.5 + x_off)
            while x < w:
                ix, iy = int(round(x)), int(round(y))
                if 0 <= iy < h and 0 <= ix < w and inner[iy, ix] > 0:
                    cx_mm = x / self.px_per_mm
                    cy_mm = y / self.px_per_mm
                    ok = True
                    for q in existing:
                        if (cx_mm - q.x_mm) ** 2 + (cy_mm - q.y_mm) ** 2 < min_d2:
                            ok = False
                            break
                    if ok:
                        for q in pads:
                            if (cx_mm - q.x_mm) ** 2 + (cy_mm - q.y_mm) ** 2 < min_d2:
                                ok = False
                                break
                    if ok:
                        pads.append(LEDPad(cx_mm, cy_mm, 1.0, 0.0))
                x += col_step
            y += row_step
            row += 1
        return pads


    def place_leds_domino(
        self,
        routing_mask: np.ndarray,
        check_mask: np.ndarray,
        gap_mm: float,
    ) -> List[LEDPad]:
        """
        Domino strategy — centre-to-centre distance D = gap_mm (NOT Ø+gap).

        Algorithm (per contour):
          1. Place the first centre on the path.
          2. From that centre, walk forward along the path until the
             Euclidean distance reaches exactly D (circle of radius D
             intersecting the outline).
          3. That intersection is the next centre; repeat.

        Result: consecutive LEDs are exactly D apart centre-to-centre,
        following the text like a chain of dominoes.
        """
        # D is pure centre-to-centre (user's gap value)
        D_mm = max(0.3, float(gap_mm))
        D_px = D_mm * self.px_per_mm
        D2 = D_px * D_px

        pads_native: List[Tuple[float, float, float, float]] = []

        binary = (routing_mask > 0).astype(np.uint8)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE
        )

        for c in contours:
            peri = float(cv2.arcLength(c, True))
            if peri < D_px:
                continue

            pts = c.reshape(-1, 2).astype(np.float64)
            if len(pts) < 4:
                continue

            # Closed ring of points
            closed = np.vstack([pts, pts[:1]])
            nseg = len(closed) - 1

            def tangent_at(i: int) -> Tuple[float, float]:
                j = min(i + 1, nseg)
                dx = float(closed[j, 0] - closed[max(i - 1, 0), 0])
                dy = float(closed[j, 1] - closed[max(i - 1, 0), 1])
                L = float(np.hypot(dx, dy))
                if L < 1e-9:
                    return 1.0, 0.0
                return dx / L, dy / L

            def to_mm(pt) -> Tuple[float, float]:
                return float(pt[0]) / self.px_per_mm, float(pt[1]) / self.px_per_mm

            # --- seed: first point on contour ---
            i0 = 0
            tx, ty = tangent_at(i0)
            cx, cy = to_mm(closed[i0])
            pads_native.append((cx, cy, tx, ty))
            last = closed[i0].copy()
            start = last.copy()
            seg_cursor = 0  # only search forward from here

            max_leds_on_contour = max(2, int(peri / D_px) + 2)

            for _ in range(max_leds_on_contour):
                found = False
                best_pt = None
                best_tang = (1.0, 0.0)
                best_seg = seg_cursor

                # Walk segments forward (wrap once around the closed loop)
                for k in range(nseg):
                    i = (seg_cursor + k) % nseg
                    p1 = closed[i]
                    p2 = closed[i + 1]
                    dvec = p2 - p1
                    f = p1 - last
                    a_coef = float(dvec[0] * dvec[0] + dvec[1] * dvec[1])
                    b_coef = 2.0 * float(f[0] * dvec[0] + f[1] * dvec[1])
                    c_coef = float(f[0] * f[0] + f[1] * f[1]) - D2
                    if a_coef < 1e-12:
                        continue
                    disc = b_coef * b_coef - 4.0 * a_coef * c_coef
                    if disc < 0.0:
                        continue
                    sqrt_disc = float(disc ** 0.5)
                    candidates = []
                    for sign in (-1.0, 1.0):
                        a = (-b_coef + sign * sqrt_disc) / (2.0 * a_coef)
                        if 0.0 <= a <= 1.0:
                            candidates.append(a)
                    if not candidates:
                        continue
                    # Prefer the intersection further along this segment
                    a = max(candidates)
                    pt = p1 + a * dvec
                    dist_last = float(np.hypot(pt[0] - last[0], pt[1] - last[1]))
                    if dist_last < D_px * 0.85:
                        continue
                    L = float(np.hypot(dvec[0], dvec[1]))
                    best_tang = (
                        (1.0, 0.0) if L < 1e-9 else (float(dvec[0] / L), float(dvec[1] / L))
                    )
                    best_pt = pt
                    best_seg = i
                    found = True
                    break

                if not found or best_pt is None:
                    break

                # Closed the loop — stop before overlapping the first LED
                if float(np.hypot(best_pt[0] - start[0], best_pt[1] - start[1])) < D_px * 0.5:
                    break

                tx, ty = best_tang
                cx, cy = to_mm(best_pt)
                pads_native.append((cx, cy, tx, ty))
                last = best_pt.copy()
                seg_cursor = best_seg  # continue forward from this segment

        # Global floor: no two centres closer than D (across contours too)
        final: List[LEDPad] = []
        min_d2 = D_mm ** 2
        for r in pads_native:
            if all(
                (r[0] - q.x_mm) ** 2 + (r[1] - q.y_mm) ** 2 >= min_d2 * 0.95
                for q in final
            ):
                final.append(LEDPad(*r))
        return final

    def place_by_mode(
        self,
        thick_mask: np.ndarray,
        gap_mm: float,
        placement_mode: str,
    ) -> List[LEDPad]:
        """Route LEDs according to strategy mode."""
        mode = (placement_mode or "edges").lower().replace(" ", "_")
        check = cv2.dilate(thick_mask, np.ones((3, 3), np.uint8))

        if mode in ("centerline", "classic_centerline"):
            routing = self.get_skeleton(thick_mask)
            return self.place_leds(routing, thick_mask, gap_mm)

        if mode in ("domino", "domino_edges"):
            return self.place_leds_domino(thick_mask, check, gap_mm)

        if mode in ("domino_centerline", "domino_skeleton"):
            # Domino along medial axis — densify skeleton so thin strokes
            # still yield a continuous path (avoids under-fitting).
            routing = self.get_skeleton(thick_mask)
            if cv2.countNonZero(routing) == 0:
                routing = thick_mask
            # Connect broken skeleton pixels, then keep inside the glyph
            routing = cv2.dilate(routing, np.ones((3, 3), np.uint8))
            routing = cv2.bitwise_and(routing, thick_mask)
            # One more light close to bridge 1-pixel gaps
            routing = cv2.morphologyEx(
                routing, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)
            )
            routing = cv2.bitwise_and(routing, thick_mask)
            if cv2.countNonZero(routing) == 0:
                routing = thick_mask
            check = cv2.dilate(routing, np.ones((5, 5), np.uint8))
            check = cv2.bitwise_and(check, thick_mask)
            return self.place_leds_domino(routing, check, gap_mm)

        if mode == "fill":
            edge_pads = self.place_leds_domino(thick_mask, check, gap_mm)
            fill_pads = self.place_interior_fill(thick_mask, gap_mm, existing=edge_pads)
            return edge_pads + fill_pads

        # default: classic edges (corners preferred)
        return self.place_leds(thick_mask, check, gap_mm)

    def _is_on_mask(self, px_mm: float, py_mm: float, mask: np.ndarray) -> bool:
        x_px = int(round(px_mm * self.px_per_mm))
        y_px = int(round(py_mm * self.px_per_mm))
        if y_px < 0 or y_px >= mask.shape[0] or x_px < 0 or x_px >= mask.shape[1]:
            return False
        return bool(mask[y_px, x_px] > 0)

    # ------------------------------------------------------------------
    # 4. Binary search for max-LED gap
    # ------------------------------------------------------------------
    def find_gap_for_max_leds(
        self,
        routing_mask: np.ndarray,
        check_mask: np.ndarray,
        max_leds: int,
        gap_min: float = 0.5,
        gap_max: float = 30.0,
        tol: int = 3,
    ) -> Tuple[float, List[LEDPad]]:
        """
        Binary search over edge-to-edge gap so that len(pads) is as close as
        possible to max_leds without exceeding it.

        Returns (best_gap_mm, pads).
        """
        lo = max(0.0, float(gap_min))
        hi = max(lo + 0.5, float(gap_max))

        best_pads: List[LEDPad] = []
        best_gap = hi
        best_n = -1

        for _ in range(20):
            mid = (lo + hi) / 2.0
            pads = self.place_leds(routing_mask, check_mask, mid)
            n = len(pads)

            if n <= max_leds and n > best_n:
                best_pads = pads
                best_gap = mid
                best_n = n

            if n > max_leds:
                # too dense → increase gap
                lo = mid
            else:
                # room for denser packing → decrease gap
                hi = mid

            if abs(n - max_leds) <= tol and n <= max_leds:
                return mid, pads

        if not best_pads:
            best_pads = self.place_leds(routing_mask, check_mask, best_gap)
        return best_gap, best_pads


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
        placement_mode: str = "edges",  # "edges" | "centerline" | "fill" | "domino"
        max_leds: Optional[int] = None,
        gap_mm: float = 1.0,
        gap_min: float = 0.5,
        gap_max: float = 25.0,
    ) -> PlacementResult:
        """
        Full pipeline: render → scale → route → place LEDs.

        gap_mm = edge-to-edge distance between LED bodies.
        Centre spacing = led_dia_mm + gap_mm.

        If max_leds is given, pads are trimmed after placement (gap stays fixed).
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

        # Fit the design inside the given box (contain).
        # Use the largest scale that keeps both axes within limits.
        # Never enlarge beyond 1:1 of the rendered mask (no upscaling).
        scale = 1.0
        if desired_width_mm > 0 and current_w_mm > 0:
            scale = min(scale, desired_width_mm / current_w_mm)
        if desired_height_mm > 0 and current_h_mm > 0:
            scale = min(scale, desired_height_mm / current_h_mm)
        # If user only set width (height=0), still allow scaling up to that width
        # so a target physical size works as before — but when BOTH are set,
        # contain-fit applies and we do not blow past either edge.
        if desired_width_mm > 0 and desired_height_mm <= 0 and current_w_mm > 0:
            scale = desired_width_mm / current_w_mm
        elif desired_height_mm > 0 and desired_width_mm <= 0 and current_h_mm > 0:
            scale = desired_height_mm / current_h_mm
        elif desired_width_mm > 0 and desired_height_mm > 0:
            sw = desired_width_mm / current_w_mm if current_w_mm > 0 else 1.0
            sh = desired_height_mm / current_h_mm if current_h_mm > 0 else 1.0
            scale = min(sw, sh)  # fit inside box, no crop

        final_w_px = max(1, int(round(w * scale)))
        final_h_px = max(1, int(round(h * scale)))
        final_w_mm = final_w_px / self.px_per_mm
        final_h_mm = final_h_px / self.px_per_mm

        thick_mask = cv2.resize(
            cropped, (final_w_px, final_h_px), interpolation=cv2.INTER_NEAREST
        )

        # Gap is FIXED — never widened for "max LEDs".
        # Max LEDs only trims excess pads after placement at the true gap.
        user_gap = max(0.0, float(gap_mm))
        mode = (placement_mode or "edges").lower()
        used_gap = user_gap
        pads = self.place_by_mode(thick_mask, used_gap, mode)

        if max_leds is not None and max_leds > 0 and len(pads) > max_leds:
            # Keep first max_leds in path order (already roughly sequential)
            pads = pads[: int(max_leds)]

        if mode in ("domino", "domino_edges", "domino_centerline", "domino_skeleton"):
            spacing = max(0.3, float(used_gap))  # gap IS centre-to-centre
        else:
            spacing = self.center_spacing_mm(used_gap)

        return PlacementResult(
            pads=pads,
            mask=thick_mask,
            final_w_mm=final_w_mm,
            final_h_mm=final_h_mm,
            gap_mm=used_gap,
            spacing_mm=spacing,
            scale=scale,
            led_dia_mm=float(self.led_dia_mm),
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
        """
        Generate TileRects covering the design.

        Same grid logic as before, but tiles are always full paper size and
        may extend *past* the design border so LEDs on the edge are not
        clipped when printing.
        """
        part_w, part_h = get_paper_dims(paper, orientation)
        canvas_w_px = int(result.final_w_mm * self.print_dpi / 25.4)
        canvas_h_px = int(result.final_h_mm * self.print_dpi / 25.4)

        underlay = cv2.resize(
            result.mask, (canvas_w_px, canvas_h_px), interpolation=cv2.INTER_AREA
        )

        # Bleed so edge LEDs sit inside the tile, not on the cut line
        bleed_mm = max(float(getattr(result, "led_dia_mm", 5.0) or 5.0), 5.0) + 3.0
        bleed_px = int(bleed_mm * self.print_dpi / 25.4)

        if smart:
            ys, xs = np.where(underlay > 128)
            if len(xs) and len(ys):
                min_x = int(np.min(xs)) - bleed_px
                max_x = int(np.max(xs)) + bleed_px
                min_y = int(np.min(ys)) - bleed_px
                max_y = int(np.max(ys)) + bleed_px
            else:
                min_x, max_x, min_y, max_y = -bleed_px, canvas_w_px + bleed_px, -bleed_px, canvas_h_px + bleed_px
        else:
            min_x, max_x = -bleed_px, canvas_w_px + bleed_px
            min_y, max_y = -bleed_px, canvas_h_px + bleed_px

        part_w_px = int(part_w * self.print_dpi / 25.4)
        part_h_px = int(part_h * self.print_dpi / 25.4)
        overlap_px = int(overlap_mm * self.print_dpi / 25.4)
        step_x = max(1, part_w_px - overlap_px)
        step_y = max(1, part_h_px - overlap_px)

        work_w = max_x - min_x
        work_h = max_y - min_y
        cols = math.ceil(work_w / step_x) if work_w > 0 else 1
        rows = math.ceil(work_h / step_y) if work_h > 0 else 1

        tiles: List[TileRect] = []
        idx = 1
        for row in range(rows):
            for col in range(cols):
                start_x = min_x + col * step_x
                start_y = min_y + row * step_y
                # Full paper size — may extend past the design border
                end_x = start_x + part_w_px
                end_y = start_y + part_h_px

                if smart:
                    # Content test against the real design (clamped sample)
                    csx = max(0, start_x)
                    csy = max(0, start_y)
                    cex = min(canvas_w_px, end_x)
                    cey = min(canvas_h_px, end_y)
                    if cex <= csx or cey <= csy:
                        continue
                    slice_mask = underlay[csy:cey, csx:cex]
                    if not np.any(slice_mask > 128):
                        continue

                x_mm = start_x * 25.4 / self.print_dpi
                y_mm = start_y * 25.4 / self.print_dpi
                tiles.append(
                    TileRect(x_mm, y_mm, part_w, part_h, label=f"P{idx}")
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
        """
        Crop the master according to tiles and save JPGs.

        Tiles may extend past the design border; out-of-bounds areas are
        filled white so edge LEDs still print fully inside the paper.
        """
        master = self.render_master_jpg(result, pads=pads)
        mh, mw = master.shape[:2]
        part_w, part_h = get_paper_dims(paper, orientation)
        part_w_px = int(part_w * self.print_dpi / 25.4)
        part_h_px = int(part_h * self.print_dpi / 25.4)

        out_dir = Path(output_dir) / "Parts_To_Print"
        out_dir.mkdir(parents=True, exist_ok=True)
        saved: List[Path] = []

        for i, t in enumerate(tiles, 1):
            # Tile rect in master pixel space (may be negative / past edges)
            sx = int(round(t.x_mm * self.print_dpi / 25.4))
            sy = int(round(t.y_mm * self.print_dpi / 25.4))
            tw = int(round(t.w_mm * self.print_dpi / 25.4))
            th = int(round(t.h_mm * self.print_dpi / 25.4))
            # Prefer full paper size on the page
            page_w = max(tw, part_w_px)
            page_h = max(th, part_h_px)
            page = np.full((page_h, page_w, 3), 255, np.uint8)

            # Region of tile that overlaps the master
            src_x0 = max(0, sx)
            src_y0 = max(0, sy)
            src_x1 = min(mw, sx + tw)
            src_y1 = min(mh, sy + th)

            if src_x1 > src_x0 and src_y1 > src_y0:
                dst_x0 = src_x0 - sx  # where that lands on the page
                dst_y0 = src_y0 - sy
                slice_img = master[src_y0:src_y1, src_x0:src_x1]
                dh, dw = slice_img.shape[:2]
                page[dst_y0 : dst_y0 + dh, dst_x0 : dst_x0 + dw] = slice_img

            cv2.rectangle(
                page,
                (0, 0),
                (page_w - 1, page_h - 1),
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
