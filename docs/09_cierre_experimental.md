# Resultados y cierre experimental — Correspondencia estéreo SAD

**Estado:** borrador de cierre técnico, para revisión por ambos integrantes.  
**Versión base del código experimental:** commit `87e916da09f09ae86102dbcd5f296aa31630939d` en `develop`.  
**Fecha de las ejecuciones:** 22–23 de noviembre de 2026, hora de Lima (según carpetas de resultados).

## 1. Alcance evaluado

Se comparó **el mismo algoritmo SAD sobre CPU** en cuatro modalidades: secuencial, multiprocessing con dos procesos (P2), multiprocessing con cuatro procesos (P4) y distribuido entre dos computadoras heterogéneas mediante ZeroMQ sobre LAN. La implementación de SAD y los parámetros de una configuración se mantuvieron iguales entre modalidades. Los resultados distribuidos proceden de dos máquinas físicas, no de un trabajador loopback.

La fuente es la escena **Adirondack** de Middlebury Stereo 2014. Las versiones Quarter (Q) y Half (H) fueron **derivadas localmente de la escena Full**; no se presentan como archivos oficiales Q/H.

- **Quarter:** ROI de 96×160, 160×256 y 224×352; ventanas K=7 y K=15; disparidades enteras en `[0,32)` y `[0,64)`.
- **Half:** ROI de 192×320; K=15 y `[0,64)`; constituye una configuración adicional, no una matriz Half completa.
- **Protocolo formal ejecutado:** diez repeticiones medidas y un calentamiento por modalidad y configuración. En Quarter: 12 configuraciones × 4 modalidades; en Half: una configuración × 4 modalidades.
- **Medición:** tiempo extremo a extremo del cálculo por modalidad; mediana y dispersión de diez repeticiones. Las aceleraciones se definen como `S = mediana(T_secuencial) / mediana(T_modalidad)` para los mismos datos y parámetros. Eficiencia local = `S/p` únicamente para P2 y P4; no se utiliza para los dos nodos heterogéneos.

## 2. Integridad de la evidencia

La consolidación T22 V3 validó **520 ejecuciones medidas**, **52 calentamientos**, **52 filas agregadas**, **18 figuras** y equivalencia de salida de todas las ejecuciones. No se observaron configuraciones LAN con aceleración mayor a uno. Los CSV, metadatos y figuras están en `results/`, excluido de Git; conservar como evidencia externa íntegra junto con el manifiesto SHA-256.

Ruta local de consolidación entregada por la ejecución: `results/t22_cierre_Quarter_Half_20261123_010819/`. El manifiesto `t22_manifiesto.json` documenta fuentes y huellas de entrada.

## 3. Resultados de rendimiento

**Medianas en segundos y aceleraciones; n=10 por modalidad.**

| Resolución / ROI | K | D | Secuencial (s) | P4 (s) | Speedup P4 | LAN (s) | Speedup LAN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q 96×160 | 7 | 32 | 1.2553 | 0.5299 | 2.369 | 1.8268 | 0.687 |
| Q 160×256 | 7 | 32 | 3.6571 | 1.1723 | 3.120 | 4.8085 | 0.761 |
| Q 224×352 | 7 | 32 | 7.3591 | 2.1511 | 3.421 | 9.8125 | 0.750 |
| Q 96×160 | 7 | 64 | 2.2659 | 0.7965 | 2.845 | 2.9211 | 0.776 |
| Q 160×256 | 7 | 64 | 6.9276 | 2.0167 | 3.435 | 8.8211 | 0.785 |
| Q 224×352 | 7 | 64 | 14.2527 | 3.9025 | 3.652 | 17.8356 | 0.799 |
| Q 96×160 | 15 | 32 | 1.2370 | 0.5492 | 2.252 | 1.6075 | 0.769 |
| Q 160×256 | 15 | 32 | 3.7813 | 1.2625 | 2.995 | 4.8308 | 0.783 |
| Q 224×352 | 15 | 32 | 7.7976 | 2.3077 | 3.379 | 9.9406 | 0.784 |
| Q 96×160 | 15 | 64 | 2.1067 | 0.8125 | 2.593 | 2.7335 | 0.771 |
| Q 160×256 | 15 | 64 | 7.4266 | 2.0947 | 3.546 | 10.9092 | 0.681 |
| Q 224×352 | 15 | 64 | 15.6984 | 4.2291 | 3.712 | 18.6155 | 0.843 |
| H 192×320 | 15 | 64 | 10.6907 | 3.2189 | 3.321 | 14.2261 | 0.751 |

**Interpretación:** P4 fue la modalidad de menor tiempo en las 13 configuraciones formales. El distribuido obtuvo `S<1` en las 13; por tanto, **no se observó un punto de cruce favorable a LAN en el conjunto medido**. No se infiere que dicho cruce sea imposible fuera de los tamaños, equipos y parámetros explorados.

