"""Particion y ensamblado por franjas horizontales con halos."""
import numpy as np


def split_rows(image_height, workers, window_size):
    """
    Divide una imagen en franjas horizontales con halos.

    Los intervalos utilizan el convenio [inicio, fin),
    donde fin no está incluido.
    """
    if image_height <= 0:
        raise ValueError("La altura debe ser positiva")

    if workers < 1 or workers > image_height:
        raise ValueError("Numero de trabajadores invalido")

    if window_size < 1 or window_size % 2 == 0:
        raise ValueError("La ventana debe ser impar y positiva")

    radius = window_size // 2
    base, remainder = divmod(image_height, workers)

    partitions = []
    start = 0

    for worker_id in range(workers):
        height = base + (1 if worker_id < remainder else 0)
        end = start + height

        partitions.append({
            "worker_id": worker_id,
            "row_start": start,
            "row_end": end,
            "halo_start": max(0, start - radius),
            "halo_end": min(image_height, end + radius)
        })

        start = end

    return partitions


def merge_rows(parts, image_height, image_width):
    """
    Ensambla los resultados de varias franjas SAD.

    Cada elemento de parts debe incluir:
    - row_start, row_end
    - halo_start, halo_end
    - disparity_map: matriz local HxW (incluye halos)
    - valid_mask: mascara local HxW (incluye halos)

    Devuelve:
    - Mapa completo float32
    - Mascara completa bool
    """
    if image_height <= 0 or image_width <= 0:
        raise ValueError("Dimensiones de imagen invalidas")

    disparity = np.full(
        (image_height, image_width),
        np.nan,
        dtype=np.float32
    )

    valid_mask = np.zeros(
        (image_height, image_width),
        dtype=bool
    )

    covered = np.zeros(image_height, dtype=bool)

    for part in parts:
        start = part["row_start"]
        end = part["row_end"]
        halo_start = part["halo_start"]
        halo_end = part["halo_end"]

        if not (
            0 <= halo_start <= start < end
            <= halo_end <= image_height
        ):
            raise ValueError("Limites de franja invalidos")

        local_map = np.asarray(
            part["disparity_map"],
            dtype=np.float32
        )
        local_mask = np.asarray(part["valid_mask"])

        expected_shape = (
            halo_end - halo_start,
            image_width
        )

        if (
            local_map.shape != expected_shape
            or local_mask.shape != expected_shape
        ):
            raise ValueError("Dimensiones locales incorrectas")

        if local_mask.dtype != np.bool_:
            raise ValueError("La mascara debe ser booleana")

        if np.any(covered[start:end]):
            raise ValueError("Existen filas duplicadas")

        # Posiciones locales de las filas utiles
        local_start = start - halo_start
        local_end = local_start + (end - start)

        useful_map = local_map[local_start:local_end]
        useful_mask = local_mask[local_start:local_end]

        if not np.all(np.isfinite(useful_map[useful_mask])):
            raise ValueError(
                "Disparidad no finita en pixeles validos"
            )

        disparity[start:end] = np.where(
            useful_mask,
            useful_map,
            np.nan
        )

        valid_mask[start:end] = useful_mask
        covered[start:end] = True

    if not np.all(covered):
        raise ValueError("Faltan filas por ensamblar")

    return disparity, valid_mask