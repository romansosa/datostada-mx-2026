"""Construye tableau/dashboard_pitch.twbx: el dashboard con el estilo del pitch «Detrás de la pantalla».

Uso (desde la raíz del repo):  py tableau/construir_twbx_pitch.py

Parte de una copia de tableau/construir_twbx_historia.py (que no se toca, igual que el respaldo
construir_twbx.py) y le aplica el estilo del pitch: fondo azul marino oscuro, texto crema, coral para
el riesgo y un color por canal (cian = mensajería, violeta = redes sociales, amarillo = llamadas).
- «Historia»: encabezado, cuatro tarjetas de resumen (cuántos, quién, qué hacen, el ranking engaña),
  01 matriz edad × año, 02 plataformas por edad y 03 entonces qué (tres tarjetas por edad y canal,
  con los colores de su canal, como en la lámina 5 del pitch).
- «Contexto»: ranking, respuestas de las víctimas y otros grupos, con la misma paleta.
- Salida reproducible: identificadores con semilla fija y fechas fijas dentro del ZIP.

Todas las cifras de los textos vienen de data/tableau/*.csv o de HALLAZGOS.md.
Si se edita el libro a mano en Tableau, no vuelvas a correr este script (borra esos cambios).
"""
import csv
import os
import random
import uuid
import zipfile
from xml.sax.saxutils import escape

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "data", "tableau")
SALIDA = os.path.join(RAIZ, "tableau", "dashboard_pitch.twbx")
CSVS = ("A-edad_anio.csv", "B-edad_plataforma.csv", "A-edad_kpi.csv", "B-edad_acciones.csv",
        "A-yucatan_vs_nacional.csv", "A-contexto_grupos.csv")

RNG = random.Random(20261115)  # semilla fija: mismos identificadores en cada corrida


def q(s):
    """Escapa para atributo XML con comillas simples."""
    return escape(s, {"'": "&apos;", '"': "&quot;"})


def gid():
    return "{" + str(uuid.UUID(int=RNG.getrandbits(128), version=4)).upper() + "}"


def hexid(n):
    return "%0*x" % (n, RNG.getrandbits(4 * n))



# ---------------------------------------------------------------- colores
# Paleta del pitch «Detrás de la pantalla» (tema del .pptx): fondo oscuro, crema, coral de acento y un
# color por canal. Coral = más riesgo; azul apagado = menos o sin diferencia.
FONDO = "#0b0f1f"       # fondo de todo el libro
PANEL = "#1a2140"       # tarjetas
RIEL = "#222a47"        # riel de 100 de las barras (las víctimas que no lo vivieron por ese canal)
TINTA = "#f4f1ea"       # texto principal (crema)
GRIS = "#a3abc7"        # texto secundario
CORAL = "#ff5470"       # acento: riesgo, 12–24 años
CIAN = "#2dd4ff"        # mensajería
VIOLETA = "#a78bfa"     # redes sociales
AMARILLO = "#ffd23f"    # llamadas
APAGADO = "#3a4470"     # resto de las barras
OSCURO_TXT = "#0b0f1f"  # texto sobre tarjetas de color
# Matriz (puntos contra el promedio del año): azul oscuro abajo, ciruela cerca y coral arriba (lámina 3).
MATRIZ = ["#1e2647", "#6b3352", CORAL]
ROJO, AMBAR, VERDE = CORAL, APAGADO, CIAN               # más / intermedio o sin diferencia / menos
ROJO_T, AMBAR_T, VERDE_T = "#c2435f", "#6b3352", "#2a3a6e"  # mapa de calor de acciones (la cifra crema se lee)
ACENTO = CORAL

# ---------------------------------------------------------------- fuentes de datos
TIPOS = {"string": ("129", "Count"), "real": ("5", "Sum"), "integer": ("20", "Sum"), "boolean": ("11", "Count")}


def tipo_columna(valores):
    vs = [v for v in valores if v != ""]
    if vs and all(v in ("True", "False") for v in vs):
        return "boolean"
    try:
        [int(v) for v in vs]
        return "integer"
    except ValueError:
        pass
    try:
        [float(v) for v in vs]
        return "real"
    except ValueError:
        return "string"


def calc(nombre, caption, datatype, formula, role=None):
    """Campo calculado. Devuelve el XML de la columna (se usa en la fuente y en las hojas)."""
    role = role or ("measure" if datatype in ("real", "integer") else "dimension")
    typ = "quantitative" if role == "measure" else "nominal"
    fmt = " default-format='n#,##0.0;-#,##0.0'" if datatype == "real" else ""
    return ("      <column caption='%s' datatype='%s'%s name='[%s]' role='%s' type='%s'>\n"
            "        <calculation class='tableau' formula='%s' />\n      </column>\n") % (
        q(caption), datatype, fmt, nombre, role, typ, q(formula))


def estilo_colores(colores):
    """Color de cada valor de una dimensión. Tableau lo guarda en la fuente de datos, después de <layout>."""
    if not colores:
        return ""
    reglas = ""
    for campo, pares in colores.items():
        mapas = "".join("            <map to='%s'>\n              <bucket>&quot;%s&quot;</bucket>\n            </map>\n" % (c, q(v))
                        for v, c in pares)
        reglas += "          <encoding attr='color' field='[%s]' type='palette'>\n%s          </encoding>\n" % (campo, mapas)
    return "      <style>\n        <style-rule element='mark'>\n%s        </style-rule>\n      </style>\n" % reglas


def nueva_ds(archivo, captions, forzar_texto=(), calcs=(), colores=None):
    """Fuente de datos de texto (CSV con configuración regional en inglés: punto decimal).

    colores: {instancia: [(valor, color), ...]} para fijar el color de cada valor.
    """
    ruta = os.path.join(DATOS, archivo)
    with open(ruta, encoding="utf-8") as f:
        filas = list(csv.reader(f))
    enc, cuerpo = filas[0], filas[1:]
    tipos = []
    for i, c in enumerate(enc):
        tipos.append("string" if c in forzar_texto else tipo_columna([r[i] for r in cuerpo]))
    base = archivo[:-4]
    nombre = "federated." + hexid(28)
    conn = "textscan." + hexid(28)
    obj = "%s_%s" % (archivo, hexid(32).upper())
    cols = "".join("            <column datatype='%s' name='%s' ordinal='%d' />\n" % (t, c, i) for i, (c, t) in enumerate(zip(enc, tipos)))
    recs = []
    for i, (c, t) in enumerate(zip(enc, tipos)):
        rt, ag = TIPOS[t]
        extra = "            <scale>1</scale>\n            <width>1073741823</width>\n" if t == "string" else ""
        col = "            <collation flag='0' name='LEN_RUS' />\n" if t == "string" else ""
        recs.append(
            "          <metadata-record class='column'>\n"
            "            <remote-name>%s</remote-name>\n            <remote-type>%s</remote-type>\n"
            "            <local-name>[%s]</local-name>\n            <parent-name>[%s]</parent-name>\n"
            "            <remote-alias>%s</remote-alias>\n            <ordinal>%d</ordinal>\n"
            "            <local-type>%s</local-type>\n            <aggregation>%s</aggregation>\n%s"
            "            <contains-null>true</contains-null>\n%s"
            "            <object-id>[%s]</object-id>\n          </metadata-record>\n"
            % (c, rt, c, archivo, c, i, t, ag, extra, col, obj))
    columnas = ""
    for c, t in zip(enc, tipos):
        if c in captions:
            cap, extra = captions[c] if isinstance(captions[c], tuple) else (captions[c], "")
            if t in ("real", "integer") and c not in forzar_texto:
                fmt = " default-format='n#,##0.0;-#,##0.0'" if t == "real" else ""
                columnas += "      <column caption='%s' datatype='%s'%s name='[%s]' role='measure' type='quantitative' />\n" % (q(cap), t, fmt, c)
            elif extra:
                columnas += "      <column caption='%s' datatype='%s' name='[%s]' role='dimension' type='nominal'>\n%s      </column>\n" % (q(cap), t, c, extra)
            else:
                columnas += "      <column caption='%s' datatype='%s' name='[%s]' role='dimension' type='nominal' />\n" % (q(cap), t, c)
    columnas += "".join(calcs)
    # Tableau declara en la fuente la instancia de cada campo que tiene colores asignados.
    for campo in (colores or {}):
        columnas += "      <column-instance column='[%s]' derivation='None' name='[%s]' pivot='key' type='nominal' />\n" % (
            campo.split(":")[1], campo)
    xml = (
        "    <datasource caption='%(base)s' inline='true' name='%(nombre)s' version='18.1'>\n"
        "      <connection class='federated'>\n        <named-connections>\n"
        "          <named-connection caption='%(base)s' name='%(conn)s'>\n"
        "            <connection class='textscan' directory='Data/tableau' filename='%(archivo)s' password='' server='' />\n"
        "          </named-connection>\n        </named-connections>\n"
        "        <relation connection='%(conn)s' name='%(archivo)s' table='[%(tabla)s]' type='table'>\n"
        "          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>\n%(cols)s"
        "          </columns>\n        </relation>\n        <metadata-records>\n"
        "          <metadata-record class='capability'>\n            <remote-name />\n            <remote-type>0</remote-type>\n"
        "            <parent-name>[%(archivo)s]</parent-name>\n            <remote-alias />\n            <aggregation>Count</aggregation>\n"
        "            <contains-null>true</contains-null>\n            <attributes>\n"
        "              <attribute datatype='string' name='character-set'>&quot;UTF-8&quot;</attribute>\n"
        "              <attribute datatype='string' name='collation'>&quot;en_US&quot;</attribute>\n"
        "              <attribute datatype='string' name='field-delimiter'>&quot;,&quot;</attribute>\n"
        "              <attribute datatype='string' name='header-row'>&quot;true&quot;</attribute>\n"
        "              <attribute datatype='string' name='locale'>&quot;en_US&quot;</attribute>\n"
        "              <attribute datatype='string' name='single-char'>&quot;&quot;</attribute>\n"
        "            </attributes>\n          </metadata-record>\n%(recs)s        </metadata-records>\n      </connection>\n"
        "      <aliases enabled='yes' />\n%(columnas)s"
        "      <layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />\n%(estilo)s"
        "      <object-graph>\n        <objects>\n          <object caption='%(archivo)s' id='%(obj)s'>\n            <properties context=''>\n"
        "              <relation connection='%(conn)s' name='%(archivo)s' table='[%(tabla)s]' type='table'>\n"
        "                <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>\n%(cols2)s"
        "                </columns>\n              </relation>\n            </properties>\n          </object>\n        </objects>\n      </object-graph>\n"
        "    </datasource>\n"
    ) % dict(base=base, nombre=nombre, conn=conn, archivo=archivo, tabla=archivo.replace(".csv", "#csv"),
             cols=cols, cols2=cols.replace("            <column", "                  <column"), recs="".join(recs),
             columnas=columnas, obj=obj, estilo=estilo_colores(colores))
    return nombre, xml


