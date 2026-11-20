import numpy as np


def compute_error_map(predicted, ground_truth, eval_mask):
    """
    Calcula el mapa de error absoluto diferencial |d_pred - d_gt|.
    En pixeles no evaluados asigna NaN.
    """
    error_map = np.full(predicted.shape, np.nan, dtype=np.float32)
    error_map[eval_mask] = np.abs(predicted[eval_mask] - ground_truth[eval_mask])
    return error_map


def evaluate_disparity(predicted, valid_mask, ground_truth, gt_mask=None, threshold=1.0):
    """
    Calcula metricas estandar de calidad estéreo sobre pixeles evaluables.

    Parametros:
    - predicted: ndarray (H, W), mapa de disparidad estimado.
    - valid_mask: ndarray (H, W), booleano de pixeles validos estimados.
    - ground_truth: ndarray (H, W), disparidad de referencia de Middlebury.
    - gt_mask: ndarray (H, W), mascara opcional de zonas validas en la referencia.
      Si es None, se descartan automaticamente valores NaN o infinitos de ground_truth.
    - threshold: umbral de error para clasificar Bad Pixels (tipicamente 1.0 pixel).

    Retorna diccionario con:
    - mae: Error Absoluto Medio (Mean Absolute Error o End-Point Error - EPE).
    - rmse: Raiz del Error Cuadratico Medio.
    - bad_pixel_ratio: Procentaje [0..100] de pixeles con error > threshold.
    - invalid_ratio: Porcentaje [0..100] de pixeles descartados por el algoritmo.
    - total_pixels: Total de pixeles en la imagen.
    - evaluated_pixels: Pixeles que cumplieron ambos criterios de validez.
    - error_map: Matriz (H, W) con los errores absolutos (NaN en no evaluados).
    """
    # Mascara de referencia valida
    finite_gt = np.isfinite(ground_truth)
    if gt_mask is not None:
        ref_mask = finite_gt & (gt_mask.astype(bool))
    else:
        ref_mask = finite_gt

    # Pixeles evaluables de forma conjunta
    eval_mask = valid_mask & ref_mask
    total_pixels = int(predicted.size)
    evaluated_pixels = int(np.sum(eval_mask))

    # Porcentaje de pixeles marcados como invalidos por el estimador
    invalid_ratio = float((1.0 - (np.sum(valid_mask) / total_pixels)) * 100.0)

    if evaluated_pixels == 0:
        return {
            "mae": float("nan"),
            "rmse": float("nan"),
            "bad_pixel_ratio": float("nan"),
            "invalid_ratio": invalid_ratio,
            "total_pixels": total_pixels,
            "evaluated_pixels": 0,
            "error_map": np.full(predicted.shape, np.nan, dtype=np.float32),
        }

    diff = np.abs(predicted[eval_mask] - ground_truth[eval_mask])

    mae = float(np.mean(diff))
    rmse = float(np.sqrt(np.mean(diff ** 2)))
    bad_pixel_ratio = float(np.mean(diff > threshold) * 100.0)

    error_map = compute_error_map(predicted, ground_truth, eval_mask)

    return {
        "mae": mae,
        "rmse": rmse,
        "bad_pixel_ratio": bad_pixel_ratio,
        "invalid_ratio": invalid_ratio,
        "total_pixels": total_pixels,
        "evaluated_pixels": evaluated_pixels,
        "error_map": error_map,
    }
