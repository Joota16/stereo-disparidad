"""Prepara imagenes en resolucion Quarter y Half a partir del par estéreo de Middlebury."""

import argparse
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np

from src.common.io_utils import read_calib, read_pfm


def save_pfm(path: Path, disparity: np.ndarray) -> None:
    """Guarda mapa de disparidad en formato PFM."""
    if disparity.ndim != 2:
        raise ValueError("Se requiere un mapa de disparidad 2D")
    height, width = disparity.shape
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        output.write(f"Pf\n{width} {height}\n-1.0\n".encode("ascii"))
        np.flipud(np.asarray(disparity, dtype="<f4")).tofile(output)


def scale_ground_truth(gt: np.ndarray, size: tuple[int, int], factor: float) -> np.ndarray:
    """Escala el ground truth a menor resolucion filtrando zonas invalidas."""
    valid = np.isfinite(gt)
    weighted_sum = cv2.resize(
        np.where(valid, gt, 0).astype(np.float32),
        size,
        interpolation=cv2.INTER_AREA,
    )
    fraction_valid = cv2.resize(
        valid.astype(np.float32), size, interpolation=cv2.INTER_AREA
    )
    scaled_gt = np.full((size[1], size[0]), np.inf, dtype=np.float32)
    safe = fraction_valid >= 0.999999
    scaled_gt[safe] = (weighted_sum[safe] / fraction_valid[safe]) * factor
    return scaled_gt


def formatted_calibration(calib: dict, factor: float, height: int, width: int) -> str:
    lines = [
        "# Calibracion derivada de Adirondack_full: intrinsecos y disparidades escalados",
        "# No confundir con la calibracion oficial Middlebury de las versiones Q/H",
    ]
    for key, value in calib.items():
        if key in ("cam0", "cam1"):
            matrix = np.asarray(value, dtype=np.float64).copy()
            if matrix.shape != (3, 3):
                raise ValueError(f"Matriz de camara invalida: {key}")
            matrix[0, :] *= factor
            matrix[1, :] *= factor
            body = "; ".join(
                " ".join(f"{float(v):.10g}" for v in row) for row in matrix
            )
            lines.append(f"{key}=[{body}]")
        elif key == "width":
            lines.append(f"{key}={width}")
        elif key == "height":
            lines.append(f"{key}={height}")
        elif key == "ndisp":
            lines.append(f"{key}={math.ceil(float(value) * factor)}")
        elif key in ("doffs", "vmin", "vmax", "dyavg", "dymax"):
            lines.append(f"{key}={float(value) * factor:.10g}")
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def prepare_scene(root: Path, scene: str) -> None:
    raw = root / "data" / "raw" / f"{scene}_full"
    ground = root / "data" / "ground_truth" / f"{scene}_full"
    left = cv2.imread(str(raw / "im0.png"), cv2.IMREAD_UNCHANGED)
    right = cv2.imread(str(raw / "im1.png"), cv2.IMREAD_UNCHANGED)
    if left is None or right is None or left.shape != right.shape:
        raise ValueError("Faltan imágenes originales o sus dimensiones no coinciden")
    if left.dtype != np.uint8 or right.dtype != np.uint8:
        raise ValueError("Las imágenes originales deben ser uint8")

    original_gt = read_pfm(ground / "disp0.pfm")
    calib = read_calib(raw / "calib.txt")
    height, width = left.shape[:2]
    if original_gt.shape != (height, width):
        raise ValueError("La forma del ground truth no coincide con las imágenes")
    if int(calib.get("ndisp", -1)) <= 0:
        raise ValueError("calib.txt debe incluir ndisp positivo")
    if int(calib.get("width", -1)) != width or int(calib.get("height", -1)) != height:
        raise ValueError("Las dimensiones de calib.txt no coinciden con las imágenes")

    for name, factor in (("H", 0.5), ("Q", 0.25)):
        scaled_width = round(width * factor)
        scaled_height = round(height * factor)
        if (scaled_width, scaled_height) != (width * factor, height * factor):
            raise ValueError("Se requieren dimensiones divisibles por 4 para escalado exacto")
        size = (scaled_width, scaled_height)
        dst_raw = root / "data" / "raw" / f"{scene}_{name}"
        dst_gt = root / "data" / "ground_truth" / f"{scene}_{name}"
        dst_raw.mkdir(parents=True, exist_ok=True)
        dst_gt.mkdir(parents=True, exist_ok=True)

        if not cv2.imwrite(str(dst_raw / "im0.png"), cv2.resize(left, size, interpolation=cv2.INTER_AREA)):
            raise OSError("No se pudo guardar im0.png")
        if not cv2.imwrite(str(dst_raw / "im1.png"), cv2.resize(right, size, interpolation=cv2.INTER_AREA)):
            raise OSError("No se pudo guardar im1.png")

        reduced_gt = scale_ground_truth(original_gt, size, factor)
        save_pfm(dst_gt / "disp0.pfm", reduced_gt)
        (dst_raw / "calib.txt").write_text(
            formatted_calibration(calib, factor, scaled_height, scaled_width),
            encoding="utf-8",
        )
        provenance = {
            "scene": scene,
            "calibration": "perfect",
            "origin": "Middlebury Stereo 2014 (full-size original scene)",
            "derivation": "Local rescaling; NOT official H/Q benchmark files",
            "scale": factor,
            "resolution_hw": [scaled_height, scaled_width],
            "ndisp": math.ceil(float(calib["ndisp"]) * factor),
            "images": "cv2.INTER_AREA",
            "ground_truth": "validity-aware INTER_AREA, disparity multiplied by scale",
            "invalid_ground_truth": "inf; any output pixel with partial invalid coverage is invalid",
        }
        (dst_raw / "provenance.json").write_text(
            json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        check_gt = read_pfm(dst_gt / "disp0.pfm")
        check_calib = read_calib(dst_raw / "calib.txt")
        assert check_gt.shape == (scaled_height, scaled_width)
        assert check_calib["ndisp"] == provenance["ndisp"]
        print(
            f"{name}: imágenes y GT {scaled_height}x{scaled_width} | "
            f"ndisp={provenance['ndisp']} | "
            f"GT válidos={np.count_nonzero(np.isfinite(check_gt)):,}/{check_gt.size:,}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default="Adirondack")
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    prepare_scene(args.root, args.scene)


if __name__ == "__main__":
    main()
