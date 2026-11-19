# Alcance y condiciones de exito

**Pregunta:** En que tamanos de imagen, ventanas y rangos de disparidad el procesamiento paralelo o distribuido supera al secuencial despues de considerar comunicacion, sincronizacion y ensamblado?

**Hipotesis:** cargas pequenas pueden estar dominadas por overhead. En cargas grandes podria existir una ganancia neta, a comprobar empiricamente.

**Dentro:** Middlebury, SAD secuencial CPU, franjas con multiprocessing, dos nodos con ZeroMQ, quality metrics, mapas, experimentacion reproducible e informe.

**Fuera:** entrenamiento de redes neuronales, GPU obligatoria, sistemas roboticos, calibracion nueva de camaras, aplicacion web y optimizaciones que cambien la formula SAD entre variantes.

**Condicion de cierre:** las tres arquitecturas producen mapas equivalentes segun pruebas acordadas; se miden tiempos totales, desglose y bytes; se presenta punto de cruce como intervalo observado o se declara que no aparecio.
