"""Análisis A · Ciberacoso en Yucatán por grupo de edad (2019–2025) y plataforma (2021–2025).

Responde D-03: ¿qué grupos de edad concentran el ciberacoso en Yucatán de manera constante
entre 2019 y 2025, y en qué plataformas digitales lo vive cada grupo?

Lee: data/clean/mociba_2019_2025_yucatan.csv
Deja en esta carpeta:
  matriz_edad_anio.csv      prevalencia por grupo de edad y año (+ 2019–2025 juntos)
  constancia_edad.csv       en cuántos años cada grupo queda arriba del promedio estatal
  distancia_al_total.csv    puntos de cada grupo (y 45+, 12–24) contra el total de su año, IC 95 %
  distancia_resumen.csv     años abajo/arriba (y cuántos significativos), mínimo y máximo
  kpi_brecha.csv            brecha 18–24 contra 60+ (puntos y veces), por año y juntos
  edad_plataforma.csv       entre víctimas, % por plataforma según grupo de edad (2021–2025)
  matriz_edad_anio.png, edad_plataforma.png
Deja en data/tableau/: A-edad_anio.csv (pieza 1 del dashboard, #18 y #20) y A-edad_kpi.csv
  (pieza 3). La pieza 2 (edad × plataforma) es de Felipe: analisis/B-plataforma/ y
  data/tableau/B-edad_plataforma.csv (H-FE-02). Aquí la parte de plataforma queda solo como
  réplica independiente (mismas cifras), sin extracto para Tableau.

Definiciones
- Prevalencia: `ciberacoso_comparable` (al menos 1 de las 10 situaciones preguntadas los siete
  años; regla de D-02). Denominador: usuarios de internet de 12 años o más.
- Plataforma: entre víctimas (`ciberacoso` = 1, indicador oficial; en 2021–2025 son las mismas
  13 situaciones todos los años), % que vivió el acoso por alguna red de esa plataforma
  (`plataforma_*`). Una víctima puede marcar varias, así que no suman 100.
- Varios años juntos: se suman los factores de expansión de todos los años (promedio de la
  población de esos años) y cada año es un estrato distinto (`estrato_pool`).

Varianza: linealización de Taylor para razones, UPM (`upm_dis`) dentro de `estrato_pool`, con
reemplazo (mismo método que data/limpieza/mociba_serie.py y analisis/B-practica). IC 95 %
(el mismo nivel del Data Brief y de docs/exploracion_mociba.md). La brecha y la razón entre
dos grupos usan la covarianza entre ambos (se linealiza la diferencia y el log de la razón).
Precisión: CV < 15 % alta, 15–30 % moderada, >= 30 % baja; también se marca n < 100.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
TABLEAU = RAIZ / "data/tableau"
Z = 1.96
EDADES = ["12-17", "18-24", "25-34", "35-44", "45-59", "60+"]
ANIOS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
JUNTOS = "2019-2025"
PLATAFORMAS = {
    "mensajeria": "Mensajería (WhatsApp, Messenger, Telegram, SMS)",
    "redes_sociales": "Redes sociales (Facebook, Instagram, TikTok, X, YouTube)",
    "llamadas": "Llamadas (celular o fijo)",
    "correo": "Correo electrónico",
}

df = pd.read_csv(RAIZ / "data/clean/mociba_2019_2025_yucatan.csv", dtype=str,
                 encoding="utf-8-sig")
df = df.apply(lambda c: c.str.strip())  # algunos CSV de INEGI traen \r pegado
df["anio"] = df["anio"].astype(int)
df["factor"] = df["factor"].astype(float)
for c in ["ciberacoso", "ciberacoso_comparable"] + [f"plataforma_{p}" for p in PLATAFORMAS]:
    df[c] = pd.to_numeric(df[c])
assert set(df["grupo_edad"]) == set(EDADES), df["grupo_edad"].unique()


# ---------- estimación por diseño ----------
def lineal(d: pd.DataFrame, var: str, dom: np.ndarray) -> tuple[float, np.ndarray, int]:
    """Razón ponderada de `var` en el dominio y su variable linealizada por persona."""
    w = d["factor"].to_numpy(float)
    m = np.asarray(dom, bool)
    y = d[var].to_numpy(float)
    assert not np.isnan(y[m]).any(), f"{var} vacía dentro del dominio"
    y = np.where(m, y, 0.0)
    X = (w * m).sum()
    r = (w * y).sum() / X
    return r, w * m * (y - r) / X, int(m.sum())


def ee(d: pd.DataFrame, z: np.ndarray) -> float:
    t = pd.DataFrame({"h": d["estrato_pool"].to_numpy(), "c": d["upm_dis"].to_numpy(), "z": z})
    tot = t.groupby(["h", "c"])["z"].sum()
    g = tot.groupby(level="h")
    k = g.transform("size").to_numpy(float)
    dif = (tot - g.transform("mean")).to_numpy()
    return float(np.sqrt((np.where(k > 1, k / np.maximum(k - 1, 1), 0) * dif**2).sum()))


def precision(cv: float, n: int) -> str:
    if n < 100 or cv >= 30:
        return "baja"
    return "moderada" if cv >= 15 else "alta"


def fila(d, var, dom, **etiquetas) -> dict:
    r, z, n = lineal(d, var, dom)
    e = ee(d, z)
    cv = 100 * e / r if r > 0 else np.nan
    return {**etiquetas, "pct": 100 * r, "ic95_inf": 100 * max(r - Z * e, 0),
            "ic95_sup": 100 * min(r + Z * e, 1), "ee": 100 * e, "cv_pct": cv,
            "casos_muestra": n, "poblacion_promedio_anual": None, "precision": precision(cv, n)}


def periodo(anio):
    return df if anio == JUNTOS else df[df["anio"] == anio]


def n_anios(anio):
    return len(ANIOS) if anio == JUNTOS else 1


# ---------- 1. matriz edad × año ----------
filas = []
for anio in ANIOS + [JUNTOS]:
    d = periodo(anio)
    todos = np.ones(len(d), bool)
    for g in ["Total"] + EDADES:
        dom = todos if g == "Total" else (d["grupo_edad"] == g).to_numpy()
        f = fila(d, "ciberacoso_comparable", dom, anio=str(anio), grupo_edad=g)
        f["poblacion_promedio_anual"] = round(d["factor"][dom].sum() / n_anios(anio))
        f["victimas_promedio_anual"] = round(f["pct"] / 100 * f["poblacion_promedio_anual"])
        filas.append(f)
matriz = pd.DataFrame(filas)

# ---------- 2. constancia: ¿en cuántos años cada grupo queda arriba del total estatal? ----------
anual = matriz[(matriz["anio"] != JUNTOS) & (matriz["grupo_edad"] != "Total")].copy()
total = matriz[(matriz["anio"] != JUNTOS) & (matriz["grupo_edad"] == "Total")].set_index("anio")["pct"]
anual["arriba_del_total"] = anual["pct"] > anual["anio"].map(total)
anual["lugar_en_el_anio"] = anual.groupby("anio")["pct"].rank(ascending=False).astype(int)
constancia = anual.groupby("grupo_edad", sort=False).agg(
    anios_arriba_del_total=("arriba_del_total", "sum"),
    anios_en_top2=("lugar_en_el_anio", lambda s: int((s <= 2).sum())),
    lugar_promedio=("lugar_en_el_anio", "mean"),
).reindex(EDADES).reset_index()
constancia["anios"] = len(ANIOS)

# ---------- 2b. distancia de cada grupo al total estatal de su año (puntos, IC 95 %) ----------
# El grupo es parte del total, así que el EE de la diferencia se saca linealizando las dos
# razones juntas (z_grupo − z_total). "45+" junta 45–59 y 60+ (pedido de la revisión de Román:
# "45 y más" es lo sólido, no "35 y más").
GRUPOS_DIST = {g: [g] for g in EDADES} | {"45+": ["45-59", "60+"], "12-24": ["12-17", "18-24"]}
dist = []
for anio in ANIOS + [JUNTOS]:
    d = periodo(anio)
    rt, zt, _ = lineal(d, "ciberacoso_comparable", np.ones(len(d), bool))
    for g, miembros in GRUPOS_DIST.items():
        rg, zg, n = lineal(d, "ciberacoso_comparable", d["grupo_edad"].isin(miembros).to_numpy())
        e = ee(d, zg - zt)
        dif = 100 * (rg - rt)
        dist.append({"anio": str(anio), "grupo_edad": g, "pct_grupo": 100 * rg,
                     "pct_total": 100 * rt, "distancia_puntos": dif,
                     "ic95_inf": dif - Z * 100 * e, "ic95_sup": dif + Z * 100 * e,
                     "significativa": abs(dif) > Z * 100 * e, "casos_muestra": n})
dist = pd.DataFrame(dist)
d_anual = dist[dist["anio"] != JUNTOS]
resumen_dist = d_anual.groupby("grupo_edad", sort=False).agg(
    anios_abajo=("distancia_puntos", lambda s: int((s < 0).sum())),
    anios_arriba=("distancia_puntos", lambda s: int((s > 0).sum())),
    anios_abajo_significativo=("distancia_puntos",
                               lambda s: int(((s < 0) & d_anual.loc[s.index, "significativa"]).sum())),
    anios_arriba_significativo=("distancia_puntos",
                                lambda s: int(((s > 0) & d_anual.loc[s.index, "significativa"]).sum())),
    distancia_min=("distancia_puntos", "min"),
    distancia_max=("distancia_puntos", "max"),
).reset_index()
resumen_dist = resumen_dist.merge(
    dist[dist["anio"] == JUNTOS][["grupo_edad", "distancia_puntos", "ic95_inf", "ic95_sup"]]
    .rename(columns={"distancia_puntos": "distancia_2019_2025", "ic95_inf": "ic95_inf_2019_2025",
                     "ic95_sup": "ic95_sup_2019_2025"}), on="grupo_edad")

# ---------- 3. KPI: brecha 18–24 contra 60+ ----------
kpi = []
for anio in ANIOS + [JUNTOS]:
    d = periodo(anio)
    r1, z1, n1 = lineal(d, "ciberacoso_comparable", (d["grupo_edad"] == "18-24").to_numpy())
    r2, z2, n2 = lineal(d, "ciberacoso_comparable", (d["grupo_edad"] == "60+").to_numpy())
    e_dif = ee(d, z1 - z2)
    e_log = ee(d, z1 / r1 - z2 / r2)  # log(r1/r2)
    kpi.append({
        "anio": str(anio), "pct_18_24": 100 * r1, "pct_60_mas": 100 * r2,
        "brecha_puntos": 100 * (r1 - r2),
        "brecha_ic95_inf": 100 * (r1 - r2 - Z * e_dif),
        "brecha_ic95_sup": 100 * (r1 - r2 + Z * e_dif),
        "veces": r1 / r2,
        "veces_ic95_inf": np.exp(np.log(r1 / r2) - Z * e_log),
        "veces_ic95_sup": np.exp(np.log(r1 / r2) + Z * e_log),
        "brecha_significativa": (r1 - r2 - Z * e_dif) > 0,
        "casos_18_24": n1, "casos_60_mas": n2,
    })
kpi = pd.DataFrame(kpi)

# ---------- 4. edad × plataforma entre víctimas, 2021–2025 juntos ----------
v = df[df["anio"] >= 2021]
victima = (v["ciberacoso"] == 1).to_numpy()
plat = []
for g in ["Total"] + EDADES:
    dom = victima if g == "Total" else victima & (v["grupo_edad"] == g).to_numpy()
    for p in PLATAFORMAS:
        f = fila(v, f"plataforma_{p}", dom, grupo_edad=g, plataforma=p,
                 plataforma_nombre=PLATAFORMAS[p])
        f["poblacion_promedio_anual"] = round(v["factor"][dom].sum() / 5)
        plat.append(f)
plat = pd.DataFrame(plat).rename(columns={"poblacion_promedio_anual": "victimas_promedio_anual",
                                          "casos_muestra": "victimas_muestra"})
plat["periodo"] = "2021-2025"

# ---------- guardar ----------
def redondear(t):
    t = t.copy()
    num = t.select_dtypes("float").columns
    t[num] = t[num].round(2 if "veces" in t else 1)
    return t


matriz = redondear(matriz.drop(columns="ee"))
plat = redondear(plat.drop(columns="ee"))
kpi = kpi.round(2)
constancia["lugar_promedio"] = constancia["lugar_promedio"].round(1)

matriz.to_csv(AQUI / "matriz_edad_anio.csv", index=False)
constancia.to_csv(AQUI / "constancia_edad.csv", index=False)
dist.round(1).to_csv(AQUI / "distancia_al_total.csv", index=False)
resumen_dist.round(1).to_csv(AQUI / "distancia_resumen.csv", index=False)
kpi.to_csv(AQUI / "kpi_brecha.csv", index=False)
plat.to_csv(AQUI / "edad_plataforma.csv", index=False)
TABLEAU.mkdir(exist_ok=True)
matriz.to_csv(TABLEAU / "A-edad_anio.csv", index=False)
kpi.to_csv(TABLEAU / "A-edad_kpi.csv", index=False)

pd.set_option("display.width", 200)
print("MATRIZ EDAD × AÑO (ciberacoso comparable, %)")
print(matriz.pivot(index="grupo_edad", columns="anio", values="pct").reindex(["Total"] + EDADES))
print("\nCONSTANCIA\n", constancia.to_string(index=False))
print("\nDISTANCIA AL TOTAL ESTATAL DEL AÑO (puntos)")
print(dist.pivot(index="grupo_edad", columns="anio", values="distancia_puntos").round(1)
      .reindex(list(GRUPOS_DIST)))
print("\nRESUMEN DISTANCIA\n", resumen_dist.round(1).to_string(index=False))
print("\nKPI 18–24 contra 60+\n", kpi.to_string(index=False))
print("\nPLATAFORMA ENTRE VÍCTIMAS, 2021–2025 (%)")
print(plat.pivot(index="grupo_edad", columns="plataforma", values="pct").reindex(["Total"] + EDADES))
print(plat[["grupo_edad", "plataforma", "ic95_inf", "ic95_sup", "victimas_muestra", "precision"]]
      .to_string(index=False))

# ---------- gráficas ----------
SUP, TXT, TXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
FUENTE = "Fuente: INEGI, MOCIBA 2019–2025, microdatos de Yucatán. Usuarios de internet de 12 años y más."


def estilo(ax):
    ax.set_facecolor(SUP)
    for lado in ["top", "right", "left"]:
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TXT2, length=0)


# Gráfica 1: matriz edad × año (secuencial azul)
azul = LinearSegmentedColormap.from_list(
    "azul", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])
cols = [str(a) for a in ANIOS] + [JUNTOS]
piv = matriz[matriz["grupo_edad"] != "Total"].pivot(index="grupo_edad", columns="anio", values="pct")
prec = matriz[matriz["grupo_edad"] != "Total"].pivot(index="grupo_edad", columns="anio",
                                                     values="precision")
piv, prec = piv.reindex(index=EDADES, columns=cols), prec.reindex(index=EDADES, columns=cols)

fig, ax = plt.subplots(figsize=(10, 5.4), dpi=150)
fig.patch.set_facecolor(SUP)
estilo(ax)
ax.spines["bottom"].set_visible(False)
vmax = 46
for i, g in enumerate(EDADES):
    for j, c in enumerate(cols):
        val = piv.loc[g, c]
        x0 = j + (0.25 if c == JUNTOS else 0)  # separa la columna de los siete años juntos
        ax.add_patch(plt.Rectangle((x0 + 0.03, i + 0.03), 0.94, 0.94, color=azul(val / vmax),
                                   linewidth=0))
        marca = {"alta": "", "moderada": "", "baja": "°"}[prec.loc[g, c]]
        ax.text(x0 + 0.5, i + 0.5, f"{val:.0f}{marca}", ha="center", va="center", fontsize=10,
                color="white" if val / vmax > 0.45 else TXT,
                fontweight="bold" if c == JUNTOS else "normal")
ax.set_xlim(0, len(cols) + 0.25)
ax.set_ylim(len(EDADES), 0)
ax.set_xticks([j + 0.5 + (0.25 if c == JUNTOS else 0) for j, c in enumerate(cols)],
              [c if c != JUNTOS else "7 años\njuntos" for c in cols])
ax.set_yticks([i + 0.5 for i in range(len(EDADES))], [f"{g} años" for g in EDADES])
ax.xaxis.tick_top()
k = kpi[kpi["anio"] == JUNTOS].iloc[0]
fig.suptitle("De cada 100 usuarios de internet, cuántos vivieron ciberacoso, por edad",
             x=0.04, ha="left", fontsize=13, color=TXT, fontweight="bold")
fig.text(0.04, 0.905,
         f"Yucatán, 2019–2025. Los de 18 a 24 años lo viven {k['veces']:.1f} veces más que los de 60 y "
         f"más ({k['pct_18_24']:.1f} % contra {k['pct_60_mas']:.1f} %, siete años juntos).",
         fontsize=9.5, color=TXT2)
fig.text(0.04, 0.01,
         FUENTE + " Indicador comparable (10 situaciones comunes a los 7 años).\n"
         "° Precisión baja (CV ≥ 30 % o menos de 100 casos): usar con reserva. 2019 tiene ~500 "
         "entrevistas, la mitad que los demás años. Script: analisis/A-edad-plataforma/analisis.py",
         fontsize=7.5, color=TXT2, va="bottom")
fig.tight_layout(rect=(0, 0.07, 1, 0.89))
fig.savefig(AQUI / "matriz_edad_anio.png", facecolor=SUP)
plt.close(fig)

# Gráfica 2: plataforma por edad entre víctimas (3 series + IC 95 %)
COLOR = {"mensajeria": "#2a78d6", "redes_sociales": "#eb6834", "llamadas": "#1baf7a"}
CORTO = {"mensajeria": "Mensajería", "redes_sociales": "Redes sociales", "llamadas": "Llamadas"}
fig, ax = plt.subplots(figsize=(9, 5.4), dpi=150)
fig.patch.set_facecolor(SUP)
estilo(ax)
x = np.arange(len(EDADES))
for p, col in COLOR.items():
    s = plat[plat["plataforma"] == p].set_index("grupo_edad").loc[EDADES]
    ax.fill_between(x, s["ic95_inf"], s["ic95_sup"], color=col, alpha=0.12, linewidth=0)
    ax.plot(x, s["pct"], color=col, linewidth=2, marker="o", markersize=7,
            markeredgecolor=SUP, markeredgewidth=2, label=CORTO[p], zorder=3)
    ax.text(x[-1] + 0.12, s["pct"].iloc[-1], f"{CORTO[p]} {s['pct'].iloc[-1]:.0f}%", va="center",
            fontsize=9, color=TXT)
    ax.text(x[0] - 0.12, s["pct"].iloc[0], f"{s['pct'].iloc[0]:.0f}%", va="center", ha="right",
            fontsize=9, color=TXT)
nvict = plat[plat["plataforma"] == "mensajeria"].set_index("grupo_edad").loc[EDADES,
                                                                             "victimas_muestra"]
ax.set_xticks(x, [f"{g}\n(n={n})" for g, n in zip(EDADES, nvict)])
ax.set_xlim(-0.6, len(EDADES) + 0.9)
ax.set_ylim(0, 80)
ax.set_xlabel("Grupo de edad (años) · n = víctimas en la muestra", color=TXT2)
ax.set_ylabel("% de las víctimas acosadas por esa plataforma", color=TXT2)
ax.yaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.45, 1.08), ncol=3,
          labelcolor=TXT)
fig.suptitle("Con la edad, el ciberacoso se mueve de las redes sociales a las llamadas",
             x=0.04, ha="left", fontsize=13, color=TXT, fontweight="bold")
fig.text(0.04, 0.01,
         FUENTE + " Víctimas de ciberacoso, 2021–2025 juntos.\n"
         "Una víctima puede marcar varias plataformas. Bandas: IC 95 %. 60+ tiene menos de 100 "
         "víctimas en la muestra. Correo (<6 %) no se muestra.\n"
         "Script: analisis/A-edad-plataforma/analisis.py",
         fontsize=7.5, color=TXT2, va="bottom")
fig.tight_layout(rect=(0, 0.09, 1, 0.95))
fig.savefig(AQUI / "edad_plataforma.png", facecolor=SUP)
plt.close(fig)
print("\nGuardado en", AQUI)
