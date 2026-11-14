"""Análisis A · Verificación de H-GA-02 (razón por edad) y H-GA-05 (sexo) contra INEGI (#28).

INEGI publica la edad en bandas de 10 años y por sexo; a nivel nacional, la razón entre la
banda más alta (20–29) y 60+ es de 2.3 a 2.75 en mujeres. Nuestro KPI dice 4.0 (18–24 contra
60+, Yucatán, 2019–2025 juntos). Este script documenta de dónde sale la diferencia y revisa si
"sin diferencia por sexo" se sostiene por edad y por tipo de situación.

Lee: data/clean/mociba_2019_2025_yucatan.csv
Deja en esta carpeta:
  razones.csv          razón joven / 60+ con distintos cortes, periodos, indicador y sexo
  sexo_edad.csv        mujeres − hombres por grupo de edad, y la interacción <40 contra 40+
  sexo_situacion.csv   mujeres y hombres por tipo de situación
  sexo_situacion.png

Método: factores de expansión; varianza por linealización de Taylor (UPM dentro de
`estrato_pool`), IC 95 %. Diferencias, razones (en log) e interacciones se linealizan juntas,
con su covarianza. Años juntos = suma de factores de esos años.
Indicadores: `ciberacoso_comparable` (10 situaciones, 2019–2025) y `ciberacoso` (oficial, 13
situaciones desde 2021). Tres situaciones solo existen desde 2021.
Aviso: son muchas comparaciones (13 situaciones, varios cortes); sin corrección por
comparaciones múltiples. Leer como exploración, no como prueba.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
Z = 1.96
COMP, OFI = "ciberacoso_comparable", "ciberacoso"
SIT_2021 = ["sit_difundir_contenido_intimo", "sit_amenazar_con_publicar", "sit_otra_situacion"]
NOMBRE_SIT = {
    "sit_mensajes_ofensivos": "Mensajes ofensivos",
    "sit_llamadas_ofensivas": "Llamadas ofensivas",
    "sit_criticas_apariencia_clase": "Críticas por apariencia o clase social",
    "sit_usurpacion_identidad": "Suplantación de identidad",
    "sit_contacto_nombres_falsos": "Contacto con identidades falsas",
    "sit_vigilar_cuentas": "Rastreo de cuentas o sitios",
    "sit_provocar_en_linea": "Provocaciones para reaccionar mal",
    "sit_insinuaciones_sexuales": "Insinuaciones o propuestas sexuales",
    "sit_envio_contenido_sexual": "Recibir contenido sexual",
    "sit_publicar_info_personal": "Publicación de información personal",
    "sit_difundir_contenido_intimo": "Difusión de contenido íntimo (desde 2021)",
    "sit_amenazar_con_publicar": "Amenaza de publicar información (desde 2021)",
    "sit_otra_situacion": "Otra situación (desde 2021)",
}

df = pd.read_csv(RAIZ / "data/clean/mociba_2019_2025_yucatan.csv", dtype=str,
                 encoding="utf-8-sig").apply(lambda c: c.str.strip())
df["anio"] = df["anio"].astype(int)
df["edad"] = df["edad"].astype(int)
df["factor"] = df["factor"].astype(float)
SITS = [c for c in df.columns if c.startswith("sit_")]
assert set(SITS) == set(NOMBRE_SIT)
for c in [COMP, OFI] + SITS:
    df[c] = pd.to_numeric(df[c])


def lineal(d, var, dom):
    w = d["factor"].to_numpy(float)
    m = np.asarray(dom, bool)
    y = d[var].to_numpy(float)
    assert not np.isnan(y[m]).any(), f"{var} vacía en el dominio"
    y = np.where(m, y, 0.0)
    X = (w * m).sum()
    r = (w * y).sum() / X
    return r, w * m * (y - r) / X, int(m.sum())


def ee(d, z):
    t = pd.DataFrame({"h": d["estrato_pool"].to_numpy(), "c": d["upm_dis"].to_numpy(), "z": z})
    tot = t.groupby(["h", "c"])["z"].sum()
    g = tot.groupby(level="h")
    k = g.transform("size").to_numpy(float)
    dif = (tot - g.transform("mean")).to_numpy()
    return float(np.sqrt((np.where(k > 1, k / np.maximum(k - 1, 1), 0) * dif**2).sum()))


def edad_entre(d, a, b):
    return ((d["edad"] >= a) & (d["edad"] <= b)).to_numpy()


def sexo(d, s):
    return np.ones(len(d), bool) if s == "Total" else (d["sexo"] == s).to_numpy()


# ---------- 1. razón joven / 60+ con distintos cortes ----------
PERIODOS = [("2019-2025", df, COMP, "comparable (10 situaciones)"),
            ("2021-2025", df[df["anio"] >= 2021], OFI, "oficial (13 situaciones)"),
            ("2024", df[df["anio"] == 2024], OFI, "oficial (13 situaciones)"),
            ("2025", df[df["anio"] == 2025], OFI, "oficial (13 situaciones)")]
CORTES = [("18-24", 18, 24, "nuestro KPI"), ("20-29", 20, 29, "banda de INEGI"),
          ("12-19", 12, 19, "banda de INEGI")]
raz = []
for per, d, var, ind in PERIODOS:
    for s in ["Total", "Mujer", "Hombre"]:
        r2, z2, n2 = lineal(d, var, sexo(d, s) & edad_entre(d, 60, 200))
        for et, a, b, nota in CORTES:
            r1, z1, n1 = lineal(d, var, sexo(d, s) & edad_entre(d, a, b))
            e_log = ee(d, z1 / r1 - z2 / r2) if r2 > 0 else np.nan
            e_dif = ee(d, z1 - z2)
            raz.append({
                "periodo": per, "indicador": ind, "sexo": s, "grupo_joven": et, "corte": nota,
                "pct_joven": 100 * r1, "pct_60_mas": 100 * r2,
                "veces": r1 / r2, "veces_ic95_inf": np.exp(np.log(r1 / r2) - Z * e_log),
                "veces_ic95_sup": np.exp(np.log(r1 / r2) + Z * e_log),
                "brecha_puntos": 100 * (r1 - r2), "brecha_ic95_inf": 100 * (r1 - r2 - Z * e_dif),
                "brecha_ic95_sup": 100 * (r1 - r2 + Z * e_dif),
                "casos_joven": n1, "casos_60_mas": n2,
                "precision": "baja" if min(n1, n2) < 100 else "aceptable",
            })
raz = pd.DataFrame(raz)

# ---------- 2. sexo por edad ----------
GRUPOS = [("12-19", 12, 19), ("20-29", 20, 29), ("30-39", 30, 39), ("40-49", 40, 49),
          ("50-59", 50, 59), ("60+", 60, 200), ("Menores de 40", 12, 39), ("40 o más", 40, 200),
          ("Total", 12, 200)]
se, zdif = [], {}
for et, a, b in GRUPOS:
    rm, zm, nm = lineal(df, COMP, sexo(df, "Mujer") & edad_entre(df, a, b))
    rh, zh, nh = lineal(df, COMP, sexo(df, "Hombre") & edad_entre(df, a, b))
    e = ee(df, zm - zh)
    zdif[et] = (rm - rh, zm - zh)
    se.append({"periodo": "2019-2025", "grupo_edad": et, "pct_mujeres": 100 * rm,
               "pct_hombres": 100 * rh, "diferencia_puntos": 100 * (rm - rh),
               "dif_ic95_inf": 100 * (rm - rh - Z * e), "dif_ic95_sup": 100 * (rm - rh + Z * e),
               "significativa": abs(rm - rh) > Z * e, "casos_mujeres": nm, "casos_hombres": nh})
(d1, z1), (d2, z2) = zdif["Menores de 40"], zdif["40 o más"]
e = ee(df, z1 - z2)
se.append({"periodo": "2019-2025", "grupo_edad": "Interacción: brecha en <40 menos brecha en 40+",
           "diferencia_puntos": 100 * (d1 - d2), "dif_ic95_inf": 100 * (d1 - d2 - Z * e),
           "dif_ic95_sup": 100 * (d1 - d2 + Z * e), "significativa": abs(d1 - d2) > Z * e})
se = pd.DataFrame(se)

# ---------- 3. sexo por tipo de situación ----------
ss = []
for sit in SITS:
    d = df[df["anio"] >= 2021] if sit in SIT_2021 else df
    rm, zm, nm = lineal(d, sit, sexo(d, "Mujer"))
    rh, zh, nh = lineal(d, sit, sexo(d, "Hombre"))
    e = ee(d, zm - zh)
    e_log = ee(d, zm / rm - zh / rh)
    ss.append({"situacion": NOMBRE_SIT[sit], "columna": sit,
               "periodo": "2021-2025" if sit in SIT_2021 else "2019-2025",
               "pct_mujeres": 100 * rm, "pct_hombres": 100 * rh,
               "diferencia_puntos": 100 * (rm - rh), "dif_ic95_inf": 100 * (rm - rh - Z * e),
               "dif_ic95_sup": 100 * (rm - rh + Z * e), "significativa": abs(rm - rh) > Z * e,
               "veces_mujer_sobre_hombre": rm / rh,
               "veces_ic95_inf": np.exp(np.log(rm / rh) - Z * e_log),
               "veces_ic95_sup": np.exp(np.log(rm / rh) + Z * e_log),
               "casos_mujeres_con_situacion": int((d[sit][sexo(d, "Mujer")] == 1).sum()),
               "casos_hombres_con_situacion": int((d[sit][sexo(d, "Hombre")] == 1).sum())})
ss = pd.DataFrame(ss).sort_values("diferencia_puntos", ascending=False)


def red(t, dec=1):
    t = t.copy()
    for c in t.select_dtypes("float").columns:
        t[c] = t[c].round(2 if c.startswith("veces") else dec)
    return t


raz, se, ss = red(raz), red(se), red(ss)
raz.to_csv(AQUI / "razones.csv", index=False)
se.to_csv(AQUI / "sexo_edad.csv", index=False)
ss.to_csv(AQUI / "sexo_situacion.csv", index=False)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 48)
print("RAZÓN JOVEN / 60+\n", raz.drop(columns=["indicador", "corte", "brecha_ic95_inf",
                                                "brecha_ic95_sup"]).to_string(index=False))
print("\nSEXO POR EDAD (2019–2025, comparable)\n", se.drop(columns="periodo").to_string(index=False))
print("\nSEXO POR SITUACIÓN\n", ss.drop(columns=["columna"]).to_string(index=False))

# ---------- gráfica: mujeres y hombres por tipo de situación ----------
SUP, TXT, TXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COL = {"Hombres": "#2a78d6", "Mujeres": "#eb6834"}
g = ss[ss["columna"] != "sit_otra_situacion"].sort_values("diferencia_puntos")
fig, ax = plt.subplots(figsize=(9.5, 5.8), dpi=150)
fig.patch.set_facecolor(SUP)
ax.set_facecolor(SUP)
y = np.arange(len(g))
ax.hlines(y, g[["pct_mujeres", "pct_hombres"]].min(axis=1),
          g[["pct_mujeres", "pct_hombres"]].max(axis=1), color=GRID, linewidth=3, zorder=1)
ax.scatter(g["pct_hombres"], y, s=70, color=COL["Hombres"], edgecolor=SUP, linewidth=2,
           label="Hombres", zorder=3)
ax.scatter(g["pct_mujeres"], y, s=70, color=COL["Mujeres"], edgecolor=SUP, linewidth=2,
           label="Mujeres", zorder=3)
for yi, (_, f) in enumerate(g.iterrows()):
    marca = " *" if f["significativa"] else ""
    ax.text(max(f["pct_mujeres"], f["pct_hombres"]) + 0.3, yi,
            f"{f['diferencia_puntos']:+.1f} pts{marca}", va="center", fontsize=8.5, color=TXT)
ax.set_yticks(y, g["situacion"])
ax.set_xlim(0, 13)
ax.set_xlabel("% de usuarios de internet que vivió la situación en los últimos 12 meses",
              color=TXT2)
ax.xaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
for lado in ["top", "right", "left", "bottom"]:
    ax.spines[lado].set_visible(False)
ax.tick_params(colors=TXT2, length=0)
ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(1, 1.0), ncol=2, labelcolor=TXT)
fig.suptitle("Misma prevalencia total, distinto tipo de acoso por sexo", x=0.04, ha="left",
             fontsize=13, color=TXT, fontweight="bold")
fig.text(0.04, 0.01,
         "Fuente: INEGI, MOCIBA 2019–2025, microdatos de Yucatán. Usuarios de internet de 12 años "
         "y más. Etiqueta: mujeres − hombres, en puntos.\n* Diferencia significativa (IC 95 % por "
         "diseño, sin corrección por comparaciones múltiples). Script: "
         "analisis/A-verificacion/analisis.py", fontsize=7.5, color=TXT2, va="bottom")
fig.tight_layout(rect=(0, 0.07, 1, 0.95))
fig.savefig(AQUI / "sexo_situacion.png", facecolor=SUP)
print("\nGuardado en", AQUI)
