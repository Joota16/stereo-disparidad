import numpy as np


def compute_sad(left_gray, right_gray, window_size, d_min, d_max):
    """
    Calcula el mapa de disparidad usando Sum of Absolute Differences (SAD).

    Parametros:
    - left_gray, right_gray: matrices uint8 de dimensiones HxW.
    - window_size: entero impar positivo (K).
    - d_min: disparidad minima (entero >= 0).
    - d_max: cota superior exclusiva (entero > d_min).

    Retorna:
    - disparity_map: float32 HxW, con NaN en pixeles invalidos.
    - valid_mask: bool HxW, True en pixeles validos.
    """
    if window_size % 2 == 0 or window_size <= 0:
        raise ValueError("window_size debe ser impar y positivo")
    if d_min < 0:
        raise ValueError("d_min debe ser no negativo")
    if d_max <= d_min:
        raise ValueError("d_max debe ser estrictamente mayor que d_min")

    h, w = left_gray.shape
    if right_gray.shape != (h, w):
        raise ValueError("Discrepancia en dimensiones de entrada")

    radius = window_size // 2
    disparity_map = np.full((h, w), np.nan, dtype=np.float32)
    valid_mask = np.zeros((h, w), dtype=bool)

    l_int = left_gray.astype(np.int32)
    r_int = right_gray.astype(np.int32)

    for y in range(radius, h - radius):
        y_top = y - radius
        y_bottom = y + radius + 1

        for x in range(radius, w - radius):
            x_left = x - radius
            x_right = x + radius + 1

            max_d_allowed = min(d_max - 1, x_left)
            if max_d_allowed < d_min:
                continue

            patch_l = l_int[y_top:y_bottom, x_left:x_right]
            best_cost = float("inf")
            best_d = d_min

            for d in range(d_min, max_d_allowed + 1):
                rx_left = x_left - d
                rx_right = x_right - d
                patch_r = r_int[y_top:y_bottom, rx_left:rx_right]

                cost = np.sum(np.abs(patch_l - patch_r))
                if cost < best_cost:
                    best_cost = cost
                    best_d = d

            disparity_map[y, x] = float(best_d)
            valid_mask[y, x] = True

    return disparity_map, valid_mask