def alias(pares):
    return "        <aliases>\n" + "".join("          <alias key='&quot;%s&quot;' value='%s' />\n" % (q(k), q(v)) for k, v in pares) + "        </aliases>\n"


def filtro_ds(campo, excluir):
    miembros = "".join("          <groupfilter function='member' level='[%s]' member='&quot;%s&quot;' />\n" % (campo, q(m)) for m in excluir)
    return ("      <filter class='categorical' column='[%s]' filter-group='2'>\n"
            "        <groupfilter function='except' user:ui-domain='database' user:ui-enumeration='exclusive' user:ui-marker='enumerate'>\n"
            "          <groupfilter function='level-members' level='[%s]' />\n%s"
            "        </groupfilter>\n      </filter>\n") % (campo, campo, miembros if len(excluir) == 1 else
            "          <groupfilter function='union'>\n" + miembros.replace("          <g", "            <g") + "          </groupfilter>\n")


def con_filtro_ds(bloque, filtros):
    return bloque.replace("      <object-graph>", filtros + "      <object-graph>", 1)


# Nombres de los campos calculados (fijos, con el formato que usa Tableau)
C_PUNTOS = "Calculation_2026111400000000001"
C_MARCA_ANIO = "Calculation_2026111400000000002"
C_GRUPO_PLAT = "Calculation_2026111400000000003"
C_PROT, C_PROT_INF, C_PROT_SUP = ("Calculation_2026111400000000011", "Calculation_2026111400000000012",
                                  "Calculation_2026111400000000013")
C_DEN, C_DEN_INF, C_DEN_SUP = ("Calculation_2026111400000000021", "Calculation_2026111400000000022",
                               "Calculation_2026111400000000023")
C_MARCA_ACC = "Calculation_2026111400000000031"
C_TIPO_ACC = "Calculation_2026111400000000032"

# Matriz: puntos arriba o abajo del promedio estatal de ese año. El promedio es la fila «Total» de
# cada año (y de 2019-2025). FIXED se calcula antes del filtro de la hoja que quita «Total», por eso
# no hay filtro de fuente de datos en esta fuente (D-02, docs/revision_dashboard.md, sección C).
CALC_ANIO = {
    C_PUNTOS: calc(C_PUNTOS, "Puntos contra el promedio del año", "real",
                   '[pct] - {FIXED [anio] : MAX(IF [grupo_edad] = "Total" THEN [pct] END)}'),
    C_MARCA_ANIO: calc(C_MARCA_ANIO, "Marca de precisión", "string",
                       'IF [precision] = "baja" THEN "†" ELSE "" END'),
}
ds_anio, x_anio = nueva_ds("A-edad_anio.csv", {
    "anio": ("Año", alias([("2019", "2019*"), ("2019-2025", "7 años")])),
    "grupo_edad": ("Edad", alias([("60+", "60 y más")])),
    "pct": "% que vivió ciberacoso", "ic95_inf": "IC 95 % inferior", "ic95_sup": "IC 95 % superior",
    "casos_muestra": "Entrevistas en la muestra", "precision": "Precisión"},
    forzar_texto=("anio",), calcs=CALC_ANIO.values())

C_CIEN = "Calculation_2026111400000000004"
CALC_PLAT = {
    C_GRUPO_PLAT: calc(C_GRUPO_PLAT, "Canal que más pesa en esa edad (color)", "string",
                       # Como en la lámina 4 del pitch: se colorea el canal donde cada edad tiene su cifra más
                       # alta del panel (mensajería 12–17: 67.7; redes 18–24 y 25–34: 61.4 y 61.1; llamadas
                       # 45–59 y 60+: 38.0 y 43.4, B-edad_plataforma.csv). Lo demás, en azul apagado.
                       'IF [plataforma] = "Mensajería" AND [grupo_de_edad] = "12-17" THEN "Mensajería" '
                       'ELSEIF [plataforma] = "Redes sociales" AND ([grupo_de_edad] = "18-24" OR [grupo_de_edad] = "25-34") THEN "Redes sociales" '
                       'ELSEIF [plataforma] = "Llamadas" AND ([grupo_de_edad] = "45-59" OR [grupo_de_edad] = "60+") THEN "Llamadas" '
                       'ELSE "Resto" END'),
    # Riel de cada barra: las 100 víctimas de esa edad. No es un dato nuevo, es la escala (0 a 100).
    C_CIEN: calc(C_CIEN, "Total de víctimas (riel de 100)", "real", "100"),
}
ds_plat, x_plat = nueva_ds("B-edad_plataforma.csv", {
    # «¿Le llegó por…?» y no «Plataforma»: una víctima puede contar en varios canales (P11 del MOCIBA
    # admite hasta 3 medios por situación), así que las tres columnas no son «elige una».
    "grupo_de_edad": ("Edad", alias([("60+", "60 y más*")])), "plataforma": "¿Le llegó por…?",
    "porcentaje_de_victimas": "% de las víctimas", "ic95_inferior": "IC 95 % inferior",
    "ic95_superior": "IC 95 % superior", "victimas_en_la_muestra": "Víctimas en la muestra"},
    forzar_texto=("menos_de_100_victimas",), calcs=CALC_PLAT.values(),
    colores={"none:%s:nk" % C_GRUPO_PLAT: [("Mensajería", CIAN), ("Redes sociales", VIOLETA), ("Llamadas", AMARILLO), ("Resto", APAGADO)]})
x_plat = con_filtro_ds(x_plat, filtro_ds("plataforma", ["Correo"]))

ds_kpi, x_kpi = nueva_ds("A-edad_kpi.csv", {
    "anio": "Periodo", "pct_18_24": "% 18 a 24", "pct_60_mas": "% 60 y más", "veces": "Veces",
    "veces_ic95_inf": "Veces IC inf", "veces_ic95_sup": "Veces IC sup", "brecha_puntos": "Brecha (puntos)"},
    forzar_texto=("anio", "brecha_significativa"))


def solo(respuesta, columna):
    return 'IF [respuesta] = "%s" THEN [%s] END' % (respuesta, columna)


CALC_ACC = {
    C_PROT: calc(C_PROT, "% se protege", "real", solo("Protegerse", "porcentaje_de_victimas")),
    C_PROT_INF: calc(C_PROT_INF, "% se protege IC inf", "real", solo("Protegerse", "ic95_inferior")),
    C_PROT_SUP: calc(C_PROT_SUP, "% se protege IC sup", "real", solo("Protegerse", "ic95_superior")),
    C_DEN: calc(C_DEN, "% denuncia", "real", solo("Denunciar", "porcentaje_de_victimas")),
    C_DEN_INF: calc(C_DEN_INF, "% denuncia IC inf", "real", solo("Denunciar", "ic95_inferior")),
    C_DEN_SUP: calc(C_DEN_SUP, "% denuncia IC sup", "real", solo("Denunciar", "ic95_superior")),
    C_MARCA_ACC: calc(C_MARCA_ACC, "Marca de casos", "string",
                      'IF [menos_de_10_casos] = "True" THEN "†" ELSE "" END'),
    # Semáforo de las respuestas: no hacer nada (rojo), defenderse solas (ámbar), buscar ayuda o denunciar (verde)
    # Nivel numérico para colorear las celdas del mapa de calor (1 = buscan ayuda o denuncian,
    # 2 = se defienden solas, 3 = no hacen nada). Tiene que ser una medida: con una dimensión en el
    # color, Tableau dibuja cuadritos en vez de rellenar la celda.
    C_TIPO_ACC: calc(C_TIPO_ACC, "Tipo de respuesta (1 ayuda, 2 solas, 3 nada)", "real",
                     'IF [respuesta] = "Ignorar o no hacer nada" THEN 3 '
                     'ELSEIF [respuesta] = "Protegerse" OR [respuesta] = "Confrontar al agresor" THEN 2 '
                     'ELSE 1 END'),
}
ds_acc, x_acc = nueva_ds("B-edad_acciones.csv", {
    "grupo_de_edad": ("Edad", alias([("60+", "60 y más*")])), "respuesta": "Respuesta",
    "porcentaje_de_victimas": "% de las víctimas", "ic95_inferior": "IC 95 % inferior",
    "ic95_superior": "IC 95 % superior", "victimas_en_la_muestra": "Víctimas en la muestra",
    "casos_en_la_muestra": "Casos en la muestra", "incluye": "Incluye"},
    forzar_texto=("menos_de_100_victimas", "menos_de_10_casos"), calcs=CALC_ACC.values())

