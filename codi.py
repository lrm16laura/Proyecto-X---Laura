# Hola
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

# Estilos CSS personalizados
st.markdown("""
    <style>
    /* Estilos generales */
    .main {
        padding-top: 2rem;
    }
    
    /* Títulos */
    h1 {
        color: #1f77b4;
        text-align: center;
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    
    h2 {
        color: #2c3e50;
        border-bottom: 3px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
    
    /* Contenedores de secciones */
    .section-container {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 1.5rem;
    }
    
    /* Botones */
    .stButton > button {
        width: 100%;
        padding: 12px;
        font-size: 1rem;
        font-weight: bold;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(31, 119, 180, 0.3);
    }
    
    /* Dataframe */
    .dataframe {
        border-radius: 8px;
    }
    
    /* Mensajes */
    .success {
        padding: 1rem;
        border-radius: 8px;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: #7f8c8d;
        font-size: 0.9rem;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #ecf0f1;
    }
    </style>
""", unsafe_allow_html=True)

# Crear carpeta para guardar archivos si no existe
UPLOAD_DIR = "archivos_cargados"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def guardar_archivo(archivo, nombre_seccion):
    """Guarda el archivo en la carpeta local"""
    if archivo is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{nombre_seccion}_{timestamp}.xlsx"
        ruta_archivo = os.path.join(UPLOAD_DIR, nombre_archivo)
        
        with open(ruta_archivo, "wb") as f:
            f.write(archivo.getbuffer())
        
        return ruta_archivo
    return None

