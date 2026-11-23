
# T18 — Resultados preliminares de instrumentación

## Objetivo

Registrar y analizar los tiempos de procesamiento y los
costos de intercambio de datos en la arquitectura SAD
distribuida mediante ZeroMQ.

## Configuración

- Maestro: PC Intel Core i7-12700KF, Ethernet.
- Trabajador: laptop AMD Ryzen 7 7735HS, Wi-Fi.
- Comunicación: ZeroMQ REQ/REP sobre TCP.
- Resolución: 192 × 320 píxeles.
- Ventana SAD: 5 × 5.
- Rango de disparidades: [0, 8).
- Entradas: matrices sintéticas reproducibles.
- Benchmark SAD: 5 repeticiones medidas.
- Control sin SAD: 5 calentamientos y 30 mediciones.

## Comparación de rendimiento

| Modalidad | Tiempo mediano (s) | Speedup |
|---|---:|---:|
| Secuencial | 1.5590 | 1.000 |
| Paralelo 2 | 0.9187 | 1.697 |
| Paralelo 4 | 0.5672 | 2.749 |
| Distribuido | 2.2861 | 0.682 |

Todas las ejecuciones del benchmark verificaron la
equivalencia exacta del mapa y la máscara de validez
respecto al algoritmo SAD secuencial.

## Control de intercambio ZeroMQ sin SAD

| Indicador | Resultado |
|---|---:|
| Mediana (s) | 0.158098 |
| Mínimo (s) | 0.116074 |
| Máximo (s) | 0.426238 |
| Solicitud (bytes) | 62,966 |
| Respuesta (bytes) | 156,969 |
| Repeticiones | 30 |
| Calentamientos descartados | 5 |

## Interpretación

El procesamiento remoto presenta un tiempo mayor que
el procesamiento local sobre franjas comparables.

El control de intercambio sin SAD presenta un tiempo
considerablemente menor que la ejecución distribuida
completa.

Sin embargo, el tiempo de control no representa
latencia pura de red y no puede restarse directamente
del tiempo distribuido para aislar el cálculo.

## Limitaciones

- Resultados exploratorios, no definitivos.
- Entradas sintéticas, no escenas Middlebury.
- Equipos con características de hardware diferentes.
- Comunicación por Wi-Fi con posible variabilidad.
- El cálculo local y remoto se ejecutan simultáneamente.
- Los tamaños de muestra difieren entre experimentos.
- No se ha identificado un punto de cruce.

## Resultado

La instrumentación permite registrar tiempos
extremo a extremo, etapas internas y bytes transferidos.

Se recomienda continuar con experimentos reproducibles
sobre escenas reales y múltiples configuraciones.