ds_nac, x_nac = nueva_ds("A-yucatan_vs_nacional.csv", {
    "anio": "Año", "yucatan_pct": "% Yucatán", "nacional_pct": "% País", "yucatan_ic95_inf": "Yucatán IC inf",
    "yucatan_ic95_sup": "Yucatán IC sup", "yucatan_vs_nacional": ("Yucatán contra el país", ""),
    "lugar": "Lugar", "lugar_min": "Lugar mín", "lugar_max": "Lugar máx"}, forzar_texto=("anio",),
    colores={"none:yucatan_vs_nacional:nk": [("arriba", ROJO), ("sin diferencia", AMBAR)]})
# Semáforo de otros grupos según H-GA-05 a 07: más ciberacoso en licenciatura y zona urbana (rojo),
# menos en primaria o menos y zona rural (verde); sexo sin diferencia y escolaridad intermedia (ámbar).
C_RIESGO = "Calculation_2026111400000000041"
CALC_CTX = {
    C_RIESGO: calc(C_RIESGO, "Nivel (semáforo)", "string",
                   'IF [grupo] = "Licenciatura o más" OR [grupo] = "Urbano" THEN "Más ciberacoso" '
                   'ELSEIF [grupo] = "Primaria o menos" OR [grupo] = "Rural" THEN "Menos ciberacoso" '
                   'ELSE "Intermedio o sin diferencia" END'),
}
ds_ctx, x_ctx = nueva_ds("A-contexto_grupos.csv", {
    "dimension": "Dimensión", "grupo": "Grupo", "pct": "% que vivió ciberacoso",
    "ic95_inf": "IC 95 % inferior", "ic95_sup": "IC 95 % superior", "casos_muestra": "Entrevistas en la muestra"},
    forzar_texto=("anio",), calcs=CALC_CTX.values(),
    colores={"none:%s:nk" % C_RIESGO: [("Más ciberacoso", ROJO), ("Intermedio o sin diferencia", AMBAR),
                                       ("Menos ciberacoso", VERDE)]})
x_ctx = con_filtro_ds(x_ctx, filtro_ds("dimension", ["Total"]))


# ---------------------------------------------------------------- hojas
def ref(ds, inst):
    return "[%s].[%s]" % (ds, inst)


def deps(ds, campos, calcs=None):
    """campos: lista de (campo, derivación) -> column-instance; calcs: dict nombre -> XML del cálculo."""
    out = ""
    usados = [c for c, _ in campos]
    for nombre, xml in (calcs or {}).items():
        if nombre in usados:
            out += xml.replace("      <", "            <").replace("        <calculation", "              <calculation")
    for campo, der in campos:
        sufijo = {"None": "nk", "Avg": "qk", "Sum": "qk", "Attribute": "nk"}[der]
        pref = {"None": "none", "Avg": "avg", "Sum": "sum", "Attribute": "attr"}[der]
        out += "            <column-instance column='[%s]' derivation='%s' name='[%s:%s:%s]' pivot='key' type='%s' />\n" % (
            campo, der, pref, campo, sufijo, "quantitative" if sufijo == "qk" else "nominal")
    return out


ESCALA_LETRA = 1.3


def _escala(at):
    at = dict(at)
    if "fontsize" in at:
        at["fontsize"] = str(round(float(at["fontsize"]) * ESCALA_LETRA))
    return at


def ftexto(runs):
    """runs: lista de (texto, atributos dict). '\n' parte párrafos."""
    out = ""
    for texto, at in runs:
        at = _escala(at)
        attrs = "".join(" %s='%s'" % (k, q(str(v))) for k, v in sorted(at.items()))
        partes = texto.split("\n")
        for i, p in enumerate(partes):
            if p:
                out += "<run%s>%s</run>" % (attrs, escape(p))
            if i < len(partes) - 1:
                out += "<run>Æ&#10;</run>"
    return "<formatted-text>%s</formatted-text>" % out


def titulo_runs(runs):
    return "      <layout-options>\n        <title>\n          %s\n        </title>\n      </layout-options>\n" % ftexto(runs)


def titulo_hoja(titulo, sub="", extra=(), kicker=""):
    runs = [(kicker + "\n", {"bold": "true", "fontsize": "9", "fontcolor": CORAL})] if kicker else []
    runs += [(titulo, {"bold": "true", "fontsize": "12", "fontcolor": TINTA})]
    if sub:
        runs += [("\n" + sub, {"fontsize": "9", "fontcolor": GRIS})]
    runs += list(extra)
    return "      <layout-options>\n        <title>\n          %s\n        </title>\n      </layout-options>\n" % ftexto(runs)


def oscuro(fondo=FONDO):
    """Estilo oscuro del pitch para una hoja: fondo, texto crema y sin líneas de cuadrícula ni divisiones."""
    reglas = [("worksheet", ["<format attr='color' value='%s' />" % TINTA]),
              ("table", ["<format attr='background-color' value='%s' />" % fondo])]
    reglas += [(e, ["<format attr='line-visibility' scope='%s' value='off' />" % sc for sc in ("rows", "cols")])
               for e in ("gridline", "zeroline", "table-div", "header-div")]
    NLX = chr(10)
    return "".join("          <style-rule element='%s'>%s%s%s          </style-rule>%s" % (
        e, NLX, "".join("            %s%s" % (f, NLX) for f in fs), "", NLX) for e, fs in reglas)


def hoja(nombre, ds, caption_ds, campos, filas, cols, marca, encodings, tooltip, label=None, filtros="",
         estilo="", estilo_pane="", titulo="", calcs=None, fondo=FONDO):
    cull = "false" if marca in ("Bar", "Text", "Square") else "true"
    lbl = ""
    if label:
        lbl = "            <customized-label>\n              <formatted-text>%s</formatted-text>\n            </customized-label>\n" % label
    return (
        "    <worksheet name='%(nombre)s'>\n%(titulo)s      <table>\n        <view>\n"
        "          <datasources>\n            <datasource caption='%(cap)s' name='%(ds)s' />\n          </datasources>\n"
        "          <datasource-dependencies datasource='%(ds)s'>\n%(deps)s          </datasource-dependencies>\n%(filtros)s"
        "          <aggregation value='true' />\n        </view>\n        <style>\n%(oscuro)s%(estilo)s        </style>\n"
        "        <panes>\n          <pane selection-relaxation-option='selection-relaxation-allow'>\n"
        "            <view>\n              <breakdown value='auto' />\n            </view>\n"
        "            <mark class='%(marca)s' />\n            <encodings>\n%(enc)s            </encodings>\n"
        "            <customized-tooltip>\n              <formatted-text>%(tt)s</formatted-text>\n            </customized-tooltip>\n%(lbl)s"
        "            <style>\n              <style-rule element='mark'>\n"
        "                <format attr='mark-labels-show' value='true' />\n                <format attr='mark-labels-cull' value='%(cull)s' />\n%(ep)s"
        "              </style-rule>\n            </style>\n          </pane>\n        </panes>\n"
        "        <rows>%(filas)s</rows>\n        <cols>%(cols)s</cols>\n      </table>\n"
        "      <simple-id uuid='%(uid)s' />\n    </worksheet>\n"
    ) % dict(nombre=q(nombre), titulo=titulo, cap=q(caption_ds), ds=ds, deps=deps(ds, campos, calcs), filtros=filtros,
             estilo=estilo, oscuro=oscuro(fondo), marca=marca, enc=encodings, tt=tooltip, lbl=lbl, ep=estilo_pane, cull=cull, filas=filas, cols=cols, uid=gid())


def run(texto, **at):
    at = _escala(at)
    attrs = "".join(" %s='%s'" % (k.replace("_", "-"), q(str(v))) for k, v in sorted(at.items()))
    return "<run%s><![CDATA[%s]]></run>" % (attrs, texto)


NL = run("Æ\n")


def color_continuo(campo_ref, colores, tipo, minimo=None, maximo=None, centro=None):
    at = ""
    if centro is not None:
        at += " center='%s'" % centro
    if maximo is not None:
        at += " max='%s'" % maximo
    if minimo is not None:
        at += " min='%s'" % minimo
    return ("          <style-rule element='mark'>\n"
            "            <encoding attr='color'%s field='%s' type='custom-interpolated'>\n"
            "              <color-palette custom='true' name='' type='%s'>\n%s"
            "              </color-palette>\n            </encoding>\n          </style-rule>\n") % (
        at, campo_ref, tipo, "".join("                <color>%s</color>\n" % c for c in colores))