def ejecutar_calculo(df_mat, df_cli, df_dem, df_cap):
    """
    Ejecuta el programa de cálculo de propuesta de fabricación
    """
    try:
        # ==========================================
        # VALIDACIONES DE SEGURIDAD
        # ==========================================
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.write("🔍 Iniciando validación de datos...")
        progress_bar.progress(10)
        
        errores_detectados = False

        # Limpieza de espacios en blanco en los nombres de las columnas
        for d in [df_mat, df_cli, df_dem, df_cap]:
            d.columns = d.columns.str.strip()

        # Definición de columnas obligatorias
        obligatorias = {
            "Maestro Materiales": ['Material', 'Unidad', 'Tiempo fabricación unidad DG', 'Tiempo fabricación unidad MCH', 'Coste unitario DG', 'Coste unitario MCH'],
            "Maestro Clientes": ['Cliente', 'Distáncia a DG', 'Distáncia a MCH', 'Coste del envío DG', 'Coste del envío MCH'],
            "Demanda": ['Material', 'Unidad', 'Cantidad', 'Fecha de necesidad', 'Cliente'],
            "Capacidad_Planta": ['Planta', 'Centro', 'Capacidad horas']
        }

        archivos = {
            "Maestro Materiales": df_mat, 
            "Maestro Clientes": df_cli, 
            "Demanda": df_dem, 
            "Capacidad_Planta": df_cap
        }

        status_text.write("🔍 Verificando columnas obligatorias...")
        progress_bar.progress(20)
        
        # Chequeo de nulos en columnas críticas
        for nombre, dataframe in archivos.items():
            cols_a_revisar = obligatorias[nombre]
            cols_existentes = [col for col in cols_a_revisar if col in dataframe.columns]
            if dataframe[cols_existentes].isnull().values.any():
                st.warning(f"⚠️ AVISO: Faltan datos obligatorios en '{nombre}'.")
                nulos = dataframe[cols_existentes].isnull().sum()
                st.write(nulos[nulos > 0])
                errores_detectados = True

        status_text.write("🔍 Validando unidades...")
        progress_bar.progress(30)
        
        # Validación de Unidades (Demanda vs Maestro)
        df_check_unidades = df_dem.merge(df_mat[['Material', 'Unidad']], on='Material', suffixes=('_dem', '_mat'))
        unidades_error = df_check_unidades[df_check_unidades['Unidad_dem'] != df_check_unidades['Unidad_mat']]
        if not unidades_error.empty:
            st.error(f"❌ ERROR: La Unidad en Demanda no coincide con el Maestro para: {unidades_error['Material'].unique()}")
            errores_detectados = True

        status_text.write("🔍 Verificando integridad de datos...")
        progress_bar.progress(40)
        
        # Chequeo de Integridad (Materiales y Clientes existentes)
        mat_demanda = set(df_dem['Material'].unique())
        mat_maestro = set(df_mat['Material'].unique())
        if not mat_demanda.issubset(mat_maestro):
            st.error(f"❌ ERROR: Materiales en Demanda que NO están en Maestro: {mat_demanda - mat_maestro}")
            errores_detectados = True

        cli_demanda = set(df_dem['Cliente'].unique())
        cli_maestro = set(df_cli['Cliente'].unique())
        if not cli_demanda.issubset(cli_maestro):
            st.error(f"❌ ERROR: Clientes en Demanda que NO están en Maestro: {cli_demanda - cli_maestro}")
            errores_detectados = True

        if errores_detectados:
            st.error("🛑 DETENIDO: Corrige los errores en los Excels antes de continuar.")
            progress_bar.progress(100)
            return None
        
        st.success("✅ Validación completada: Datos consistentes")
        progress_bar.progress(50)

        # ==========================================
        # PREPARACIÓN Y ASIGNACIÓN INICIAL
        # ==========================================
        status_text.write("⚙️ Preparando datos...")
        progress_bar.progress(60)
        
        df_mat[['% fijo DG', '% fijo MCH']] = df_mat[['% fijo DG', '% fijo MCH']].fillna(0)
        df_cli[['Exclusico DG', 'Exclusivo MCH']] = df_cli[['Exclusico DG', 'Exclusivo MCH']].fillna('')

        df = df_dem.merge(df_mat, on=['Material', 'Unidad'], how='left')
        df = df.merge(df_cli, on='Cliente', how='left')

        # Cálculos de costes para decisión
        df['C_DG'] = (df['Cantidad'] * df['Coste unitario DG']) + (df['Distáncia a DG'] * df['Coste del envío DG'] * df['Cantidad'])
        df['C_MCH'] = (df['Cantidad'] * df['Coste unitario MCH']) + (df['Distáncia a MCH'] * df['Coste del envío MCH'] * df['Cantidad'])

        # Asignación de planta
        def decidir_planta(r):
            if r['Exclusico DG'] == 'X': return 'España'
            if r['Exclusivo MCH'] == 'X': return 'Suiza'
            return 'España' if r['C_DG'] <= r['C_MCH'] else 'Suiza'

        df['Planta_Temp'] = df.apply(decidir_planta, axis=1)

        status_text.write("📦 Agrupando por lotes...")
        progress_bar.progress(70)
        
        # ==========================================
        # AGRUPACIÓN POR LOTE
        # ==========================================
        df_agrupado = df.groupby(['Material', 'Unidad', 'Planta_Temp', 'Fecha de necesidad']).agg({
            'Cantidad': 'sum',
            'Tamaño lote mínimo': 'first',
            'Tamaño lote máximo': 'first',
            'Tiempo fabricación unidad DG': 'first',
            'Tiempo fabricación unidad MCH': 'first'
        }).reset_index()

        centros_map = {
            'España': df_cap.loc[df_cap['Planta'] == 'DG', 'Centro'].values[0] if len(df_cap.loc[df_cap['Planta'] == 'DG']) > 0 else 'DG',
            'Suiza': df_cap.loc[df_cap['Planta'] == 'MCH', 'Centro'].values[0] if len(df_cap.loc[df_cap['Planta'] == 'MCH']) > 0 else 'MCH'
        }

        resultado_lotes = []
        cont_propuesta = 1

        for _, fila in df_agrupado.iterrows():
            cant_total = fila['Cantidad']
            lote_min = fila['Tamaño lote mínimo']
            lote_max = fila['Tamaño lote máximo']
            
            # Ajuste al Lote Mínimo
            if cant_total < lote_min:
                cant_total = lote_min
                
            # División por Lote Máximo
            num_ordenes = math.ceil(cant_total / lote_max)
            cant_por_orden = cant_total / num_ordenes

            for _ in range(num_ordenes):
                fecha_str = pd.to_datetime(fila['Fecha de necesidad']).strftime('%Y%m%d')
                
                resultado_lotes.append({
                    'Nº de propuesta': cont_propuesta,
                    'Material': fila['Material'],
                    'Centro': centros_map[fila['Planta_Temp']],
                    'Clase de orden': 'NORM',
                    'Cantidad a fabricar': round(cant_por_orden, 2),
                    'Unidad': fila['Unidad'],
                    'Fecha de fabricación': fecha_str
                })
                cont_propuesta += 1

        status_text.write("💾 Guardando resultados...")
        progress_bar.progress(90)
        
        # ==========================================
        # EXPORTACIÓN
        # ==========================================
        df_final = pd.DataFrame(resultado_lotes)
        ruta_salida = os.path.join(UPLOAD_DIR, f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        df_final.to_excel(ruta_salida, index=False)

        status_text.write("✅ ¡Cálculo completado!")
        progress_bar.progress(100)
        
        return df_final, ruta_salida

    except Exception as e:
        st.error(f"❌ Error durante el cálculo: {str(e)}")
        return None, None

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================

# Título principal
st.markdown("<h1>📊 Sistema de Cálculo de Fabricación</h1>", unsafe_allow_html=True)
st.markdown("Carga los 4 archivos Excel necesarios y ejecuta el cálculo de propuesta de fabricación")
st.markdown("---")

# Tabs para mejor organización
tab1, tab2 = st.tabs(["📥 Carga de Archivos", "⚙️ Ejecución"])

# ==========================================
# TAB 1: CARGA DE ARCHIVOS
# ==========================================
with tab1:
    st.subheader("📁 Carga tus archivos Excel")
    
    col1, col2 = st.columns(2)
    
    # BOTÓN 1: CAPACIDAD DE PLANTA
    with col1:
        with st.container():
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown("### 🏭 Capacidad de planta")
            file1 = st.file_uploader("", type=["xlsx", "xls"], key="file1", label_visibility="collapsed")
            df_cap = None
            
            if file1 is not None:
                try:
                    df_cap = pd.read_excel(file1)
                    ruta = guardar_archivo(file1, "capacidad_planta")
                    st.success("✅ Archivo cargado correctamente")
                    st.dataframe(df_cap, use_container_width=True, height=200)
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
            else:
                st.info("Esperando archivo...")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # BOTÓN 2: MAESTRO DE MATERIALES
    with col2:
        with st.container():
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown("### 📦 Maestro de materiales")
            file2 = st.file_uploader("", type=["xlsx", "xls"], key="file2", label_visibility="collapsed")
            df_mat = None
            
            if file2 is not None:
                try:
                    df_mat = pd.read_excel(file2)
                    ruta = guardar_archivo(file2, "maestro_materiales")
                    st.success("✅ Archivo cargado correctamente")
                    st.dataframe(df_mat, use_container_width=True, height=200)
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
            else:
                st.info("Esperando archivo...")
            st.markdown('</div>', unsafe_allow_html=True)
    
    col3, col4 = st.columns(2)
    
    # BOTÓN 3: MAESTRO DE CLIENTES
    with col3:
        with st.container():
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown("### 👥 Maestro de clientes")
            file3 = st.file_uploader("", type=["xlsx", "xls"], key="file3", label_visibility="collapsed")
            df_cli = None
            
            if file3 is not None:
                try:
                    df_cli = pd.read_excel(file3)
                    ruta = guardar_archivo(file3, "maestro_clientes")
                    st.success("✅ Archivo cargado correctamente")
                    st.dataframe(df_cli, use_container_width=True, height=200)
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
            else:
                st.info("Esperando archivo...")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # BOTÓN 4: DEMANDA
    with col4:
        with st.container():
            st.markdown('<div class="section-container">', unsafe_allow_html=True)
            st.markdown("### 📈 Demanda")
            file4 = st.file_uploader("", type=["xlsx", "xls"], key="file4", label_visibility="collapsed")
            df_dem = None
            
            if file4 is not None:
                try:
                    df_dem = pd.read_excel(file4)
                    ruta = guardar_archivo(file4, "demanda")
                    st.success("✅ Archivo cargado correctamente")
                    st.dataframe(df_dem, use_container_width=True, height=200)
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
            else:
                st.info("Esperando archivo...")
            st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# TAB 2: EJECUCIÓN
# ==========================================
with tab2:
    st.subheader("⚙️ Ejecutar cálculo de fabricación")
    
    with st.container():
        st.markdown('<div class="section-container">', unsafe_allow_html=True)
        col_btn = st.columns([2, 1, 2])
        
        with col_btn[1]:
            if st.button("🚀 EJECUTAR CÁLCULO", key="btn_calcular", use_container_width=True):
                if df_cap is None or df_mat is None or df_cli is None or df_dem is None:
                    st.error("❌ Por favor, carga todos los 4 archivos Excel antes de ejecutar el cálculo.")
                else:
                    st.markdown("---")
                    df_resultado, ruta_salida = ejecutar_calculo(df_mat, df_cli, df_dem, df_cap)
                    
                    if df_resultado is not None:
                        st.markdown("---")
                        st.subheader("📋 Resultado de la Propuesta de Fabricación")
                        
                        # Métricas
                        col_metrics = st.columns(4)
                        col_metrics[0].metric("📦 Total de Propuestas", len(df_resultado))
                        col_metrics[1].metric("🏭 Centros utilizados", df_resultado['Centro'].nunique())
                        col_metrics[2].metric("📊 Materiales distintos", df_resultado['Material'].nunique())
                        col_metrics[3].metric("📈 Cantidad total", f"{df_resultado['Cantidad a fabricar'].sum():.0f}")
                        
                        st.markdown("---")
                        st.dataframe(df_resultado, use_container_width=True)
                        
                        col_download = st.columns([1, 2, 1])
                        
                        with col_download[1]:
                            # Opción para descargar Excel
                            with open(ruta_salida, "rb") as f:
                                st.download_button(
                                    label="📥 Descargar Excel",
                                    data=f,
                                    file_name=f"Propuesta_Fabricacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )
        
        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>✨ <strong>Sistema de Cálculo de Fabricación</strong> - Versión 2.0</p>
    <p>Desarrollado con Streamlit | 2026</p>
</div>
""", unsafe_allow_html=True)
