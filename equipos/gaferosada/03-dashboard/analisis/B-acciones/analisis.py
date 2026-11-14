"""Complementaria de D-03 (D-05, issue #23) · Qué hacen las víctimas de ciberacoso, según edad.

Pregunta complementaria (D-05): ¿qué hacen las víctimas de ciberacoso en Yucatán ante lo que
vivieron (bloquear, reportar, contarle a alguien, denunciar o nada) y cambia según su grupo de
edad? MOCIBA 2021–2025.

Lee: data/clean/mociba_2019_2025_yucatan.csv (carril Datos)
Deja en esta carpeta:
  - tabla.csv            % de víctimas que hizo cada respuesta (agrupada), por grupo de edad
  - tabla_detalle.csv    lo mismo con las 11 respuestas originales
  - diferencias.csv      contrastes entre grupos de edad, con IC 95 % de la diferencia
  - tabla_por_anio.csv   constancia: respuestas agrupadas por año, con 3 grupos de edad amplios
  - grafica.png
Deja en data/tableau/: B-edad_acciones.csv

Población: víctimas de ciberacoso (ciberacoso == 1, 13 situaciones) de 12 años o más que usan
internet en Yucatán, 2021–2025 juntos (1,662 en la muestra): las mismas que la Gráfica 2
(analisis/B-plataforma/). Por qué no 2019–2020: entonces la lista tenía 8 respuestas y desde
2021 tiene 10 u 11 (agrega "denunciar en la escuela o el trabajo", "publicarlo en redes" y
"ninguna acción"); mezclarlas crearía diferencias del cuestionario, no de la realidad (D-05).

Respuestas agrupadas (una víctima cuenta en un grupo si hizo al menos una de sus respuestas):
  Protegerse            = bloquear, cambiar de número o cuenta, borrar la publicación
  Reportar a la plataforma
  Contarle a alguien
  Confrontar al agresor
  Denunciar             = ante la escuela o el trabajo, o ante una autoridad (MP/Fiscalía o policía)
  Ignorar o no hacer nada = ignorar, o "ninguna acción"
"Publicarlo en redes" (<1 %) solo va en la tabla de detalle. Una víctima puede hacer varias
cosas: los porcentajes NO suman 100.

Estimación: igual que la Gráfica 2. Proporción ponderada con `factor`; EE por linealización
(UPM `upm_dis` dentro de `estrato_pool`), cada grupo como dominio de la muestra 2021–2025, con la
función `proporcion` del carril Datos (data/limpieza/mociba_serie.py). IC 95 %. Cuadra con
docs/exploracion_mociba.md, sección 8 (por año). Asociación con la edad, no causa.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "data" / "limpieza"))
from mociba_serie import proporcion  # noqa: E402  (función del carril Datos; no se modifica)

Z95 = 1.96
POCAS = 100        # menos de 100 víctimas en el grupo = marcar
POCOS_CASOS = 10   # menos de 10 víctimas que hicieron esa respuesta = cifra muy inestable
EDADES = ["12-17", "18-24", "25-34", "35-44", "45-59", "60+"]
AMPLIO = {"12-17": "12-24", "18-24": "12-24", "25-34": "25-44", "35-44": "25-44",
          "45-59": "45+", "60+": "45+"}

DETALLE = {
    "accion_bloquear": "Bloquear",
    "accion_cambiar_numero_cuenta": "Cambiar de número o cuenta",
    "accion_eliminar_publicacion": "Borrar la publicación",
    "accion_reportar_plataforma": "Reportar a la plataforma",
    "accion_contarle_a_alguien": "Contarle a alguien",
    "accion_confrontar": "Confrontar al agresor",
    "accion_denunciar_escuela_trabajo": "Denunciar en la escuela o el trabajo",
    "accion_denunciar_autoridad": "Denunciar ante una autoridad",
    "accion_ignorar": "Ignorar",
    "accion_ninguna_accion": "Ninguna acción",
    "accion_publicarlo_en_redes": "Publicarlo en redes",
}
GRUPOS = {
    "Protegerse": ["accion_bloquear", "accion_cambiar_numero_cuenta",
                   "accion_eliminar_publicacion"],
    "Reportar a la plataforma": ["accion_reportar_plataforma"],
    "Contarle a alguien": ["accion_contarle_a_alguien"],
    "Confrontar al agresor": ["accion_confrontar"],
    "Denunciar": ["accion_denunciar_escuela_trabajo", "accion_denunciar_autoridad"],
    "Ignorar o no hacer nada": ["accion_ignorar", "accion_ninguna_accion"],
}
COL = {g: "g_" + g.lower().replace(" ", "_") for g in GRUPOS}

# ---------------------------------------------------------------- datos
df = pd.read_csv(RAIZ / "data/clean/mociba_2019_2025_yucatan.csv", encoding="utf-8-sig",
                 dtype={"upm_dis": str, "est_dis": str, "estrato_pool": str}, low_memory=False)
d = df[df["anio"] >= 2021].reset_index(drop=True)
victima = (d["ciberacoso"] == 1).to_numpy()
assert d.loc[victima, list(DETALLE)].notna().all().all(), "hay víctimas sin dato de acciones"
for g, cols in GRUPOS.items():
    # Fuera de las víctimas las acciones vienen vacías; se rellenan con 0 (no entran al dominio).
    d[COL[g]] = (d[cols].fillna(0).max(axis=1) > 0).astype(float)
d["edad_amplia"] = d["grupo_edad"].map(AMPLIO)
sin_respuesta = int((d.loc[victima, list(DETALLE)].sum(axis=1) == 0).sum())


def fila(dd, var, m, **extra):
    p, ee, n = proporcion(dd, var, m)
    casos = int(dd.loc[m, var].fillna(0).sum())
    return {**extra, "porcentaje": round(100 * p, 1),
            "ic95_inf": round(max(0.0, 100 * (p - Z95 * ee)), 1),
            "ic95_sup": round(100 * (p + Z95 * ee), 1),
            "cv": round(100 * ee / p, 1) if p > 0 else np.nan,
            "victimas_muestra": n, "casos_muestra": casos,
            "poca_muestra": n < POCAS, "pocos_casos": casos < POCOS_CASOS}


def diferencia(dd, var, dom_a, dom_b):
    """Diferencia de proporciones (a − b) entre dos dominios, linealizada con el mismo diseño."""
    z = dd[var].astype(float).fillna(0).to_numpy()
    w = dd["factor"].to_numpy(dtype=float)
    u, ps = np.zeros(len(dd)), []
    for signo, m in [(1, dom_a), (-1, dom_b)]:
        m = np.asarray(m, bool)
        W = (w * m).sum()
        p = (w * m * z).sum() / W
        ps.append(p)
        u += signo * w * m * (z - p) / W
    t = pd.DataFrame({"h": dd["estrato_pool"].to_numpy(), "c": dd["upm_dis"].to_numpy(), "u": u})
    tot = t.groupby(["h", "c"], sort=False)["u"].sum()
    g = tot.groupby(level="h", sort=False)
    k = g.transform("size").to_numpy(dtype=float)
    dif = (tot - g.transform("mean")).to_numpy()
    v = (np.where(k > 1, k / np.maximum(k - 1, 1), 0.0) * dif ** 2).sum()
    return ps[0] - ps[1], float(np.sqrt(v))


# ---------------------------------------------------------------- 1. tablas por edad
def por_edad(variables):
    filas = []
    for edad in ["Todas"] + EDADES:
        m = victima if edad == "Todas" else victima & (d["grupo_edad"] == edad).to_numpy()
        for var, nombre in variables.items():
            filas.append(fila(d, var, m, grupo_edad=edad, respuesta=nombre))
    return pd.DataFrame(filas)


tabla = por_edad({COL[g]: g for g in GRUPOS})
tabla.to_csv(AQUI / "tabla.csv", index=False, encoding="utf-8")
detalle = por_edad(DETALLE)
detalle.to_csv(AQUI / "tabla_detalle.csv", index=False, encoding="utf-8")

# ---------------------------------------------------------------- 2. contrastes
# Las respuestas raras (denunciar) se comparan con grupos amplios para no depender de celdas
# con menos de 10 casos.
def dom(grupos, col="grupo_edad"):
    return victima & d[col].isin(grupos).to_numpy()


contrastes = [
    ("Contarle a alguien", ["12-17"], ["25-34", "35-44", "45-59", "60+"], "12-17", "25 y más"),
    ("Confrontar al agresor", ["12-17"], ["25-34", "35-44", "45-59", "60+"], "12-17", "25 y más"),
    ("Reportar a la plataforma", ["18-24", "25-34"], ["45-59", "60+"], "18-34", "45 y más"),
    ("Denunciar", ["35-44", "45-59", "60+"], ["12-17", "18-24"], "35 y más", "12-24"),
    ("Ignorar o no hacer nada", ["45-59", "60+"], ["12-17", "18-24"], "45 y más", "12-24"),
    ("Protegerse", ["12-17", "18-24"], ["45-59", "60+"], "12-24", "45 y más"),
]
filas = []
for g, a, b, ea, eb in contrastes:
    dif, ee = diferencia(d, COL[g], dom(a), dom(b))
    pa, _, _ = proporcion(d, COL[g], dom(a))
    pb, _, _ = proporcion(d, COL[g], dom(b))
    filas.append({"respuesta": g, "grupo_a": ea, "grupo_b": eb,
                  "porcentaje_a": round(100 * pa, 1), "porcentaje_b": round(100 * pb, 1),
                  "diferencia_pp": round(100 * dif, 1),
                  "ic95_inf": round(100 * (dif - Z95 * ee), 1),
                  "ic95_sup": round(100 * (dif + Z95 * ee), 1),
                  "significativa_95": abs(dif) > Z95 * ee})
difs = pd.DataFrame(filas)
difs.to_csv(AQUI / "diferencias.csv", index=False, encoding="utf-8")

# Denuncia ante autoridad sola (la que le importa a la policía cibernética), por edad amplia
denuncia_aut = pd.DataFrame([fila(d, "accion_denunciar_autoridad",
                                  victima & (d["edad_amplia"] == g).to_numpy(), edad_amplia=g)
                             for g in ["12-24", "25-44", "45+"]])

# ---------------------------------------------------------------- 3. constancia por año
filas = []
for anio in range(2021, 2026):
    da = d[d["anio"] == anio].reset_index(drop=True)
    va = (da["ciberacoso"] == 1).to_numpy()
    for g in ["Todas", "12-24", "25-44", "45+"]:
        m = va if g == "Todas" else va & (da["edad_amplia"] == g).to_numpy()
        for grp in GRUPOS:
            filas.append(fila(da, COL[grp], m, anio=anio, edad_amplia=g, respuesta=grp))
por_anio = pd.DataFrame(filas)
por_anio.to_csv(AQUI / "tabla_por_anio.csv", index=False, encoding="utf-8")

tot = por_anio[por_anio["edad_amplia"] == "Todas"].pivot(index="anio", columns="respuesta",
                                                          values="porcentaje")
constancia = {
    "años en que protegerse es la respuesta más común": int(
        (tot.idxmax(axis=1) == "Protegerse").sum()),
    "años con denuncia < 10 %": int((tot["Denunciar"] < 10).sum()),
    "rango de denuncia por año (%)": (tot["Denunciar"].min(), tot["Denunciar"].max()),
}

# ---------------------------------------------------------------- 4. extracto para Tableau
# Incluye las filas "Todas las edades" (pedido #29): así la cifra general del dashboard (71.5 %
# se protege, 5.6 % denuncia) sale del CSV y no de un texto fijo. orden_edad = 0 para esa fila;
# en Tableau, filtrar `grupo_de_edad` si una vista solo debe mostrar los seis grupos.
tb = tabla.replace({"grupo_edad": {"Todas": "Todas las edades"}}).rename(columns={
    "grupo_edad": "grupo_de_edad", "porcentaje": "porcentaje_de_victimas",
    "ic95_inf": "ic95_inferior", "ic95_sup": "ic95_superior",
    "victimas_muestra": "victimas_en_la_muestra", "casos_muestra": "casos_en_la_muestra",
    "poca_muestra": "menos_de_100_victimas", "pocos_casos": "menos_de_10_casos"})
tb.insert(0, "periodo", "2021-2025")
tb["orden_edad"] = tb["grupo_de_edad"].map(
    {"Todas las edades": 0, **{e: i + 1 for i, e in enumerate(EDADES)}})
tb["orden_respuesta"] = tb["respuesta"].map({g: i + 1 for i, g in enumerate(GRUPOS)})
tb["incluye"] = tb["respuesta"].map(
    {g: ", ".join(DETALLE[c] for c in cols).lower() for g, cols in GRUPOS.items()})
tb["nota"] = ("% de las víctimas del grupo que hizo esa respuesta; una víctima puede hacer "
              "varias, no suman 100. Fuente: INEGI, MOCIBA 2021-2025.")
tb = tb[["periodo", "grupo_de_edad", "orden_edad", "respuesta", "orden_respuesta", "incluye",
         "porcentaje_de_victimas", "ic95_inferior", "ic95_superior", "cv",
         "victimas_en_la_muestra", "casos_en_la_muestra", "menos_de_100_victimas",
         "menos_de_10_casos", "nota"]]
tb.to_csv(RAIZ / "data/tableau/B-edad_acciones.csv", index=False, encoding="utf-8")

# ---------------------------------------------------------------- 5. gráfica (mapa de calor)
# Magnitud en una matriz edad × respuesta: secuencial de un solo tono (azul), claro → oscuro.
TINTA, TINTA2, FONDO = "#0b0b0b", "#52514e", "#fcfcfb"
cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
    "azul", ["#f1f6fd", "#a9c9f2", "#2a78d6", "#123f78"])
filas_g = ["Todas"] + EDADES
M = tabla.pivot(index="grupo_edad", columns="respuesta", values="porcentaje").loc[
    filas_g, list(GRUPOS)]
POC = tabla.pivot(index="grupo_edad", columns="respuesta", values="pocos_casos").loc[
    filas_g, list(GRUPOS)]

fig, ax = plt.subplots(figsize=(9.6, 5.8), dpi=150)
fig.patch.set_facecolor(FONDO)
ax.set_facecolor(FONDO)
norma = matplotlib.colors.Normalize(0, 80)
for i, g in enumerate(filas_g):
    for j, r in enumerate(GRUPOS):
        v = M.loc[g, r]
        y = i + (0.25 if i > 0 else 0)  # separa la fila "Todas"
        ax.add_patch(plt.Rectangle((j + 0.03, y + 0.04), 0.94, 0.92, color=cmap(norma(v)),
                                   lw=0))
        txt = f"{v:.0f} %" + ("†" if POC.loc[g, r] else "")
        ax.text(j + 0.5, y + 0.5, txt, ha="center", va="center", fontsize=9.5,
                color="white" if v >= 40 else TINTA, fontweight="bold" if i == 0 else "normal")
ax.set_xlim(0, len(GRUPOS))
ax.set_ylim(len(filas_g) + 0.25, 0)
ax.set_xticks(np.arange(len(GRUPOS)) + 0.5,
              [r.replace(" a la ", "\na la ").replace(" o no", "\no no").replace(" al ", "\nal ")
               .replace("Contarle a ", "Contarle\na ") for r in GRUPOS],
              fontsize=9, color=TINTA)
ax.xaxis.tick_top()
n_por = tabla.drop_duplicates("grupo_edad").set_index("grupo_edad")["victimas_muestra"]
ylab = [f"Todas (n={n_por['Todas']})"] + [
    f"{e} (n={n_por[e]})" + (" *" if n_por[e] < POCAS else "") for e in EDADES]
ax.set_yticks([0.5] + [i + 0.75 for i in range(1, len(filas_g))], ylab, fontsize=9,
              color=TINTA2)
ax.tick_params(length=0)
for s in ax.spines.values():
    s.set_visible(False)

fig.suptitle("Las víctimas se protegen solas: bloquean, y casi nadie denuncia",
             x=0.03, ha="left", fontsize=13, fontweight="bold", color=TINTA, y=0.98)
fig.text(0.03, 0.915, "% de víctimas de cada grupo de edad que hizo cada cosa · Yucatán, "
         "2021–2025 juntos", fontsize=9.5, color=TINTA2)
fig.text(0.03, 0.015,
         "Fuente: INEGI, MOCIBA 2021–2025, usuarios de internet de 12 años o más que vivieron "
         "ciberacoso. Una víctima puede hacer varias cosas (no suman 100).\nProtegerse = "
         "bloquear, cambiar de número o cuenta, borrar la publicación · Denunciar = en la escuela "
         "o el trabajo, o ante MP/Fiscalía o policía.\n† menos de 10 casos en la muestra: cifra "
         "muy inestable · * 60+: menos de 100 víctimas. IC 95 % en analisis/B-acciones/tabla.csv. "
         "Asociación, no causa.",
         fontsize=7.5, color=TINTA2, va="bottom")
fig.subplots_adjust(left=0.15, right=0.98, top=0.80, bottom=0.14)
fig.savefig(AQUI / "grafica.png", facecolor=FONDO)

# ---------------------------------------------------------------- resumen en consola
pd.set_option("display.width", 160)
print("Víctimas 2021–2025:", int(victima.sum()), "· sin ninguna de las 11 respuestas:",
      sin_respuesta)
print(M.to_string())
print("\nIC 'Todas':\n", tabla[tabla.grupo_edad == "Todas"][
    ["respuesta", "porcentaje", "ic95_inf", "ic95_sup"]].to_string(index=False))
print("\nDetalle 'Todas':\n", detalle[detalle.grupo_edad == "Todas"][
    ["respuesta", "porcentaje", "ic95_inf", "ic95_sup", "casos_muestra"]].to_string(index=False))
print("\nContrastes:\n", difs.to_string(index=False))
print("\nDenuncia ante autoridad por edad amplia:\n", denuncia_aut[
    ["edad_amplia", "porcentaje", "ic95_inf", "ic95_sup", "casos_muestra"]].to_string(index=False))
print("\nConstancia:", constancia)
print(tot.round(1).to_string())