def titulo_eje(campo_ref, texto, scope="cols"):
    return ("          <style-rule element='axis'>\n"
            "            <format attr='title' class='0' field='%s' scope='%s' value='%s' />\n"
            "          </style-rule>\n") % (campo_ref, scope, q(texto))


def sin_eje(campo_ref, scope="cols"):
    """Oculta el eje de una medida (como desmarcar «Mostrar encabezado» en Tableau): las barras ya llevan etiqueta."""
    return ("          <style-rule element='axis'>\n"
            "            <format attr='display' class='0' field='%s' scope='%s' value='false' />\n"
            "          </style-rule>\n") % (campo_ref, scope)


def ancho_encabezado(campo_ref, px):
    return ("          <style-rule element='header'>\n"
            "            <format attr='width' field='%s' value='%d' />\n          </style-rule>\n") % (campo_ref, px)


def orden_manual(campo_ref, valores):
    return ("          <sort class='manual' column='%s' direction='ASC'>\n            <dictionary>\n%s            </dictionary>\n          </sort>\n") % (
        campo_ref, "".join("              <bucket>&quot;%s&quot;</bucket>\n" % q(v) for v in valores))


def filtro_excluir(campo_ref, nivel, miembros):
    mm = "".join("              <groupfilter function='member' level='[%s]' member='&quot;%s&quot;' />\n" % (nivel, q(m)) for m in miembros)
    return ("          <filter class='categorical' column='%s'>\n"
            "            <groupfilter function='except' user:ui-domain='database' user:ui-enumeration='exclusive' user:ui-marker='enumerate'>\n"
            "              <groupfilter function='level-members' level='[%s]' />\n%s"
            "            </groupfilter>\n          </filter>\n") % (campo_ref, nivel, mm)


def filtro_incluir(campo_ref, nivel, miembro):
    return ("          <filter class='categorical' column='%s'>\n"
            "            <groupfilter function='member' level='[%s]' member='&quot;%s&quot;' user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />\n"
            "          </filter>\n") % (campo_ref, nivel, q(miembro))


def slices(*campos):
    return "          <slices>\n%s          </slices>\n" % "".join("            <column>%s</column>\n" % c for c in campos)


def tooltips(*cols):
    return "".join("              <tooltip column='%s' />\n" % c for c in cols)


# Nombres de hojas
H_BRECHA = "1a · Brecha"
H_MATRIZ = "1b · Matriz edad x año"
H_PLAT = "2 · Plataforma por edad"
H_ACC_KPI = "3 · Qué hacen"
H_RANK = "Contexto · Ranking"
H_ACC = "Contexto · Acciones por edad"
H_GRUPOS = "Contexto · Otros grupos"

# 1a. Brecha (KPI de texto)
K = lambda i: ref(ds_kpi, i)
h_brecha = hoja(
    H_BRECHA, ds_kpi, "A-edad_kpi",
    [("anio", "None"), ("veces", "Sum"), ("pct_18_24", "Sum"), ("pct_60_mas", "Sum"),
     ("veces_ic95_inf", "Sum"), ("veces_ic95_sup", "Sum")],
    "", "", "Automatic",
    "".join("              <text column='%s' />\n" % K(c) for c in
            ("sum:veces:qk", "sum:pct_18_24:qk", "sum:pct_60_mas:qk", "sum:veces_ic95_inf:qk", "sum:veces_ic95_sup:qk")),
    run("Brecha entre 18–24 años y 60 y más, MOCIBA 2019–2025 juntos, indicador comparable"),
    # Las cifras van en el título de la hoja (con los campos de la vista), no como texto de la marca:
    # el título se ajusta en varias líneas, y una marca de texto que no cabe sale como «####».
    label=run(" "),
    filtros=filtro_incluir(K("none:anio:nk"), "none:anio:nk", "2019-2025") + slices(K("none:anio:nk")),
    fondo=PANEL,
    titulo=titulo_runs([
        ("QUIÉN: LA EDAD DECIDE · IC 95 %%: <%s> a <%s>" % (K("sum:veces_ic95_inf:qk"), K("sum:veces_ic95_sup:qk")),
         {"fontsize": "8", "bold": "true", "fontcolor": GRIS}),
        ("\n<%s>× más" % K("sum:veces:qk"), {"fontsize": "22", "bold": "true", "fontcolor": CORAL}),
        ("\n18 a 24 años: 1 de cada 3 (<%s> %%)" % K("sum:pct_18_24:qk"), {"fontsize": "9", "bold": "true", "fontcolor": TINTA}),
        ("\n60 y más: 1 de cada 12 (<%s> %%) · 2019–2025" % K("sum:pct_60_mas:qk"), {"fontsize": "8", "fontcolor": GRIS})]))

# 1b. Matriz edad x año (color = puntos contra el promedio del año)
A = lambda i: ref(ds_anio, i)
ANIOS = ["2019", "2020", "2021", "2022", "2023", "2024", "2025", "2019-2025"]
h_matriz = hoja(
    H_MATRIZ, ds_anio, "A-edad_anio",
    [("anio", "None"), ("grupo_edad", "None"), ("pct", "Avg"), ("ic95_inf", "Avg"), ("ic95_sup", "Avg"),
     ("casos_muestra", "Sum"), ("precision", "Attribute"), (C_PUNTOS, "Avg"), (C_MARCA_ANIO, "Attribute")],
    A("none:grupo_edad:nk"), A("none:anio:nk"), "Square",
    "              <color column='%s' />\n" % A("avg:%s:qk" % C_PUNTOS)
    + "              <text column='%s' />\n              <text column='%s' />\n" % (A("avg:pct:qk"), A("attr:%s:nk" % C_MARCA_ANIO))
    + tooltips(A("avg:ic95_inf:qk"), A("avg:ic95_sup:qk"), A("sum:casos_muestra:qk"), A("attr:precision:nk")),
    run("Edad: ", bold="true") + run("<%s>" % A("none:grupo_edad:nk")) + run("   Año: ", bold="true") + run("<%s>" % A("none:anio:nk")) + NL
    + run("<%s> %%" % A("avg:pct:qk"), bold="true", fontsize="12") + run(" vivió ciberacoso en los 12 meses previos") + NL
    + run("<%s> puntos contra el promedio de Yucatán ese año" % A("avg:%s:qk" % C_PUNTOS)) + NL
    + run("IC 95 %%: <%s> – <%s> %%" % (A("avg:ic95_inf:qk"), A("avg:ic95_sup:qk"))) + NL
    + run("Entrevistas: <%s> · precisión <%s>" % (A("sum:casos_muestra:qk"), A("attr:precision:nk")), fontcolor=GRIS) + NL
    + run("Clic: la gráfica 2 muestra las plataformas de esta edad", fontcolor=GRIS, italic="true"),
    label=run("<%s>" % A("avg:pct:qk")) + run("<%s>" % A("attr:%s:nk" % C_MARCA_ANIO)),
    filtros=filtro_excluir(A("none:grupo_edad:nk"), "none:grupo_edad:nk", ["Total"])
    + orden_manual(A("none:anio:nk"), ANIOS) + slices(A("none:grupo_edad:nk")),
    estilo=color_continuo(A("avg:%s:qk" % C_PUNTOS), MATRIZ, "ordered-diverging",
                          minimo="-20.0", maximo="20.0", centro="0.0")
    + ancho_encabezado(A("none:grupo_edad:nk"), 74),
    titulo=titulo_hoja("De 12 a 24 años, arriba del promedio los siete años", "", [
        ("\n% que vivió ciberacoso.  ", {"fontsize": "8", "fontcolor": GRIS}),
        ("■", {"fontsize": "9", "fontcolor": CORAL}), (" arriba del promedio de Yucatán ese año  ", {"fontsize": "8", "fontcolor": TINTA}),
        ("■", {"fontsize": "9", "fontcolor": MATRIZ[1]}), (" cerca  ", {"fontsize": "8", "fontcolor": TINTA}),
        ("■", {"fontsize": "9", "fontcolor": APAGADO}), (" abajo", {"fontsize": "8", "fontcolor": TINTA}),
        ("\n7 años = 2019–2025 · *2019: 508 entrevistas · † precisión baja · clic en una edad: filtra la 02",
         {"fontsize": "8", "fontcolor": GRIS})], kicker="01 · QUIÉN, AÑO POR AÑO"),
    calcs=CALC_ANIO)

