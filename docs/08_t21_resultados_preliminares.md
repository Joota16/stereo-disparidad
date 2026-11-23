# T21 — Lectura preliminar de los resultados T18

**Naturaleza de los datos:** tiempos medianos compartidos previamente por el equipo
para matrices sintéticas aleatorias, ventana 5×5 y búsqueda `d_max=8`.
No son resultados definitivos de Middlebury; no se dispone aquí de todas las
repeticiones individuales, por lo que no corresponde inferir significancia estadística.

| Imagen | n | Secuencial (s) | P2 (s) | P4 (s) | Distribuido (s) | Speedup P4 | Speedup distribuido |
|---|---:|---:|---:|---:|---:|---:|---:|
| 95x161 | 3 | 0.3777 | 0.3227 | 0.2522 | 0.8402 | 1.498x | 0.450x |
| 192x320 | 5 | 1.5562 | 0.9174 | 0.5593 | 2.3076 | 2.782x | 0.674x |
| 288x480 | 5 | 3.5898 | 1.9120 | 1.0661 | 5.1304 | 3.367x | 0.700x |

## Interpretación delimitada

- Multiproceso 4 obtuvo mayor speedup que multiproceso 2 y que distribuido en los tres tamaños medidos.
- Distribuido fue más lento que secuencial en los tres tamaños ensayados (`speedup < 1`).
- **No se observó un punto de cruce** bajo estos parámetros, y no puede afirmarse que no exista para otros tamaños.
- La comparación se refiere a la CPU maestro y al trabajador remoto específicos; no es una propiedad universal del sistema distribuido.
- `T18` reportó que la CPU remota tardaba considerablemente más que la local en procesar su franja. Parte del resultado puede explicarse por heterogeneidad y costos de comunicación, pero no deben sumarse etapas concurrentes como si fueran secuenciales.
- Para completar T21: usar los tiempos individuales de T19, variar tamaño manteniendo K y D, y registrar metadata de ambos nodos.
