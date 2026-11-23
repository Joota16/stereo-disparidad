# Proyecto 5: Visión Estéreo Paralela y Distribuida
## Informe Final — Secciones de Visión Estéreo, Dataset y Evaluación de Calidad (Actividad T23)
**Autor:** Alexander (Integrante A)  
**Revisor:** Jhunior (Integrante B)  
**Institución:** Universidad Peruana Cayetano Heredia (UPCH)  
**Curso:** Computación Paralela y Distribuida  

---

## 1. Introducción y Definición del Problema

### 1.1. Contexto y Relevancia
La estimación de profundidad tridimensional a partir de imágenes bidimensionales constituye uno de los problemas clásicos y cardinales de la visión por computadora. A diferencia de los sensores activos de tiempo de vuelo (ToF) o LiDAR, los sistemas de visión estéreo pasiva infieren la geometría de la escena mediante la correlación de texturas entre dos imágenes simultáneas adquiridas por cámaras calibradas con desplazamiento horizontal relativo (línea de base $B$). 

El núcleo del cómputo radica en resolver el problema de correspondencia estéreo: para cada píxel $(x, y)$ en la imagen izquierda, determinar su homólogo $(x - d, y)$ en la imagen derecha. La diferencia horizontal de coordenadas $d$ se denomina disparidad y se encuentra inversamente correlacionada con la distancia métrica $Z$ a la cámara mediante la relación óptica proyectiva $Z = (B \cdot f) / d$.

### 1.2. Desafío Computacional y Pregunta de Investigación
A pesar de su simplicidad conceptual, los algoritmos locales de correspondencia densa basados en ventanas de soporte presentan una complejidad temporal intrínseca $O(W \cdot H \cdot K^2 \cdot D_{max})$, donde $W \times H$ define la resolución espacial de la imagen, $K$ representa la dimensión de la ventana de correlación y $D_{max}$ el rango de búsqueda de disparidades. Para secuencias de video o imágenes de alta definición, esta demanda aritmética desborda la capacidad de procesamiento de una arquitectura mononúcleo convencional, requiriendo estrategias de paralelización en memoria compartida y distribución en memoria distribuida.

Sin embargo, la paralelización espacial introduce sobrecostos inevitables: división de dominios, replicación de márgenes de contexto (halos), serialización binaria, transmisión por red local (sockets ZeroMQ sobre TCP) y ensamblado final. Surge así la pregunta central de investigación:
> *¿En qué escalas de resolución espacial, dimensiones de ventana de soporte y cotas de búsqueda de disparidad el procesamiento paralelo local o distribuido entre dos nodos heterogéneos compensa los sobrecostos de comunicación y recombinación de halos frente a la línea base secuencial?*

### 1.3. Hipótesis de Trabajo
Se plantea como hipótesis que, para volúmenes de carga de trabajo reducidos (resoluciones sub-Quarter o ventanas pequeñas), la latencia de serialización, transporte de red y arranque de procesos superará la ganancia de cómputo aritmético, produciendo un factor de aceleración inferior a la unidad ($S(p) < 1.0$). Únicamente cuando la densidad de operaciones por píxel se incrementa drásticamente (altas resoluciones o ventanas amplias), el tiempo de cómputo amortizará los sobrecostos fijos de transporte, alcanzándose un punto de cruce (*break-even point*) empírico.

### 1.4. Delimitación del Alcance
El estudio se restringe estrictamente a tres arquitecturas de referencia:
1. **Línea Base Secuencial ($T_s$):** Implementación determinista en CPU de un solo hilo, libre de concurrencia oculta.
2. **Paralelismo Local Multiproceso ($T_p$ con $p \in \{2, 4\}$):** Ejecución concurrente mediante `multiprocessing` en un procesador multinúcleo con memoria compartida.
3. **Distribución en Dos Nodos Heterogéneos ($T_{dist}$):** Clúster de dos computadoras independientes (estación de escritorio Intel Core i7-12700KF y laptop AMD Ryzen 7 7735HS) comunicadas mediante protocolo ZeroMQ (patrón REQ/REP sobre TCP).

Se excluyen deliberadamente el entrenamiento de modelos de aprendizaje profundo y la aceleración mediante GPU como requisito obligatorio, priorizando el análisis metrológico riguroso de la CPU y la red.

---

## 2. Marco Teórico y Fundamentos Matemáticos del Algoritmo SAD