# 2. Plataforma por edad: tres paneles (uno por canal), edades en filas. Cada barra se dibuja sobre un
# riel gris de 0 a 100 = las 100 víctimas de esa edad: la parte de color son las que lo vivieron por ese
# canal y la gris, las que no. Así cada barra se lee sola («de 100») y no como parte de un total que
# reparte a las víctimas entre los tres canales (una víctima puede contar en varios: P11 del MOCIBA).
# Doble eje con el mismo formato que guarda Tableau (libro de ejemplo «Indicadores mundiales»): riel y
# barra en el mismo eje sincronizado, fijo de 0 a 100, con los ejes ocultos.
P = lambda i: ref(ds_plat, i)
PCT, CIEN = P("avg:porcentaje_de_victimas:qk"), P("avg:%s:qk" % C_CIEN)
TT_PLAT = (
    run("<%s>" % PCT, bold="true", fontsize="12")
    + run(" de cada 100 víctimas de <%s> años lo vivieron por <%s>" % (P("none:grupo_de_edad:nk"), P("none:plataforma:nk")))
    + run(" (pueden haberlo vivido también por otros canales).") + NL
    + run("IC 95 %%: <%s> – <%s> · víctimas en la muestra: <%s>" % (
        P("avg:ic95_inferior:qk"), P("avg:ic95_superior:qk"), P("sum:victimas_en_la_muestra:qk")), fontcolor=GRIS))
TT_ENC = tooltips(PCT, P("avg:ic95_inferior:qk"), P("avg:ic95_superior:qk"), P("sum:victimas_en_la_muestra:qk"))


def pane_plat(pid, eje, marcas, etiqueta, estilo_marca):
    lbl = ("            <customized-label>\n              <formatted-text>%s</formatted-text>\n"
           "            </customized-label>\n" % etiqueta) if etiqueta else ""
    return (
        "          <pane id='%d' selection-relaxation-option='selection-relaxation-allow' x-axis-name='%s'>\n"
        "            <view>\n              <breakdown value='auto' />\n            </view>\n"
        "            <mark class='Bar' />\n            <encodings>\n%s            </encodings>\n"
        "            <customized-tooltip>\n              <formatted-text>%s</formatted-text>\n            </customized-tooltip>\n%s"
        "            <style>\n              <style-rule element='mark'>\n%s              </style-rule>\n            </style>\n"
        "          </pane>\n") % (pid, eje, marcas, TT_PLAT, lbl, estilo_marca)


h_plat = (
    "    <worksheet name='%s'>\n" % q(H_PLAT)
    + titulo_hoja("Mensajería en 12–17, redes en 18–34 y llamadas desde los 45", "",
                  [("\nDe cada 100 víctimas de cada edad, cuántas lo vivieron por cada canal. ", {"fontsize": "8", "fontcolor": TINTA}),
                   ("Una víctima puede contar en varios: no suman 100.", {"fontsize": "8", "bold": "true", "fontcolor": TINTA}),
                   ("\n■", {"fontsize": "9", "fontcolor": CIAN}), (" ■", {"fontsize": "9", "fontcolor": VIOLETA}),
                   (" ■", {"fontsize": "9", "fontcolor": AMARILLO}), (" el canal que más pesa en esa edad   ", {"fontsize": "8", "fontcolor": TINTA}),
                   ("■", {"fontsize": "9", "fontcolor": APAGADO}), (" los demás   ", {"fontsize": "8", "fontcolor": TINTA}),
                   ("■", {"fontsize": "9", "fontcolor": RIEL}), (" no lo vivieron por ese canal · *60+: muestra chica", {"fontsize": "8", "fontcolor": GRIS})],
                  kicker="02 · POR DÓNDE")
    + "      <table>\n        <view>\n"
    "          <datasources>\n            <datasource caption='B-edad_plataforma' name='%s' />\n          </datasources>\n" % ds_plat
    + "          <datasource-dependencies datasource='%s'>\n%s          </datasource-dependencies>\n" % (ds_plat, deps(ds_plat, [
        ("grupo_de_edad", "None"), ("plataforma", "None"), ("porcentaje_de_victimas", "Avg"), ("ic95_inferior", "Avg"),
        ("ic95_superior", "Avg"), ("victimas_en_la_muestra", "Sum"), (C_GRUPO_PLAT, "None"), (C_CIEN, "Avg")], CALC_PLAT))
    + orden_manual(P("none:plataforma:nk"), ["Mensajería", "Redes sociales", "Llamadas"])
    + "          <aggregation value='true' />\n        </view>\n        <style>\n" + oscuro() +
    "          <style-rule element='axis'>\n"
    "            <encoding attr='space' class='0' field='%s' field-type='quantitative' max='100.0' min='0.0' range-type='fixed' scope='cols' type='space' />\n"
    "            <encoding attr='space' class='0' field='%s' field-type='quantitative' fold='true' scope='cols' synchronized='true' type='space' />\n"
    "            <format attr='display' class='0' field='%s' scope='cols' value='false' />\n"
    "            <format attr='display' class='0' field='%s' scope='cols' value='false' />\n"
    "          </style-rule>\n" % (CIEN, PCT, CIEN, PCT)
    + ancho_encabezado(P("none:grupo_de_edad:nk"), 90)
    + "        </style>\n        <panes>\n"
    "          <pane selection-relaxation-option='selection-relaxation-allow'>\n"
    "            <view>\n              <breakdown value='auto' />\n            </view>\n"
    "            <mark class='Bar' />\n          </pane>\n"
    # Panel 1: el riel gris de 100, sin etiqueta. Panel 2: la barra real, encima, con su cifra.
    + pane_plat(1, CIEN, TT_ENC, "",
                "                <format attr='mark-labels-show' value='false' />\n"
                "                <format attr='mark-color' value='%s' />\n" % RIEL)
    + pane_plat(2, PCT, "              <color column='%s' />\n              <text column='%s' />\n" % (P("none:%s:nk" % C_GRUPO_PLAT), PCT)
                + TT_ENC.replace("              <tooltip column='%s' />\n" % PCT, ""),
                run("<%s>" % PCT, fontsize="8"),
                "                <format attr='mark-labels-show' value='true' />\n"
                "                <format attr='mark-labels-cull' value='false' />\n")
    + "        </panes>\n"
    "        <rows>%s</rows>\n        <cols>(%s / (%s + %s))</cols>\n      </table>\n" % (P("none:grupo_de_edad:nk"), P("none:plataforma:nk"), CIEN, PCT)
    + "      <simple-id uuid='%s' />\n    </worksheet>\n" % gid())

# 3. Qué hacen: cifra de «Todas las edades» (B-edad_acciones.csv)
C = lambda i: ref(ds_acc, i)
h_acc_kpi = hoja(
    H_ACC_KPI, ds_acc, "B-edad_acciones",
    [("grupo_de_edad", "None"), (C_PROT, "Sum"), (C_PROT_INF, "Sum"), (C_PROT_SUP, "Sum"),
     (C_DEN, "Sum"), (C_DEN_INF, "Sum"), (C_DEN_SUP, "Sum")],
    "", "", "Automatic",
    "".join("              <text column='%s' />\n" % C("sum:%s:qk" % c) for c in (C_PROT, C_PROT_INF, C_PROT_SUP, C_DEN, C_DEN_INF, C_DEN_SUP)),
    run("Víctimas de todas las edades, MOCIBA 2021–2025 juntos"),
    label=run(" "),  # las cifras van en el título (ver la nota de la hoja 1a)
    filtros=filtro_incluir(C("none:grupo_de_edad:nk"), "none:grupo_de_edad:nk", "Todas las edades") + slices(C("none:grupo_de_edad:nk")),
    fondo=PANEL,
    titulo=titulo_runs([
        ("QUÉ HACEN LAS VÍCTIMAS", {"fontsize": "8", "bold": "true", "fontcolor": GRIS}),
        ("\n<%s> %% denuncia" % C("sum:%s:qk" % C_DEN), {"fontsize": "22", "bold": "true", "fontcolor": CORAL}),
        ("\n<%s> %% se protege sola" % C("sum:%s:qk" % C_PROT), {"fontsize": "9", "bold": "true", "fontcolor": TINTA}),
        ("\ndenunciar = escuela, trabajo o autoridad", {"fontsize": "8", "fontcolor": GRIS})]),
    calcs=CALC_ACC)

# Contexto · Ranking (Yucatán contra el país)
N = lambda i: ref(ds_nac, i)
h_rank = hoja(
    H_RANK, ds_nac, "A-yucatan_vs_nacional",
    [("anio", "None"), ("yucatan_vs_nacional", "None"), ("yucatan_pct", "Avg"), ("nacional_pct", "Avg"),
     ("lugar", "Sum"), ("lugar_min", "Sum"), ("lugar_max", "Sum"), ("yucatan_ic95_inf", "Avg"), ("yucatan_ic95_sup", "Avg")],
    N("avg:yucatan_pct:qk"), N("none:anio:nk"), "Bar",
    "              <color column='%s' />\n" % N("none:yucatan_vs_nacional:nk")
    + "".join("              <text column='%s' />\n" % N(c) for c in ("avg:yucatan_pct:qk", "sum:lugar:qk"))
    + tooltips(N("avg:nacional_pct:qk"), N("sum:lugar_min:qk"), N("sum:lugar_max:qk"), N("avg:yucatan_ic95_inf:qk"), N("avg:yucatan_ic95_sup:qk")),
    run("<%s>" % N("none:anio:nk"), bold="true") + NL
    + run("Yucatán: <%s> %% (IC 95 %%: <%s> – <%s>)" % (N("avg:yucatan_pct:qk"), N("avg:yucatan_ic95_inf:qk"), N("avg:yucatan_ic95_sup:qk"))) + NL
    + run("País: <%s> %% · Yucatán <%s> del país" % (N("avg:nacional_pct:qk"), N("none:yucatan_vs_nacional:nk"))) + NL
    + run("Lugar <%s> de 32, compatible con cualquier lugar del <%s> al <%s>" % (N("sum:lugar:qk"), N("sum:lugar_min:qk"), N("sum:lugar_max:qk")), fontcolor=GRIS),
    label=run("<%s> %%" % N("avg:yucatan_pct:qk"), bold="true") + NL + run("lugar <%s>" % N("sum:lugar:qk"), fontsize="8"),
    estilo=titulo_eje(N("avg:yucatan_pct:qk"), "% Yucatán", scope="rows"),
    titulo=titulo_hoja("El ranking engaña: del lugar 1 (2024) al 25 (2025)",
                       "% de usuarios con ciberacoso en Yucatán y su lugar entre 32 entidades", kicker="EL RANKING", extra=
                       [("\n■", {"fontsize": "9", "fontcolor": ROJO}), (" arriba del país    ", {"fontsize": "9", "bold": "true", "fontcolor": TINTA}),
                        ("■", {"fontsize": "9", "fontcolor": AMBAR}), (" sin diferencia significativa", {"fontsize": "9", "fontcolor": TINTA})]))

