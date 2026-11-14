"""Análisis A · Contexto transversal del ciberacoso en Yucatán (complementaria de D-03, #25).

1. Sexo, escolaridad y zona urbana/rural, 2019–2025 (indicador comparable).
2. Yucatán contra el país, por año, con su lugar entre las 32 entidades.

Lee: data/clean/mociba_2019_2025_yucatan.csv
     data/clean/mociba_prevalencia_estatal_2019_2025.csv
Deja en esta carpeta:
  grupos.csv               prevalencia por sexo, escolaridad y zona; por año y 2019–2025 juntos
  contrastes.csv           diferencias entre grupos con IC 95 % y en cuántos años se repiten
  yucatan_vs_nacional.csv  Yucatán y nacional por año, diferencia, lugar y rango de lugares
  grupos.png, yucatan_vs_nacional.png
Deja en data/tableau/: A-contexto_grupos.csv, A-yucatan_vs_nacional.csv

Definiciones
- Prevalencia: `ciberacoso_comparable` (al menos 1 de las 10 situaciones preguntadas los siete
  años). Denominador: usuarios de internet de 12 años o más.
- Varios años juntos: se suman los factores de los siete años; cada año es un estrato distinto
  (`estrato_pool`). Varianza por linealización de Taylor (UPM dentro de estrato), IC 95 %.
- Contrastes: la diferencia entre dos grupos se linealiza junta (incluye su covarianza).
- Escolaridad está ligada a la edad (los de 12–17 no pueden tener licenciatura y los mayores
  tienen menos escolaridad), así que el contraste se repite solo con personas de 25 años o más.
- Yucatán contra el país: las cifras por entidad ya vienen calculadas por el carril Datos. La
  diferencia Yucatán − nacional usa EE = raíz(ee_yuc² + ee_nac²): es una aproximación (Yucatán es
  ~2 % de la muestra nacional, así que la covarianza es mínima).
- Rango de lugares: el lugar publicado es una estimación. `lugar_min` = 1 + entidades con
  prevalencia significativamente mayor que Yucatán; `lugar_max` = 32 − entidades con prevalencia
  significativamente menor (muestras independientes entre entidades, z = 1.96).
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
TABLEAU = RAIZ / "data/tableau"
Z = 1.96
ANIOS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
JUNTOS = "2019-2025"
VAR = "ciberacoso_comparable"
DIMENSIONES = {
    "Sexo": ("sexo", ["Hombre", "Mujer"]),
    "Escolaridad": ("escolaridad", ["Primaria o menos", "Secundaria", "Bachillerato o técnico",
                                    "Licenciatura o más"]),
    "Zona": ("dominio", ["Rural", "Urbano"]),
}
# (dimensión, grupo A, grupo B, edad mínima): diferencia = A − B
CONTRASTES = [
    ("Sexo", "Mujer", "Hombre", 12),
    ("Escolaridad", "Licenciatura o más", "Primaria o menos", 12),
    ("Escolaridad", "Licenciatura o más", "Primaria o menos", 25),
    ("Zona", "Urbano", "Rural", 12),
]

df = pd.read_csv(RAIZ / "data/clean/mociba_2019_2025_yucatan.csv", dtype=str,
                 encoding="utf-8-sig")
df = df.apply(lambda c: c.str.strip())
df["anio"] = df["anio"].astype(int)
df["edad"] = df["edad"].astype(int)
df["factor"] = df["factor"].astype(float)
df[VAR] = df[VAR].astype(float)
for _, (col, niveles) in DIMENSIONES.items():
    assert set(df[col].dropna()) == set(niveles), df[col].unique()


# ---------- estimación por diseño ----------
def lineal(d, dom):
    w = d["factor"].to_numpy(float)
    m = np.asarray(dom, bool)
    y = np.where(m, d[VAR].to_numpy(float), 0.0)
    X = (w * m).sum()
    r = (w * y).sum() / X
    return r, w * m * (y - r) / X, int(m.sum()), X


def ee(d, z):
    t = pd.DataFrame({"h": d["estrato_pool"].to_numpy(), "c": d["upm_dis"].to_numpy(), "z": z})
    tot = t.groupby(["h", "c"])["z"].sum()
    g = tot.groupby(level="h")
    k = g.transform("size").to_numpy(float)
    dif = (tot - g.transform("mean")).to_numpy()
    return float(np.sqrt((np.where(k > 1, k / np.maximum(k - 1, 1), 0) * dif**2).sum()))


def precision(cv, n):
    if n < 100 or cv >= 30:
        return "baja"
    return "moderada" if cv >= 15 else "alta"


def periodo(anio):
    return df if anio == JUNTOS else df[df["anio"] == anio]


# ---------- 1. grupos ----------
filas = []
for anio in ANIOS + [JUNTOS]:
    d = periodo(anio)
    na = len(ANIOS) if anio == JUNTOS else 1
    celdas = [("Total", "Total", np.ones(len(d), bool))]
    for dim, (col, niveles) in DIMENSIONES.items():
        celdas += [(dim, nv, (d[col] == nv).to_numpy()) for nv in niveles]
    for dim, nv, dom in celdas:
        r, z, n, X = lineal(d, dom)
        e = ee(d, z)
        cv = 100 * e / r
        filas.append({"anio": str(anio), "dimension": dim, "grupo": nv, "pct": 100 * r,
                      "ic95_inf": 100 * (r - Z * e), "ic95_sup": 100 * (r + Z * e),
                      "cv_pct": cv, "casos_muestra": n,
                      "poblacion_promedio_anual": round(X / na),
                      "precision": precision(cv, n)})
grupos = pd.DataFrame(filas)

contr = []
for dim, a, b, edad_min in CONTRASTES:
    col = DIMENSIONES[dim][0]
    res = {}
    for anio in ANIOS + [JUNTOS]:
        d = periodo(anio)
        base = (d["edad"] >= edad_min).to_numpy()
        r1, z1, n1, _ = lineal(d, base & (d[col] == a).to_numpy())
        r2, z2, n2, _ = lineal(d, base & (d[col] == b).to_numpy())
        e = ee(d, z1 - z2)
        res[anio] = (100 * r1, 100 * r2, 100 * (r1 - r2), 100 * e, n1, n2)
    p1, p2, dif, e, n1, n2 = res[JUNTOS]
    contr.append({
        "dimension": dim, "grupo_a": a, "grupo_b": b,
        "poblacion": "12 años o más" if edad_min == 12 else f"{edad_min} años o más",
        "pct_a": p1, "pct_b": p2, "diferencia_puntos": dif,
        "dif_ic95_inf": dif - Z * e, "dif_ic95_sup": dif + Z * e,
        "significativa": abs(dif) > Z * e,
        "anios_a_mayor_que_b": sum(res[y][2] > 0 for y in ANIOS),
        "anios_dif_significativa": sum(abs(res[y][2]) > Z * res[y][3] for y in ANIOS),
        "anios": len(ANIOS), "casos_a": n1, "casos_b": n2,
    })
contr = pd.DataFrame(contr)

# ---------- 2. Yucatán contra el país ----------
est = pd.read_csv(RAIZ / "data/clean/mociba_prevalencia_estatal_2019_2025.csv", dtype=str,
                  encoding="utf-8-sig").apply(lambda c: c.str.strip())
est["anio"] = est["anio"].astype(int)
num = ["prevalencia_comparable", "ee_comparable", "ic95_inf_comparable", "ic95_sup_comparable",
       "lugar_comparable", "n"]
est[num] = est[num].apply(pd.to_numeric)
yn = []
for anio in ANIOS:
    e_ = est[est["anio"] == anio]
    y = e_[e_["cve_ent"] == "31"].iloc[0]
    nac = e_[e_["cve_ent"] == "00"].iloc[0]
    otras = e_[~e_["cve_ent"].isin(["00", "31"])]
    assert len(otras) == 31
    zs = (otras["prevalencia_comparable"] - y["prevalencia_comparable"]) / np.sqrt(
        otras["ee_comparable"] ** 2 + y["ee_comparable"] ** 2)
    dif = y["prevalencia_comparable"] - nac["prevalencia_comparable"]
    e_dif = np.sqrt(y["ee_comparable"] ** 2 + nac["ee_comparable"] ** 2)
    yn.append({
        "anio": anio,
        "yucatan_pct": y["prevalencia_comparable"],
        "yucatan_ic95_inf": y["ic95_inf_comparable"], "yucatan_ic95_sup": y["ic95_sup_comparable"],
        "nacional_pct": nac["prevalencia_comparable"],
        "nacional_ic95_inf": nac["ic95_inf_comparable"],
        "nacional_ic95_sup": nac["ic95_sup_comparable"],
        "diferencia_puntos": dif, "dif_ic95_inf": dif - Z * e_dif, "dif_ic95_sup": dif + Z * e_dif,
        "yucatan_vs_nacional": ("arriba" if dif - Z * e_dif > 0 else
                                "abajo" if dif + Z * e_dif < 0 else "sin diferencia"),
        "lugar": int(y["lugar_comparable"]),
        "lugar_min": 1 + int((zs > Z).sum()), "lugar_max": 32 - int((zs < -Z).sum()),
        "entrevistas_yucatan": int(y["n"]),
    })
yn = pd.DataFrame(yn)

# ---------- guardar ----------
def red(t):
    t = t.copy()
    c = t.select_dtypes("float").columns
    t[c] = t[c].round(1)
    return t


grupos, contr, yn = red(grupos), red(contr), red(yn)
grupos.to_csv(AQUI / "grupos.csv", index=False)
contr.to_csv(AQUI / "contrastes.csv", index=False)
yn.to_csv(AQUI / "yucatan_vs_nacional.csv", index=False)
TABLEAU.mkdir(exist_ok=True)
grupos.to_csv(TABLEAU / "A-contexto_grupos.csv", index=False)
yn.to_csv(TABLEAU / "A-yucatan_vs_nacional.csv", index=False)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
print("GRUPOS, 2019–2025 juntos\n", grupos[grupos["anio"] == JUNTOS].to_string(index=False))
print("\nGRUPOS por año (%)\n", grupos.pivot(index=["dimension", "grupo"], columns="anio",
                                              values="pct"))
print("\nCONTRASTES\n", contr.to_string(index=False))
print("\nYUCATÁN CONTRA EL PAÍS\n", yn.to_string(index=False))

# ---------- gráficas ----------
SUP, TXT, TXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
AZUL, GRIS = "#2a78d6", "#8a8984"
FUENTE = ("Fuente: INEGI, MOCIBA 2019–2025. Usuarios de internet de 12 años y más. Indicador "
          "comparable (10 situaciones comunes a los 7 años).")


def estilo(ax):
    ax.set_facecolor(SUP)
    for lado in ["top", "right", "left"]:
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TXT2, length=0)


# Gráfica 1: Yucatán contra el país
fig, ax = plt.subplots(figsize=(9.5, 5.4), dpi=150)
fig.patch.set_facecolor(SUP)
estilo(ax)
x = yn["anio"].to_numpy()
ax.fill_between(x, yn["nacional_ic95_inf"], yn["nacional_ic95_sup"], color=GRIS, alpha=0.18,
                linewidth=0)
ax.plot(x, yn["nacional_pct"], color=GRIS, linewidth=2, marker="o", markersize=6,
        markeredgecolor=SUP, markeredgewidth=2, label="Nacional", zorder=3)
ax.errorbar(x, yn["yucatan_pct"], yerr=[yn["yucatan_pct"] - yn["yucatan_ic95_inf"],
                                        yn["yucatan_ic95_sup"] - yn["yucatan_pct"]],
            fmt="none", ecolor=AZUL, elinewidth=1.4, capsize=4, alpha=0.6, zorder=3)
ax.plot(x, yn["yucatan_pct"], color=AZUL, linewidth=2, marker="o", markersize=8,
        markeredgecolor=SUP, markeredgewidth=2, label="Yucatán", zorder=4)
for _, f in yn.iterrows():
    abajo = f["anio"] == 2025  # ahí arriba van las etiquetas de fin de línea
    ax.text(f["anio"], f["yucatan_ic95_inf"] - 0.7 if abajo else f["yucatan_ic95_sup"] + 0.7,
            f"lugar {f['lugar']}\n({f['lugar_min']} a {f['lugar_max']})", ha="center",
            va="top" if abajo else "bottom", fontsize=8.5, color=TXT, linespacing=1.15)
ax.text(2025.12, yn["yucatan_pct"].iloc[-1], f"Yucatán {yn['yucatan_pct'].iloc[-1]:.1f}%",
        va="center", fontsize=9, color=TXT)
ax.text(2025.12, yn["nacional_pct"].iloc[-1] + 0.6, f"Nacional {yn['nacional_pct'].iloc[-1]:.1f}%",
        va="center", fontsize=9, color=TXT)
ax.set_xticks(x)
ax.set_xlim(2018.6, 2026.2)
ax.set_ylim(0, 42)
ax.set_ylabel("Vivió ciberacoso en los últimos 12 meses (%)", color=TXT2)
ax.yaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="lower left", ncol=2, labelcolor=TXT)
fig.suptitle("El ranking engaña: Yucatán pasó del lugar 1 al 25 en un año",
             x=0.04, ha="left", fontsize=13, color=TXT, fontweight="bold")
fig.text(0.04, 0.875, "Ciberacoso en Yucatán y en el país, 2019–2025. Junto a cada punto: lugar "
         "de Yucatán entre las 32 entidades y,\nentre paréntesis, el rango de lugares compatible "
         "con su margen de error.", fontsize=9, color=TXT2)
fig.text(0.04, 0.01, FUENTE + "\nBarras y banda: IC 95 %. 2019 tiene 508 entrevistas en Yucatán "
         "(los demás años, ~1,300). Script: analisis/A-contexto/analisis.py",
         fontsize=7.5, color=TXT2, va="bottom")
fig.tight_layout(rect=(0, 0.06, 1, 0.87))
fig.savefig(AQUI / "yucatan_vs_nacional.png", facecolor=SUP)
plt.close(fig)

# Gráfica 2: sexo, escolaridad y zona (2019–2025 juntos)
j = grupos[grupos["anio"] == JUNTOS]
total = j[j["dimension"] == "Total"]["pct"].iloc[0]
alturas = [len(v[1]) for v in DIMENSIONES.values()]
fig, ejes = plt.subplots(3, 1, figsize=(9, 5.6), dpi=150, sharex=True,
                         gridspec_kw={"height_ratios": alturas, "hspace": 0.35})
fig.patch.set_facecolor(SUP)
for ax, (dim, (_, niveles)) in zip(ejes, DIMENSIONES.items()):
    estilo(ax)
    s = j[j["dimension"] == dim].set_index("grupo").loc[niveles]
    yy = np.arange(len(niveles))
    ax.axvline(total, color=TXT2, linestyle="--", linewidth=1, zorder=1)
    ax.errorbar(s["pct"], yy, xerr=[s["pct"] - s["ic95_inf"], s["ic95_sup"] - s["pct"]],
                fmt="none", ecolor=AZUL, elinewidth=2, capsize=0, alpha=0.45, zorder=2)
    ax.scatter(s["pct"], yy, s=70, color=AZUL, edgecolor=SUP, linewidth=2, zorder=3)
    for yi, (v, sup) in enumerate(zip(s["pct"], s["ic95_sup"])):
        ax.text(sup + 0.6, yi, f"{v:.1f}%", va="center", fontsize=9, color=TXT)
    ax.set_yticks(yy, niveles)
    ax.set_ylim(len(niveles) - 0.4, -0.6)
    ax.set_title(dim, loc="left", fontsize=10, color=TXT, fontweight="bold", pad=4)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["bottom"].set_visible(False)
ejes[0].text(total - 0.4, -0.55, f"Total Yucatán {total:.1f}%", fontsize=8.5, color=TXT2,
             va="top", ha="right")
ejes[-1].set_xlim(0, 36)
ejes[-1].set_xlabel("Vivió ciberacoso en los últimos 12 meses (%), 2019–2025 juntos", color=TXT2)
fig.suptitle("El sexo no marca diferencia en el ciberacoso; la escolaridad y la zona sí",
             x=0.04, ha="left", fontsize=13, color=TXT, fontweight="bold")
fig.text(0.04, 0.01, FUENTE + "\nYucatán. Líneas: IC 95 %. Escolaridad y zona están ligadas a la "
         "edad: es asociación, no causa. Script: analisis/A-contexto/analisis.py",
         fontsize=7.5, color=TXT2, va="bottom")
fig.subplots_adjust(left=0.22, right=0.96, top=0.88, bottom=0.17)
fig.savefig(AQUI / "grupos.png", facecolor=SUP)
plt.close(fig)
print("\nGuardado en", AQUI)
