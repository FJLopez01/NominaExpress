"""
app.py — Interfaz web Streamlit.

Responsabilidad única: presentar datos y traducir eventos de UI
en llamadas a procesador.py. No contiene lógica de negocio.

Para ejecutar:
    streamlit run app.py
"""

import os
import time
import pandas as pd
from datetime import datetime

import streamlit as st

from config import XML_PATH, PDF_PATH, EXCEL_CORREOS, validar_entorno
from logger import ruta_log_actual
from procesador import (
    ResultadoNomina,
    EstadoNomina,
    leer_correos_excel,
    construir_indice_pdfs,
    ejecutar_procesamiento,
)

# ------------------------------------------------------------------
# Configuración de la página
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Nóminas Automático",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Estado de sesión
# ------------------------------------------------------------------
if "procesamiento_completado" not in st.session_state:
    st.session_state.procesamiento_completado = False
if "resultados" not in st.session_state:
    st.session_state.resultados: list[ResultadoNomina] = []
if "logs" not in st.session_state:
    st.session_state.logs: list[str] = []


# ------------------------------------------------------------------
# Helpers de UI
# ------------------------------------------------------------------

def contar_archivos() -> tuple[int, int]:
    xml_count = len([f for f in os.listdir(XML_PATH) if f.endswith(".xml")]) if XML_PATH.exists() else 0
    pdf_count = len([f for f in os.listdir(PDF_PATH) if f.endswith(".pdf")]) if PDF_PATH.exists() else 0
    return xml_count, pdf_count


def obtener_preview_correos():
    try:
        return pd.read_excel(EXCEL_CORREOS)
    except Exception:
        return None


def mostrar_logs(logs: list[str], cantidad: int = 10) -> None:
    for log in reversed(logs[-cantidad:]):
        if "✅" in log:
            st.success(log)
        elif "❌" in log:
            st.error(log)
        elif "⚠️" in log:
            st.warning(log)
        else:
            st.info(log)


def resultado_a_log(resultado: ResultadoNomina) -> str:
    """Convierte un ResultadoNomina en una línea de log para la UI."""
    iconos = {
        EstadoNomina.EXITOSO:               "✅",
        EstadoNomina.PDF_NO_ENCONTRADO:      "⚠️",
        EstadoNomina.CORREO_NO_ENCONTRADO:   "⚠️",
        EstadoNomina.ERROR_XML:              "❌",
        EstadoNomina.ERROR_RENAME:           "❌",
        EstadoNomina.ERROR_SMTP_AUTH:        "❌",
        EstadoNomina.ERROR_SMTP:             "❌",
        EstadoNomina.ERROR_ARCHIVO:          "❌",
        EstadoNomina.ERROR_VALIDACION:       "❌",
    }
    icono = iconos.get(resultado.estado, "ℹ️")
    return f"{icono} {resultado.mensaje}"


# ------------------------------------------------------------------
# Procesamiento — solo orquesta UI + llama a procesador.py
# ------------------------------------------------------------------

def procesar_nominas() -> None:
    st.session_state.logs = []
    st.session_state.resultados = []

    progress_bar = st.progress(0)
    status_text = st.empty()
    logs_container = st.empty()

    xml_files = [f for f in os.listdir(XML_PATH) if f.endswith(".xml")]
    total = len(xml_files)

    if total == 0:
        st.error("No se encontraron archivos XML para procesar.")
        return

    try:
        status_text.text("📧 Cargando base de correos...")
        correos_por_nombre = leer_correos_excel()
        st.session_state.logs.append(f"✅ {len(correos_por_nombre)} registros de correo cargados")

        status_text.text("📂 Indexando PDFs...")
        indice_pdfs = construir_indice_pdfs()
        st.session_state.logs.append(f"✅ {len(indice_pdfs)} PDFs indexados")

    except Exception as e:
        st.error(f"❌ Error al cargar datos iniciales: {e}")
        return

    # Callback de progreso: actualiza UI después de cada XML
    def on_progreso(procesados: int, total: int, resultado: ResultadoNomina) -> None:
        progress_bar.progress(procesados / total)
        status_text.text(f"📄 Procesando {resultado.xml_file} ({procesados}/{total})")
        st.session_state.logs.append(resultado_a_log(resultado))

        with logs_container.container():
            mostrar_logs(st.session_state.logs, cantidad=5)

        time.sleep(0.1)

    # Llamada a lógica pura — app.py no sabe cómo se procesan los XMLs
    resultados = ejecutar_procesamiento(correos_por_nombre, indice_pdfs, on_progreso)
    st.session_state.resultados = resultados

    # Detectar error fatal de autenticación
    if any(r.estado == EstadoNomina.ERROR_SMTP_AUTH for r in resultados):
        st.error(
            "🔐 Error de autenticación con Gmail. "
            "Verifica EMAIL_SENDER y EMAIL_PASSWORD en tu archivo .env"
        )
        return

    st.session_state.procesamiento_completado = True
    progress_bar.progress(1.0)
    status_text.text("🎉 Procesamiento completado")


# ------------------------------------------------------------------
# Interfaz principal
# ------------------------------------------------------------------

st.markdown('<h1 class="main-header">💼 Sistema de Nóminas Automático</h1>', unsafe_allow_html=True)