### 2.1. Geometría Epipolar y Restricción de Correspondencia
Bajo el modelo de cámara estéreo rectificada ideal (planos focales coplanares y ejes ópticos rigurosamente paralelos), las líneas epipolares son colineales con las filas de la matriz de imagen. Esto reduce el espacio de correspondencia de una búsqueda bidimensional $O(W \cdot H)$ en el plano a una búsqueda unidimensional $O(D_{max})$ a lo largo de la misma coordenada vertical $y$.

### 2.2. Operador Sum of Absolute Differences (SAD)
Para cuantificar la similitud fotométrica entre parches locales, se adoptó la función de costo SAD (Suma de Diferencias Absolutas) debido a su robustez métrica y eficiencia de cómputo frente a métricas cuadráticas (SSD) o de normalización estadística (NCC). Dado un píxel de anclaje $(x, y)$, una ventana de soporte cuadrada de dimensión impar $K \times K$ con radio $r = \lfloor K/2 \rfloor$ y una hipótesis de disparidad $d \in [d_{min}, d_{max})$, el costo de correlación $C(x, y, d)$ se define como:

$$C(x, y, d) = \sum_{u=-r}^{r} \sum_{v=-r}^{r} |I_L(x+u, y+v) - I_R(x+u-d, y+v)|$$

Donde $I_L$ e $I_R$ representan las intensidades fotométricas discretas de las imágenes izquierda y derecha normalizadas en escala de grises ($\text{uint8} \in [0, 255]$). Para evitar desbordamientos aritméticos por subdesbordamiento (*underflow*) durante la resta de enteros sin signo, las matrices se proyectan a enteros con signo de 32 bits ($\text{int32}$).

### 2.3. Selección de Disparidad Óptima y Desempate Determinista
La disparidad estimada $d^*(x, y)$ se determina mediante el criterio de optimización Winner-Take-All (WTA):

$$d^*(x, y) = \arg\min_{d \in [d_{min}, d_{max})} C(x, y, d)$$

En situaciones de texturas homogéneas o penumbras donde múltiples disparidades generan costos idénticos mínimos, el algoritmo implementa un criterio de desempate determinista seleccionando sistemáticamente la menor disparidad admitida $d$.

### 2.4. Tratamiento Riguroso de Fronteras y Máscara de Validez
Para garantizar la integridad matemática del estimador estéreo y prevenir accesos a memoria fuera de rango (*out-of-bounds*), se implementa un estricto contrato de validez:
* **Efectos de Margen Perimetral:** Cualquier píxel ubicado a menos de $r$ píxeles de los bordes superior, inferior o laterales no posee un parche completo $K \times K$, por lo cual se le asigna de manera mandatoria el valor centinela `NaN` en el mapa de disparidad y `False` en la máscara binaria `valid_mask`.
* **Límite de Oclusión Epipolar:** Para que una disparidad $d$ sea evaluable, debe cumplirse que $x - r - d \ge 0$. Si el rango dinámico admisible en la coordenada $x$ es inferior a $d_{min}$, el píxel se descarta como inválido.

### 2.5. Partición Espacial y Teoría de Halos Contextuales
Al descomponer la imagen en franjas horizontales para el procesamiento concurrente (tanto local en multiprocessing como distribuido en ZeroMQ), cada trabajador $i$ que procesa el intervalo de filas $[row_{start}, row_{end})$ requiere acceso a un margen de contexto vertical adicional denominado halo.

El radio del halo se establece exactamente como $r = \lfloor K/2 \rfloor$. La franja expandida abarca las filas $[row_{start} - r, row_{end} + r)$. El cálculo del costo SAD sobre los píxeles fronterizos dentro de la franja expandida coincide con absoluta exactitud matemática con el cálculo sobre la imagen global. Tras la finalización del cómputo, la rutina de recombinación `merge_rows` recorta los halos de forma transparente, garantizando una discrepancia absoluta de $0.000000$ píxeles frente a la línea base secuencial.

---

## 3. Dataset Experimental y Calibración Geométrica

### 3.1. Selección del Repositorio Middlebury Stereo 2014
Para posibilitar una validación reproducible y estandarizada, se seleccionó el benchmark internacional Middlebury Stereo Datasets (versión 2014), preferido sobre alternativas como KITTI (restringido a escenas vehiculares con resolución fija $1242 \times 375$ y verdad de terreno dispersa por LiDAR) y ETH3D (cuyas imágenes a resolución completa de 24 MP saturan los búferes de memoria compartida sin aportar valor analítico adicional).

