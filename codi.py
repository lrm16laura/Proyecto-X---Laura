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
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_seccion}_{timestamp}.xlsx"
        ruta_archivo = os.path.join(UPLOAD_DIR, nombre_archivo)
        with open(ruta_archivo, "wb") as f:
            f.write(archivo.getbuffer())
        return ruta_archivo
    return None


def procesar_logica_estable(df_dem, df_mat, df_cli, df_cap, ajustes_semanales):
    lista_centros_disponibles = df_cap['Centro'].unique().tolist()
    C1 = str(lista_centros_disponibles[0])
    C2 = str(lista_centros_disponibles[1]) if len(lista_centros_disponibles) > 1 else C1

    PRECIO_KM = 0.15

    df_dem['Fecha_DT'] = pd.to_datetime(df_dem['Fecha de necesidad'])
    df_dem['Semana_Label'] = df_dem['Fecha_DT'].dt.strftime('%Y-W%U')

    df = df_dem.merge(df_mat, on=['Material', 'Unidad'], how='left')
    df = df.merge(df_cli, on='Cliente', how='left')

    cols_lower = {c.lower(): c for c in df.columns}

    def pick(options):
        for opt in options:
            if opt.lower() in cols_lower:
                return cols_lower[opt.lower()]
        return None

    col_dist_c1 = pick(["Distancia a DG", "Distáncia a DG"])
    col_dist_c2 = pick(["Distancia a MCH", "Distáncia a MCH"])
    col_costkm_c1 = pick(["Coste del envío DG", "Coste envio DG", "Precio KM DG"])
    col_costkm_c2 = pick(["Coste del envío MCH", "Coste envio MCH", "Precio KM MCH"])

    def decidir_centro(r):
        if str(r.get('Exclusico DG', r.get('Exclusivo DG', ''))).strip().upper() == 'X':
            return C1
        if str(r.get('Exclusivo MCH', '')).strip().upper() == 'X':
            return C2

        dist1 = float(r.get(col_dist_c1, 0) or 0)
        dist2 = float(r.get(col_dist_c2, 0) or 0)
        precio1 = float(r.get(col_costkm_c1, PRECIO_KM) or PRECIO_KM)
        precio2 = float(r.get(col_costkm_c2, PRECIO_KM) or PRECIO_KM)

        cf1 = float(r.get('Coste fabricacion unidad DG', 0) or 0)
        cf2 = float(r.get('Coste fabricacion unidad MCH', 0) or 0)
        cant = float(r.get('Cantidad', 0) or 0)

        coste1 = dist1 * precio1 + cant * cf1
        coste2 = dist2 * precio2 + cant * cf2

        if coste1 < coste2:
            return C1
        elif coste2 < coste1:
            return C2

        rng = np.random.RandomState(r.name)
        umbral = ajustes_semanales.get(r['Semana_Label'], 50) / 100
        return C1 if rng.rand() < umbral else C2

    df['Centro_Final'] = df.apply(decidir_centro, axis=1)

    df_agrupado = df.groupby(
        ['Material', 'Unidad', 'Centro_Final', 'Fecha de necesidad', 'Semana_Label']
    ).agg({
        'Cantidad': 'sum',
        'Tamaño lote mínimo': 'first',
        'Tamaño lote máximo': 'first',
        'Tiempo fabricación unidad DG': 'first',
        'Tiempo fabricación unidad MCH': 'first'
    }).reset_index()

    # === CAPACIDAD DIARIA ===
    horas_col = None
    for c in df_cap.columns:
        if 'hora' in c.lower() or 'capacidad' in c.lower():
            horas_col = c
            break

    if horas_col:
        capacidad_base = df_cap.groupby('Centro')[horas_col].sum().to_dict()
    else:
        capacidad_base = {C1: float('inf'), C2: float('inf')}

    fechas = sorted(pd.to_datetime(df_agrupado['Fecha de necesidad']).dt.normalize().unique())
    capacidad_restante = {(c, f): capacidad_base[c] for c in capacidad_base for f in fechas}

    resultado_lotes = []
    cont = 1

    for _, fila in df_agrupado.iterrows():
        fecha = pd.to_datetime(fila['Fecha de necesidad']).normalize()
        semana = fila['Semana_Label']
        pref = fila['Centro_Final']

        cantidad = max(float(fila['Cantidad']), float(fila['Tamaño lote mínimo']))
        lote_max = float(fila['Tamaño lote máximo'])
        num_lotes = math.ceil(cantidad / lote_max)
        cantidad_lote = round(cantidad / num_lotes, 2)

        t_dg = float(fila['Tiempo fabricación unidad DG'])
        t_mch = float(fila['Tiempo fabricación unidad MCH'])

        def horas_lote(centro):
            return cantidad_lote * (t_dg if centro == C1 else t_mch)

        for _ in range(num_lotes):
            centro = pref
            h_pref = horas_lote(centro)

            if capacidad_restante[(centro, fecha)] >= h_pref:
                capacidad_restante[(centro, fecha)] -= h_pref
                sin_cap = False
            else:
                otro = C2 if centro == C1 else C1
                h_otro = horas_lote(otro)

                if capacidad_restante[(otro, fecha)] >= h_otro:
                    centro = otro
                    capacidad_restante[(otro, fecha)] -= h_otro
                    sin_cap = False
                else:
                    sin_cap = True

            tiempo = cantidad_lote * (t_dg if centro == C1 else t_mch)

            resultado_lotes.append({
                'Nº de propuesta': cont,
                'Material': fila['Material'],
                'Centro': centro,
                'Clase de orden': 'NORM',
                'Cantidad a fabricar': cantidad_lote,
                'Unidad': fila['Unidad'],
                'Fecha de fabricación': fecha.strftime('%Y%m%d'),
                'Semana': semana,
                'Horas': tiempo,
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

df_cap, df_mat, df_cli, df_dem = None, None, None, None


# --- TAB 1 ---
with tab1:
    st.subheader("📁 Carga tus archivos Excel")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 🏭 Capacidad de planta")
        file1 = st.file_uploader("Subir Capacidad", type=["xlsx"], key="u1", label_visibility="collapsed")
        if file1:
            df_cap = pd.read_excel(file1)
            guardar_archivo(file1, "capacidad_planta")
            st.success("✅ Cargado")
            st.dataframe(df_cap, use_container_width=True, height=150)
        else:
            st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📦 Maestro de materiales")
        file2 = st.file_uploader("Subir Materiales", type=["xlsx"], key="u2", label_visibility="collapsed")
        if file2:
            df_mat = pd.read_excel(file2)
            guardar_archivo(file2, "maestro_materiales")
            st.success("✅ Cargado")
            st.dataframe(df_mat, use_container_width=True, height=400)
        else:
            st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 👥 Maestro de clientes")
        file3 = st.file_uploader("Subir Clientes", type=["xlsx"], key="u3", label_visibility="collapsed")
        if file3:
            df_cli = pd.read_excel(file3)
            guardar_archivo(file3, "maestro_clientes")
            st.success("✅ Cargado")
            st.dataframe(df_cli, use_container_width=True, height=400)
        else:
            st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        st.markdown("### 📈 Demanda")
        file4 = st.file_uploader("Subir Demanda", type=["xlsx"], key="u4", label_visibility="collapsed")
        if file4:
            df_dem = pd.read_excel(file4)
            guardar_archivo(file4, "demanda")
            st.success("✅ Cargado")
            st.dataframe(df_dem, use_container_width=True, height=400)
        else:
            st.info("Esperando archivo...")
        st.markdown('</div>', unsafe_allow_html=True)


# --- TAB 2 ---
with tab2:
    if df_cap is None or df_mat is None or df_cli is None or df_dem is None:
        st.warning("⚠️ Por favor, carga los 4 archivos en la pestaña anterior para habilitar los ajustes.")
    else:
        for d in [df_cap, df_mat, df_cli, df_dem]:
            d.columns = d.columns.str.strip()
        
        centros_detectados = [str(c) for c in df_cap['Centro'].unique()]
        df_dem['Semana_Label'] = pd.to_datetime(df_dem['Fecha de necesidad']).dt.strftime('%Y-W%U')
        lista_semanas = sorted(df_dem['Semana_Label'].unique())

        st.subheader("⚙️ Configuración de Porcentajes por Semana")
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

            st.dataframe(df_res.drop(columns=['Horas']), use_container_width=True)

            output_path = os.path.join(UPLOAD_DIR, "Propuesta_Final.xlsx")
            df_res.drop(columns=['Semana', 'Horas']).to_excel(output_path, index=False)
            with open(output_path, "rb") as f:
                st.download_button("📥 Descargar Propuesta en Excel", data=f,
                                   file_name=f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d')}.xlsx")


# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>✨ <strong>Sistema de Cálculo de Fabricación</strong> - Versión 3.2 (Interfaz Unificada)</p>
    <p>Desarrollado con Streamlit | 2026</p>
</div>
""", unsafe_allow_html=True)