# Contexto · Acciones por edad (mapa de calor respuesta x edad, sin «Todas las edades»)
h_acc = hoja(
    H_ACC, ds_acc, "B-edad_acciones",
    [("respuesta", "None"), ("grupo_de_edad", "None"), ("porcentaje_de_victimas", "Avg"),
     ("ic95_inferior", "Avg"), ("ic95_superior", "Avg"), ("victimas_en_la_muestra", "Sum"),
     ("casos_en_la_muestra", "Sum"), ("incluye", "Attribute"), (C_MARCA_ACC, "Attribute"), (C_TIPO_ACC, "Avg")],
    C("none:respuesta:nk"), C("none:grupo_de_edad:nk"), "Square",
    "              <color column='%s' />\n              <text column='%s' />\n              <text column='%s' />\n"
    % (C("avg:%s:qk" % C_TIPO_ACC), C("avg:porcentaje_de_victimas:qk"), C("attr:%s:nk" % C_MARCA_ACC))
    + tooltips(C("avg:ic95_inferior:qk"), C("avg:ic95_superior:qk"), C("sum:victimas_en_la_muestra:qk"),
               C("sum:casos_en_la_muestra:qk"), C("attr:incluye:nk")),
    run("<%s> %%" % C("avg:porcentaje_de_victimas:qk"), bold="true", fontsize="12")
    + run(" de las víctimas de <%s> años: <%s>" % (C("none:grupo_de_edad:nk"), C("none:respuesta:nk"))) + NL
    + run("Incluye: <%s>" % C("attr:incluye:nk"), fontcolor=GRIS) + NL
    + run("IC 95 %%: <%s> – <%s> %% · víctimas en la muestra: <%s> · casos: <%s>" % (
        C("avg:ic95_inferior:qk"), C("avg:ic95_superior:qk"), C("sum:victimas_en_la_muestra:qk"), C("sum:casos_en_la_muestra:qk"))),
    label=run("<%s>" % C("avg:porcentaje_de_victimas:qk")) + run("<%s>" % C("attr:%s:nk" % C_MARCA_ACC)),
    filtros=filtro_excluir(C("none:grupo_de_edad:nk"), "none:grupo_de_edad:nk", ["Todas las edades"])
    # Filas agrupadas por color: primero el peligro (rojo), luego ámbar y al final verde.
    + orden_manual(C("none:respuesta:nk"), ["Ignorar o no hacer nada", "Protegerse", "Confrontar al agresor",
                                             "Contarle a alguien", "Reportar a la plataforma", "Denunciar"])
    + slices(C("none:grupo_de_edad:nk")),
    # Tres colores fijos: 1 → azul claro, 2 → durazno claro, 3 → coral claro (centro en 2).
    estilo=color_continuo(C("avg:%s:qk" % C_TIPO_ACC), [VERDE_T, AMBAR_T, ROJO_T], "ordered-diverging",
                          minimo="1.0", maximo="3.0", centro="2.0")
    + ancho_encabezado(C("none:respuesta:nk"), 200),
    titulo=titulo_hoja("64 % a 74 % se protege sola; menos de 1 de cada 10 denuncia",
                       "% de las víctimas de cada edad, 2021–2025 · † menos de 10 casos",
                       [("\n■", {"fontsize": "9", "fontcolor": ROJO_T}), (" no hacen nada   ", {"fontsize": "9", "fontcolor": TINTA}),
                        ("■", {"fontsize": "9", "fontcolor": AMBAR_T}), (" se defienden solas   ", {"fontsize": "9", "fontcolor": TINTA}),
                        ("■", {"fontsize": "9", "fontcolor": VERDE_T}), (" buscan ayuda o denuncian", {"fontsize": "9", "fontcolor": TINTA})]),
    calcs=CALC_ACC)

# Contexto · Otros grupos (sexo, escolaridad y zona, 2019–2025)
X = lambda i: ref(ds_ctx, i)
h_grupos = hoja(
    H_GRUPOS, ds_ctx, "A-contexto_grupos",
    [("anio", "None"), ("dimension", "None"), ("grupo", "None"), ("pct", "Avg"),
     ("ic95_inf", "Avg"), ("ic95_sup", "Avg"), ("casos_muestra", "Sum"), (C_RIESGO, "None")],
    "(%s / %s)" % (X("none:dimension:nk"), X("none:grupo:nk")), X("avg:pct:qk"), "Bar",
    "              <color column='%s' />\n              <text column='%s' />\n" % (X("none:%s:nk" % C_RIESGO), X("avg:pct:qk"))
    + tooltips(X("avg:ic95_inf:qk"), X("avg:ic95_sup:qk"), X("sum:casos_muestra:qk")),
    run("<%s>: " % X("none:grupo:nk"), bold="true") + run("<%s> %%" % X("avg:pct:qk")) + NL
    + run("IC 95 %%: <%s> – <%s> %% · entrevistas: <%s> · 2019–2025" % (X("avg:ic95_inf:qk"), X("avg:ic95_sup:qk"), X("sum:casos_muestra:qk"))),
    label=run("<%s>" % X("avg:pct:qk"), fontsize="8"),
    filtros=filtro_incluir(X("none:anio:nk"), "none:anio:nk", "2019-2025")
    + orden_manual(X("none:grupo:nk"), ["Hombre", "Mujer", "Primaria o menos", "Secundaria", "Bachillerato o técnico",
                                        "Licenciatura o más", "Rural", "Urbano"])
    + slices(X("none:anio:nk")),
    estilo=sin_eje(X("avg:pct:qk")) + ancho_encabezado(X("none:grupo:nk"), 176),
    titulo=titulo_hoja("Más con licenciatura (28.6 %) y en zona urbana (24.6 %)",
                       "2019–2025 juntos · hombres 24.4 % y mujeres 23.3 %: sin diferencia",
                       [("\n■", {"fontsize": "9", "fontcolor": ROJO}), (" más ciberacoso   ", {"fontsize": "9", "fontcolor": TINTA}),
                        ("■", {"fontsize": "9", "fontcolor": AMBAR}), (" intermedio o sin diferencia   ", {"fontsize": "9", "fontcolor": TINTA}),
                        ("■", {"fontsize": "9", "fontcolor": VERDE}), (" menos ciberacoso", {"fontsize": "9", "fontcolor": TINTA})]),
    calcs=CALC_CTX)

# ---------------------------------------------------------------- dashboards
def z_estilo(margen=4, fondo=None, borde=None, relleno=None):
    s = "            <zone-style>\n"
    if borde:
        s += "              <format attr='border-color' value='%s' />\n              <format attr='border-style' value='solid' />\n              <format attr='border-width' value='1' />\n" % borde
    else:
        s += "              <format attr='border-color' value='#444444' />\n              <format attr='border-style' value='none' />\n              <format attr='border-width' value='0' />\n"
    s += "              <format attr='margin' value='%d' />\n" % margen
    if relleno is not None:
        s += "              <format attr='padding' value='%d' />\n" % relleno
    if fondo:
        s += "              <format attr='background-color' value='%s' />\n" % fondo
    return s + "            </zone-style>\n"


class Ids:
    n = 100

    @classmethod
    def sig(cls):
        cls.n += 1
        return cls.n


def z(x, y, w, h, contenido="", **at):
    attrs = "".join(" %s='%s'" % (k.replace("_", "-"), q(str(v))) for k, v in at.items())
    return "<zone h='%d' id='%d'%s w='%d' x='%d' y='%d'>\n%s</zone>\n" % (h, Ids.sig(), attrs, w, x, y, contenido)


def z_texto(x, y, w, h, runs, fondo=None, borde=None):
    """Texto. Con fondo es una tarjeta: margen de 5 px (deja ver el fondo entre tarjetas) y relleno de 10."""
    if fondo:
        return z(x, y, w, h, ftexto(runs) + "\n" + z_estilo(5, fondo, borde, relleno=10), type_v2="text")
    return z(x, y, w, h, ftexto(runs) + "\n" + z_estilo(8, fondo, borde), type_v2="text")


