"""Ejecucion paralela en memoria compartida del algoritmo SAD."""

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

import numpy as np

from src.parallel.partition import split_rows, merge_rows
from src.stereo.sad import compute_sad


def _compute_stripe(job):
    """Ejecuta SAD sobre una franja con sus halos."""
    part, left, right, window_size, d_min, d_max = job

    disparity, valid_mask = compute_sad(
        left, right, window_size, d_min, d_max
    )

    return {
        **part,
        "disparity_map": disparity,
        "valid_mask": valid_mask,
    }


def compute_disparity_parallel(
    left_gray,
    right_gray,
    window_size,
    d_min,
    d_max,
    workers,
):
    """Calcula disparidad con varios procesos de CPU."""

    if not isinstance(left_gray, np.ndarray) or not isinstance(
        right_gray, np.ndarray
    ):
        raise ValueError("Las entradas deben ser matrices NumPy")

    if left_gray.ndim != 2 or right_gray.ndim != 2:
        raise ValueError("Las imagenes deben ser 2D")

    if left_gray.shape != right_gray.shape:
        raise ValueError("Las imagenes deben tener igual dimension")

    if left_gray.dtype != np.uint8 or right_gray.dtype != np.uint8:
        raise ValueError("Las imagenes deben ser uint8")

    height, width = left_gray.shape

    if width <= 0:
        raise ValueError("Ancho de imagen invalido")

    if d_min < 0 or d_max <= d_min:
        raise ValueError("Rango de disparidad invalido")

    partitions = split_rows(height, workers, window_size)

    # Un trabajador: ejecutar la linea base directamente.
    if workers == 1:
        return compute_sad(
            left_gray, right_gray,
            window_size, d_min, d_max
        )

    jobs = []

    for part in partitions:
        hs = part["halo_start"]
        he = part["halo_end"]

        jobs.append((
            part,
            np.ascontiguousarray(left_gray[hs:he]),
            np.ascontiguousarray(right_gray[hs:he]),
            window_size,
            d_min,
            d_max,
        ))

    # Los procesos reciben datos independientes.
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=get_context("spawn"),
    ) as executor:
        results = list(executor.map(_compute_stripe, jobs))

    return merge_rows(results, height, width)
