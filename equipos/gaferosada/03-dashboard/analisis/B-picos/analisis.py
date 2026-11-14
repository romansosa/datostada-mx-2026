"""Análisis B · ¿Los picos de la serie 2019–2025 son reales o vienen de cómo se levantó la encuesta?

Pregunta del equipo (13 nov): la prevalencia de Yucatán sube y baja (27.8 % en 2022, 20.3 % en
2023, 27.9 % en 2024, 17.3 % en 2025) y algunas celdas edad × año saltan (18–24 en 2022: 45.2 %;
60+ en 2024: 15.4 %). ¿Se debe a que ese año se entrevistó a más gente o a otra gente?

Lee: data/clean/mociba_2019_2025_yucatan.csv y data/clean/mociba_prevalencia_estatal_2019_2025.csv
Deja en esta carpeta:
  muestra_por_anio.csv     entrevistas, UPM, estratos, prevalencia, IC y efecto de diseño por año
  tamano_vs_prevalencia.csv  correlación entre entrevistas de cada año y su prevalencia
  cambios_anuales.csv      cambio contra el año anterior (total y por edad), con IC 95 %
  homogeneidad.csv         prueba de Wald «los 7 años son iguales» (total y por edad)
  composicion.csv          % ponderado y sin ponderar de cada grupo de edad, sexo y zona por año
  estandarizada.csv        prevalencia cruda contra estandarizada por edad, sexo y zona
  picos.csv                las celdas que parecen picos: casos, CV y si se salen de su serie
  otras_entidades.csv      la misma prueba de homogeneidad para las 32 entidades
  picos.png

Método: indicador comparable (10 situaciones, D-02), factores de expansión e IC 95 % por diseño
(Taylor, UPM dentro de estrato), igual que analisis/A-edad-plataforma. Los años son muestras
independientes, así que la varianza de una diferencia entre años es la suma de las varianzas.
Prueba de homogeneidad: W = Σ ((p_t − p̄) / ee_t)², con p̄ el promedio ponderado por 1/ee²; bajo
«no cambió nada» W ~ χ² con 6 g.l. (7 años). Estandarización directa: se fija la estructura
2019–2025 de edad × sexo × zona y se aplica la prevalencia de cada celda de cada año.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

RAIZ = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
Z = 1.96
EDADES = ["12-17", "18-24", "25-34", "35-44", "45-59", "60+"]
ANIOS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

df = pd.read_csv(RAIZ / "data/clean/mociba_2019_2025_yucatan.csv", dtype=str, encoding="utf-8-sig")
df = df.apply(lambda c: c.str.strip())
df["anio"] = df["anio"].astype(int)
df["factor"] = df["factor"].astype(float)
df["y"] = pd.to_numeric(df["ciberacoso_comparable"]).astype(float)
assert df["y"].notna().all()


# ---------- estimación por diseño (mismo método que A-edad-plataforma) ----------
def razon(d: pd.DataFrame, dom: np.ndarray) -> tuple[float, float, int]:
    w = d["factor"].to_numpy(float)
    m = np.asarray(dom, bool)
    y = np.where(m, d["y"].to_numpy(float), 0.0)
    X = (w * m).sum()
    r = (w * y).sum() / X
    z = w * m * (y - r) / X
    t = pd.DataFrame({"h": d["est_dis"].to_numpy(), "c": d["upm_dis"].to_numpy(), "z": z})
    tot = t.groupby(["h", "c"])["z"].sum()
    g = tot.groupby(level="h")
    k = g.transform("size").to_numpy(float)
    dif = (tot - g.transform("mean")).to_numpy()
    var = (np.where(k > 1, k / np.maximum(k - 1, 1), 0) * dif**2).sum()
    return r, float(np.sqrt(var)), int(m.sum())


def anio(a):
    return df[df["anio"] == a]


def homogeneidad(p, e):
    p, e = np.asarray(p, float), np.asarray(e, float)
    w = 1 / e**2
    pbar = (w * p).sum() / w.sum()
    W = float((((p - pbar) / e) ** 2).sum())
    gl = len(p) - 1
    return pbar, W, gl, float(stats.chi2.sf(W, gl))


# ---------- 1. muestra y prevalencia por año ----------
filas = []
for a in ANIOS:
    d = anio(a)
    r, e, n = razon(d, np.ones(len(d), bool))
    var_mas = r * (1 - r) / n  # varianza si fuera muestreo aleatorio simple
    filas.append({"anio": a, "entrevistas": n, "upm": d["upm_dis"].nunique(), "estratos": d["est_dis"].nunique(),
                  "pct": 100 * r, "ee": 100 * e, "ic95_inf": 100 * (r - Z * e), "ic95_sup": 100 * (r + Z * e),
                  "ancho_ic": 200 * Z * e, "efecto_diseno": e**2 / var_mas,
                  "pct_sin_ponderar": 100 * d["y"].mean(),
                  "poblacion_expandida": round(d["factor"].sum())})
muestra = pd.DataFrame(filas)
muestra.round(2).to_csv(AQUI / "muestra_por_anio.csv", index=False)

# ¿Los años con más entrevistas tienen más ciberacoso?
rho_s, p_s = stats.spearmanr(muestra["entrevistas"], muestra["pct"])
r_p, p_p = stats.pearsonr(muestra["entrevistas"], muestra["pct"])
sin19 = muestra[muestra["anio"] != 2019]
rho_s2, p_s2 = stats.spearmanr(sin19["entrevistas"], sin19["pct"])
pd.DataFrame([
    {"comparacion": "7 años", "spearman": rho_s, "p_spearman": p_s, "pearson": r_p, "p_pearson": p_p},
    {"comparacion": "2020-2025 (sin 2019)", "spearman": rho_s2, "p_spearman": p_s2, "pearson": np.nan, "p_pearson": np.nan},
]).round(3).to_csv(AQUI / "tamano_vs_prevalencia.csv", index=False)

# ---------- 2. prevalencia por edad y año ----------
celdas = []
for a in ANIOS:
    d = anio(a)
    for g in ["Total"] + EDADES:
        dom = np.ones(len(d), bool) if g == "Total" else (d["grupo_edad"] == g).to_numpy()
        r, e, n = razon(d, dom)
        celdas.append({"anio": a, "grupo_edad": g, "pct": 100 * r, "ee": 100 * e, "casos": n,
                       "victimas_en_muestra": int(d.loc[dom, "y"].sum()),
                       "cv": 100 * e / r if r > 0 else np.nan})
celdas = pd.DataFrame(celdas)

# cambios contra el año anterior
camb = []
for g in ["Total"] + EDADES:
    s = celdas[celdas["grupo_edad"] == g].set_index("anio")
    for a0, a1 in zip(ANIOS[:-1], ANIOS[1:]):
        dlt = s.loc[a1, "pct"] - s.loc[a0, "pct"]
        e = np.hypot(s.loc[a1, "ee"], s.loc[a0, "ee"])
        camb.append({"grupo_edad": g, "de": a0, "a": a1, "cambio_puntos": dlt,
                     "ic95_inf": dlt - Z * e, "ic95_sup": dlt + Z * e,
                     "significativo": abs(dlt) > Z * e})
camb = pd.DataFrame(camb)
camb.round(2).to_csv(AQUI / "cambios_anuales.csv", index=False)

# prueba «los 7 años son iguales»
homo = []
for g in ["Total"] + EDADES:
    s = celdas[celdas["grupo_edad"] == g]
    pbar, W, gl, p = homogeneidad(s["pct"], s["ee"])
    homo.append({"grupo_edad": g, "promedio_ponderado": pbar, "W": W, "gl": gl, "p_valor": p,
                 "cambios_anuales_significativos": int(camb[camb["grupo_edad"] == g]["significativo"].sum())})
homo = pd.DataFrame(homo)
homo.round(4).to_csv(AQUI / "homogeneidad.csv", index=False)

# ---------- 3. ¿cambió a quién se entrevistó? ----------
comp = []
for var in ["grupo_edad", "sexo", "dominio", "escolaridad"]:
    for a in ANIOS:
        d = anio(a)
        pond = d.groupby(var)["factor"].sum() / d["factor"].sum() * 100
        crudo = d[var].value_counts(normalize=True) * 100
        for cat in sorted(df[var].dropna().unique()):  # escolaridad trae vacíos
            comp.append({"variable": var, "categoria": cat, "anio": a,
                         "pct_ponderado": pond.get(cat, 0.0), "pct_muestra_sin_ponderar": crudo.get(cat, 0.0)})
comp = pd.DataFrame(comp)
comp.round(2).to_csv(AQUI / "composicion.csv", index=False)

# estandarización directa por edad × sexo × zona (estructura 2019–2025 junta)
celda = ["grupo_edad", "sexo", "dominio"]
estructura = df.groupby(celda)["factor"].sum()
estructura = estructura / estructura.sum()
est = []
for a in ANIOS:
    d = anio(a)
    pc = d.groupby(celda).apply(lambda x: np.average(x["y"], weights=x["factor"]), include_groups=False)
    comun = estructura.index.intersection(pc.index)
    estd = (pc[comun] * estructura[comun]).sum() / estructura[comun].sum()
    est.append({"anio": a, "pct_crudo": muestra.set_index("anio").loc[a, "pct"], "pct_estandarizado": 100 * estd,
                "celdas_sin_casos": len(estructura) - len(comun)})
est = pd.DataFrame(est)
est["diferencia"] = est["pct_crudo"] - est["pct_estandarizado"]
est.round(2).to_csv(AQUI / "estandarizada.csv", index=False)

# ---------- 4. los picos que se ven en la matriz ----------
PICOS = [(2022, "18-24"), (2024, "60+"), (2024, "45-59"), (2024, "12-17"), (2020, "60+"), (2024, "Total"),
         (2022, "Total"), (2023, "Total"), (2025, "Total")]
pic = []
for a, g in PICOS:
    s = celdas[celdas["grupo_edad"] == g].set_index("anio")
    resto = s.drop(index=a)
    pbar, _, _, _ = homogeneidad(resto["pct"], resto["ee"])
    e_resto = np.sqrt(1 / (1 / resto["ee"] ** 2).sum())
    dlt = s.loc[a, "pct"] - pbar
    e = np.hypot(s.loc[a, "ee"], e_resto)
    pic.append({"anio": a, "grupo_edad": g, "pct": s.loc[a, "pct"], "ic95_inf": s.loc[a, "pct"] - Z * s.loc[a, "ee"],
                "ic95_sup": s.loc[a, "pct"] + Z * s.loc[a, "ee"], "casos": s.loc[a, "casos"],
                "victimas_en_muestra": s.loc[a, "victimas_en_muestra"], "cv": s.loc[a, "cv"],
                "promedio_otros_anios": pbar, "diferencia": dlt, "dif_ic95_inf": dlt - Z * e,
                "dif_ic95_sup": dlt + Z * e, "se_sale_de_su_serie": abs(dlt) > Z * e})
pic = pd.DataFrame(pic)
pic.round(2).to_csv(AQUI / "picos.csv", index=False)

# ---------- 5. ¿pasa lo mismo en las otras entidades? ----------
ent = pd.read_csv(RAIZ / "data/clean/mociba_prevalencia_estatal_2019_2025.csv", dtype={"cve_ent": str})
otras = []
for (cve, nom), s in ent[ent["cve_ent"] != "00"].groupby(["cve_ent", "nom_ent"]):
    s = s.sort_values("anio")
    pbar, W, gl, p = homogeneidad(s["prevalencia_comparable"], s["ee_comparable"])
    otras.append({"cve_ent": cve, "entidad": nom, "promedio": pbar, "W": W, "p_valor": p,
                  "rango_max_min": s["prevalencia_comparable"].max() - s["prevalencia_comparable"].min(),
                  "n_promedio": s["n"].mean()})
otras = pd.DataFrame(otras).sort_values("W", ascending=False)
otras["lugar_por_variacion"] = np.arange(1, len(otras) + 1)
otras.round(4).to_csv(AQUI / "otras_entidades.csv", index=False)

# ---------- gráfica ----------
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
m = muestra
ax[0].errorbar(m["anio"], m["pct"], yerr=Z * m["ee"], fmt="o-", capsize=4, color="#c0392b", label="Ponderada (IC 95 %)")
ax[0].plot(est["anio"], est["pct_estandarizado"], "s--", color="#4e79a7", label="Estandarizada por edad, sexo y zona")
nac = ent[ent["cve_ent"] == "00"].sort_values("anio")
ax[0].plot(nac["anio"], nac["prevalencia_comparable"], ":", color="#5b6770", label="Nacional")
for _, r in m.iterrows():
    ax[0].annotate(f"n={int(r['entrevistas'])}", (r["anio"], r["ic95_inf"]), textcoords="offset points",
                   xytext=(0, -14), ha="center", fontsize=8, color="#5b6770")
ax[0].set_title("Yucatán: prevalencia por año y entrevistas (n)")
ax[0].set_ylabel("% de usuarios de internet (indicador comparable)")
ax[0].legend(fontsize=8, loc="upper right")
ax[0].set_ylim(5, 40)
o = otras.reset_index(drop=True)
col = ["#c0392b" if c == "31" else "#9aa5ad" for c in o["cve_ent"]]
ax[1].bar(range(len(o)), o["W"], color=col)
ax[1].axhline(stats.chi2.ppf(0.95, 6), color="#1f2d3d", ls="--", lw=1)
ax[1].text(len(o) - 1, stats.chi2.ppf(0.95, 6) + 1, "límite de lo que explica el azar (p = 0.05)", ha="right", fontsize=8)
ax[1].set_xticks(range(len(o)))
ax[1].set_xticklabels(o["entidad"].str.slice(0, 10), rotation=90, fontsize=7)
ax[1].set_title("¿Cuánto sube y baja cada entidad entre años?\n(W: más alto = más variación de la que explica el azar)", fontsize=10)
fig.text(0.01, 0.01, "Fuente: INEGI, MOCIBA 2019–2025, microdatos. Indicador comparable, factores de expansión, IC 95 % por diseño.",
         fontsize=8, color="#5b6770")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(AQUI / "picos.png", dpi=150)

# ---------- resumen en pantalla ----------
pd.set_option("display.width", 200)
print(muestra.round(2).to_string(index=False))
print("\nTamaño vs prevalencia:\n", pd.read_csv(AQUI / "tamano_vs_prevalencia.csv").to_string(index=False))
print("\nHomogeneidad:\n", homo.round(4).to_string(index=False))
print("\nCambios significativos:\n", camb[camb["significativo"]].round(1).to_string(index=False))
print("\nEstandarizada:\n", est.round(2).to_string(index=False))
print("\nComposición por edad (ponderada vs sin ponderar):")
print(comp[comp["variable"] == "grupo_edad"].pivot(index="categoria", columns="anio", values="pct_ponderado").round(1))
print(comp[comp["variable"] == "grupo_edad"].pivot(index="categoria", columns="anio", values="pct_muestra_sin_ponderar").round(1))
print("\nPicos:\n", pic.round(1).to_string(index=False))
print("\nYucatán entre las entidades:\n", otras[otras["cve_ent"] == "31"].round(3).to_string(index=False))
print("Entidades con p < 0.05:", int((otras["p_valor"] < 0.05).sum()), "de", len(otras))
