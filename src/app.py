"""
app.py — Interfaz web Streamlit.

Responsabilidad única: presentar datos y traducir eventos de UI
en llamadas a procesador.py. No contiene lógica de negocio.

Para ejecutar:
    streamlit run src/app.py
"""

import os
import time
import pandas as pd
from datetime import datetime

import streamlit as st

from config import XML_PATH, PDF_PATH, EXCEL_CORREOS, validar_entorno
from database import inicializar_db, obtener_historial
from logger import ruta_log_actual
from procesador import (
    ResultadoNomina,
    EstadoNomina,
    leer_correos_excel,
    construir_indice_pdfs,
    ejecutar_procesamiento,
)

# ------------------------------------------------------------------
# Inicializar BD al arrancar (idempotente)
# ------------------------------------------------------------------
inicializar_db()

# ------------------------------------------------------------------
# Configuración de página
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Nóminas AGD Legal",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Fuente y paleta corporativa */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* Header principal */
    .main-header {
        font-size: 1.8rem;
        font-weight: 600;
        color: #1a1a2e;
        letter-spacing: -0.5px;
        margin-bottom: 0.25rem;
    }
    .main-subtitle {
        font-size: 0.9rem;
        color: #6b7280;
        margin-bottom: 2rem;
    }

    /* Tarjetas de métricas mejoradas */
    [data-testid="metric-container"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem 1.25rem;
    }
    [data-testid="metric-container"] label {
        color: #64748b !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.8rem !important;
        color: #1a1a2e !important;
        font-weight: 600 !important;
    }

    /* Tabla de resultados */
    .stDataFrame { border-radius: 8px; overflow: hidden; }

    /* Estado badges */
    .badge-exitoso  { background:#dcfce7; color:#166534; padding:2px 10px; border-radius:20px; font-size:0.8rem; font-weight:500; }
    .badge-ya-enviado { background:#dbeafe; color:#1e40af; padding:2px 10px; border-radius:20px; font-size:0.8rem; font-weight:500; }
    .badge-error    { background:#fee2e2; color:#991b1b; padding:2px 10px; border-radius:20px; font-size:0.8rem; font-weight:500; }
    .badge-warning  { background:#fef9c3; color:#854d0e; padding:2px 10px; border-radius:20px; font-size:0.8rem; font-weight:500; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #1a1a2e;
    }
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    section[data-testid="stSidebar"] .stMetric {
        background: rgba(255,255,255,0.05);
        border-radius: 8px;
        padding: 0.5rem;
    }
    section[data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.1);
    }

    /* Botón primario */
    .stButton > button[kind="primary"] {
        background: #1a1a2e;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        letter-spacing: 0.02em;
        transition: all 0.2s;
    }
    .stButton > button[kind="primary"]:hover {
        background: #2d2d4e;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(26,26,46,0.3);
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


def resultado_a_log(resultado: ResultadoNomina) -> str:
    iconos = {
        EstadoNomina.EXITOSO:              "✅",
        EstadoNomina.YA_ENVIADO:           "⏭️",
        EstadoNomina.PDF_NO_ENCONTRADO:    "⚠️",
        EstadoNomina.CORREO_NO_ENCONTRADO: "⚠️",
        EstadoNomina.ERROR_XML:            "❌",
        EstadoNomina.ERROR_RENAME:         "❌",
        EstadoNomina.ERROR_AUTH_GRAPH:     "🔐",
        EstadoNomina.ERROR_ENVIO:          "❌",
        EstadoNomina.ERROR_ARCHIVO:        "❌",
        EstadoNomina.ERROR_VALIDACION:     "❌",
    }
    return f"{iconos.get(resultado.estado, 'ℹ️')} {resultado.mensaje}"


def mostrar_logs(logs: list[str], cantidad: int = 10) -> None:
    for log_line in reversed(logs[-cantidad:]):
        if "✅" in log_line or "⏭️" in log_line:
            st.success(log_line)
        elif "❌" in log_line or "🔐" in log_line:
            st.error(log_line)
        elif "⚠️" in log_line:
            st.warning(log_line)
        else:
            st.info(log_line)


# ------------------------------------------------------------------
# Procesamiento
# ------------------------------------------------------------------

def procesar_nominas() -> None:
    st.session_state.logs = []
    st.session_state.resultados = []

    progress_bar = st.progress(0)
    status_text  = st.empty()
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

    def on_progreso(procesados: int, total: int, resultado: ResultadoNomina) -> None:
        progress_bar.progress(procesados / total)
        status_text.text(f"📄 Procesando {resultado.xml_file} ({procesados}/{total})")
        st.session_state.logs.append(resultado_a_log(resultado))
        with logs_container.container():
            mostrar_logs(st.session_state.logs, cantidad=5)
        time.sleep(0.05)

    resultados = ejecutar_procesamiento(correos_por_nombre, indice_pdfs, on_progreso)
    st.session_state.resultados = resultados

    if any(r.estado == EstadoNomina.ERROR_AUTH_GRAPH for r in resultados):
        st.error(
            "🔐 **Error de autenticación con Azure AD.**\n\n"
            "Verifica AZURE_TENANT_ID, AZURE_CLIENT_ID y AZURE_CLIENT_SECRET en tu archivo .env\n\n"
            "Consulta la guía en `docs/configurar_azure_ad.md`"
        )
        return

    st.session_state.procesamiento_completado = True
    progress_bar.progress(1.0)
    status_text.text("🎉 Procesamiento completado")


# ------------------------------------------------------------------
# Layout principal
# ------------------------------------------------------------------

# Sidebar
errores_config = validar_entorno()
xml_count, pdf_count = contar_archivos()

with st.sidebar:
    st.markdown("### 💼 Nóminas AGD Legal")
    st.markdown("---")

    if errores_config:
        st.error("❌ Configuración incompleta")
        for error in errores_config:
            st.caption(f"• {error}")
    else:
        st.success("✅ Sistema listo")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("XMLs", xml_count)
    with col2:
        st.metric("PDFs", pdf_count)

    st.markdown("---")
    st.caption("📁 **Rutas configuradas**")
    st.caption(f"XML: `{XML_PATH}`")
    st.caption(f"PDF: `{PDF_PATH}`")

    st.markdown("---")
    log_path = ruta_log_actual()
    if log_path.exists():
        st.caption(f"📋 Log activo: `{log_path.name}`")
    else:
        st.caption("📋 Log se creará al procesar")


# Header
st.markdown('<h1 class="main-header">💼 Sistema de Nóminas</h1>', unsafe_allow_html=True)
st.markdown('<p class="main-subtitle">AGD Legal · Procesamiento automático de recibos CFDI 4.0</p>', unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 Inicio", "📧 Correos", "🚀 Procesar", "📋 Resultados", "📊 Historial"
])

# ── Tab 1: Inicio ──────────────────────────────────────────────────
with tab1:
    if not errores_config:
        st.success("🎯 El sistema está configurado correctamente y listo para procesar.")
    else:
        st.error("⚠️ Hay problemas de configuración que deben resolverse antes de continuar.")
        for e in errores_config:
            st.write(f"• {e}")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**📄 Archivos XML**\n\nCFDI de nómina del SAT en formato 4.0")
    with col2:
        st.info("**📊 Base de Correos**\n\nExcel con Nombre y Correo de cada empleado")
    with col3:
        st.info("**📁 PDFs**\n\nRecibos vinculados por CURP al XML correspondiente")

    st.markdown("---")
    st.markdown("**Pasos para procesar una nómina:**")
    st.write("1. Coloca los XMLs en la carpeta configurada")
    st.write("2. Coloca los PDFs correspondientes en la carpeta de PDFs")
    st.write("3. Verifica la base de correos en la pestaña **Correos**")
    st.write("4. Ve a la pestaña **Procesar** y presiona el botón")
    st.write("5. Revisa los resultados y el historial")


# ── Tab 2: Correos ─────────────────────────────────────────────────
with tab2:
    st.header("📧 Base de Correos Electrónicos")
    df_correos = obtener_preview_correos()

    if df_correos is not None:
        st.success(f"✅ Archivo cargado — {len(df_correos)} registros")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total empleados", len(df_correos))
        with col2:
            correos_validos = df_correos.iloc[:, 1].notna().sum()
            st.metric("Correos válidos", correos_validos)
        with col3:
            st.metric("Faltantes", len(df_correos) - correos_validos)

        busqueda = st.text_input("🔍 Buscar empleado")
        if busqueda:
            col_nombre = df_correos.columns[0]
            filtrado = df_correos[
                df_correos[col_nombre].str.contains(busqueda, case=False, na=False)
            ]
            st.dataframe(filtrado, use_container_width=True)
        else:
            st.dataframe(df_correos.head(20), use_container_width=True)
    else:
        st.error("❌ No se pudo cargar el archivo de correos.")
        st.write(f"Ruta esperada: `{EXCEL_CORREOS}`")


# ── Tab 3: Procesamiento ───────────────────────────────────────────
with tab3:
    st.header("🚀 Procesamiento de Nóminas")

    if errores_config:
        st.error("No se puede procesar debido a errores de configuración.")
    elif xml_count == 0:
        st.warning("No hay archivos XML para procesar en la carpeta configurada.")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(
                f"**{xml_count} XMLs** listos para procesar · "
                f"**{pdf_count} PDFs** disponibles\n\n"
                "Los recibos ya enviados anteriormente se omitirán automáticamente."
            )
        with col2:
            if st.button("🚀 Iniciar", type="primary", use_container_width=True):
                procesar_nominas()

        if st.session_state.logs:
            st.subheader("📝 Actividad")
            mostrar_logs(st.session_state.logs)


# ── Tab 4: Resultados ──────────────────────────────────────────────
with tab4:
    st.header("📋 Resultados del Procesamiento")

    if st.session_state.procesamiento_completado and st.session_state.resultados:
        resultados = st.session_state.resultados
        total     = len(resultados)
        exitosos  = sum(1 for r in resultados if r.estado == EstadoNomina.EXITOSO)
        omitidos  = sum(1 for r in resultados if r.estado == EstadoNomina.YA_ENVIADO)
        errores   = sum(1 for r in resultados if not r.exitoso)

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total XMLs", total)
        with col2:
            st.metric("✅ Enviados", exitosos)
        with col3:
            st.metric("⏭️ Ya enviados", omitidos)
        with col4:
            st.metric("❌ Errores", errores)
        with col5:
            pct = ((exitosos + omitidos) / total * 100) if total > 0 else 0
            st.metric("% Procesado", f"{pct:.1f}%")

        # Gráfico
        df_grafico = pd.DataFrame({
            "Estado": ["Enviados", "Ya enviados", "Errores"],
            "Cantidad": [exitosos, omitidos, errores],
        })
        st.bar_chart(df_grafico.set_index("Estado"))

        # Tabla de errores
        errores_detalle = [r for r in resultados if not r.exitoso]
        if errores_detalle:
            st.subheader("⚠️ Detalle de errores")
            df_errores = pd.DataFrame([
                {
                    "Empleado": r.nombre or r.xml_file,
                    "Estado": r.estado.name,
                    "Mensaje": r.mensaje,
                }
                for r in errores_detalle
            ])
            st.dataframe(df_errores, use_container_width=True)

        st.caption(f"Procesado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if st.button("🔄 Nuevo procesamiento", type="secondary"):
            st.session_state.procesamiento_completado = False
            st.session_state.resultados = []
            st.session_state.logs = []
            st.rerun()
    else:
        st.info("Aún no se ha ejecutado ningún procesamiento. Ve a la pestaña **Procesar** para comenzar.")


# ── Tab 5: Historial ───────────────────────────────────────────────
with tab5:
    st.header("📊 Historial de Envíos")
    st.caption("Todos los correos enviados exitosamente, persistidos en base de datos.")

    historial = obtener_historial(limite=500)

    if not historial:
        st.info("Aún no hay envíos registrados. El historial aparecerá aquí después del primer procesamiento exitoso.")
    else:
        # Métricas del historial
        df_hist = pd.DataFrame(historial)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total enviados (histórico)", len(df_hist))
        with col2:
            empleados_unicos = df_hist["num_empleado"].nunique()
            st.metric("Empleados distintos", empleados_unicos)
        with col3:
            ultimo = df_hist["fecha_envio"].max()[:10] if len(df_hist) > 0 else "—"
            st.metric("Último envío", ultimo)

        # Filtro por periodo
        periodos = sorted(df_hist["periodo_inicio"].dropna().unique(), reverse=True)
        if periodos:
            periodo_sel = st.selectbox("Filtrar por período de inicio:", ["Todos"] + list(periodos))
            if periodo_sel != "Todos":
                df_hist = df_hist[df_hist["periodo_inicio"] == periodo_sel]

        # Búsqueda por nombre
        busqueda_hist = st.text_input("🔍 Buscar por nombre")
        if busqueda_hist:
            df_hist = df_hist[
                df_hist["nombre"].str.contains(busqueda_hist, case=False, na=False)
            ]

        # Columnas legibles
        columnas_mostrar = {
            "nombre": "Empleado",
            "num_empleado": "# Emp",
            "correo": "Correo",
            "periodo_inicio": "Período inicio",
            "periodo_fin": "Período fin",
            "total": "Total",
            "fecha_envio": "Fecha envío",
        }
        df_display = df_hist[list(columnas_mostrar.keys())].rename(columns=columnas_mostrar)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # Exportar a Excel
        if st.button("⬇️ Exportar historial a Excel"):
            excel_bytes = df_display.to_excel(index=False, engine="openpyxl")
            st.download_button(
                label="Descargar historial.xlsx",
                data=df_display.to_csv(index=False).encode("utf-8"),
                file_name=f"historial_nominas_{datetime.now():%Y%m%d}.csv",
                mime="text/csv",
            )

st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#9ca3af; font-size:0.78rem;'>"
    "💼 Sistema de Nóminas AGD Legal · CFDI 4.0"
    "</div>",
    unsafe_allow_html=True,
)