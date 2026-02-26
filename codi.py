import streamlit as st
import pandas as pd
import numpy as np
import os
import math
from datetime import datetime

# Configuración de página
st.set_page_config(
    page_title="Sistema de Cálculo de Fabricación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# ESTILOS CSS PERSONALIZADOS (Programa 1 + 2)
# ==========================================
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
    </style>
""", unsafe_allow_html=True)

# Crear carpeta para guardar archivos si no existe
UPLOAD_DIR = "archivos_cargados"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# ==========================================
# FUNCIONES AUXILIARES Y LÓGICA (Programa 2)
# ==========================================

def guardar_archivo(archivo, nombre_seccion):
    """Guarda el archivo en la carpeta local (del Programa 1)"""
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_seccion}_{timestamp}.xlsx"
        ruta_archivo = os.path.join(UPLOAD_DIR, nombre_archivo)
        with open(ruta_archivo, "wb") as f:
            f.write(archivo.getbuffer())
        return ruta_archivo
    return None

def procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes_semanales):
    """Lógica optimizada del Programa 2 (coste correcto + capacidad DIARIA + fix KeyError)"""

    # --- Helper robusto para convertir a float (soporta "0,3") ---
    def to_float(x, default=0.0):
        if pd.isna(x):
            return default
        if isinstance(x, str):
            x = x.strip().replace(',', '.')
            if x == '':
                return default
        try:
            return float(x)
        except Exception:
            return default

    # --- Mapeo fiable de DG/MCH según códigos detectados ---
    centros = [str(c).strip() for c in df_cap['Centro'].astype(str).unique()]
    DG_CODE = next((c for c in centros if c.endswith('833')), (centros[0] if centros else '833'))
    MCH_CODE = next((c for c in centros if c.endswith('184') and c != DG_CODE),
                    (centros[1] if len(centros) > 1 else DG_CODE))

    C1, C2 = DG_CODE, MCH_CODE  # mantenemos la semántica original: C1=DG, C2=MCH

    # --- Preparación de fechas y semanas ---
    df_dem['Fecha_DT'] = pd.to_datetime(df_dem['Fecha de necesidad'])
    df_dem['Semana_Label'] = df_dem['Fecha_DT'].dt.strftime('%Y-W%U')

    # --- Merge de datos (mantiene tus claves) ---
    df = df_dem.merge(df_mat, on=['Material', 'Unidad'], how='left')
    df = df.merge(df_cli, on='Cliente', how='left')

    # --- Nombres EXACTOS de tus columnas (según capturas) ---
    COL_DIST_DG  = "Distáncia a DG"
    COL_DIST_MCH = "Distáncia a MCH"
    COL_COST_DG  = "Coste del envío DG"
    COL_COST_MCH = "Coste del envío MCH"
    COL_CF_DG    = "Coste unitario DG"
    COL_CF_MCH   = "Coste unitario MCH"

    # --- Fallback si faltaran columnas de coste de envío ---
    PRECIO_KM_FALLBACK = 0.15

    # --- Función de decisión del centro por menor coste real ---
    def decidir_centro(r):
        # Exclusividades (respeta tu Excel con "Exclusico")
        if str(r.get('Exclusico DG', '')).strip().upper() == 'X':
            return C1
        if str(r.get('Exclusivo MCH', '')).strip().upper() == 'X':
            return C2

        dist_dg  = to_float(r.get(COL_DIST_DG, 0))
        dist_mch = to_float(r.get(COL_DIST_MCH, 0))
        pkm_dg   = to_float(r.get(COL_COST_DG, PRECIO_KM_FALLBACK))
        pkm_mch  = to_float(r.get(COL_COST_MCH, PRECIO_KM_FALLBACK))

        cf_dg = to_float(r.get(COL_CF_DG, 0))
        cf_mch = to_float(r.get(COL_CF_MCH, 0))
        cantidad = to_float(r.get('Cantidad', 0))

        coste_dg  = dist_dg * pkm_dg   + cantidad * cf_dg
        coste_mch = dist_mch * pkm_mch + cantidad * cf_mch

        if coste_dg < coste_mch:
            return C1
        elif coste_mch < coste_dg:
            return C2
        else:
            # Empate técnico: usa % semanal
            rng = np.random.RandomState(r.name)
            umbral = ajustes_semanales.get(r['Semana_Label'], 50) / 100
            return C1 if rng.rand() < umbral else C2

    df['Centro_Final'] = df.apply(decidir_centro, axis=1)

    # --- Agrupación (manteniendo fecha para capacidad diaria) ---
    df_agrupado = df.groupby(['Material', 'Unidad', 'Centro_Final', 'Fecha de necesidad', 'Semana_Label']).agg({
        'Cantidad': 'sum',
        'Tamaño lote mínimo': 'first',
        'Tamaño lote máximo': 'first',
        'Tiempo fabricación unidad DG': 'first',
        'Tiempo fabricación unidad MCH': 'first'
    }).reset_index()

    # ============
    # CAPACIDAD DIARIA (no semanal) + fix KeyError
    # ============
    horas_col = None
    for c in df_cap.columns:
        if ('hora' in str(c).lower()) or ('capacidad' in str(c).lower()):
            horas_col = c
            break

    if horas_col:
        # Capacidad base por centro (horas diarias)
        base_cap_por_centro = df_cap.groupby('Centro')[horas_col].sum().to_dict()
        # Asegura que existan ambos centros en dict
        for k in [C1, C2]:
            if k not in base_cap_por_centro:
                base_cap_por_centro[k] = 0.0
    else:
        # Si no hay columna de horas/capacidad, capacidad infinita
        base_cap_por_centro = {C1: float('inf'), C2: float('inf')}

    fechas_demanda = sorted(pd.to_datetime(df_agrupado['Fecha de necesidad']).dt.normalize().unique().tolist())
    capacidad_restante = {(str(centro), fecha): float(base_cap_por_centro.get(str(centro), 0.0))
                          for centro in [C1, C2] for fecha in fechas_demanda}

    # ============================
    # Generación de órdenes/lotes
    # ============================
    resultado_lotes = []
    cont = 1
    for _, fila in df_agrupado.iterrows():
        fecha_dia = pd.to_datetime(fila['Fecha de necesidad']).normalize()
        semana = fila['Semana_Label']
        pref = str(fila['Centro_Final']).strip()

        cant_total = max(to_float(fila['Cantidad']), to_float(fila['Tamaño lote mínimo']))
        tam_lote_max = to_float(fila['Tamaño lote máximo'])
        num_ordenes = int(math.ceil(cant_total / tam_lote_max)) if tam_lote_max > 0 else 1
        cant_por_orden = round(cant_total / num_ordenes, 2)

        tf_dg  = to_float(fila['Tiempo fabricación unidad DG'])
        tf_mch = to_float(fila['Tiempo fabricación unidad MCH'])

        def horas_lote(centro, cantidad):
            return cantidad * (tf_dg if str(centro) == str(C1) else tf_mch)

        for _ in range(num_ordenes):
            centro_asignado = pref
            h_pref = horas_lote(centro_asignado, cant_por_orden)
            clave_pref = (str(centro_asignado), fecha_dia)

            if capacidad_restante.get(clave_pref, -1) >= h_pref:
                capacidad_restante[clave_pref] -= h_pref
                t_fab = tf_dg if str(centro_asignado) == str(C1) else tf_mch
                sin_cap = False
            else:
                otro = str(C2) if str(centro_asignado) == str(C1) else str(C1)
                h_otro = horas_lote(otro, cant_por_orden)
                clave_otro = (otro, fecha_dia)

                if capacidad_restante.get(clave_otro, -1) >= h_otro:
                    centro_asignado = otro
                    capacidad_restante[clave_otro] -= h_otro
                    t_fab = tf_dg if str(centro_asignado) == str(C1) else tf_mch
                    sin_cap = False
                else:
                    # Ninguno tiene capacidad ese día → se queda en preferido y marcamos
                    t_fab = tf_dg if str(centro_asignado) == str(C1) else tf_mch
                    sin_cap = True

            resultado_lotes.append({
                'Nº de propuesta': cont,
                'Material': fila['Material'],
                'Centro': str(centro_asignado),
                'Clase de orden': 'NORM',
                'Cantidad a fabricar': cant_por_orden,
                'Unidad': fila['Unidad'],
                'Fecha de fabricación': fecha_dia.strftime('%Y%m%d'),
                'Semana': semana,
                'Horas': cant_por_orden * t_fab,
                'Sin capacidad (informativo)': sin_cap
            })
            cont += 1

    return pd.DataFrame(resultado_lotes)

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel necesarios y ajusta los parámetros de ejecución.")
st.markdown("---")

tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Ajuste y Ejecución"])

# Variables de estado para los DataFrames
df_cap, df_mat, df_cli, df_dem = None, None, None, None

# --- TAB 1: CARGA DE ARCHIVOS (Diseño Programa 1) ---
with tab1:
    st.subheader("📁 Carga tus archivos Excel")
    
    col1, col2 = st.columns(2)
    
    # Bloque 1: Capacidad
    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 🏭 Capacidad de planta")
        file1 = st.file_uploader("Subir Capacidad", type=["xlsx"], key="u1", label_visibility="collapsed")
        if file1:
            try:
                df_cap = pd.read_excel(file1)
                guardar_archivo(file1, "capacidad_planta")
                st.success("✅ Cargado")
                st.dataframe(df_cap, use_container_width=True, height=150)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    # Bloque 2: Maestro Materiales
    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📦 Maestro de materiales")
        file2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="u2", label_visibility="collapsed")
        if file2:
            try:
                df_mat = pd.read_excel(file2)
                guardar_archivo(file2, "maestro_materiales")
                st.success("✅ Cargado")
                st.dataframe(df_mat, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    
    # Bloque 3: Maestro Clientes
    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 👥 Maestro de clientes")
        file3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="u3", label_visibility="collapsed")
        if file3:
            try:
                df_cli = pd.read_excel(file3)
                guardar_archivo(file3, "maestro_clientes")
                st.success("✅ Cargado")
                st.dataframe(df_cli, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    # Bloque 4: Demanda
    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📈 Demanda")
        file4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="u4", label_visibility="collapsed")
        if file4:
            try:
                df_dem = pd.read_excel(file4)
                guardar_archivo(file4, "demanda")
                st.success("✅ Cargado")
                st.dataframe(df_dem, use_container_width=True, height=400)
            except Exception as e: st.error(f"Error: {e}")
        else: st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: EJECUCIÓN (Lógica Programa 2) ---
with tab2:
    if df_cap is None or df_mat is None or df_cli is None or df_dem is None:
        st.warning("⚠️ Por favor, carga los 4 archivos en la pestaña anterior para habilitar los ajustes.")
    else:
        # Limpieza de columnas
        for d in [df_cap, df_mat, df_cli, df_dem]: d.columns = d.columns.str.strip()
        
        centros_detectados = [str(c) for c in df_cap['Centro'].astype(str).unique()]
        df_dem['Semana_Label'] = pd.to_datetime(df_dem['Fecha de necesidad']).dt.strftime('%Y-W%U')
        lista_semanas = sorted(df_dem['Semana_Label'].unique())

        st.subheader("⚙️ Configuración de Porcentajes por Semana")
        c1_name = centros_detectados[0]
        c2_name = centros_detectados[1] if len(centros_detectados) > 1 else "Centro 2"
        
        st.info(f"El sistema priorizará automáticamente el centro más barato. Usa los sliders para definir el reparto en caso de empate técnico entre **{c1_name}** y **{c2_name}**.")

        ajustes = {}
        cols_sliders = st.columns(4)
        for i, sem in enumerate(lista_semanas):
            with cols_sliders[i % 4]:
                ajustes[sem] = st.slider(f"Sem {sem}", 0, 100, 50)

        st.markdown("---")
        if st.button("🚀 EJECUTAR CÁLCULO DE PROPUESTA", use_container_width=True):
            with st.spinner("Calculando asignación óptima de costes..."):
                df_res = procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes)

                st.success("✅ Cálculo completado con éxito.")
                
                # Métricas
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Propuestas", len(df_res))
                for i, centro in enumerate(centros_detectados):
                    if i == 0:
                        m2.metric(f"Horas Totales {centro}", f"{df_res[df_res['Centro']==centro]['Horas'].sum():,.1f}h")
                    elif i == 1:
                        m3.metric(f"Horas Totales {centro}", f"{df_res[df_res['Centro']==centro]['Horas'].sum():,.1f}h")

                st.subheader("📊 Distribución de Carga Horaria")
                carga_plot = df_res.groupby(['Semana', 'Centro'])['Horas'].sum().unstack().fillna(0)
                st.bar_chart(carga_plot)

                st.subheader("📋 Detalle de la Propuesta")
                st.dataframe(df_res.drop(columns=['Horas']), use_container_width=True)

                # Exportación
                output_path = os.path.join(UPLOAD_DIR, "Propuesta_Final.xlsx")
                df_res.drop(columns=['Semana', 'Horas']).to_excel(output_path, index=False)
                with open(output_path, "rb") as f:
                    st.download_button("📥 Descargar Propuesta en Excel", data=f, file_name=f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d')}.xlsx")

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>✨ <strong>Sistema de Cálculo de Fabricación</strong> - Versión 3.2 (Interfaz Unificada)</p>
    <p>Desarrollado con Streamlit | 2026</p>
</div>
""", unsafe_allow_html=True)