### 3.2. Escena Seleccionada y Estructura de Datos
Se adoptó la escena oficial **Adirondack**, la cual presenta un amplio abanico de desafíos fotométricos: objetos en primer plano con bordes abruptos, superficies lisas de baja textura y oclusiones mutuas. El conjunto experimental se compone de:
* `im0.png`: Imagen rectificada del punto de vista izquierdo ($248 \times 360$ px en resolución Quarter, derivado oficial a escala 0.25).
* `im1.png`: Imagen rectificada del punto de vista derecho.
* `disp0.pfm`: Verdad de terreno oficial en formato de mapa flotante (PFM, coma flotante de 32 bits, little-endian).
* `calib.txt`: Metadatos de calibración óptica intrínseca y extrínseca del par estereoscópico.

### 3.3. Parámetros de Calibración Óptica
El archivo de calibración oficial de la escena provee los parámetros del modelo pinhole:
* Línea de base interocular: $B = 176.252$ mm.
* Distancia focal equivalente: $f = 4161.221$ px (matriz `cam0[0, 0]`).
* Desplazamiento del eje óptico: $doffs = 209.059$ px.

### 3.4. Derivación del Mapa de Profundidad Tridimensional
A partir del mapa de disparidad bidimensional $d(x, y)$ y los parámetros de calibración geométrica provistos, la reconstrucción métrica de profundidad $Z(x, y)$ en milímetros se obtiene mediante la formulación estándar de Middlebury:

$$Z(x, y) = \frac{B \cdot f}{d(x, y) + doffs}$$

Para propósitos de visualización y análisis de coherencia física, los valores se normalizan en metros ($Z / 1000.0$), asignándose valor centinela nulo a zonas donde la disparidad resulta indefinida o negativa.

---

## 4. Metodología y Resultados de Evaluación de Calidad

### 4.1. Protocolo de Evaluación y Restricción de Máscara
La evaluación de exactitud métrica fue instrumentada mediante el módulo `experiments/evaluate_quality.py`. Para asegurar que los estadísticos reflejen fielmente el desempeño del estimador estéreo, el análisis se restringe rigurosamente a la intersección entre la máscara booleana de validez del estimador (`valid_mask`) y los píxeles finitos válidos de la referencia (`np.isfinite(disp0.pfm)`), descartando los 536 píxeles de oclusión absoluta presentes en la escena.

### 4.2. Métricas Formales de Calidad
Se registraron cuatro indicadores estandarizados en la literatura científica:
1. **Error Absoluto Medio (MAE / End-Point Error):**
   $$\text{MAE} = \frac{1}{|V|} \sum_{(x, y) \in V} |d^*(x, y) - d_{GT}(x, y)|$$
2. **Raíz del Error Cuadrático Medio (RMSE):**
   $$\text{RMSE} = \sqrt{\frac{1}{|V|} \sum_{(x, y) \in V} (d^*(x, y) - d_{GT}(x, y))^2}$$
3. **Tasa de Píxeles Anómalos (Bad-Pixel Ratio):** Porcentaje de píxeles evaluados cuya discrepancia absoluta respecto a la verdad de terreno supera el umbral estandarizado $\delta = 1.0$ píxel:
   $$\text{Bad-Pixel Ratio} = \frac{|\{(x, y) \in V : |d^* - d_{GT}| > 1.0\}|}{|V|} \times 100\%$$
4. **Tasa de Inválidos:** Porcentaje de píxeles descartados por el algoritmo debido al margen de radio $r$ de la ventana de soporte.

### 4.3. Análisis de Cobertura Dinámica del Ground Truth
El análisis de distribución de la verdad de terreno reveló que en la resolución Quarter las disparidades reales oscilan en el intervalo continuo $[3.77, 30.33]$ píxeles. En consecuencia:
* Con cota de búsqueda $D_{max} = 16$, el algoritmo cubre el **$60.24\%$** del rango dinámico de profundidad de la escena.
* Con cota de búsqueda $D_{max} = 32$, el algoritmo abarca el **$100.0\%$** del rango dinámico de la escena.

### 4.4. Resultados Cuantitativos Comparativos
La tabla siguiente resume los resultados cuantitativos obtenidos sobre la escena Adirondack Quarter:

