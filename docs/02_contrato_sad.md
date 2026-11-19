# Contrato comun del nucleo SAD - aprobar entre ambos antes de implementar

Interfaz:
```python
compute_sad(left_gray, right_gray, window_size, d_min, d_max) -> (disparity_map, valid_mask)
```

- Entradas rectificadas, en gris, mismas dimensiones HxW. Se comparan correspondencias de izquierda a derecha.
- `window_size` impar y positivo; radio vertical/horizontal `r = window_size // 2`.
- Disparidades enteras en el intervalo **[d_min, d_max)**, con `d_min >= 0`, `d_max > d_min`.
- Convencion: `d = x_izquierda - x_derecha`. Resolver empate eligiendo la menor disparidad.
- Salida de dimension HxW; mapa de disparidad `float32` y mascara `bool` de misma dimension.
- Para pixeles invalidos, definir `NaN` y `valid_mask=False`; validacion de ventanas completas y limites horizontales.
- Todas las arquitecturas usan el MISMO nucleo SAD y el mismo tratamiento de bordes/invalidos.
- Para franjas: agregar halo vertical `r`; conservar ancho completo, procesar y ensamblar solo filas utiles.
- Equivalencia: comparar mapas y mascaras de secuencial/paralelo/distribuido en iguales parametros.
- Antes de aceptar el contrato, discutir escenas sin candidatos validos, sentinelas de ground truth, disparidad real escalada y overflow al calcular diferencias.
