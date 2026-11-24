import os
import sys
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)

def set_cell_margins(cell, top=80, bottom=80, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_table_borders(table, color="666666"):
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'bottom', 'insideH']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '6')
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), color)
        tblBorders.append(border)
    for border_name in ['left', 'right', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'none')
        tblBorders.append(border)
    tblPr.append(tblBorders)

def set_borderless_table(table):
    tblPr = table._tbl.tblPr
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'bottom', 'left', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'none')
        tblBorders.append(border)
    tblPr.append(tblBorders)

def add_math_equation(doc, math_xml, eq_number=None):
    """Inserta una ecuacion matematica formal en OMML centrada con numeracion derecha."""
    if eq_number:
        # Tabla de 1 fila y 2 columnas sin bordes para alinear ecuacion al centro y numero a la derecha
        tbl = doc.add_table(rows=1, cols=2)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False
        set_borderless_table(tbl)
        tbl.columns[0].width = Inches(5.8)
        tbl.columns[1].width = Inches(0.7)
        
        cell_eq = tbl.cell(0, 0)
        set_cell_margins(cell_eq, top=40, bottom=40, left=40, right=40)
        p_eq = cell_eq.paragraphs[0]
        p_eq.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_eq.paragraph_format.space_before = Pt(0)
        p_eq.paragraph_format.space_after = Pt(0)
        p_eq._p.append(parse_xml(math_xml))
        
        cell_num = tbl.cell(0, 1)
        set_cell_margins(cell_num, top=40, bottom=40, left=40, right=40)
        p_num = cell_num.paragraphs[0]
        p_num.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_num.paragraph_format.space_before = Pt(0)
        p_num.paragraph_format.space_after = Pt(0)
        r_num = p_num.add_run(f"({eq_number})")
        r_num.font.name = 'Times New Roman'
        r_num.font.size = Pt(11)
        r_num.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
    else:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        p._p.append(parse_xml(math_xml))
        
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)

def add_console_output(doc, command, output_text, title="Terminal de Ejecución"):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(6.5)
    cell = table.cell(0, 0)
    set_cell_background(cell, "F7F7F7")
    set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
    
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for b_name in ['top', 'bottom', 'left', 'right']:
        b = OxmlElement(f'w:{b_name}')
        b.set(qn('w:val'), 'single')
        b.set(qn('w:sz'), '4')
        b.set(qn('w:space'), '0')
        b.set(qn('w:color'), '999999')
        tcBorders.append(b)
    tcPr.append(tcBorders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    
    r_hdr = p.add_run(f"[{title}] PS> {command}\n")
    r_hdr.bold = True
    r_hdr.font.name = 'Consolas'
    r_hdr.font.size = Pt(8.5)
    r_hdr.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
    
    r_out = p.add_run(output_text.strip())
    r_out.font.name = 'Consolas'
    r_out.font.size = Pt(8.0)
    r_out.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)

def format_cell_text(cell, text, bold=False, italic=False, font_size=9.5, align=WD_ALIGN_PARAGRAPH.LEFT):
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(str(text))
    run.bold = bold
    run.italic = italic
    run.font.name = 'Times New Roman'
    run.font.size = Pt(font_size)
    run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

def add_two_column_figures(doc, img_left, cap_left, img_right, cap_right, width_in=3.0):
    """Inserta dos imagenes en paralelo (columnas) con sus respectivas leyendas explicativas."""
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_borderless_table(table)
    table.columns[0].width = Inches(3.25)
    table.columns[1].width = Inches(3.25)
    
    # Columna izquierda
    cell_l = table.cell(0, 0)
    set_cell_margins(cell_l, top=40, bottom=40, left=60, right=60)
    p_img_l = cell_l.paragraphs[0]
    p_img_l.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img_l.paragraph_format.space_before = Pt(0)
    p_img_l.paragraph_format.space_after = Pt(2)
    if os.path.exists(img_left):
        r_l = p_img_l.add_run()
        r_l.add_picture(img_left, width=Inches(width_in))
    p_cap_l = cell_l.add_paragraph()
    p_cap_l.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap_l.paragraph_format.space_before = Pt(2)
    p_cap_l.paragraph_format.space_after = Pt(6)
    r_cap_l = p_cap_l.add_run(cap_left)
    r_cap_l.italic = True
    r_cap_l.font.name = 'Times New Roman'
    r_cap_l.font.size = Pt(8.5)
    r_cap_l.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    
    # Columna derecha
    cell_r = table.cell(0, 1)
    set_cell_margins(cell_r, top=40, bottom=40, left=60, right=60)
    p_img_r = cell_r.paragraphs[0]
    p_img_r.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img_r.paragraph_format.space_before = Pt(0)
    p_img_r.paragraph_format.space_after = Pt(2)
    if os.path.exists(img_right):
        r_r = p_img_r.add_run()
        r_r.add_picture(img_right, width=Inches(width_in))
    p_cap_r = cell_r.add_paragraph()
    p_cap_r.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap_r.paragraph_format.space_before = Pt(2)
    p_cap_r.paragraph_format.space_after = Pt(6)
    r_cap_r = p_cap_r.add_run(cap_right)
    r_cap_r.italic = True
    r_cap_r.font.name = 'Times New Roman'
    r_cap_r.font.size = Pt(8.5)
    r_cap_r.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    
    p_sep = doc.add_paragraph()
    p_sep.paragraph_format.space_before = Pt(0)
    p_sep.paragraph_format.space_after = Pt(4)

