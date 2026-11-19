# Proyecto 5 - Vision estereo paralela y distribuida

Investigacion sobre el punto de cruce entre ganancia de computo y costo de comunicacion en la estimacion de disparidad estereo.

**Estado actual:** estructura inicial. Los modulos SAD, multiprocessing y ZeroMQ son plantillas pendientes de implementar; no son algoritmos funcionales.

## Alcance acordado
1. **Secuencial:** algoritmo SAD sobre ventanas en CPU.
2. **Paralelo local:** el mismo SAD repartido por franjas con `multiprocessing` (2 y 4 procesos; 8 si el hardware lo permite).
3. **Distribuido real:** dos computadoras con comunicacion ZeroMQ, calculo local y remoto, ensamblado de un unico mapa.

GPU es ampliacion **opcional**, no incluida en esta estructura. Dataset principal: Middlebury Stereo.

## Roles
- **A = Alexander:** dataset, nucleo SAD secuencial, calidad y errores de disparidad.
- **B = Jhunior:** repositorio, particionado/ensamblado, multiprocessing, ZeroMQ y rendimiento.
- Cada modulo necesita pruebas, evidencia y revision del otro integrante antes del merge.

## Instalacion en Windows (PowerShell)
Requiere Python 3.11 o superior, Git y acceso a pip.

```powershell
.\scripts\setup_windows.ps1
.\.venv\Scripts\python.exe -m pytest -q
```

Alternativa manual:
```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Si PowerShell bloquea los scripts, usa la alternativa manual en lugar de cambiar la politica global de ejecucion.

## Estructura
```text
configs/                Configuraciones de experimentos y red (ejemplos)
data/raw/               Pares Middlebury (no subir imagenes pesadas)
data/ground_truth/      Mapas de referencia (no subir)
src/common/             IO, metricas y tiempo
src/stereo/             SAD unico y secuencial (Alexander)
src/parallel/           Franjas, halos y multiprocessing (Jhunior)
src/distributed/        Maestro y trabajador ZeroMQ (Jhunior)
tests/                  Pruebas de unidad/equivalencia (ambos)
experiments/            Ejecutor de benchmarks reproducibles
results/                CSV y datos medidos (ignorado por Git)
figures/                Mapas y graficos generados (ignorado por Git)
docs/                   Alcance, contrato, red, protocolo, bitacora
report/                 Redaccion y bibliografia
.github/                CI, issues y plantilla de PR
scripts/                Preparacion y verificacion de entornos
```

## Contratos compartidos
Consultar `docs/02_contrato_sad.md` y `docs/03_protocolo_mensajes.md` **antes de programar**. Las tres arquitecturas deben emplear el mismo nucleo de calculo y las mismas convenciones de validez/disparidad.

## Reglas Git
- `main`: codigo estable entregable.
- `develop`: integracion del equipo.
- `feature/TXX-descripcion`: una actividad del tablero por rama.
- Pull Requests hacia `develop`, revisados por el otro integrante y con pruebas.
- No subir datasets grandes, entornos virtuales, credenciales ni resultados temporales.

## Orden de implementacion
1. Contratos y datos Middlebury.
2. SAD secuencial y validacion de referencia.
3. Particion/ensamblado con halos y multiprocessing.
4. ZeroMQ entre dos nodos y equivalencia de mapas.
5. Experimentos reproducibles: tiempo total, comunicacion, bytes, speedup, eficiencia, calidad.
6. Informe y defensa cruzada.

**Nota:** `pytest` al crear el repositorio comprueba unicamente estructura/contratos iniciales. No verifica precision ni velocidad hasta implementar los modulos y sus pruebas reales.
