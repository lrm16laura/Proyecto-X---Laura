# ============================================================
# SISTEMA DE CÁLCULO DE FABRICACIÓN — Flujo en 2 fases:
#   1) Cálculo inicial (Modo C)
#   2) Reajustar y volver a planificar por porcentajes (Re‑Modo C)
# Visual: Gráfico único 0184 vs 0833 (Horas)
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# ------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Cálculo de Fabricación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------
# ESTILOS CSS (idéntico al estilo de referencia)
# ------------------------------------------------------------
st.markdown("""
    <style>
    .main { padding-top: 2rem; }
    h1 { color: #1f77b4; text-align: center; font-size: 2.5rem; margin-bottom: 1rem; }
    h2 { color: #2c3e50; border-bottom: 3px solid #1f77b4; padding-bottom: 0.5rem; }
    .section-container {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 1.5rem;
    }
    .footer {
        text-align: center; color: #7f8c8d; font-size: 0.9rem; margin-top: 2rem;
        padding-top: 1rem; border-top: 1px solid #ecf0f1;
    }
    .stButton > button { width: 100%; font-weight: bold; border-radius: 8px; }
    .small-note { color:#7f8c8d; font-size:0.85rem; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# CONSTANTES Y UTILIDADES
# ------------------------------------------------------------
UPLOAD_DIR = "archivos_cargados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def guardar_archivo(archivo, nombre_seccion):
    """Guarda el archivo subido con sello de tiempo."""
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_seccion}_{timestamp}.xlsx"
        ruta_archivo = os.path.join(UPLOAD_DIR, nombre_archivo)
        with open(ruta_archivo, "wb") as f:
            f.write(archivo.getbuffer())
        return ruta_archivo
    return None

def to_float_safe(v, default=0.0):
    """Convierte valores a float, aceptando coma decimal y vacíos."""
    if pd.isna(v): return float(default)
    if isinstance(v, str):
        v = v.replace(",", ".").strip()
        if v == "": return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)

def norm_code(code):
    """
    Normaliza el código de centro:
    - Convierte a str
    - Extrae dígitos
    - Rellena a 4 dígitos si aplica (ej. 833 -> 0833)
    """
    s = str(code).strip()
    if s.endswith(".0"): s = s[:-2]
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "":
        return s
    if len(digits) < 4:
        digits = digits.zfill(4)
    return digits

def leer_capacidades(df_cap):
    """
    Lee exactamente la columna 'Capacidad horas' por centro.
    Estructura esperada:
      - 'Planta' (opcional)
      - 'Centro'
      - 'Capacidad horas'
    """
    if "Centro" not in df_cap.columns:
        st.error("❌ No se encuentra la columna 'Centro' en el Excel de capacidad.")
        st.stop()

    col_nor = {c: c.strip().lower() for c in df_cap.columns}
    cap_col = None
    for col, low in col_nor.items():
        if low == "capacidad horas" or (("capacidad" in low) and ("hora" in low)):
            cap_col = col
            break

    if cap_col is None:
        st.error("❌ No se encuentra la columna 'Capacidad horas' en el Excel de capacidad.")
        st.stop()

    capacidades = {}
    for _, r in df_cap.iterrows():
        c = norm_code(r["Centro"])
        capacidades[c] = to_float_safe(r[cap_col], 0.0)

    if not capacidades:
        st.error("❌ No se han podido leer capacidades del Excel.")
        st.stop()

    return capacidades

def detectar_centros_desde_capacidades(capacidades):
    """
    Identifica DG y MCH usando sufijos habituales.
    DG = termina en '833'
    MCH = termina en '184'
    """
    keys = list(capacidades.keys())
    DG = next((k for k in keys if k.endswith("833")), keys[0])
    MCH = next((k for k in keys if k.endswith("184") and k != DG),
               keys[1] if len(keys) > 1 else keys[0])
    return DG, MCH, keys

# ------------------------------------------------------------
# REPARTO PROPORCIONAL POR SEMANA (POR HORAS)
# ------------------------------------------------------------
def repartir_porcentaje(df_semana, pct_dg, dg_code, mch_code):
    """
    Reparte proporcionalmente HORAS: pct_dg% a DG, resto a MCH.
    """
    if df_semana.empty:
        return df_semana
    if pct_dg <= 0:
        df_semana["Centro"] = mch_code
        return df_semana
    if pct_dg >= 100:
        df_semana["Centro"] = dg_code
        return df_semana

    df_semana = df_semana.sort_values("Horas", ascending=False).copy()
    total_h = df_semana["Horas"].sum()
    objetivo = total_h * (pct_dg / 100.0)

    acumulado = 0.0
    centros = []
    for _, r in df_semana.iterrows():
        if acumulado < objetivo:
            centros.append(dg_code)
            acumulado += float(r["Horas"])
        else:
            centros.append(mch_code)
    df_semana["Centro"] = centros
    return df_semana

# ------------------------------------------------------------
# MODO C — PLANIFICACIÓN (capacidad diaria, lotes, mover +1 día, mismo centro)
# ------------------------------------------------------------
def modo_C(df_agrupado, df_mat, capacidades, DG_code, MCH_code):
    """
    Aplica la planificación Modo C:
      - Capacidad diaria por centro (desde Excel 'Capacidad horas').
      - Divide por lotes (mínimo/máximo).
      - Si no cabe, mueve solo al día siguiente, mismo centro.
      - Respeta fecha mínima.
      - Devuelve 'Fecha' en formato dd.MM.yyyy.
    Mantiene Lote_min y Lote_max.
    """

    tiempos = df_mat[[
        "Material", "Unidad",
        "Tiempo fabricación unidad DG",
        "Tiempo fabricación unidad MCH",
        "Tamaño lote mínimo", "Tamaño lote máximo"
    ]].drop_duplicates()

    df = df_agrupado.merge(
        tiempos,
        on=["Material", "Unidad"],
        how="left",
        suffixes=("","_mat")
    )

    capacidad_restante = {}
    def get_cap(centro, fecha):
        clave = (str(centro), fecha)
        if clave not in capacidad_restante:
            capacidad_restante[clave] = float(capacidades.get(str(centro), 0.0))
        return capacidad_restante[clave]

    def consume(centro, fecha, horas):
        capacidad_restante[(str(centro), fecha)] = get_cap(centro, fecha) - float(horas)

    def tiempo_necesario(centro, qty, r):
        tu = to_float_safe(
            r["Tiempo fabricación unidad DG"] if str(centro) == str(DG_code) else r["Tiempo fabricación unidad MCH"], 0
        )
        return qty * tu

    def cantidad_por_capacidad(centro, cap_horas, r):
        tu = to_float_safe(
            r["Tiempo fabricación unidad DG"] if str(centro) == str(DG_code) else r["Tiempo fabricación unidad MCH"], 0
        )
        return (cap_horas / tu) if tu > 0 else 0

    def parse_fecha(x):
        if isinstance(x, (pd.Timestamp, datetime)):
            return pd.to_datetime(x).normalize()
        x = str(x)
        try:
            return pd.to_datetime(x, format="%d.%m.%Y").normalize()
        except Exception:
            return pd.to_datetime(x).normalize()

    out = []
    contador = 1
    MAX_DIAS = 365

    if "Lote_min" not in df.columns:
        df["Lote_min"] = df.get("Tamaño lote mínimo", np.nan)
    if "Lote_max" not in df.columns:
        df["Lote_max"] = df.get("Tamaño lote máximo", np.nan)

    for _, r in df.iterrows():
        centro = norm_code(r["Centro"])
        fecha = parse_fecha(r["Fecha"])
        semana = r["Semana"] if "Semana" in r and pd.notna(r["Semana"]) else fecha.strftime("%Y-W%U")

        total = max(
            to_float_safe(r["Cantidad"], 0),
            to_float_safe(r.get("Lote_min", r.get("Tamaño lote mínimo", 0)), 0)
        )
        lote_max = max(
            1.0,
            to_float_safe(r.get("Lote_max", r.get("Tamaño lote máximo", 1)), 1)
        )
        lote_min = to_float_safe(r.get("Lote_min", r.get("Tamaño lote mínimo", 0)), 0)

        # Troceo por Lote_max
        lotes = []
        resto = total
        while resto > 0:
            q = min(resto, lote_max)
            lotes.append(round(q, 2))
            resto = round(resto - q, 6)

        for ql in lotes:
            pendiente = ql
            dias = 0

            if capacidades.get(str(centro), 0) <= 0:
                out.append({
                    "Nº de propuesta": contador,
                    "Material": r["Material"],
                    "Centro": centro,
                    "Clase de orden": "NORM",
                    "Cantidad a fabricar": round(pendiente, 2),
                    "Unidad": r["Unidad"],
                    "Fecha": fecha.strftime("%d.%m.%Y"),
                    "Semana": semana,
                    "Lote_min": lote_min,
                    "Lote_max": lote_max
                })
                contador += 1
                continue

            while pendiente > 0:
                cap_dia = get_cap(centro, fecha)
                horas_nec = tiempo_necesario(centro, pendiente, r)

                if cap_dia >= horas_nec:
                    consume(centro, fecha, horas_nec)
                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(pendiente, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana,
                        "Lote_min": lote_min,
                        "Lote_max": lote_max
                    })
                    contador += 1
                    pendiente = 0
                    break

                q_posible = cantidad_por_capacidad(centro, cap_dia, r)
                if q_posible > 0:
                    h_prod = tiempo_necesario(centro, q_posible, r)
                    consume(centro, fecha, h_prod)
                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(q_posible, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana,
                        "Lote_min": lote_min,
                        "Lote_max": lote_max
                    })
                    contador += 1
                    pendiente = round(pendiente - q_posible, 6)

                if pendiente <= 0:
                    break

                if dias >= MAX_DIAS:
                    out.append({
                        "Nº de propuesta": contador,
                        "Material": r["Material"],
                        "Centro": centro,
                        "Clase de orden": "NORM",
                        "Cantidad a fabricar": round(pendiente, 2),
                        "Unidad": r["Unidad"],
                        "Fecha": fecha.strftime("%d.%m.%Y"),
                        "Semana": semana,
                        "Lote_min": lote_min,
                        "Lote_max": lote_max
                    })
                    contador += 1
                    pendiente = 0
                    break

                fecha = (fecha + timedelta(days=1)).normalize()
                semana = fecha.strftime("%Y-W%U")
                dias += 1

    return pd.DataFrame(out)

# ------------------------------------------------------------
# EJECUCIÓN — Separada en 2 fases
#   A) Modo C inicial
#   B) Reajuste + Re‑Modo C
# ------------------------------------------------------------
def ejecutar_modoC_base(df_cap, df_mat, df_cli, df_dem):
    # 1) Capacidades exactas
    capacidades = leer_capacidades(df_cap)
    DG_code, MCH_code, _ = detectar_centros_desde_capacidades(capacidades)

    # 2) Normalizar fechas y semana en demanda
    df_dem = df_dem.copy()
    df_dem["Fecha_DT"] = pd.to_datetime(df_dem["Fecha de necesidad"])
    df_dem["Semana_Label"] = df_dem["Fecha_DT"].dt.strftime("%Y-W%U")

    # 3) Merge con maestros
    df = df_dem.merge(df_mat, on=["Material", "Unidad"], how="left")
    df = df.merge(df_cli, on="Cliente", how="left")

    # 4) Decidir centro por costes (respetando exclusividades)
    col_excl_dg = next((c for c in df.columns if str(c).strip().lower() in ["exclusico dg","exclusivo dg"]), None)
    col_excl_mch = next((c for c in df.columns if str(c).strip().lower() in ["exclusivo mch","exclusivo mch."]), None)

    COL_COST_DG = next((c for c in df.columns if "coste" in str(c).lower() and "env" in str(c).lower() and "dg" in str(c).lower()), "Coste del envío DG")
    COL_COST_MCH = next((c for c in df.columns if "coste" in str(c).lower() and "env" in str(c).lower() and "mch" in str(c).lower()), "Coste del envío MCH")
    COL_CU_DG = next((c for c in df.columns if "coste unit" in str(c).lower() and "dg" in str(c).lower()), "Coste unitario DG")
    COL_CU_MCH = next((c for c in df.columns if "coste unit" in str(c).lower() and "mch" in str(c).lower()), "Coste unitario MCH")

    def decidir_centro(r):
        if col_excl_dg and str(r.get(col_excl_dg, "")).strip().upper() == "X":
            return DG_code
        if col_excl_mch and str(r.get(col_excl_mch, "")).strip().upper() == "X":
            return MCH_code
        c1 = to_float_safe(r.get(COL_COST_DG, 0)) + to_float_safe(r.get("Cantidad", 0)) * to_float_safe(r.get(COL_CU_DG, 0))
        c2 = to_float_safe(r.get(COL_COST_MCH, 0)) + to_float_safe(r.get("Cantidad", 0)) * to_float_safe(r.get(COL_CU_MCH, 0))
        return DG_code if c1 < c2 else MCH_code

    df["Centro_Base"] = df.apply(decidir_centro, axis=1)

    # 5) Agrupar para Modo C
    g = df.groupby(
        ["Material", "Unidad", "Centro_Base", "Fecha de necesidad", "Semana_Label"], dropna=False
    ).agg({
        "Cantidad": "sum",
        "Tamaño lote mínimo": "first",
        "Tamaño lote máximo": "first"
    }).reset_index()

    g = g.rename(columns={
        "Centro_Base": "Centro",
        "Fecha de necesidad": "Fecha",
        "Semana_Label": "Semana"
    })
    g["Centro"] = g["Centro"].apply(norm_code)
    g["Lote_min"] = g["Tamaño lote mínimo"]
    g["Lote_max"] = g["Tamaño lote máximo"]

    # 6) PRIMER MODO C
    df_c = modo_C(
        df_agrupado=g[["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]],
        df_mat=df_mat,
        capacidades=capacidades,
        DG_code=DG_code, MCH_code=MCH_code
    )

    # 7) Calcular Horas (para métricas y gráfico)
    tiempos = df_mat[["Material","Unidad","Tiempo fabricación unidad DG","Tiempo fabricación unidad MCH"]].drop_duplicates()
    df_c = df_c.merge(tiempos, on=["Material","Unidad"], how="left")
    df_c["Horas"] = np.where(
        df_c["Centro"].astype(str) == str(DG_code),
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad DG"],
        df_c["Cantidad a fabricar"] * df_c["Tiempo fabricación unidad MCH"]
    )

    return df_c, capacidades, DG_code, MCH_code

def replanificar_con_porcentajes(df_base, df_mat, capacidades, DG_code, MCH_code, ajustes):
    """
    A partir del resultado base (df_base con Horas y Semana),
    reparte por semana según 'ajustes' y re-ejecuta Modo C.
    """
    # 1) Reparto por semana (en HORAS)
    df_repartido = []
    for sem in sorted(df_base["Semana"].dropna().unique().tolist()):
        df_sem = df_base[df_base["Semana"] == sem].copy()
        if df_sem.empty:
            continue
        pct = ajustes.get(sem, 50)
        df_sem = repartir_porcentaje(df_sem, pct, DG_code, MCH_code)
        df_repartido.append(df_sem)

    df_adj = pd.concat(df_repartido, ignore_index=True) if df_repartido else df_base.copy()

    # 2) Re‑Modo C
    df_adj_pre = df_adj.rename(columns={"Cantidad a fabricar":"Cantidad"})[
        ["Material","Unidad","Centro","Cantidad","Fecha","Semana","Lote_min","Lote_max"]
    ]
    df_final = modo_C(df_adj_pre, df_mat, capacidades, DG_code, MCH_code)

    # 3) Recalcular Horas
    tiempos = df_mat[["Material","Unidad","Tiempo fabricación unidad DG","Tiempo fabricación unidad MCH"]].drop_duplicates()
    df_final = df_final.merge(tiempos, on=["Material","Unidad"], how="left")
    df_final["Horas"] = np.where(
        df_final["Centro"].astype(str) == str(DG_code),
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad DG"],
        df_final["Cantidad a fabricar"] * df_final["Tiempo fabricación unidad MCH"]
    )

    return df_final

# ------------------------------------------------------------
# INTERFAZ
# ------------------------------------------------------------
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel. Primero ejecuta el cálculo inicial (Modo C). Después podrás **reajustar y re‑planificar por semana** con porcentajes.")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Cálculo y Reajuste"])

# =========================
# TAB 1 — CARGA
# =========================
with tab1:
    st.subheader("📁 Carga tus archivos Excel")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 🏭 Capacidad de planta")
        f1 = st.file_uploader("Subir Capacidad (Capacidad horas por Centro)", type=["xlsx"], key="u1", label_visibility="collapsed")
        if f1:
            try:
                df_cap = pd.read_excel(f1)
                st.session_state.df_cap = df_cap.copy()
                guardar_archivo(f1, "capacidad_planta")
                st.success("✅ Cargado")
                st.dataframe(df_cap, use_container_width=True, height=150)
                st.caption("Lee exactamente la columna **Capacidad horas** por **Centro** (ej.: 0833=40, 0184=20).")
            except Exception as e:
                st.error(f"Error al leer Capacidad: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📦 Maestro de materiales")
        f2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="u2", label_visibility="collapsed")
        if f2:
            try:
                df_mat = pd.read_excel(f2)
                st.session_state.df_mat = df_mat.copy()
                guardar_archivo(f2, "maestro_materiales")
                st.success("✅ Cargado")
                st.dataframe(df_mat, use_container_width=True, height=400)
            except Exception as e:
                st.error(f"Error al leer Materiales: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 👥 Maestro de clientes")
        f3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="u3", label_visibility="collapsed")
        if f3:
            try:
                df_cli = pd.read_excel(f3)
                st.session_state.df_cli = df_cli.copy()
                guardar_archivo(f3, "maestro_clientes")
                st.success("✅ Cargado")
                st.dataframe(df_cli, use_container_width=True, height=400)
            except Exception as e:
                st.error(f"Error al leer Clientes: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📈 Demanda")
        f4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="u4", label_visibility="collapsed")
        if f4:
            try:
                df_dem = pd.read_excel(f4)
                st.session_state.df_dem = df_dem.copy()
                guardar_archivo(f4, "demanda")
                st.success("✅ Cargado")
                st.dataframe(df_dem, use_container_width=True, height=400)
            except Exception as e:
                st.error(f"Error al leer Demanda: {e}")
        else:
            st.info("Esperando archivo…")
        st.markdown('</div>', unsafe_allow_html=True)

# =========================
# TAB 2 — EJECUCIÓN y REAJUSTE
# =========================
with tab2:
    # Recuperar de session_state si existen
    df_cap = st.session_state.get("df_cap", None)
    df_mat = st.session_state.get("df_mat", None)
    df_cli = st.session_state.get("df_cli", None)
    df_dem = st.session_state.get("df_dem", None)

    if any(x is None for x in [df_cap, df_mat, df_cli, df_dem]):
        st.warning("⚠️ Por favor, carga los 4 archivos en la pestaña anterior para habilitar el cálculo.")
        st.stop()

    # Limpieza de columnas
    for d in [df_cap, df_mat, df_cli, df_dem]:
        d.columns = d.columns.str.strip()

    st.subheader("🚀 Cálculo inicial (Modo C)")

    if st.button("Ejecutar cálculo inicial", use_container_width=True):
        with st.spinner("Calculando Modo C (inicial)…"):
            df_base, capacidades, DG, MCH = ejecutar_modoC_base(df_cap, df_mat, df_cli, df_dem)

        # Guardar en sesión para permitir el reajuste posterior
        st.session_state.calculo_realizado = True
        st.session_state.df_base = df_base
        st.session_state.capacidades = capacidades
        st.session_state.DG = DG
        st.session_state.MCH = MCH
        st.success("✅ Cálculo inicial completado.")

    # Mostrar resultados del cálculo inicial (si ya existe en sesión)
    if st.session_state.get("calculo_realizado", False):
        df_base = st.session_state.df_base
        capacidades = st.session_state.capacidades
        DG = st.session_state.DG
        MCH = st.session_state.MCH

        # Métricas básicas
        total_props = len(df_base)
        horas_por_centro = df_base.groupby("Centro")["Horas"].sum().to_dict()
        m = st.columns(3)
        m[0].metric("Total Propuestas (inicial)", f"{total_props:,}".replace(",", "."))
        m[1].metric(f"Horas totales {DG}", f"{horas_por_centro.get(DG, 0):,.1f}h".replace(",", "."))
        m[2].metric(f"Horas totales {MCH}", f"{horas_por_centro.get(MCH, 0):,.1f}h".replace(",", "."))

        st.markdown("---")
        st.subheader("📊 Único gráfico — Producción por centro (Horas)")

        # ==== GRÁFICO ÚNICO: solo 0184 vs 0833 (en HORAS) ====
        # Tomamos explícitamente los centros detectados DG (sufijo 833) y MCH (sufijo 184)
        resumen = pd.Series({
            str(MCH): float(horas_por_centro.get(MCH, 0.0)),
            str(DG): float(horas_por_centro.get(DG, 0.0))
        }, name="Horas").to_frame()
        st.bar_chart(resumen, use_container_width=True)

        st.caption("El gráfico muestra horas totales planificadas por centro (inicial).")

        st.markdown("---")
        st.subheader("📋 Detalle de la Propuesta (inicial)")
        cols_to_show = ["Nº de propuesta","Material","Centro","Clase de orden",
                        "Cantidad a fabricar","Unidad","Fecha","Semana",
                        "Lote_min","Lote_max"]
        cols_presentes = [c for c in cols_to_show if c in df_base.columns]
        st.dataframe(df_base[cols_presentes], use_container_width=True, height=420)

        output_path_base = os.path.join(UPLOAD_DIR, f"Propuesta_Inicial_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_base[cols_presentes].to_excel(output_path_base, index=False)
        with open(output_path_base, "rb") as f:
            st.download_button(
                "📥 Descargar Propuesta Inicial (Excel)",
                data=f,
                file_name=f"Propuesta_Inicial_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )

        st.markdown("---")
        st.subheader("🔁 ¿Quieres reajustar por semana y re‑planificar?")

        # Botón que habilita los sliders de porcentajes por semana
        if st.button("Reajustar y re‑planificar por semana", use_container_width=True):
            st.session_state.mostrar_reajuste = True

        if st.session_state.get("mostrar_reajuste", False):
            # Sliders por semana (a partir de df_base)
            lista_semanas = sorted(df_base["Semana"].dropna().unique())
            st.markdown("**Configura los porcentajes por semana (0% = MCH · 100% = DG)**")
            ajustes = {}
            cols_sliders = st.columns(4)
            for i, sem in enumerate(lista_semanas):
                with cols_sliders[i % 4]:
                    ajustes[sem] = st.slider(f"Sem {sem}", 0, 100, 50, key=f"slider_{sem}")

            st.info("Pulsa **Aplicar porcentajes** para re‑planificar (Re‑Modo C).")
            if st.button("Aplicar porcentajes y re‑planificar", use_container_width=True):
                with st.spinner("Aplicando reparto y re‑planificando…"):
                    df_final = replanificar_con_porcentajes(
                        df_base=st.session_state.df_base,
                        df_mat=st.session_state.df_mat,
                        capacidades=st.session_state.capacidades,
                        DG_code=st.session_state.DG,
                        MCH_code=st.session_state.MCH,
                        ajustes=ajustes
                    )

                st.session_state.df_final_reajuste = df_final
                st.success("✅ Re‑planificación completada.")

        # Mostrar resultados del reajuste si existen
        if st.session_state.get("df_final_reajuste", None) is not None:
            df_final = st.session_state.df_final_reajuste

            # Métricas actualizadas
            st.markdown("---")
            st.subheader("📈 Resultados tras Re‑planificación")
            horas_por_centro_final = df_final.groupby("Centro")["Horas"].sum().to_dict()
            m2 = st.columns(3)
            m2[0].metric("Total Propuestas (reajuste)", f"{len(df_final):,}".replace(",", "."))
            m2[1].metric(f"Horas totales {DG}", f"{horas_por_centro_final.get(DG, 0):,.1f}h".replace(",", "."))
            m2[2].metric(f"Horas totales {MCH}", f"{horas_por_centro_final.get(MCH, 0):,.1f}h".replace(",", "."))

            # Gráfico único actualizado
            st.markdown("**Gráfico (actualizado)** — Producción por centro (Horas):")
            resumen_final = pd.Series({
                str(MCH): float(horas_por_centro_final.get(MCH, 0.0)),
                str(DG): float(horas_por_centro_final.get(DG, 0.0))
            }, name="Horas").to_frame()
            st.bar_chart(resumen_final, use_container_width=True)

            st.subheader("📋 Detalle de la Propuesta (reajustada)")
            cols_to_show = ["Nº de propuesta","Material","Centro","Clase de orden",
                            "Cantidad a fabricar","Unidad","Fecha","Semana",
                            "Lote_min","Lote_max"]
            cols_presentes = [c for c in cols_to_show if c in df_final.columns]
            st.dataframe(df_final[cols_presentes], use_container_width=True, height=420)

            output_path_final = os.path.join(UPLOAD_DIR, f"Propuesta_Replan_{datetime.now().strftime('%Y%m%d')}.xlsx")
            df_final[cols_presentes].to_excel(output_path_final, index=False)
            with open(output_path_final, "rb") as f:
                st.download_button(
                    "📥 Descargar Propuesta Re‑planificada (Excel)",
                    data=f,
                    file_name=f"Propuesta_Replan_{datetime.now().strftime('%Y%m%d')}.xlsx"
                )

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>✨ <strong>Sistema de Cálculo de Fabricación</strong> — Flujo en 2 fases</p>
    <p>Modo C inicial → Reparto por semana → Re‑Modo C | Fechas dd.MM.yyyy | Capacidades desde “Capacidad horas”</p>
</div>
""", unsafe_allow_html=True)