La instrumentación T18 en Quarter K7/D32 mostró que el tiempo de cálculo remoto fue, en promedio, aproximadamente **2.5–2.7 veces** el tiempo del cálculo local de su franja. El resultado es compatible con desequilibrio de procesamiento entre nodos. La espera de recepción engloba procesamiento remoto y otros costos; **no equivale a latencia pura de red**, y los tiempos de fases parcialmente solapadas no deben sumarse.

En Quarter 224×352, K15/D64, P2 mostró speedup 2.051× y eficiencia aparente 1.026. Se conserva como medida observada; no implica más del 100 % de capacidad física, ni justifica generalizar una aceleración superlineal.

## 4. Resultados de calidad estéreo

Se compararon las estimaciones SAD frente al ground truth Quarter derivado, utilizando un umbral Bad Pixels de **error absoluto mayor que 1 píxel**. Las cuatro configuraciones también se evaluaron sobre una **máscara común de 332,812 píxeles**, para evitar que diferencias de bordes inválidos entre K7 y K15 alteren el conjunto de evaluación.

| Configuración | MAE (px) | RMSE (px) | Bad Pixels (%) |
|---|---:|---:|---:|
| K7/D32 | 11.6658 | 16.4066 | 80.68 |
| K7/D64 | 11.1208 | 16.9174 | 71.17 |
| K15/D32 | 10.1593 | 15.2044 | 73.54 |
| **K15/D64** | **8.8700** | **15.0598** | **60.49** |

En la evaluación original de cada ventana, los porcentajes inválidos del estimador fueron **2.03 % en K7** y **4.71 % en K15**. La cobertura de rango GT Quarter fue **59.84 % para D32** y **100 % para D64**. Cobertura no significa precisión.

**Estratificación sobre la misma máscara:**

| Grupo de disparidad GT | MAE K7/D32 | MAE K7/D64 | MAE K15/D32 | MAE K15/D64 |
|---|---:|---:|---:|---:|
| GT `[0,32)` | 6.6661 | 11.5920 | **5.3980** | 9.3171 |
| GT `[32,64)` | 18.9361 | 10.4356 | 17.0829 | **8.2200** |

Aumentar D mejora la representación de disparidades altas, pero puede empeorar las correspondencias del grupo de disparidades bajas. K15/D64 presenta el mejor desempeño **global medido**, no precisión elevada: su Bad Pixels global sigue en 60.49 %. El paralelismo aceleró el cálculo sin alterar sus métricas de calidad, tal como se verificó para secuencial y P4.

## 5. Limitaciones y validez

1. El estudio de rendimiento utiliza **ROI**, no todas las imágenes completas, y la evaluación formal Half se limita a un caso.
2. Las imágenes Q y H y su ground truth son derivados locales de Full; registrar la procedencia y escalado. Half/D64 no abarca todas las disparidades GT válidas de Half.
3. La comparación de rendimiento Q frente a H no aísla un efecto exclusivo de la resolución: también cambian tamaño de ROI, ventana y rango.
4. Dos equipos heterogéneos constituyen un entorno de observación específico. Registrar procesador, RAM, sistema, software, energía y conexión de **ambos** nodos; el JSON automático de T19 describe el maestro.
5. El orden de ejecución por modalidad fue fijo; factores temporales, térmicos y carga del sistema podrían influir en los tiempos.
6. El estudio reporta descriptivos de diez repeticiones y no demuestra significancia estadística; tampoco extrapola un punto de cruce.
7. La comparación controlada de calidad utiliza 332,812 píxeles comunes. No confundir esas métricas con las calculadas originalmente sobre máscaras diferentes.
8. El algoritmo SAD es básico, sin tratamiento avanzado de oclusiones/discontinuidades; no reclamar calidad alta ni equivalencia con algoritmos estéreo modernos.

## 6. Evidencias por conservar

- `results/t22_cierre_Quarter_Half_20261123_010819/`: tablas, 18 figuras, manifiesto y lista de fuentes con SHA-256.
- `runs.csv`, `summary.csv` y `runs_metadata.json` de cada configuración formal; el manifiesto permite enlazarlos a la consolidación.
- Los cuatro `t20_metricas_calidad.csv`, el estratificado K7 y `t20_mascara_comun_*/comparacion.csv`.
- Los scripts de análisis T20 (`t20_analisis_por_rango.py`, `t20_mascara_comun.py`) y consolidadores T22 V2/V3, manteniendo su dependencia explícita.
- El ejecutor paramétrico `experiments/run_roi_study.py` para nuevas reproducciones, sin reemplazar retrospectivamente la procedencia de las ejecuciones ya realizadas.

**Pendientes de archivo final:** revisar legibilidad y ejes de las 18 figuras, registrar hardware/estado energético de ambos nodos, confirmar copia externa íntegra de `results/`, y realizar revisión cruzada del informe con Alexander.