def z_hoja(x, y, w, h, nombre, fondo=None):
    if fondo:
        return z(x, y, w, h, z_estilo(5, fondo, relleno=6), name=nombre)
    return z(x, y, w, h, z_estilo(4), name=nombre)


def z_boton(x, y, w, h, texto, ventana_destino):
    """Botón de navegación de Tableau (objeto «Navegación»): va al dashboard de esa ventana."""
    boton = (
        "<button action='tabdoc:goto-sheet window-id=&quot;%s&quot;' button-type='text'>\n"
        "  <button-visual-state>\n"
        "    <caption>%s</caption>\n"
        "    <button-caption-font-style bold='true' fontcolor='%s' fontsize='12' />\n"
        "    <format attr='background-color' value='%s' />\n"
        "  </button-visual-state>\n"
        "</button>\n") % (ventana_destino, escape(texto), OSCURO_TXT, CORAL)
    return z(x, y, w, h, boton + z_estilo(4), type_v2="dashboard-object")


def flujo(x, y, w, h, hijos, horz=True):
    return z(x, y, w, h, "".join(hijos), param="horz" if horz else "vert", type_v2="layout-flow")


def dashboard(nombre, ancho, alto, zonas):
    return (
        "    <dashboard enable-sort-zone-taborder='true' name='%s'>\n      <style />\n"
        "      <size sizing-mode='automatic' />\n      <zones>\n"
        "<zone h='100000' id='%d' type-v2='layout-basic' w='100000' x='0' y='0'>\n%s%s</zone>\n"
        "      </zones>\n      <simple-id uuid='%s' />\n    </dashboard>\n"
    ) % (q(nombre), Ids.sig(), zonas, z_estilo(8, FONDO), gid())


D1 = "Historia"
D2 = "Contexto"
VENTANA_D1 = gid()  # simple-id de la ventana de cada dashboard (los botones apuntan aquí)
VENTANA_D2 = gid()

# Coordenadas en unidades de 100000 (x, y, ancho, alto); tamaños fijos en píxeles para que
# Tableau respete la distribución. Dashboard de 1280 x 760 (cabe en una pantalla de 768 de alto).
ANCHO_PX, ALTO_PX = 1920, 1080
EX, EY = 1920 / 1280, 1080 / 760  # escala de los tamaños medidos en 1280 x 760
M = int(100000 * 8 / ANCHO_PX)  # margen de 8 px
W = 100000 - 2 * M


def fijar(zona, px):
    return zona.replace("<zone ", "<zone fixed-size='%d' is-fixed='true' " % px, 1)


def filas(spec):
    """spec: lista de (alto_px o None, [(ancho_px o None, fn(x,y,w,h)), ...]). None = toma lo que sobra."""
    spec = [(round(a * EY) if a else None, [(round(w * EX) if w else None, fn) for w, fn in celdas]) for a, celdas in spec]
    usados = sum(a for a, _ in spec if a)
    libre = ALTO_PX - 16 - usados
    out, y = [], M
    for alto_px, celdas in spec:
        apx = alto_px or libre
        alto = int(100000 * apx / ALTO_PX)
        if len(celdas) == 1:
            zona = celdas[0][1](M, y, W, alto)
        else:
            usados_w = sum(c[0] for c in celdas if c[0])
            x, hijos = M, []
            for ancho_px, fn in celdas:
                wpx = ancho_px or (ANCHO_PX - 16 - usados_w)
                w = int(100000 * wpx / ANCHO_PX)
                hz = fn(x, y, w, alto)
                hijos.append(fijar(hz, wpx) if ancho_px else hz)
                x += w
            zona = flujo(M, y, W, alto, hijos)
        out.append(fijar(zona, alto_px) if alto_px else zona)
        y += alto
    return flujo(M, M, W, y - M, out, horz=False)


# Medidas tomadas del PDF exportado por Tableau (px reales por carácter / alto de línea):
# 8 pt ≈ 6.6 / 18 · 9 pt ≈ 7.8 / 21 · 10 pt ≈ 8.7 / 23 · 12 pt negrita ≈ 10.3 / 27 · 15 pt negrita ≈ 12.6 / 34.
# Cada texto de abajo está medido para que quepa en su zona sin cortarse.


def b(texto, tam, color=TINTA, negrita=False):
    """Atajo para un tramo de texto con tamaño y color."""
    at = {"fontsize": str(tam), "fontcolor": color}
    if negrita:
        at["bold"] = "true"
    return (texto, at)


# Encabezado (como la portada del pitch)
titulo1 = [b("DATOSTADA MX 2026 · RETO YUCATÁN DIGITAL · DETRÁS DE LA PANTALLA", 9, CORAL, True),
           b("\nLa edad decide quién vive el ciberacoso en Yucatán y por dónde le llega", 18, TINTA, True),
           b("\nINEGI, MOCIBA 2019–2025 · usuarios de internet de 12 años o más · para la Secretaría de Educación (SEGEY), "
             "escuelas, universidades y Policía Cibernética", 9, GRIS)]

# Tarjetas de resumen. La 2 y la 3 son hojas (sus cifras salen del CSV); la 1 y la 4 son texto con cifras
# de A-contexto_grupos.csv (Total 2019-2025: 23.8 %) y A-yucatan_vs_nacional.csv (lugar 1 en 2024 y 25 en 2025).
tarjeta_cuantos = [b("CUÁNTOS", 8, GRIS, True),
                   b("\n1 de cada 4", 20, CORAL, True),
                   b("\nde los usuarios de internet", 9, TINTA, True),
                   b("\nde 12+ lo vivió: 23.8 %, 2019–2025", 8, GRIS)]
tarjeta_ranking = [b("EL RANKING ENGAÑA", 8, GRIS, True),
                   b("\n#1 → #25", 20, AMARILLO, True),
                   b("\nlugar de Yucatán, 2024 → 2025", 9, TINTA, True),
                   b("\nel lugar salta; quién lo vive, no", 8, GRIS)]

# 03 · Entonces qué: una tarjeta por edad, con el color de su canal (lámina 5 del pitch)
entonces_titulo = [b("03 · ENTONCES QUÉ", 9, CORAL, True),
                   b("\nUna campaña genérica no llega a nadie", 12, TINTA, True)]


def tarjeta_accion(edad, quien, publico, accion):
    return [b(edad, 18, OSCURO_TXT, True), b("   " + quien, 10, OSCURO_TXT, True),
            b("\n" + publico, 8, OSCURO_TXT), b("\n" + accion, 10, OSCURO_TXT, True)]


accion_1217 = tarjeta_accion("12–17", "Escuelas y SEGEY", "secundarias y prepas · mensajería",
                             "Privacidad y seguridad en chats")
accion_1834 = tarjeta_accion("18–34", "Universidades y SEGEY", "universitarios · redes sociales",
                             "Campañas en redes sociales")
accion_45 = tarjeta_accion("45+", "Policía Cibernética", "mayores de 45 · llamadas",
                           "Alertas y denuncia fácil")

instruccion1 = [b("▶ Elige una edad: ", 10, CORAL, True),
                b("clic en una fila de la matriz 01 y la gráfica 02 muestra solo esa edad (otro clic: todas).", 10, TINTA)]

# El pie cabe en 3 líneas de 8 pt (~186 caracteres por línea).
FUENTE = (
    "Fuente: INEGI, MOCIBA 2019–2025 (microdatos), Yucatán · % de usuarios de internet de 12+ con ciberacoso en 12 meses, "
    "con factores de expansión; matriz y brecha: 10 situaciones comunes.\n"
    "Plataformas y acciones: % de las víctimas, 2021–2025 juntos (no suman 100) · IC 95 % en los tooltips · * muestra chica · "
    "† precisión baja · relación, no causa.\n"
    "Uso de IA: Claude (Anthropic) apoyó la armonización de los microdatos, los scripts de estimación y este libro; "
    "el equipo verificó las cifras contra INEGI.")
fuente = [b(FUENTE, 8, GRIS)]

# Alto: 760 − 16 de margen = 744 = 84 + 148 + 288 + 124 + 36 + 64
zonas1 = filas([
    (84, [(None, lambda x, y, w, h: z_texto(x, y, w, h, titulo1))]),
    (148, [(290, lambda x, y, w, h: z_texto(x, y, w, h, tarjeta_cuantos, fondo=PANEL)),
           (340, lambda x, y, w, h: z_hoja(x, y, w, h, H_BRECHA, fondo=PANEL)),
           (340, lambda x, y, w, h: z_hoja(x, y, w, h, H_ACC_KPI, fondo=PANEL)),
           (None, lambda x, y, w, h: z_texto(x, y, w, h, tarjeta_ranking, fondo=PANEL))]),
    (None, [(600, lambda x, y, w, h: z_hoja(x, y, w, h, H_MATRIZ)),
            (None, lambda x, y, w, h: z_hoja(x, y, w, h, H_PLAT))]),
    (124, [(232, lambda x, y, w, h: z_texto(x, y, w, h, entonces_titulo)),
           (344, lambda x, y, w, h: z_texto(x, y, w, h, accion_1217, fondo=CIAN)),
           (344, lambda x, y, w, h: z_texto(x, y, w, h, accion_1834, fondo=VIOLETA)),
           (None, lambda x, y, w, h: z_texto(x, y, w, h, accion_45, fondo=AMARILLO))]),
    (36, [(None, lambda x, y, w, h: z_texto(x, y, w, h, instruccion1)),
          (260, lambda x, y, w, h: z_boton(x, y, w, h, "Ver contexto →", VENTANA_D2))]),
    (64, [(None, lambda x, y, w, h: z_texto(x, y, w, h, fuente))]),
])

