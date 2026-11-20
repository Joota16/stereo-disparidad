
import pytest
import numpy as np

from src.parallel.partition import split_rows
from src.parallel.partition import split_rows, merge_rows

def test_division_exacta():
    parts = split_rows(8, 2, 3)

    assert len(parts) == 2
    assert parts[0]["row_start"] == 0
    assert parts[0]["row_end"] == 4
    assert parts[1]["row_start"] == 4
    assert parts[1]["row_end"] == 8


def test_altura_no_divisible():
    parts = split_rows(10, 3, 5)

    assert [
        (p["row_start"], p["row_end"])
        for p in parts
    ] == [(0, 4), (4, 7), (7, 10)]

    assert [
        (p["halo_start"], p["halo_end"])
        for p in parts
    ] == [(0, 6), (2, 9), (5, 10)]


def test_ventana_invalida():
    with pytest.raises(ValueError):
        split_rows(10, 2, 4)


def test_demasiados_trabajadores():
    with pytest.raises(ValueError):
        split_rows(3, 4, 3)



def make_test_parts(height=10, width=4, workers=3):
    """Construye resultados locales sinteticos."""
    original = np.arange(
        height * width,
        dtype=np.float32
    ).reshape(height, width)

    mask = np.ones((height, width), dtype=bool)

    partitions = split_rows(height, workers, 5)

    parts = []

    for p in partitions:
        hs = p["halo_start"]
        he = p["halo_end"]

        parts.append({
            **p,
            "disparity_map": original[hs:he].copy(),
            "valid_mask": mask[hs:he].copy()
        })

    return parts, original, mask


def test_merge_reconstruye_imagen():
    parts, original, mask = make_test_parts()

    result, valid = merge_rows(parts, 10, 4)

    np.testing.assert_array_equal(result, original)
    np.testing.assert_array_equal(valid, mask)

    assert result.dtype == np.float32
    assert valid.dtype == np.bool_


def test_merge_preserva_invalidos():
    parts, original, _ = make_test_parts()

    # Fila global 4, columna 0
    for p in parts:
        if p["row_start"] <= 4 < p["row_end"]:
            local_row = 4 - p["halo_start"]
            p["valid_mask"][local_row, 0] = False

    result, valid = merge_rows(parts, 10, 4)

    expected = original.copy()
    expected[4, 0] = np.nan

    np.testing.assert_allclose(
        result, expected, equal_nan=True
    )
    assert not valid[4, 0]


def test_merge_detecta_duplicados():
    parts, _, _ = make_test_parts()

    parts.append(parts[0])

    with pytest.raises(ValueError):
        merge_rows(parts, 10, 4)


def test_merge_detecta_filas_faltantes():
    parts, _, _ = make_test_parts()

    parts.pop()

    with pytest.raises(ValueError):
        merge_rows(parts, 10, 4)


def test_merge_detecta_formato_incorrecto():
    parts, _, _ = make_test_parts()

    parts[1]["disparity_map"] = (
        parts[1]["disparity_map"][:-1]
    )

    with pytest.raises(ValueError):
        merge_rows(parts, 10, 4)




def test_un_solo_trabajador():
    parts, original, mask = make_test_parts(
        height=7, width=5, workers=1
    )

    result, valid = merge_rows(parts, 7, 5)

    np.testing.assert_array_equal(result, original)
    np.testing.assert_array_equal(valid, mask)


def test_un_trabajador_por_fila():
    parts, original, mask = make_test_parts(
        height=6, width=4, workers=6
    )

    result, valid = merge_rows(parts, 6, 4)

    np.testing.assert_array_equal(result, original)
    np.testing.assert_array_equal(valid, mask)


def test_ensamblado_fuera_de_orden():
    parts, original, mask = make_test_parts()

    parts.reverse()

    result, valid = merge_rows(parts, 10, 4)

    np.testing.assert_array_equal(result, original)
    np.testing.assert_array_equal(valid, mask)


def test_disparidad_invalida_en_pixel_valido():
    parts, _, _ = make_test_parts()

    parts[0]["disparity_map"][0, 0] = np.nan

    with pytest.raises(ValueError):
        merge_rows(parts, 10, 4)
