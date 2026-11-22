# Guía de Configuración y Ejecución Distribuida (T16)

Esta guía documenta los pasos para desplegar el cómputo estéreo distribuido entre dos computadoras independientes sobre la misma red de área local (LAN o Wi-Fi), utilizando el protocolo ZeroMQ implementado en el proyecto.

---

## 1. Topología y Roles de los Nodos

| Rol | Equipo | Responsabilidad | Dirección y Puerto |
| :--- | :--- | :--- | :--- |
| **Trabajador (Worker)** | Laptop (Jhunior) | Escucha peticiones ZeroMQ (REP), procesa franja con halo y devuelve disparidad. | `tcp://0.0.0.0:5555` (Bind en todas las interfaces) |
| **Maestro (Master)** | PC (Alexander) | Carga imágenes, divide en 2 franjas con halos, envía franja remota (REQ), computa franja local y ensambla el mapa final. | Se conecta a `tcp://<IP_LAPTOP>:5555` |

---

## 2. Requisitos Previos y Entorno

Ambos equipos deben contar con el repositorio clonado en la rama `develop` y las dependencias instaladas en un entorno Python 3.10+:

```powershell
python -m pip install numpy opencv-python pyzmq pytest
```

Verifique la versión de ZeroMQ y NumPy ejecutando en PowerShell:
```powershell
python -c "import zmq, numpy; print('ZMQ:', zmq.__version__, '| NumPy:', numpy.__version__)"
```

---

## 3. Configuración de Conectividad y Red

### Paso 3.1: Obtener la dirección IP local de la Laptop (Trabajador)
En la Laptop, abra PowerShell y ejecute:
```powershell
ipconfig
```
Localice el adaptador activo (Wi-Fi o Ethernet) y anote la dirección **IPv4** (por ejemplo: `192.168.1.45` o `192.168.137.2`).

### Paso 3.2: Configurar el Firewall de Windows en la Laptop
Para permitir que la PC conecte al puerto TCP 5555 sin desactivar la protección del sistema, ejecute PowerShell como Administrador en la Laptop:

```powershell
netsh advfirewall firewall add rule name="ZeroMQ_SAD_5555" dir=in action=allow protocol=TCP localport=5555
```

*(Si desea revertir la regla al finalizar las pruebas, ejecute:*
`netsh advfirewall firewall delete rule name="ZeroMQ_SAD_5555"`*)*

### Paso 3.3: Diagnóstico de conectividad con `verify_network_node.py`
Antes de ejecutar el algoritmo estéreo, valide la conectividad básica ejecutando la herramienta de diagnóstico:

1. **En la Laptop (Trabajador):**
   ```powershell
   python scripts/verify_network_node.py --mode server --bind tcp://0.0.0.0:5555
   ```

2. **En la PC (Maestro):**
   ```powershell
   python scripts/verify_network_node.py --mode client --connect tcp://<IP_LAPTOP>:5555
   ```

Si la prueba muestra `[OK] Handshake completado exitosamente`, la red está lista para la ejecución de imágenes.

---

## 4. Ejecución del Procesamiento Estéreo Distribuido

### Paso 4.1: Iniciar el nodo Trabajador en la Laptop
En la Laptop, dentro de la raíz del proyecto:
```powershell
python -m src.distributed.worker --bind tcp://0.0.0.0:5555
```
El trabajador quedará a la espera de solicitudes mostrando:
`Trabajador SAD escuchando en tcp://0.0.0.0:5555`.

### Paso 4.2: Iniciar el nodo Maestro en la PC
En la PC, dentro de la raíz del proyecto:
```powershell
python -m src.distributed.master --connect tcp://<IP_LAPTOP>:5555
```
Para ejecutar sobre la imagen real de Middlebury Adirondack (Quarter size):
```powershell
python -m src.distributed.verify_equivalence_distributed --connect tcp://<IP_LAPTOP>:5555
```

---

## 5. Matriz de Errores Comunes y Soluciones

| Síntoma / Error | Causa Raíz | Solución |
| :--- | :--- | :--- |
| `zmq.error.Again: Resource temporarily unavailable` / `TimeoutError` | El Firewall de Windows está bloqueando el puerto 5555 o el trabajador no está corriendo. | 1. Verificar que el trabajador esté iniciado en la Laptop.<br>2. Comprobar la regla de firewall en la Laptop.<br>3. Probar `Test-NetConnection -ComputerName <IP_LAPTOP> -Port 5555` desde la PC. |
| `zmq.error.ZMQError: Address already in use` | Otro proceso tiene tomado el puerto 5555 en la Laptop. | Cambiar a otro puerto (ej. 5556) en ambos comandos con `--bind` y `--connect`, o cerrar el proceso previo con `Stop-Process`. |
| Discrepancia en dimensiones o tipos | Diferencia en el formato de imágenes o parámetros SAD (`d_min`, `d_max`, `window_size`). | El protocolo T15 valida automáticamente metadatos y rechaza peticiones incompatibles con un mensaje descriptivo JSON. |