titulo2 = [b("CONTEXTO · LO QUE RESPALDA LA HISTORIA", 9, CORAL, True),
           b("\nEl ranking cambia cada año; lo que se repite es la edad", 18, TINTA, True)]
lectura2 = [b("Cómo leerlo", 12, TINTA, True),
            b("\nRanking: ", 9, CORAL, True),
            b("el lugar de Yucatán salta cada año (10, 19, 6, 2, 17, 1 y 25) y cada lugar tiene un margen amplio (el de 2025 va "
              "del 14 al 31). Cambia más que el azar, sin causa conocida; por eso la historia sigue lo que se repite.", 9),
            b("\nRespuestas: ", 9, CORAL, True),
            b("en todas las edades la mayoría se protege sola; los de 12 a 24 años casi nunca acuden a una autoridad.", 9),
            b("\nSexo: ", 9, CORAL, True),
            b("misma proporción, pero no lo mismo: a las mujeres les llegan casi el doble de insinuaciones sexuales "
              "(8.2 % contra 4.4 %).", 9),
            b("\nEscolaridad y zona: ", 9, CORAL, True),
            b("relaciones, no causas; con 25 años o más, la brecha por escolaridad se mantiene (25.7 % contra 10.7 %).", 9)]
instruccion2 = [b("Pasa el cursor sobre cada barra o celda para ver su intervalo de confianza y su tamaño de muestra.", 10, TINTA)]

# Alto (en 1280 x 760, se escala): 744 = 84 + 300 + 260 + 36 + 64
zonas2 = filas([
    (84, [(None, lambda x, y, w, h: z_texto(x, y, w, h, titulo2))]),
    (300, [(620, lambda x, y, w, h: z_hoja(x, y, w, h, H_RANK)),
           (None, lambda x, y, w, h: z_hoja(x, y, w, h, H_ACC))]),
    (None, [(None, lambda x, y, w, h: z_hoja(x, y, w, h, H_GRUPOS))]),
    (36, [(260, lambda x, y, w, h: z_boton(x, y, w, h, "◀ Volver a la historia", VENTANA_D1)),
          (None, lambda x, y, w, h: z_texto(x, y, w, h, instruccion2))]),
    (64, [(None, lambda x, y, w, h: z_texto(x, y, w, h, fuente))]),
])


# ---------------------------------------------------------------- ventanas
def ventana_hoja(nombre):
    return (
        "    <window class='worksheet' name='%s'>\n      <cards>\n        <edge name='left'>\n          <strip size='160'>\n"
        "            <card type='pages' />\n            <card type='filters' />\n            <card type='marks' />\n          </strip>\n        </edge>\n"
        "        <edge name='top'>\n          <strip size='2147483647'>\n            <card type='columns' />\n          </strip>\n"
        "          <strip size='2147483647'>\n            <card type='rows' />\n          </strip>\n"
        "          <strip size='2147483647'>\n            <card type='title' />\n          </strip>\n        </edge>\n      </cards>\n"
        "      <simple-id uuid='%s' />\n    </window>\n") % (q(nombre), gid())


def ventana_dash(nombre, hojas, uid, activo=False):
    vps = "".join("        <viewpoint name='%s'>\n          <zoom type='entire-view' />\n        </viewpoint>\n" % q(h) for h in hojas)
    return ("    <window class='dashboard'%s name='%s'>\n      <viewpoints>\n%s      </viewpoints>\n      <active id='-1' />\n"
            "      <simple-id uuid='%s' />\n    </window>\n") % (" maximized='true'" if activo else "", q(nombre), vps, uid)


HOJAS1 = [H_BRECHA, H_MATRIZ, H_PLAT, H_ACC_KPI]
HOJAS2 = [H_RANK, H_ACC, H_GRUPOS]

encabezado = (
    "<?xml version='1.0' encoding='utf-8' ?>\n\n"
    "<workbook original-version='18.1' source-build='2024.3.0' source-platform='win' version='18.1' "
    "xmlns:user='http://www.tableausoftware.com/xml/user'>\n"
    "  <document-format-change-manifest>\n"
    # BasicButtonObject y BasicButtonObjectTextSupport habilitan los botones de navegación (sin ellas,
    # Tableau rechaza el elemento <button> al abrir el libro: error D2E8DA72).
    + "".join("    <%s />\n" % t for t in ("AccessibleZoneTabOrder", "AnimationOnByDefault",
              "BasicButtonObject", "BasicButtonObjectTextSupport", "MarkAnimation",
              "ObjectModelEncapsulateLegacy", "ObjectModelTableType", "SchemaViewerObjectModel",
              "SetMembershipControl", "SheetIdentifierTracking", "WindowsPersistSimpleIdentifiers"))
    + "  </document-format-change-manifest>\n")

# Acción de filtro: al seleccionar una edad en la matriz, la gráfica 2 muestra solo esa edad
# (grupo_edad -> grupo_de_edad, fuentes distintas). Mismo formato que el respaldo, que sí funciona.
ACCION = """  <actions>
    <action caption='Elige una edad: plataformas de esa edad' name='[Action1_7B1D2C3E4F5A46B7889900AABBCCDDEE]'>
      <activation auto-clear='true' type='on-select' />
      <source dashboard='%(d1)s' type='sheet'>
        <exclude-sheet name='%(brecha)s' />
        <exclude-sheet name='%(plat)s' />
        <exclude-sheet name='%(acc)s' />
      </source>
      <link caption='Elige una edad: plataformas de esa edad' delimiter=',' escape='\\' expression='tsl:%(d1)s?%%5B%(ds_plat)s%%5D.%%5Bgrupo_de_edad%%5D~s0=&lt;[%(ds_anio)s].[grupo_edad]~na&gt;' include-null='true' multi-select='true' url-escape='true' />
      <command command='tsc:tsl-filter'>
        <param name='exclude' value='%(brecha)s,%(matriz)s,%(acc)s' />
        <param name='target' value='%(d1)s' />
      </command>
    </action>
    <datasources>
      <datasource caption='A-edad_anio' name='%(ds_anio)s' />
      <datasource caption='B-edad_plataforma' name='%(ds_plat)s' />
    </datasources>
    <datasource-dependencies datasource='%(ds_anio)s'>
      <column caption='Edad' datatype='string' name='[grupo_edad]' role='dimension' type='nominal'>
        <aliases>
          <alias key='&quot;60+&quot;' value='60 y más' />
        </aliases>
      </column>
    </datasource-dependencies>
    <datasource-dependencies datasource='%(ds_plat)s'>
      <column caption='Edad' datatype='string' name='[grupo_de_edad]' role='dimension' type='nominal'>
        <aliases>
          <alias key='&quot;60+&quot;' value='60 y más*' />
        </aliases>
      </column>
    </datasource-dependencies>
  </actions>
""" % dict(d1=D1, ds_anio=ds_anio, ds_plat=ds_plat, brecha=q(H_BRECHA), plat=q(H_PLAT), acc=q(H_ACC_KPI), matriz=q(H_MATRIZ))

twb = (encabezado
       + "  <datasources>\n" + x_anio + x_plat + x_kpi + x_acc + x_nac + x_ctx + "  </datasources>\n"
       + ACCION
       + "  <worksheets>\n" + h_brecha + h_matriz + h_plat + h_acc_kpi + h_rank + h_acc + h_grupos + "  </worksheets>\n"
       + "  <dashboards>\n" + dashboard(D1, ANCHO_PX, ALTO_PX, zonas1) + dashboard(D2, ANCHO_PX, ALTO_PX, zonas2) + "  </dashboards>\n"
       + "  <windows source-height='89'>\n" + "".join(ventana_hoja(h) for h in HOJAS1 + HOJAS2)
       + ventana_dash(D1, HOJAS1, VENTANA_D1, activo=True)
       + ventana_dash(D2, HOJAS2, VENTANA_D2)
       + "  </windows>\n</workbook>\n")


def escribir(destino):
    """Empaqueta el .twb y los CSV con fechas fijas: el mismo contenido da el mismo archivo."""
    fecha = (2026, 11, 14, 0, 0, 0)
    tmp = destino + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z_:
        info = zipfile.ZipInfo("dashboard_pitch.twb", fecha)
        info.compress_type = zipfile.ZIP_DEFLATED
        z_.writestr(info, twb.encode("utf-8"))
        for a in CSVS:
            info = zipfile.ZipInfo("Data/tableau/" + a, fecha)
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(DATOS, a), "rb") as f:
                z_.writestr(info, f.read())
    os.replace(tmp, destino)


if __name__ == "__main__":
    import sys
    destino = sys.argv[1] if len(sys.argv) > 1 else SALIDA
    escribir(destino)
    print("Escrito:", destino)
