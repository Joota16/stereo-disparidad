"""Aplica ajustes puntuales a T19 y T20 sobre el commit revisado de Alexander.

Uso, en la raiz del repositorio, rama derivada de feature/T19-T20-benchmark-calidad:
    python tools/apply_t19_t20_fixes.py

El script compara fragmentos exactos y detiene la operacion si el codigo ya cambio.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def change(text: str, old: str, new: str, description: str, count: int = 1) -> str:
    found = text.count(old)
    if found != count:
        raise RuntimeError(
            f"{description}: se esperaban {count} apariciones y se encontraron {found}. "
            "La rama pudo actualizarse; revisa el cambio manualmente."
        )
    return text.replace(old, new)


def patch_benchmark(text: str) -> str:
    text = change(text,
        '    counterbalance: bool = False,\n) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:',
        '    counterbalance: bool = False,\n    overwrite: bool = False,\n) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:',
        'Parametro de sobrescritura')

    text = change(text,
        '    if warmup < 0:\n        raise ValueError(f"El numero de calentamientos debe ser >= 0 (recibido: {warmup})")\n',
        '    if warmup < 0:\n        raise ValueError(f"El numero de calentamientos debe ser >= 0 (recibido: {warmup})")\n'
        '    if "secuencial" not in modes:\n'
        '        raise ValueError("Se requiere la modalidad secuencial como referencia de speedup")\n'
        '    if len(set(modes)) != len(modes):\n'
        '        raise ValueError("No deben repetirse modalidades en un mismo benchmark")\n',
        'Validar linea base')

    text = change(text,
        '    if runs_csv_p.exists():\n        runs_csv_p.unlink()\n    if summary_csv_p.exists():\n        summary_csv_p.unlink()\n',
        '    runs_csv_p.parent.mkdir(parents=True, exist_ok=True)\n'
        '    summary_csv_p.parent.mkdir(parents=True, exist_ok=True)\n'
        '    if runs_csv_p.resolve() == summary_csv_p.resolve():\n'
        '        raise ValueError("Los CSV de repeticiones y resumen deben tener rutas diferentes")\n'
        '    meta_path = runs_csv_p.with_name(f"{runs_csv_p.stem}_metadata.json")\n'
        '    if not overwrite and any(p.exists() for p in (runs_csv_p, summary_csv_p, meta_path)):\n'
        '        raise FileExistsError("Ya existen resultados: usa otras rutas o --overwrite explicitamente")\n'
        '    if overwrite:\n'
        '        for path in (runs_csv_p, summary_csv_p):\n'
        '            if path.exists():\n'
        '                path.unlink()\n',
        'Proteger resultados previos')

    text = change(text,
        '    meta_path = runs_csv_p.parent / "t19_benchmark_metadata.json"\n'
        '    with open(meta_path, "w", encoding="utf-8") as f:\n',
        '    env_meta["experiment"] = {\n'
        '        "modes": resolved_modes, "repetitions": reps, "warmup": warmup,\n'
        '        "endpoint": endpoint or "loopback local",\n'
        '        "cases": [{"name": c["name"], "K": c["K"], "d_min": c["d_min"],\n'
        '                   "d_max": c["d_max"], "shape": list(c["left"].shape)}\n'
        '                  for c in grid_configs],\n'
        '    }\n'
        '    with open(meta_path, "w", encoding="utf-8") as f:\n',
        'Registrar experimento y metadatos')

    text = change(text,
        '                    equiv = bool(np.array_equal(mask_w, ref_mask) and np.allclose(disp_w, ref_disp, atol=0.0, rtol=0.0, equal_nan=True))\n'
        '                    run_record = {',
        '                    equiv = bool(np.array_equal(mask_w, ref_mask) and np.allclose(disp_w, ref_disp, atol=0.0, rtol=0.0, equal_nan=True))\n'
        '                    if not equiv:\n'
        '                        raise AssertionError(f"Fallo equivalencia en calentamiento: {case_name}, {mode}")\n'
        '                    run_record = {',
        'Rechazar calentamiento no equivalente')

    text = change(text,
        '                    if not equiv:\n'
        '                        print(f"  [ERROR] ¡Fallo de equivalencia en {mode} rep {rep_i+1}!", flush=True)\n',
        '                    if not equiv:\n'
        '                        raise AssertionError(\n'
        '                            f"Fallo equivalencia: {case_name}, {mode}, repeticion {rep_i+1}"\n'
        '                        )\n',
        'Rechazar repeticion no equivalente')

    text = change(text,
        '"tipo_conexion": "loopback" if is_loopback else "lan_remota",',
        '"tipo_conexion": (("loopback" if is_loopback else "lan_remota")\n'
        '                                   if mode.startswith("distribuido") else "local"),',
        'Separar local de LAN', count=3)

    text = change(text,
        '                if mode.startswith("distribuido"):\n'
        '                    efficiency = "N/A"\n'
        '                    note = "Cluster heterogeneo PC+Laptop; eficiencia homogenea no aplicable."\n',
        '                if mode.startswith("distribuido"):\n'
        '                    efficiency = "N/A"\n'
        '                    note = ("Control ZeroMQ loopback; no representa dos nodos fisicos."\n'
        '                            if mode == "distribuido_loopback"\n'
        '                            else "Cluster heterogeneo PC+Laptop; eficiencia homogenea no aplicable.")\n',
        'Nota metodologica loopback')

    text = change(text,
        '    data_dir = Path("data/raw/adirondack_Q")',
        '    data_dir = Path("data/raw/Adirondack_Q")',
        'Ruta Middlebury en filesystem case sensitive')

    text = change(text,
        '    parser.add_argument("--counterbalance", action="store_true", help="Alternar orden de modalidades")\n',
        '    parser.add_argument("--counterbalance", action="store_true", help="Aleatorizar el orden de bloques por configuracion")\n'
        '    parser.add_argument("--overwrite", action="store_true", help="Sobrescribir archivos de salida existentes")\n',
        'Bandera de seguridad')
    text = change(text,
        '        counterbalance=args.counterbalance,\n    )',
        '        counterbalance=args.counterbalance,\n        overwrite=args.overwrite,\n    )',
        'Propagar bandera de seguridad')
    return text


def patch_quality(text: str) -> str:
    helper = '''def ground_truth_range_coverage(ground_truth: np.ndarray, d_min: int, d_max: int) -> float:
    """Porcentaje de GT valido con disparidades en [d_min, d_max)."""
    if d_max <= d_min:
        raise ValueError("d_max debe ser mayor que d_min")
    valid = np.isfinite(ground_truth) & (ground_truth >= 0)
    total = int(np.count_nonzero(valid))
    if total == 0:
        raise ValueError("Ground truth sin pixeles validos no negativos")
    covered = int(np.count_nonzero(
        valid & (ground_truth >= d_min) & (ground_truth < d_max)
    ))
    return 100.0 * covered / total


'''
    text = change(text,
        'def run_quality_evaluation(\n',
        helper + 'def run_quality_evaluation(\n',
        'Funcion de cobertura basada en GT')
    text = change(text,
        '    gt_valid = gt_disp[np.isfinite(gt_disp)]',
        '    gt_valid = gt_disp[np.isfinite(gt_disp) & (gt_disp >= 0)]',
        'Excluir GT negativo')
    text = change(text,
        '        coverage_pct = round(min(100.0, max(0.0, (min(dm, gt_max) - c[\'d_min\']) / (gt_max - gt_min) * 100.0)), 2)',
        '        coverage_pct = round(ground_truth_range_coverage(gt_disp, c["d_min"], dm), 2)',
        'Corregir cobertura no uniforme')
    text = change(text,
        '        metrics = evaluate_disparity(disp, mask, gt_disp, threshold=1.0)',
        '        metrics = evaluate_disparity(\n'
        '            disp, mask, gt_disp,\n'
        '            gt_mask=np.isfinite(gt_disp) & (gt_disp >= 0), threshold=1.0\n'
        '        )',
        'Respetar mascara GT en metricas')
    text = change(text,
        '    if windows is None:\n        windows = [5, 9]\n',
        '    if windows is None:\n        windows = [5, 9]\n'
        '    if not windows or any(k < 1 or k % 2 == 0 for k in windows):\n'
        '        raise ValueError("Se requiere al menos una ventana impar positiva")\n'
        '    if d_max <= 0:\n'
        '        raise ValueError("d_max debe ser positivo")\n',
        'Validar parametros calidad')
    text = change(text,
        '    data_dir: str = "data/raw/adirondack_Q",\n'
        '    gt_path: str = "data/ground_truth/adirondack_Q/disp0.pfm",',
        '    data_dir: str = "data/raw/Adirondack_Q",\n'
        '    gt_path: str = "data/ground_truth/Adirondack_Q/disp0.pfm",',
        'Rutas por defecto calidad')
    text = change(text,
        '    parser.add_argument("--data-dir", default="data/raw/adirondack_Q")\n'
        '    parser.add_argument("--gt", default="data/ground_truth/adirondack_Q/disp0.pfm")',
        '    parser.add_argument("--data-dir", default="data/raw/Adirondack_Q")\n'
        '    parser.add_argument("--gt", default="data/ground_truth/Adirondack_Q/disp0.pfm")',
        'Rutas CLI calidad')
    return text


def main() -> None:
    sources = {
        ROOT / "experiments/run_benchmark_grid.py": patch_benchmark,
        ROOT / "experiments/evaluate_quality.py": patch_quality,
    }
    # Aplicar atomicamente respecto de las comprobaciones de contexto.
    updated = {}
    for path, patch_func in sources.items():
        if not path.is_file():
            raise FileNotFoundError(f"No existe {path}. Verifica la rama de Alexander.")
        original = path.read_text(encoding="utf-8")
        modified = patch_func(original)
        compile(modified, str(path), "exec")
        updated[path] = modified

    for path, modified in updated.items():
        path.write_text(modified, encoding="utf-8")
        print(f"ACTUALIZADO: {path.relative_to(ROOT)}")
    print("Cambios aplicados. Ejecuta pytest antes de confirmar el commit.")


if __name__ == "__main__":
    main()
