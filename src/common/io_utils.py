import re
from pathlib import Path
import cv2
import numpy as np


def load_stereo_pair(left_path, right_path):
    """Carga y valida un par estereo en escala de grises."""
    left_gray = cv2.imread(str(left_path), cv2.IMREAD_GRAYSCALE)
    right_gray = cv2.imread(str(right_path), cv2.IMREAD_GRAYSCALE)

    if left_gray is None or right_gray is None:
        raise FileNotFoundError("No se pudo cargar una o ambas imagenes del par estereo.")

    if left_gray.shape != right_gray.shape:
        raise ValueError("Las dimensiones del par estereo deben coincidir.")

    return left_gray, right_gray


def read_pfm(file_path):
    """Lee mapas de disparidad de referencia en formato PFM de Middlebury."""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    with open(file_path, "rb") as f:
        header = f.readline().decode("latin-1").strip()
        if header not in ("Pf", "PF"):
            raise ValueError(f"Formato PFM no soportado: {header}")
        is_color = (header == "PF")

        dims_line = f.readline().decode("latin-1").strip()
        while dims_line.startswith("#"):
            dims_line = f.readline().decode("latin-1").strip()
        width, height = map(int, dims_line.split())

        scale_line = f.readline().decode("latin-1").strip()
        scale = float(scale_line)
        endian = "<" if scale < 0 else ">"

        num_channels = 3 if is_color else 1
        data = np.fromfile(f, endian + "f")

        if is_color:
            data = np.reshape(data, (height, width, num_channels))
        else:
            data = np.reshape(data, (height, width))

        # En PFM el origen esta en la esquina inferior izquierda
        return np.flipud(data).astype(np.float32)


def read_calib(file_path):
    """Lee parametros de calibracion desde calib.txt."""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Archivo calib.txt no encontrado: {file_path}")

    params = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()

            if key in ("cam0", "cam1"):
                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", val)
                if numbers:
                    params[key] = np.array([float(n) for n in numbers]).reshape((3, 3))
            else:
                try:
                    params[key] = float(val) if "." in val else int(val)
                except ValueError:
                    params[key] = val
    return params


def save_disparity_colormap(disparity_map, output_path, valid_mask=None):
    """Guarda visualizacion de disparidad usando colormap JET."""
    disp = disparity_map.copy()
    disp = np.nan_to_num(disp, nan=0.0, posinf=0.0, neginf=0.0)

    if valid_mask is not None:
        disp[~valid_mask] = 0.0

    valid_vals = disp[valid_mask] if valid_mask is not None else disp
    min_val = float(np.min(valid_vals)) if valid_vals.size > 0 else 0.0
    max_val = float(np.max(valid_vals)) if valid_vals.size > 0 else 1.0

    if max_val > min_val:
        norm = ((disp - min_val) / (max_val - min_val) * 255.0).astype(np.uint8)
    else:
        norm = np.zeros_like(disp, dtype=np.uint8)

    colored = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
    if valid_mask is not None:
        colored[~valid_mask] = [0, 0, 0]

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_p), colored)