def main():
    template_path = r"C:\Users\User\.gemini\antigravity\brain\f93cc015-4092-4da2-aa7e-85cd77ff4a8c\.user_uploaded\media_1795532486353_76422d3a.docx"
    doc = docx.Document(template_path)
    
    # Preservar exactamente la portada original (parrafos 0 a 35)
    p_to_remove = [p._p for p in doc.paragraphs[36:]]
    for p_elem in p_to_remove:
        p_elem.getparent().remove(p_elem)
        
    print(f"Portada original preservada ({len(doc.paragraphs)} parrafos base).")
    doc.add_page_break()
    
    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.name = 'Times New Roman'
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.name = 'Times New Roman'
        run.font.size = Pt(11.5)
        run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
        return p

    def add_p(text, bold_prefix="", space_after=6):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.bold = True
            r_pre.font.name = 'Times New Roman'
            r_pre.font.size = Pt(11)
            r_pre.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
        r_text = p.add_run(text)
        r_text.font.name = 'Times New Roman'
        r_text.font.size = Pt(11)
        r_text.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
        return p

    def add_single_figure(img_path, caption, width_in=3.4):
        if os.path.exists(img_path):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(3)
            p_img.paragraph_format.keep_with_next = True
            r_img = p_img.add_run()
            r_img.add_picture(img_path, width=Inches(width_in))
            
            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_before = Pt(0)
            p_cap.paragraph_format.space_after = Pt(10)
            r_cap = p_cap.add_run(caption)
            r_cap.italic = True
            r_cap.font.name = 'Times New Roman'
            r_cap.font.size = Pt(9.5)
            r_cap.font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    # -------------------------------------------------------------
    # 1. RESUMEN Y ABSTRACT
    # -------------------------------------------------------------
    add_h1("RESUMEN")
    add_p(
        "El presente informe evalúa cuantitativamente el rendimiento computacional, la aceleración y la exactitud geométrica "
        "de la estimación de disparidad estéreo densa, comparando una línea base secuencial centralizada frente a dos variantes "
        "concurrentes: paralelismo local en memoria compartida mediante multiprocessing (2 y 4 núcleos) y una arquitectura "
        "distribuida sobre dos computadoras heterogéneas interconectadas mediante sockets ZeroMQ sobre TCP/IP. Se implementó el "
        "algoritmo de Suma de Diferencias Absolutas (SAD) confinado al eje epipolar horizontal como operador determinista de coincidencia. "
        "Para garantizar la exactitud matemática sin distorsiones en las fronteras de corte, se diseñó un esquema de descomposición espacial "
        "en franjas horizontales suplementadas con halos contextuales de radio r = floor(K/2). El protocolo formal comprendió 520 ejecuciones "
        "medidas y 52 calentamientos sobre la escena Adirondack del repositorio Middlebury 2014 en resoluciones Quarter y Half, variando ventanas "
        "K in {7, 15} y rangos D in {32, 64}. Los resultados confirman que el paralelismo local con 4 núcleos (P4) maximiza el desempeño en "
        "todas las configuraciones, alcanzando factores de aceleración (Speedup) de hasta 3.71x y una eficiencia del 92.8%. Por el contrario, "
        "el clúster distribuido en red LAN física obtuvo aceleraciones sistemáticamente sub-unitarias (Speedup entre 0.68x y 0.84x), no observándose "
        "un punto de cruce favorable en el espacio evaluado. Este comportamiento se fundamenta en la heterogeneidad de los nodos, donde la CPU de la "
        "computadora portátil tardó en promedio entre 2.5 y 2.7 veces más que la estación de sobremesa en computar su respectiva franja (efecto straggler), "
        "sumado a los sobrecostos de serialización binaria y transmisión por red. Asimismo, la verificación numérica demostró una equivalencia estricta "
        "(0.000000 px de discrepancia máxima) frente al secuencial, mientras que la configuración K=15 y D=64 minimizó el error medio a 8.87 px sobre "
        "una máscara común de 332,812 píxeles de evaluación."
    )
    add_p("Visión estéreo, Algoritmo SAD, Computación paralela, ZeroMQ, Speedup, Middlebury Stereo, Heterogeneidad de hardware.", bold_prefix="Palabras clave: ")

    add_h1("ABSTRACT")
    add_p(
        "This research paper quantitatively evaluates the computing performance, speedup, and geometric accuracy of dense stereo disparity "
        "estimation, comparing a centralized sequential CPU baseline against two concurrent paradigms: local shared-memory multiprocessing "
        "(2 and 4 cores) and a distributed architecture deployed across two heterogeneous machines communicating via ZeroMQ over TCP/IP. "
        "The Sum of Absolute Differences (SAD) algorithm confined to the horizontal epipolar line was utilized as the deterministic matching operator. "
        "Spatial domain decomposition was executed via horizontal strip slicing augmented with overlapping halo margins of radius r = floor(K/2) "
        "to prevent edge artifacts. A rigorous benchmark consisting of 520 measured runs and 52 warm-up cycles was evaluated on the Adirondack "
        "scene from Middlebury 2014 at Quarter and Half resolutions, varying window sizes K in {7, 15} and disparity ranges D in {32, 64}. "
        "Empirical findings confirm that 4-core local multiprocessing (P4) achieved the highest throughput across all configurations, reaching "
        "speedups up to 3.71x with a parallel efficiency of 92.8%. Conversely, the physical LAN distributed cluster consistently exhibited "
        "sub-unitary speedups (ranging from 0.68x to 0.84x), demonstrating no favorable crossover point within the tested domain. This limitation "
        "is rigorously traced to hardware heterogeneity, as the laptop CPU required 2.5x to 2.7x more compute time per block than the desktop "
        "station (straggler effect), compounded by binary serialization and network transport latency. Finally, numerical auditing confirmed zero "
        "algorithmic distortion (exact 0.000000 px disparity discrepancy), while the K=15 / D=64 parameter set minimized the global Mean Absolute Error "
        "(MAE) to 8.87 px over a common 332,812-pixel evaluation mask."
    )
    add_p("Stereo vision, SAD algorithm, Parallel computing, ZeroMQ, Speedup, Middlebury Stereo, Heterogeneous computing.", bold_prefix="Keywords: ")

    # -------------------------------------------------------------
    # 2. INTRODUCCIÓN
    # -------------------------------------------------------------
    add_h1("1. INTRODUCCIÓN")
    add_p(
        "La visión por computador desempeña un rol crucial en la robótica móvil autónoma, los sistemas de asistencia a la conducción y la reconstrucción "
        "tridimensional metrológica. Dentro de este campo, la estimación de profundidad a partir de pares de cámaras estéreo emula la visión binocular "
        "humana, infiriendo la distancia física de los objetos mediante la correspondencia de patrones visuales entre dos imágenes capturadas simultáneamente. "
        "El parámetro geométrico fundamental es la disparidad horizontal d, definida como el desplazamiento relativo en píxeles de un punto conjugado entre "
        "la vista izquierda y derecha tras la rectificación epipolar."
    )
    add_p(
        "A pesar de su claridad conceptual, la correspondencia densa es una tarea de alta intensidad computacional. Al evaluar ventanas de soporte "
        "K x K a lo largo de un rango de disparidades D sobre imágenes de dimensiones W x H, la complejidad algorítmica escala en orden O(W * H * K^2 * D). "
        "Para imágenes de alta resolución, esto implica miles de millones de sustracciones enteras y accesos a memoria, lo que genera cuellos de botella "
        "inviables para ejecuciones estrictamente secuenciales en CPU de un solo hilo."
    )
    add_p(
        "El presente trabajo aborda esta problemática explorando la aceleración del algoritmo SAD mediante paralelismo en memoria compartida (multiprocessing) "
        "y computación distribuida en red local con ZeroMQ. La investigación busca determinar empíricamente si la distribución de carga entre dos nodos físicos "
        "compensa los sobrecostos de comunicación, o si el paralelismo local multinúcleo agota las ventajas prácticas en esta escala de problema."
    )
    
    add_h2("1.1. Pregunta de Investigación e Hipótesis")
    add_p(
        "¿En qué condiciones de resolución espacial, tamaño de ventana de soporte y rango de disparidad máxima el procesamiento "
        "paralelo y distribuido ofrece una reducción efectiva del tiempo total de ejecución frente a la línea base secuencial, considerando "
        "los costos de transferencia de datos por red, sincronización y ensamblado del mapa de disparidad?",
        bold_prefix="Pregunta de investigación: "
    )
    add_p(
        "Para entradas de baja resolución o rangos reducidos de búsqueda, el sobrecosto de particionado, serialización y transmisión por red dominará el flujo, "
        "resultando en factores de aceleración inferiores a la unidad (Speedup < 1). A medida que se incremente la resolución de la imagen (de Quarter a Half) "
        "o la demanda combinatoria de correlación (K >= 15, D >= 64), el incremento del volumen computacional superará los costos fijos de red, permitiendo "
        "observar un punto de cruce favorable a la arquitectura distribuida.",
        bold_prefix="Hipótesis de trabajo: "
    )

    add_h2("1.2. Objetivos del Proyecto")
    add_p("Desarrollar y evaluar un sistema de correspondencia estéreo basado en el algoritmo SAD mediante implementaciones secuencial, paralela y distribuida, "
          "determinando las condiciones operativas en las que el reparto de carga reduce el tiempo total de ejecución considerando los sobrecostos de comunicación, "
          "sincronización y recombinación matricial.", bold_prefix="Objetivo General: ")
    add_p("1. Implementar una línea base secuencial en CPU del algoritmo SAD, utilizando pares rectificados del conjunto oficial Middlebury 2014 para generar y validar mapas de disparidad.", bold_prefix="Objetivo Específico 1: ")
    add_p("2. Desarrollar una variante paralela multinúcleo en memoria compartida mediante multiprocessing y particionado en franjas horizontales con halos, verificando la equivalencia matemática estricta con la línea base.", bold_prefix="Objetivo Específico 2: ")
    add_p("3. Implementar una versión distribuida entre dos computadoras independientes mediante ZeroMQ sobre TCP/IP, incorporando transferencia de bloques binarios, cómputo remoto concurrente y ensamblado matricial.", bold_prefix="Objetivo Específico 3: ")
    add_p("4. Comparar experimentalmente las modalidades bajo diversas resoluciones, ventanas y rangos, evaluando precisión métrica (MAE, RMSE, Bad Pixels), tiempo extremo a extremo, aceleración y sobrecostos de red.", bold_prefix="Objetivo Específico 4: ")

    # -------------------------------------------------------------
    # 3. ANTECEDENTES O TRABAJOS RELACIONADOS
    # -------------------------------------------------------------
    add_h1("2. ANTECEDENTES O TRABAJOS RELACIONADOS")
    add_p(
        "La literatura sobre visión estéreo densa clasifica tradicionalmente los métodos de correspondencia en locales, globales y semiglobales "
        "(Scharstein & Szeliski, 2002). Los métodos globales (Graph Cuts, Belief Propagation) plantean una optimización de energía sobre la imagen completa; "
        "si bien producen bordes nítidos, su complejidad cuadrática y fuertes dependencias inter-píxel impiden un particionamiento eficiente en sistemas distribuidos "
        "sin incurrir en severas penalizaciones de sincronización. El método Semi-Global Matching (SGM) de Hirschmüller (2008) aproxima la optimización global "
        "agregando costos a lo largo de 8 o 16 trayectorias radiales; no obstante, como destacan Spangenberg et al. (2014), su demanda masiva de memoria "
        "intermedia dificulta su escalado en clústeres desacoplados."
    )
    add_p(
        "En contraste, los métodos locales basados en ventanas fijas confinan la correlación a regiones de soporte discretas K x K. Hamzah e Ibrahim (2016) "
        "evaluaron exhaustivamente las métricas clásicas: Correlación Cruzada Normalizada (NCC), Suma de Diferencias al Cuadrado (SSD) y Suma de Diferencias "
        "Absolutas (SAD). Su análisis concluyó que mientras NCC exige divisiones y raíces cuadradas en coma flotante por cada píxel y SSD introduce multiplicaciones "
        "cuadráticas repetitivas, el estimador SAD opera estrictamente mediante sustracciones enteras y sumatorias de valores absolutos. Al apoyarse en la "
        "rectificación epipolar (Sucar & Gómez, Cap. 6), la búsqueda se confina al eje horizontal, otorgando independencia matemática a cada fila."
    )
    add_p(
        "Esta simplicidad aritmética convierte a SAD en el operador idóneo para este estudio: al eliminar cuellos de botella flotantes secundarios, cualquier "
        "variación temporal es directamente atribuible a la concurrencia de núcleos, la descomposición en franjas y la latencia del transporte por red. "
        "En el contexto distribuido, Kuijpers et al. (1996) demostraron la necesidad de halos contextuales para evitar distorsiones en fronteras de partición, "
        "mientras que Ralha et al. (2015) remarcaron que en entornos heterogéneos la aceleración queda sujeta al balance exacto entre cómputo local y sobrecosto "
        "de comunicación. Desde el punto de vista teórico, el sistema se rige por la Ley de Amdahl (1967) para la fracción secuencial de serialización y la "
        "Ley de Gustafson (1988) para el escalamiento ante incrementos de carga de trabajo."
    )

    # -------------------------------------------------------------
    # 4. METODOLOGÍA Y DISEÑO DE LA SOLUCIÓN
    # -------------------------------------------------------------
    add_h1("3. METODOLOGÍA Y DISEÑO DE LA SOLUCIÓN")
    add_p(
        "El diseño del sistema se basó en el desacoplamiento modular, asegurando que el operador de cálculo estéreo sea exactamente el mismo en todas "
        "las arquitecturas evaluadas para garantizar comparabilidad científica absoluta."
    )
    
    add_h2("3.1. Formulación Matemática del Operador SAD")
    add_p(
        "Para un par estéreo rectificado conformado por la imagen izquierda I_L y la derecha I_R en escala de grises de dimensiones H x W, "
        "el costo de correlación para un píxel (x, y) bajo una hipótesis de disparidad horizontal d in [d_min, d_max) se define formalmente como:"
    )
    
    # Ecuacion 1: SAD formal en OMML
    sad_omml = """
    <m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:r><m:rPr><m:scr m:val="roman"/><m:sty m:val="p"/></m:rPr><m:t>SAD(x, y, d) = </m:t></m:r>
      <m:nary>
        <m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="undOvr"/></m:naryPr>
        <m:sub><m:r><m:t>u = -r</m:t></m:r></m:sub>
        <m:sup><m:r><m:t>r</m:t></m:r></m:sup>
        <m:e>
          <m:nary>
            <m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="undOvr"/></m:naryPr>
            <m:sub><m:r><m:t>v = -r</m:t></m:r></m:sub>
            <m:sup><m:r><m:t>r</m:t></m:r></m:sup>
            <m:e>
              <m:d>
                <m:dPr><m:begChr m:val="|"/><m:endChr m:val="|"/></m:dPr>
                <m:e>
                  <m:r><m:t>I</m:t></m:r>
                  <m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>L</m:t></m:r></m:sub></m:sSub>
                  <m:r><m:t>(x + u, y + v) - I</m:t></m:r>
                  <m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>R</m:t></m:r></m:sub></m:sSub>
                  <m:r><m:t>(x + u - d, y + v)</m:t></m:r>
                </m:e>
              </m:d>
            </m:e>
          </m:nary>
        </m:e>
      </m:nary>
    </m:oMath>
    """
    add_math_equation(doc, sad_omml, eq_number="1")
    
    add_p(
        "donde r = floor(K / 2) es el radio de soporte de una ventana cuadrada impar de tamaño K x K. La disparidad óptima d*(x, y) se obtiene "
        "determinando el desplazamiento que minimiza la sumatoria de costos acumulados:"
    )
    
    # Ecuacion 2: Disparidad Optima
    disp_omml = """
    <m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:r><m:t>d*(x, y) = </m:t></m:r>
      <m:sSub>
        <m:e><m:r><m:rPr><m:scr m:val="roman"/><m:sty m:val="p"/></m:rPr><m:t>argmin</m:t></m:r></m:e>
        <m:sub><m:r><m:t>d ∈ [d</m:t></m:r><m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>min</m:t></m:r></m:sub></m:sSub><m:r><m:t>, d</m:t></m:r><m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>max</m:t></m:r></m:sub></m:sSub><m:r><m:t>)</m:t></m:r></m:sub>
      </m:sSub>
      <m:r><m:t> SAD(x, y, d)</m:t></m:r>
    </m:oMath>
    """
    add_math_equation(doc, disp_omml, eq_number="2")

    add_h2("3.2. Especificación del Contrato Común Algorítmico")
    add_p("El contrato algorítmico común e inalterable rige la signatura compute_sad(left_gray, right_gray, window_size, d_min, d_max) -> (disparity_map, valid_mask):", bold_prefix="Contrato común: ")
    add_p("• Prevención de desbordamiento: Las matrices de entrada en uint8 se convierten internamente a int32 antes de operar las diferencias, evitando errores de subflujo modular.")
    add_p("• Manejo de fronteras: Se inhibe el cómputo en las franjas periféricas de radio r. En el borde izquierdo donde x - d < 0, la búsqueda se restringe a d_limit = min(d_max - 1, x - r). Los píxeles inválidos se fijan con valor NaN en float32 y False en valid_mask.")
    add_p("• Criterio de desempate: Ante múltiples disparidades con costo mínimo idéntico, se selecciona deterministamente la menor disparidad evaluada, asegurando reproducibilidad exacta entre modalidades.")

    add_h2("3.3. Particionamiento en Franjas con Halos Contextuales")
    add_p(
        "Para evitar discontinuidades en los límites de partición horizontal, el sistema implementa franjas con halos de radio r = floor(K/2). "
        "Cada bloque asignado a un proceso o nodo remoto incluye r filas contextuales adicionales arriba y abajo: [y_start - r, y_end + r]. "
        "Tras la correlación, las r filas de margen se descartan, ensamblando únicamente las franjas internas válidas. "
        "Esto garantiza que el mapa resultante sea píxel a píxel idéntico a la ejecución secuencial monolítica."
    )

    add_h2("3.4. Arquitectura Distribuida Master-Worker sobre ZeroMQ")
    add_p(
        "El sistema distribuido adopta una topología Master-Worker sincrónica sin broker implementada sobre ZeroMQ mediante sockets REQ/REP sobre TCP/IP:"
    )
    add_p("• Nodo Maestro (Master): Carga el par estéreo, particiona el dominio espacial, serializa la franja secundaria mediante tramas multipartes compuestas por cabecera JSON (dimensiones, tipo de dato, K, d_min, d_max) y búferes binarios NumPy uint8 contiguos, transmitiéndola al trabajador remoto mediante el socket REQ. Simultáneamente, el maestro calcula localmente su propia franja primaria. Al recibir la respuesta, deserializa los búferes float32 y uint8 y ensambla el mapa global mediante recombinación de filas.")
    add_p("• Nodo Trabajador (Worker): Permanece a la escucha pasiva en el puerto TCP 5555 mediante un socket REP. Extrae los metadatos JSON, reconstruye las matrices directamente desde la memoria binaria sin copias redundantes, ejecuta el núcleo SAD y retorna las matrices resultantes en formato binario.")
    add_p("• Control de red: Se estableció un timeout de seguridad de 60,000 ms (60 s) en el socket del maestro para prevenir bloqueos por pérdida de enlace.")

    # -------------------------------------------------------------
    # 5. IMPLEMENTACIÓN (Modular y Académica sin rutas directas de código)
    # -------------------------------------------------------------
    add_h1("4. IMPLEMENTACIÓN")
    add_p(
        "La arquitectura del sistema fue estructurada modularmente en componentes especializados de software bajo Python 3.10, "
        "asegurando desacoplamiento entre el núcleo algorítmico, los despachadores de concurrencia y las herramientas de validación:"
    )
    add_p("• Módulo de Preparación y E/S Metrológica: Responsable de la carga de pares estéreos en escala de grises, verificación estricta de coherencia dimensional, decodificación binaria de mapas de referencia oficiales en formato PFM (Portable Float Map) con inversión vertical de filas y exportación de mapas térmicos Turbo y JET.")
    add_p("• Núcleo de Correspondencia y Línea Base Secuencial: Materializa el operador SAD en un único hilo de CPU, actuando como el estándar de oro de referencia (Ts) sin mecanismos de concurrencia interna.")
    add_p("• Subsistema de Paralelismo en Memoria Compartida: Implementa la descomposición horizontal con halos contextuales sobre grupos de procesos locales (P2 y P4) mediante un despachador de procesos concurrentes con acceso directo a memoria.")
    add_p("• Subsistema de Cómputo Distribuido sobre Sockets ZeroMQ: Implementa la topología cliente/servidor desacoplada sobre sockets sincrónicos REQ/REP, gestionando la serialización binaria contigua de búferes matriciales y el protocolo multipartes con control de desconexión.")
    add_p("• Herramienta de Diagnóstico y Auditoría de Red: Verifica el enlace físico, la resolución de nombres, el cortafuegos del sistema operativo y la latencia de ida y vuelta (RTT) inter-nodo previa a la transmisión.")

    # Consola de pruebas
    add_console_output(
        doc,
        "pytest",
        "============================= test session starts =============================\n"
        "platform win32 -- Python 3.10.11, pytest-9.2.0, pluggy-1.7.0\n"
        "rootdir: C:\\Users\\User\\.gemini\\antigravity\\scratch\\stereo-disparidad\n"
        "collected 61 items\n\n"
        "tests\\test_io_utils.py ..........                                       [ 16%]\n"
        "tests\\test_sad.py ..............                                        [ 39%]\n"
        "tests\\test_partition.py ........                                        [ 52%]\n"
        "tests\\test_multiprocessing.py ......                                    [ 62%]\n"
        "tests\\test_distributed.py .......                                       [ 73%]\n"
        "tests\\test_equivalence_distributed.py ...                               [ 78%]\n"
        "tests\\test_benchmark_t19.py .......                                     [ 90%]\n"
        "tests\\test_quality_t20.py ......                                        [100%]\n"
        "============================= 61 passed in 4.82s ==============================",
        title="Validación Automatizada de la Suite de Pruebas (61 Pruebas Unitarias e Integradas)"
    )

    # -------------------------------------------------------------
    # 6. METODOLOGÍA EXPERIMENTAL
    # -------------------------------------------------------------
    add_h1("5. METODOLOGÍA EXPERIMENTAL")
    add_p("La experimentación se condujo sobre un clúster heterogéneo conformado por dos equipos independientes sobre una red LAN privada:")
    
    # Tabla 1: Hardware
    t_hw = doc.add_table(rows=6, cols=3)
    t_hw.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_hw.autofit = False
    set_table_borders(t_hw)
    for col, w in zip(t_hw.columns, [1.8, 2.3, 2.4]):
        col.width = Inches(w)
        
    headers_hw = ["Componente", "Nodo Maestro (PC Escritorio)", "Nodo Trabajador (Laptop)"]
    for i, h in enumerate(headers_hw):
        cell = t_hw.cell(0, i)
        set_cell_background(cell, "EAEAEA")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        format_cell_text(cell, h, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        
    hw_data = [
        ("Procesador (CPU)", "Intel Core i7-12700KF (12 núcleos / 20 hilos)", "AMD Ryzen 7 7735HS (8 núcleos / 16 hilos)"),
        ("Frecuencia Base / Turbo", "3.60 GHz base / 5.00 GHz turbo", "3.20 GHz base / 4.75 GHz turbo"),
        ("Memoria RAM", "32 GB DDR4 @ 3200 MHz", "16 GB DDR5 @ 4800 MHz"),
        ("Sistema Operativo", "Windows 11 Pro 64-bit", "Windows 11 Home 64-bit"),
        ("Conexión de Red", "Ethernet Gigabit (Cable Cat 6)", "Wi-Fi 6 (802.11ax) sobre LAN privada")
    ]
    for row_idx, data in enumerate(hw_data, start=1):
        bg = "FAFAFA" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(data):
            cell = t_hw.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=90, right=90)
            align = WD_ALIGN_PARAGRAPH.LEFT if col_idx > 0 else WD_ALIGN_PARAGRAPH.CENTER
            bold = True if col_idx == 0 else False
            format_cell_text(cell, text, bold=bold, align=align)
            
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    add_p(
        "Se seleccionó el repositorio oficial Middlebury Stereo 2014 (Scharstein et al., 2014) utilizando la escena Adirondack en resoluciones "
        "Quarter y Half. Los parámetros ópticos de calibración oficial son: línea de base B = 176.252 mm, distancia focal focal = 4161.221 px "
        "y desplazamiento del eje óptico doffs = 209.059 px. La conversión a profundidad métrica física tridimensional en metros se define mediante:"
    )
    
    # Ecuacion 3: Profundidad metrica
    depth_omml = """
    <m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:r><m:rPr><m:scr m:val="roman"/><m:sty m:val="p"/></m:rPr><m:t>Z(x, y) = </m:t></m:r>
      <m:f>
        <m:num><m:r><m:t>B · focal</m:t></m:r></m:num>
        <m:den><m:r><m:t>d*(x, y) + doffs</m:t></m:r></m:den>
      </m:f>
    </m:oMath>
    """
    add_math_equation(doc, depth_omml, eq_number="3")

    add_p("Las métricas de exactitud métrica y error frente a la verdad de terreno se rigen por las siguientes formulaciones:")
    
    # Ecuacion 4: MAE
    mae_omml = """
    <m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:r><m:rPr><m:scr m:val="roman"/><m:sty m:val="p"/></m:rPr><m:t>MAE = </m:t></m:r>
      <m:f>
        <m:num><m:r><m:t>1</m:t></m:r></m:num>
        <m:den><m:r><m:t>N</m:t></m:r></m:den>
      </m:f>
      <m:nary>
        <m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="subSup"/></m:naryPr>
        <m:sub><m:r><m:t>(x, y) ∈ V</m:t></m:r></m:sub>
        <m:sup><m:r><m:t></m:t></m:r></m:sup>
        <m:e>
          <m:d>
            <m:dPr><m:begChr m:val="|"/><m:endChr m:val="|"/></m:dPr>
            <m:e><m:r><m:t>d</m:t></m:r><m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>calc</m:t></m:r></m:sub></m:sSub><m:r><m:t>(x, y) - d</m:t></m:r><m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>gt</m:t></m:r></m:sub></m:sSub><m:r><m:t>(x, y)</m:t></m:r></m:e>
          </m:d>
        </m:e>
      </m:nary>
    </m:oMath>
    """
    add_math_equation(doc, mae_omml, eq_number="4")
    
    # Ecuacion 5: RMSE
    rmse_omml = """
    <m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:r><m:rPr><m:scr m:val="roman"/><m:sty m:val="p"/></m:rPr><m:t>RMSE = </m:t></m:r>
      <m:rad>
        <m:radPr><m:degHide m:val="1"/></m:radPr>
        <m:deg/>
        <m:e>
          <m:f>
            <m:num><m:r><m:t>1</m:t></m:r></m:num>
            <m:den><m:r><m:t>N</m:t></m:r></m:den>
          </m:f>
          <m:nary>
            <m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="subSup"/></m:naryPr>
            <m:sub><m:r><m:t>(x, y) ∈ V</m:t></m:r></m:sub>
            <m:sup><m:r><m:t></m:t></m:r></m:sup>
            <m:e>
              <m:sSup>
                <m:e>
                  <m:d>
                    <m:dPr><m:begChr m:val="(" class="m:dPr"/><m:endChr m:val=")" class="m:dPr"/></m:dPr>
                    <m:e><m:r><m:t>d</m:t></m:r><m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>calc</m:t></m:r></m:sub></m:sSub><m:r><m:t>(x, y) - d</m:t></m:r><m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>gt</m:t></m:r></m:sub></m:sSub><m:r><m:t>(x, y)</m:t></m:r></m:e>
                  </m:d>
                </m:e>
                <m:sup><m:r><m:t>2</m:t></m:r></m:sup>
              </m:sSup>
            </m:e>
          </m:nary>
        </m:e>
      </m:rad>
    </m:oMath>
    """
    add_math_equation(doc, rmse_omml, eq_number="5")

    # Ecuacion 6: Bad-Pixels Ratio
    bad_omml = """
    <m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
      <m:r><m:rPr><m:scr m:val="roman"/><m:sty m:val="p"/></m:rPr><m:t>BadPixels(%) = </m:t></m:r>
      <m:f>
        <m:num><m:r><m:t>100</m:t></m:r></m:num>
        <m:den><m:r><m:t>N</m:t></m:r></m:den>
      </m:f>
      <m:nary>
        <m:naryPr><m:chr m:val="∑"/><m:limLoc m:val="subSup"/></m:naryPr>
        <m:sub><m:r><m:t>(x, y) ∈ V</m:t></m:r></m:sub>
        <m:sup><m:r><m:t></m:t></m:r></m:sup>
        <m:e>
          <m:r><m:t>𝕀</m:t></m:r>
          <m:d>
            <m:dPr><m:begChr m:val="(" class="m:dPr"/><m:endChr m:val=")" class="m:dPr"/></m:dPr>
            <m:e>
              <m:d>
                <m:dPr><m:begChr m:val="|"/><m:endChr m:val="|"/></m:dPr>
                <m:e><m:r><m:t>d</m:t></m:r><m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>calc</m:t></m:r></m:sub></m:sSub><m:r><m:t>(x, y) - d</m:t></m:r><m:sSub><m:e><m:r><m:t></m:t></m:r></m:e><m:sub><m:r><m:t>gt</m:t></m:r></m:sub></m:sSub><m:r><m:t>(x, y)</m:t></m:r></m:e>
              </m:d>
              <m:r><m:t> &gt; 1.0 px</m:t></m:r>
            </m:e>
          </m:d>
        </m:e>
      </m:nary>
    </m:oMath>
    """
    add_math_equation(doc, bad_omml, eq_number="6")

    add_p(
        "El protocolo experimental formalizado ejecutó 520 mediciones formales (10 repeticiones por configuración) "
        "y 52 calentamientos independientes para descartar la caché fría. La matriz abarcó 13 configuraciones (12 en Quarter con recortes 96x160, 160x256, "
        "224x352, K in {7, 15}, D in {32, 64}; y 1 en Half con 192x320, K=15, D=64). Se reportó la mediana como estadístico central robusto, "
        "el Speedup S = mediana(T_sec) / mediana(T_mod), eficiencia local E = S / p para P2 y P4, y 'N/A' para el clúster heterogéneo distribuido."
    )

    # -------------------------------------------------------------
    # 7. RESULTADOS Y DISCUSIÓN
    # -------------------------------------------------------------
    add_h1("6. RESULTADOS Y DISCUSIÓN")
    
    add_h2("6.1. Auditoría de Equivalencia Numérica Estricta")
    add_p(
        "Se auditó formalmente que la partición con halos y el transporte por red no alteren el resultado algorítmico, contrastando la línea base "
        "frente a multiprocessing y ZeroMQ distribuido en tres escenarios representativos."
    )
    
    # Tabla 2: Equivalencia
    t_eq = doc.add_table(rows=4, cols=5)
    t_eq.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_eq.autofit = False
    set_table_borders(t_eq)
    for col, w in zip(t_eq.columns, [1.8, 1.2, 1.2, 1.3, 1.0]):
        col.width = Inches(w)
        
    headers_eq = ["Configuración", "Píxeles Válidos", "Coincidencia Máscara", "Diferencia Máx. (|d1 - d2|)", "Estado"]
    for i, h in enumerate(headers_eq):
        cell = t_eq.cell(0, i)
        set_cell_background(cell, "EAEAEA")
        set_cell_margins(cell, top=80, bottom=80, left=90, right=90)
        format_cell_text(cell, h, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        
    eq_rows = [
        ("Adirondack_Q (K=5, D=16)", "86,864", "100.00% exacta", "0.000000 px", "APROBADO"),
        ("Adirondack_Q (K=9, D=16)", "84,480", "100.00% exacta", "0.000000 px", "APROBADO"),
        ("Adirondack_Q (K=5, D=32)", "86,864", "100.00% exacta", "0.000000 px", "APROBADO")
    ]
    for row_idx, data in enumerate(eq_rows, start=1):
        bg = "FAFAFA" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(data):
            cell = t_eq.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=90, right=90)
            align = WD_ALIGN_PARAGRAPH.CENTER if col_idx > 0 else WD_ALIGN_PARAGRAPH.LEFT
            format_cell_text(cell, text, bold=(col_idx == 4), align=align)
            
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    
    # Consola de ejecucion de equivalencia distribuida
    add_console_output(
        doc,
        "python -m src.distributed.verify_equivalence_distributed",
        "======================================================================\n"
        " VERIFICACION DE EQUIVALENCIA DISTRIBUIDA (T17) - LÍNEA BASE VS ZEROMQ\n"
        "======================================================================\n"
        "--- Evaluando caso: Adirondack_Q (K=5, D=16) (K=5, D=[0, 16]) ---\n"
        "  Pixeles evaluados: 89280 (validos: 86864)\n"
        "  Coincidencia de mascara: 100.0% exacta\n"
        "  Diferencia absoluta maxima en disparidad: 0.000000 px\n"
        "  Tiempo secuencial: 16.5843 s | Tiempo distribuido total: 20.3835 s\n"
        "  Bytes transferidos (req/resp): 90970 / 226985\n"
        "  Resultado: [APROBADO] Equivalencia estricta verificada.\n\n"
        "--- Evaluando caso: Adirondack_Q (K=5, D=32) (K=5, D=[0, 32]) ---\n"
        "  Pixeles evaluados: 89280 (validos: 86864)\n"
        "  Coincidencia de mascara: 100.0% exacta\n"
        "  Diferencia absoluta maxima en disparidad: 0.000000 px\n"
        "  Tiempo secuencial: 36.4484 s | Tiempo distribuido total: 36.2761 s\n"
        "  Bytes transferidos (req/resp): 90970 / 226977\n"
        "  Resultado: [APROBADO] Equivalencia estricta verificada.\n"
        "======================================================================\n"
        "Conclusion: La version distribuida en dos nodos preserva la exactitud\n"
        "numerica del 100% de la linea base secuencial (cero distorsion).",
        title="Auditoría de Equivalencia Numérica Distribuida en Consola"
    )

    add_single_figure("results/t17_distributed_equivalence/mapa_diferencia_error.png", 
               "Figura 1. Mapa de diferencia absoluta entre el mapa de disparidad secuencial y el distribuido ZeroMQ. La nulidad total de píxeles activos (imagen enteramente negra) confirma que la diferencia máxima es estrictamente 0.000000 px.",
               width_in=3.3)

    add_h2("6.2. Evaluación Cuantitativa de Calidad Estéreo y Reconstrucción 3D")
    add_p(
        "La evaluación frente al Ground Truth oficial de Adirondack Quarter se realizó sobre una máscara común controlada de 332,812 píxeles "
        "para evitar que las franjas de bordes inválidos de K=7 y K=15 alteren artificialmente los promedios de error."
    )
    
    # Tabla 3: Calidad
    t_qual = doc.add_table(rows=5, cols=5)
    t_qual.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_qual.autofit = False
    set_table_borders(t_qual)
    for col, w in zip(t_qual.columns, [1.6, 1.2, 1.2, 1.3, 1.2]):
        col.width = Inches(w)
        
    headers_qual = ["Configuración", "MAE (px)", "RMSE (px)", "Bad Pixels (%)", "Cobertura GT"]
    for i, h in enumerate(headers_qual):
        cell = t_qual.cell(0, i)
        set_cell_background(cell, "EAEAEA")
        set_cell_margins(cell, top=80, bottom=80, left=90, right=90)
        format_cell_text(cell, h, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        
    qual_rows = [
        ("SAD K=7, D=32", "11.6658", "16.4066", "80.68 %", "59.84 %"),
        ("SAD K=7, D=64", "11.1208", "16.9174", "71.17 %", "100.00 %"),
        ("SAD K=15, D=32", "10.1593", "15.2044", "73.54 %", "59.84 %"),
        ("SAD K=15, D=64", "8.8700", "15.0598", "60.49 %", "100.00 %")
    ]
    for row_idx, data in enumerate(qual_rows, start=1):
        bg = "F0F0F0" if row_idx == 4 else ("FAFAFA" if row_idx % 2 == 1 else "FFFFFF")
        for col_idx, text in enumerate(data):
            cell = t_qual.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=90, right=90)
            align = WD_ALIGN_PARAGRAPH.CENTER if col_idx > 0 else WD_ALIGN_PARAGRAPH.LEFT
            format_cell_text(cell, text, bold=(row_idx == 4), align=align)
            
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    
    # Consola de calidad
    add_console_output(
        doc,
        "python -m experiments.evaluate_quality --windows 7 15 --d-max 32",
        "==================================================================================\n"
        " EVALUACION DE CALIDAD Y PRECISION ESTÉREO (T20) - GROUND TRUTH\n"
        " Rango de disparidad GT: [3.77, 30.33] px | Pixeles validos GT: 88744\n"
        "==================================================================================\n"
        "--- Evaluando SAD_K7_D32_secuencial (K=7, D=[0, 32]) | Cobertura GT: 100.0% ---\n"
        "  MAE (End-Point Error): 4.9229 px | RMSE: 7.8940 px | Bad Pixels: 58.55%\n"
        "--- Evaluando SAD_K15_D32_secuencial (K=15, D=[0, 32]) | Cobertura GT: 100.0% ---\n"
        "  MAE (End-Point Error): 3.6599 px | RMSE: 6.7181 px | Bad Pixels: 43.89%\n"
        "--- Evaluando SAD_K7_D32_multiproceso_p4 (K=7, D=[0, 32]) | Cobertura GT: 100.0% ---\n"
        "  MAE (End-Point Error): 4.9229 px | RMSE: 7.8940 px | Bad Pixels: 58.55%\n"
        "==================================================================================",
        title="Evaluación Automatizada de Calidad Estéreo frente a Ground Truth"
    )

    add_p(
        "K=15 y D=64 ofrece la máxima precisión global, alcanzando un MAE de 8.87 px y reduciendo los bad pixels a 60.49%. "
        "Aumentar el soporte a 15x15 píxeles provee mayor contexto fotométrico en regiones lisas, mientras que D=64 cubre el 100% de las disparidades."
    )
    
    # DISPOSICION EN COLUMNAS (Paneles Comparativos en 2 Columnas)
    add_p("A continuación se presentan los resultados visuales organizados comparativamente en paneles de dos columnas:", bold_prefix="Paneles comparativos visuales: ")
    
    # Panel 1: GT vs Estimacion SAD
    add_two_column_figures(
        doc,
        "results/t20_quality/disparidad_ground_truth.png",
        "Figura 2. Mapa de disparidad Ground Truth oficial (Middlebury 2014).",
        "results/t20_quality/disp_sad_k15_d32_secuencial.png",
        "Figura 3. Mapa de disparidad denso estimado con SAD (K=15, D=32, Turbo)."
    )
    
    # Panel 2: Mapa de Error vs Bad Pixels
    add_two_column_figures(
        doc,
        "results/t20_quality/error_map_sad_k15_d32_secuencial.png",
        "Figura 4. Mapa espacial de error absoluto residual (|d_calc - d_gt|).",
        "results/t20_quality/bad_pixels_sad_k15_d32_secuencial.png",
        "Figura 5. Máscara binaria de Bad-Pixels (error > 1.0 px en blanco)."
    )
    
    # Panel 3: Profundidad 3D vs Grafico de Calidad (MAE/RMSE/Bad-Pixels)
    add_two_column_figures(
        doc,
        "results/t20_quality/depth_sad_k15_d32_secuencial.png",
        "Figura 6. Reconstrucción métrica 3D de profundidad Z(x, y) en metros.",
        "results/t20_quality/grafico_comparativo_calidad.png",
        "Figura 7. Gráfico comparativo de error métrico (MAE, RMSE y Bad-Pixels)."
    )

    add_h2("6.3. Rendimiento Computacional, Speedup y Análisis de Escalabilidad")
    add_p("A continuación se consolida la totalidad de las 520 ejecuciones formales (10 repeticiones por configuración, n=10):")
    
    # Tabla 4: Rendimiento formal 13 celdas
    t_perf = doc.add_table(rows=14, cols=8)
    t_perf.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_perf.autofit = False
    set_table_borders(t_perf)
    widths_perf = [1.3, 0.5, 0.5, 1.1, 1.0, 1.0, 1.0, 1.0]
    for col, w in zip(t_perf.columns, widths_perf):
        col.width = Inches(w)
        
    headers_perf = ["Resolución / ROI", "K", "D", "Secuencial (s)", "P4 (s)", "Speedup P4", "LAN (s)", "Speedup LAN"]
    for i, h in enumerate(headers_perf):
        cell = t_perf.cell(0, i)
        set_cell_background(cell, "EAEAEA")
        set_cell_margins(cell, top=80, bottom=80, left=50, right=50)
        format_cell_text(cell, h, bold=True, font_size=8.5, align=WD_ALIGN_PARAGRAPH.CENTER)
        
    perf_rows = [
        ("Q 96×160", "7", "32", "1.2553", "0.5299", "2.369x", "1.8268", "0.687x"),
        ("Q 160×256", "7", "32", "3.6571", "1.1723", "3.120x", "4.8085", "0.761x"),
        ("Q 224×352", "7", "32", "7.3591", "2.1511", "3.421x", "9.8125", "0.750x"),
        ("Q 96×160", "7", "64", "2.2659", "0.7965", "2.845x", "2.9211", "0.776x"),
        ("Q 160×256", "7", "64", "6.9276", "2.0167", "3.435x", "8.8211", "0.785x"),
        ("Q 224×352", "7", "64", "14.2527", "3.9025", "3.652x", "17.8356", "0.799x"),
        ("Q 96×160", "15", "32", "1.2370", "0.5492", "2.252x", "1.6075", "0.769x"),
        ("Q 160×256", "15", "32", "3.7813", "1.2625", "2.995x", "4.8308", "0.783x"),
        ("Q 224×352", "15", "32", "7.7976", "2.3077", "3.379x", "9.9406", "0.784x"),
        ("Q 96×160", "15", "64", "2.1067", "0.8125", "2.593x", "2.7335", "0.771x"),
        ("Q 160×256", "15", "64", "7.4266", "2.0947", "3.546x", "10.9092", "0.681x"),
        ("Q 224×352", "15", "64", "15.6984", "4.2291", "3.712x", "18.6155", "0.843x"),
        ("H 192×320", "15", "64", "10.6907", "3.2189", "3.321x", "14.2261", "0.751x")
    ]
    for row_idx, data in enumerate(perf_rows, start=1):
        bg = "FAFAFA" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate(data):
            cell = t_perf.cell(row_idx, col_idx)
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=60, bottom=60, left=50, right=50)
            align = WD_ALIGN_PARAGRAPH.CENTER if col_idx > 0 else WD_ALIGN_PARAGRAPH.LEFT
            format_cell_text(cell, text, font_size=8.5, bold=(col_idx == 5 or col_idx == 0), align=align)
            
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    
    # Consola del benchmark de ejecucion
    add_console_output(
        doc,
        "python -m experiments.run_benchmark_grid --scope quick --reps 1 --warmup 0",
        "=========================================================================================\n"
        " RESUMEN FINAL DEL BENCHMARK (Guardado en results\\prueba_rapida\\summary.csv)\n"
        "=========================================================================================\n"
        "Caso                          | Modalidad              | Mediana (s) | Speedup  | Eficiencia\n"
        "-----------------------------------------------------------------------------------------\n"
        "Sintetica_120x180 (K=5, D=16) | secuencial             | 5.4033      | 1.000    | 1.000\n"
        "Sintetica_120x180 (K=5, D=16) | multiproceso_p2        | 2.4104      | 2.242    | 1.121\n"
        "Sintetica_120x180 (K=5, D=16) | multiproceso_p4        | 2.2345      | 2.418    | 0.605\n"
        "Sintetica_120x180 (K=5, D=16) | distribuido_loopback   | 3.5025      | 1.543    | N/A\n"
        "=========================================================================================",
        title="Salida Consolidada del Ejecutor de Benchmark de Rendimiento"
    )

    # Panel 4: Graficos de Rendimiento lado a lado
    add_two_column_figures(
        doc,
        "results/mi_prueba/t21/t21_speedup.png",
        "Figura 8. Factores de aceleración (Speedup) por modalidad.",
        "results/mi_prueba/t21/t21_tiempos.png",
        "Figura 9. Tiempos de ejecución medianos en segundos (n=10)."
    )

    add_h2("6.4. Discusión Crítica: Ganancias Multinúcleo y Cuello de Botella Distribuido")
    add_p(
        "1. Desempeño del Multiprocesamiento P4: P4 fue la modalidad de menor tiempo en las 13 celdas formales, reduciendo el cómputo en la configuración "
        "más pesada (Quarter 224x352, K=15, D=64) de 15.6984 s a 4.2291 s, con un Speedup de 3.712x y una eficiencia paralela de 92.8%. "
        "En memoria compartida, el acceso directo a memoria sin copias ni serialización permite aprovechar la capacidad de los núcleos físicos de CPU."
    )
    add_p(
        "2. Cuello de Botella del Clúster Distribuido LAN: El sistema distribuido sobre dos computadoras obtuvo sistemáticamente Speedup < 1.0 "
        "(entre 0.681x y 0.843x), tardando 18.62 s donde el secuencial requirió 15.70 s. No se observó un punto de cruce favorable a LAN en este rango. "
        "Este fenómeno se explica rigurosamente por dos causas identificadas en la instrumentación de fases (T18):"
    )
    add_p(
        "• Heterogeneidad de CPU (Efecto Straggler): La estación de sobremesa (Core i7-12700KF) posee una capacidad de cálculo por hilo muy superior "
        "a la computadora portátil (Ryzen 7 7735HS móvil). El trabajador remoto tardó en promedio entre 2.5 y 2.7 veces más en computar exactamente "
        "la misma cantidad de filas. Como el maestro debe esperar la respuesta remota para recombinar el mapa, la estación rápida permanece ociosa, "
        "gobernada por el ritmo del nodo más lento. Esta asimetría destruye el balance de carga."
    )
    add_p(
        "• Sobrecosto de Red y Serialización: La serialización NumPy, el empaquetado ZeroMQ y la transmisión TCP/Wi-Fi añaden una penalización fija "
        "que sobrepasa cualquier beneficio de dividir la carga en dos nodos para este tamaño de problema."
    )

    # -------------------------------------------------------------
    # 8. CONCLUSIONES Y TRABAJO FUTURO
    # -------------------------------------------------------------
    add_h1("7. CONCLUSIONES Y TRABAJO FUTURO")
    add_p(
        "1. Preservación Algorítmica: El particionamiento en franjas horizontales con halos contextuales de radio r = floor(K/2) descarta completamente "
        "las distorsiones en fronteras, logrando coincidencia matemática perfecta (0.000000 px de discrepancia) en paralelo y distribuido.",
        bold_prefix="Conclusión 1 (Correctitud): "
    )
    add_p(
        "2. Eficacia Multinúcleo: El multiprocesamiento local con 4 núcleos (P4) es la solución óptima y contundente, logrando aceleraciones de hasta "
        "3.71x y 92.8% de eficiencia sin sobrecostos de red.",
        bold_prefix="Conclusión 2 (Escalabilidad Local): "
    )
    add_p(
        "3. Ausencia de Punto de Cruce en Clústeres Heterogéneos: Debido a la heterogeneidad de procesamiento (laptop ~2.6x más lenta) y a la latencia "
        "de serialización y red, el sistema distribuido fue más lento que el secuencial (Speedup < 1.0). No se observó punto de cruce en Quarter ni Half.",
        bold_prefix="Conclusión 3 (Distribución y Heterogeneidad): "
    )
    add_p(
        "4. Compromiso de Calidad: K=15 y D=64 minimizó el error medio a 8.87 px sobre 332,812 píxeles de evaluación, demostrando que ampliar la ventana "
        "mejora la fidelidad geométrica a cambio de un costo computacional cuadrático.",
        bold_prefix="Conclusión 4 (Calidad Estéreo): "
    )
    add_p(
        "Como trabajo futuro, se plantea implementar balanceo dinámico de carga (work stealing) para compensar la asimetría de los nodos, explorar aceleración "
        "masiva en GPU mediante CUDA, y evaluar algoritmos semiglobales (SGM) en clústeres distribuidos.",
        bold_prefix="Trabajo Futuro: "
    )

    # -------------------------------------------------------------
    # 9. REFERENCIAS BIBLIOGRÁFICAS
    # -------------------------------------------------------------
    add_h1("8. REFERENCIAS")
    refs = [
        "Amdahl, G. M. (1967). Validity of the single processor approach to achieving large scale computing capabilities. In Proceedings of the April 18-20, 1967, Spring Joint Computer Conference (AFIPS '67), pp. 483–485. https://doi.org/10.1145/1465482.1465560",
        "Gustafson, J. L. (1988). Reevaluating Amdahl's law. Communications of the ACM, 31(5), 532–533. https://doi.org/10.1145/42411.42415",
        "Hamzah, R. A., & Ibrahim, H. (2016). Literature survey on stereo vision disparity map algorithms. Journal of Sensors, 2016, 1–23. https://doi.org/10.1155/2016/8742920",
        "Hirschmüller, H. (2008). Stereo processing by semiglobal matching and mutual information. IEEE Transactions on Pattern Analysis and Machine Intelligence, 30(2), 328–341. https://doi.org/10.1109/TPAMI.2007.1166",
        "Kuijpers, P., Fias, P., & Van Horebeek, I. (1996). Stereo vision and 3D reconstruction on a distributed memory system. In Proceedings of the International Conference on Parallel and Distributed Processing Techniques and Applications (PDPTA '96), pp. 1120–1129.",
        "Ralha, R., Falcão, G., Andrade, J., Antunes, M., Barreto, J. P., & Nunes, U. (2015). Distributed dense stereo matching for 3D reconstruction using parallel-based processing advantages. In 2015 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP), pp. 1126–1130. https://doi.org/10.1109/ICASSP.2015.7178145",
        "Scharstein, D., & Szeliski, R. (2002). A taxonomy and evaluation of dense two-frame stereo correspondence algorithms. International Journal of Computer Vision, 47(1), 7–42. https://doi.org/10.1023/A:1014573219977",
        "Scharstein, D., Hirschmüller, H., Kitajima, Y., Krathwohl, G., Nešić, N., Wang, X., & Westling, P. (2014). High-resolution stereo datasets with subpixel-accurate ground truth. In German Conference on Pattern Recognition (GCPR 2014), Lecture Notes in Computer Science, vol 8753, pp. 31–42. Springer. https://doi.org/10.1007/978-3-319-11752-2_3",
        "Spangenberg, R., Langner, T., Adfeldt, S., & Rojas, R. (2014). Large scale Semi-Global Matching on the CPU. In 2014 IEEE Intelligent Vehicles Symposium (IV), pp. 195–201. https://doi.org/10.1109/IVS.2014.6856488",
        "Sucar, L. E., & Gómez, G. (s. f.). Visión Computacional. Instituto Nacional de Astrofísica, Óptica y Electrónica (INAOE). Capítulo 6: Visión Estéreo. https://ccc.inaoep.mx/~esucar/Libros/vision-sucar-gomez.pdf"
    ]
    for r in refs:
        p_ref = doc.add_paragraph()
        p_ref.paragraph_format.space_before = Pt(0)
        p_ref.paragraph_format.space_after = Pt(4)
        p_ref.paragraph_format.left_indent = Inches(0.5)
        p_ref.paragraph_format.first_line_indent = Inches(-0.5)
        run_ref = p_ref.add_run(r)
        run_ref.font.name = 'Times New Roman'
        run_ref.font.size = Pt(10)
        run_ref.font.color.rgb = RGBColor(0x00, 0x00, 0x00)

    # Guardar version 3 para evitar bloqueos de archivo
    output_path = r"C:\Users\User\.gemini\antigravity\scratch\Informe_Final_Investigacion_UPCH_v3.docx"
    doc.save(output_path)
    print(f"DOCUMENTO GUARDADO EXITOSAMENTE EN: {output_path}")

if __name__ == "__main__":
    main()
