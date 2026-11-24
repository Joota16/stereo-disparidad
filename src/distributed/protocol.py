"""Protocolo de comunicacion: metadatos JSON y buffers binarios NumPy."""

import json
import numpy as np

VERSION = 1
MAX_PIXELS = 4_194_304  # límite de seguridad de la demostración


def _meta_frame(meta):
    return json.dumps(meta, separators=(",", ":")).encode("utf-8")


def _int(value, label, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError(f"{label} invalido")
    return value


def _validate_part(part, height, width, image_height):
    if not isinstance(part, dict):
        raise ValueError("part debe ser un objeto")
    for key in ("worker_id", "row_start", "row_end", "halo_start", "halo_end"):
        _int(part.get(key), key, 0)
    a, b = part["row_start"], part["row_end"]
    hs, he = part["halo_start"], part["halo_end"]
    if not (0 <= hs <= a < b <= he <= image_height and he - hs == height):
        raise ValueError("Limites de franja incorrectos")
    if width < 1:
        raise ValueError("Ancho invalido")


def encode_request(part, left, right, image_height, window_size, d_min, d_max, job_id):
    if not isinstance(job_id, str) or not 1 <= len(job_id) <= 128:
        raise ValueError("job_id invalido")
    if not isinstance(left, np.ndarray) or not isinstance(right, np.ndarray):
        raise ValueError("Se requieren matrices NumPy")
    if left.ndim != 2 or left.shape != right.shape or left.dtype != np.uint8 or right.dtype != np.uint8:
        raise ValueError("Entradas 2D uint8 con iguales dimensiones requeridas")
    h, w = left.shape
    _int(image_height, "image_height", 1)
    _validate_part(part, h, w, image_height)
    _int(window_size, "window_size", 1)
    _int(d_min, "d_min", 0)
    _int(d_max, "d_max", 1)
    if window_size % 2 != 1 or d_max <= d_min:
        raise ValueError("Parametros SAD invalidos")
    if h * w > MAX_PIXELS:
        raise ValueError("Franja demasiado grande para el protocolo")
    metadata = {
        "version": VERSION, "operation": "sad", "job_id": job_id,
        "image_height": image_height, "shape": [h, w], "dtype": "uint8",
        "window_size": window_size, "d_min": d_min, "d_max": d_max,
        "part": part,
    }
    return [_meta_frame(metadata), np.ascontiguousarray(left).tobytes(), np.ascontiguousarray(right).tobytes()]


def decode_request(frames):
    if len(frames) != 3 or len(frames[0]) > 8192:
        raise ValueError("Solicitud malformada")
    meta = json.loads(frames[0].decode("utf-8"))
    if not isinstance(meta, dict) or meta.get("version") != VERSION or meta.get("operation") != "sad":
        raise ValueError("Version u operacion incompatible")
    if meta.get("dtype") != "uint8":
        raise ValueError("Tipo no admitido")
    job_id = meta.get("job_id")
    if not isinstance(job_id, str) or not 1 <= len(job_id) <= 128:
        raise ValueError("job_id invalido")
    shape = meta.get("shape")
    if not isinstance(shape, list) or len(shape) != 2:
        raise ValueError("Forma invalida")
    h, w = (_int(v, "shape", 1) for v in shape)
    if h * w > MAX_PIXELS:
        raise ValueError("Franja excede limite")
    full_height = _int(meta.get("image_height"), "image_height", 1)
    _validate_part(meta.get("part"), h, w, full_height)
    ws = _int(meta.get("window_size"), "window_size", 1)
    d_min = _int(meta.get("d_min"), "d_min", 0)
    d_max = _int(meta.get("d_max"), "d_max", 1)
    if ws % 2 != 1 or d_max <= d_min:
        raise ValueError("Parametros SAD invalidos")
    if len(frames[1]) != h * w or len(frames[2]) != h * w:
        raise ValueError("Bytes de imagen incorrectos")
    left = np.frombuffer(frames[1], dtype=np.uint8).reshape(h, w)
    right = np.frombuffer(frames[2], dtype=np.uint8).reshape(h, w)
    return meta, left, right


def encode_response(meta, disparity, valid_mask, compute_seconds):
    h, w = meta["shape"]
    if disparity.shape != (h, w) or valid_mask.shape != (h, w):
        raise ValueError("Forma de respuesta invalida")
    payload = {
        "version": VERSION, "status": "ok", "job_id": meta["job_id"],
        "worker_id": meta["part"]["worker_id"], "shape": [h, w],
        "disparity_dtype": "<f4", "mask_dtype": "uint8",
        "compute_seconds": float(compute_seconds),
    }
    return [
        _meta_frame(payload),
        np.ascontiguousarray(disparity, dtype="<f4").tobytes(),
        np.ascontiguousarray(valid_mask, dtype=np.uint8).tobytes(),
    ]


def encode_error(message):
    return [_meta_frame({"version": VERSION, "status": "error", "message": str(message)}), b"", b""]


def decode_response(frames, job_id, part, image_width):
    if len(frames) != 3 or len(frames[0]) > 8192:
        raise ValueError("Respuesta malformada")
    meta = json.loads(frames[0].decode("utf-8"))
    if not isinstance(meta, dict) or meta.get("version") != VERSION:
        raise ValueError("Version de respuesta incorrecta")
    if meta.get("status") == "error":
        raise RuntimeError(f"Error remoto: {meta.get('message', 'desconocido')}")
    h = part["halo_end"] - part["halo_start"]
    w = image_width
    if (meta.get("status") != "ok" or meta.get("job_id") != job_id
            or meta.get("worker_id") != part["worker_id"] or meta.get("shape") != [h, w]
            or meta.get("disparity_dtype") != "<f4" or meta.get("mask_dtype") != "uint8"):
        raise ValueError("Metadatos de respuesta incorrectos")
    if len(frames[1]) != h * w * 4 or len(frames[2]) != h * w:
        raise ValueError("Longitud binaria de respuesta incorrecta")
    remote_seconds = meta.get("compute_seconds")
    if not isinstance(remote_seconds, (float, int)) or remote_seconds < 0:
        raise ValueError("Tiempo remoto invalido")
    disparity = np.frombuffer(frames[1], dtype="<f4").reshape(h, w).copy()
    mask_bytes = np.frombuffer(frames[2], dtype=np.uint8)
    if np.any(mask_bytes > 1):
        raise ValueError("Mascara no binaria")
    mask = mask_bytes.reshape(h, w).astype(bool)
    return disparity, mask, float(remote_seconds)