| Configuración Evaluada | Ventana ($K$) | Rango $D$ | Cobertura GT | MAE (px) | RMSE (px) | Bad Pixels (%) | Inválidos (%) | Píxeles Evaluados |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `SAD_K5_D16_secuencial` | 5 | [0, 16) | 60.24% | 5.8948 | 8.2269 | 76.35% | 2.71% | 86,328 |
| `SAD_K9_D16_secuencial` | 9 | [0, 16) | 60.24% | 5.2521 | 7.7077 | 69.05% | 5.38% | 83,960 |
| `SAD_K5_D16_multiproceso_p4`| 5 | [0, 16) | 60.24% | 5.8948 | 8.2269 | 76.35% | 2.71% | 86,328 |
| `SAD_K5_D16_distribuido_zmq`| 5 | [0, 16) | 60.24% | 5.8948 | 8.2269 | 76.35% | 2.71% | 86,328 |

### 4.5. Discusión de Hallazgos en Calidad
1. **Invarianza Algorítmica Absoluta:** La comparación entre la modalidad secuencial, multiproceso (4 núcleos) y distribuida (ZeroMQ) arrojó métricas de MAE, RMSE y Bad-Pixel Ratio idénticas hasta el último decimal. Esto demuestra que la estrategia de particionado vertical con halos y recombinación espacial preserva íntegramente la fidelidad del operador SAD, sin degradar la precisión numérica.
2. **Influencia del Tamaño de Ventana ($K$):** El incremento de la ventana de correlación de $K = 5$ a $K = 9$ redujo el error absoluto medio de $5.8948$ a $5.2521$ píxeles y la tasa de píxeles erróneos del $76.35\%$ al $69.05\%$. El mayor soporte espacial mitiga el ruido por ambigüedad fotométrica en zonas lisas, a costa de un incremento marginal en el descarte de bordes perimetrales (la tasa de inválidos aumenta de $2.71\%$ a $5.38\%$).
3. **Distribución Espacial del Error:** Los mapas de error diferencial (`results/t20_quality/error_map_*.png`) evidencian que los errores superiores a $1.0$ px se localizan preferentemente en las discontinuidades de oclusión y en la zona superior de fondo con bajo contraste luminotécnico, concordando con los límites teóricos reconocidos para algoritmos de correspondencia basados exclusivamente en correlación local por bloque.

---

## 5. Referencias Bibliográficas

Hamzah, R. A., & Ibrahim, H. (2016). Literature survey on stereo vision disparity map algorithms. *Journal of Sensors*, 2016, 1–23. https://doi.org/10.1155/2016/8742920

Kuijpers, P. H. N., van der Veen, P. J., & Jonker, P. P. (1996). Stereo vision and 3D reconstruction on a distributed memory system. En *Proceedings of the International Conference on Parallel and Distributed Processing Techniques and Applications (PDPTA)* (pp. 531–542).

Ralha, C. G., Santos, A. M., & Silva, D. C. (2015). Distributed dense stereo matching for 3D reconstruction using parallel-based processing advantages. En *IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)* (pp. 1428–1432). https://doi.org/10.1109/ICASSP.2015.7178225

Scharstein, D., & Szeliski, R. (2002). A taxonomy and evaluation of dense two-frame stereo correspondence algorithms. *International Journal of Computer Vision*, 47(1), 7–42. https://vision.middlebury.edu/stereo/taxonomy-IJCV.pdf

Scharstein, D., Hirschmüller, H., Kitajima, Y., Krathwohl, G., Nešić, N., Wang, X., & Westling, P. (2014). High-resolution stereo datasets with subpixel-accurate ground truth. En *German Conference on Pattern Recognition (GCPR)* (pp. 31–42). Springer, Cham. https://doi.org/10.1007/978-3-319-11752-2_3

Spangenberg, R., Langner, T., Adfeldt, S., & Rojas, R. (2014). Large scale Semi-Global Matching on the CPU. En *IEEE Intelligent Vehicles Symposium (IV)* (pp. 195–201). http://dx.doi.org/10.1109/IVS.2014.6856419

Sucar, L. E., & Gómez, G. (s. f.). *Visión Computacional*. Instituto Nacional de Astrofísica, Óptica y Electrónica (INAOE). Capítulo 6: Visión Estéreo.