errores_config = validar_entorno()
xml_count, pdf_count = contar_archivos()

with st.sidebar:
    st.header("📊 Panel de Control")

    if errores_config:
        st.error("❌ Configuración incompleta")
        for error in errores_config:
            st.write(f"• {error}")
    else:
        st.success("✅ Configuración correcta")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("XMLs", xml_count)
    with col2:
        st.metric("PDFs", pdf_count)

    st.divider()

    st.subheader("📁 Rutas configuradas")
    st.write(f"**XML:** `{XML_PATH}`")
    st.write(f"**PDF:** `{PDF_PATH}`")
    st.write(f"**Correos:** `{EXCEL_CORREOS}`")

    st.divider()
    st.subheader("📋 Log del día")
    log_path = ruta_log_actual()
    if log_path.exists():
        st.success(f"✅ `{log_path.name}`")
    else:
        st.info("Se creará al iniciar el primer procesamiento.")

tab1, tab2, tab3, tab4 = st.tabs(["🏠 Inicio", "📧 Base de Correos", "🚀 Procesamiento", "📋 Resultados"])

with tab1:
    st.header("Bienvenido al Sistema de Nóminas")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**📄 Archivos XML**\n\nContienen los datos de CFDI de nómina")
    with col2:
        st.info("**📊 Base de Correos**\n\nRelación empleado-correo electrónico")
    with col3:
        st.info("**📁 Archivos PDF**\n\nRecibos de nómina en formato PDF")

    st.markdown("---")

    if not errores_config:
        st.success("🎯 **El sistema está listo para procesar nóminas**")
        st.write("1. Verifica la base de correos en la pestaña correspondiente")
        st.write("2. Ve a la pestaña 'Procesamiento' para iniciar")
        st.write("3. Revisa los resultados en la última pestaña")
    else:
        st.error("⚠️ **Hay problemas de configuración que deben resolverse**")

with tab2:
    st.header("📧 Base de Correos Electrónicos")

    df_correos = obtener_preview_correos()

    if df_correos is not None:
        st.success(f"✅ Archivo cargado correctamente — {len(df_correos)} registros")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total empleados", len(df_correos))
        with col2:
            correos_validos = df_correos["Correo"].notna().sum()
            st.metric("Correos válidos", correos_validos)
        with col3:
            st.metric("Correos faltantes", len(df_correos) - correos_validos)

        st.subheader("Vista previa de datos")
        st.dataframe(df_correos.head(10), use_container_width=True)

        busqueda = st.text_input("🔍 Buscar empleado por nombre")
        if busqueda:
            filtrado = df_correos[df_correos["Nombre"].str.contains(busqueda, case=False, na=False)]
            st.dataframe(filtrado, use_container_width=True)
    else:
        st.error("❌ No se pudo cargar el archivo de correos")

with tab3:
    st.header("🚀 Procesamiento de Nóminas")

    if errores_config:
        st.error("No se puede procesar debido a errores de configuración.")
    elif xml_count == 0:
        st.warning("No hay archivos XML para procesar.")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.info(f"📊 **Archivos listos:** {xml_count} XMLs · {pdf_count} PDFs")
        with col2:
            if st.button("🚀 Iniciar Procesamiento", type="primary", use_container_width=True):
                procesar_nominas()

        if st.session_state.logs:
            st.subheader("📝 Registro de Actividad")
            mostrar_logs(st.session_state.logs)

with tab4:
    st.header("📋 Resultados del Procesamiento")

    if st.session_state.procesamiento_completado and st.session_state.resultados:
        resultados = st.session_state.resultados
        total     = len(resultados)
        exitosos  = sum(1 for r in resultados if r.exitoso)
        errores   = total - exitosos

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total", total)
        with col2:
            st.metric("✅ Exitosos", exitosos)
        with col3:
            st.metric("❌ Con errores", errores)
        with col4:
            pct = (exitosos / total * 100) if total > 0 else 0
            st.metric("% Éxito", f"{pct:.1f}%")

        df_grafico = pd.DataFrame({
            "Estado": ["Exitosos", "Con Errores"],
            "Cantidad": [exitosos, errores],
        })
        st.subheader("📊 Distribución de Resultados")
        st.bar_chart(df_grafico.set_index("Estado"))

        # Tabla detallada de errores para facilitar corrección
        errores_detalle = [r for r in resultados if not r.exitoso]
        if errores_detalle:
            st.subheader("⚠️ Detalle de errores")
            df_errores = pd.DataFrame([
                {"Empleado": r.nombre or r.xml_file, "Estado": r.estado.name, "Mensaje": r.mensaje}
                for r in errores_detalle
            ])
            st.dataframe(df_errores, use_container_width=True)

        st.info(f"🕐 Procesamiento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if st.button("🔄 Nuevo Procesamiento", type="secondary"):
            st.session_state.procesamiento_completado = False
            st.session_state.resultados = []
            st.session_state.logs = []
            st.rerun()
    else:
        st.info("👆 Aún no se ha ejecutado ningún procesamiento. Ve a la pestaña 'Procesamiento' para comenzar.")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.8em;'>"
    "💼 Sistema de Nóminas Automático | Desarrollado con Streamlit"
    "</div>",
    unsafe_allow_html=True,
)