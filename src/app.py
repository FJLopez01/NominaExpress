import streamlit as st
import os
import pandas as pd
from datetime import datetime
import xml.etree.ElementTree as ET
from pathlib import Path
import time

# Importar módulos existentes
from config import XML_PATH, PDF_PATH, EXCEL_CORREOS
from procesador import leer_correos_excel, extraer_datos_xml, buscar_pdf_por_curp
from utilidades import limpiar_nombre, normalizar_nombre_para_busqueda
from correo import enviar_correo

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Nóminas Automático",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar estado de la sesión
if 'procesamiento_completado' not in st.session_state:
    st.session_state.procesamiento_completado = False
if 'resultados' not in st.session_state:
    st.session_state.resultados = []
if 'logs' not in st.session_state:
    st.session_state.logs = []

def verificar_configuracion():
    """Verifica que todos los directorios y archivos necesarios existan"""
    errores = []
    
    if not os.path.exists(XML_PATH):
        errores.append(f"Directorio XML no existe: {XML_PATH}")
    if not os.path.exists(PDF_PATH):
        errores.append(f"Directorio PDF no existe: {PDF_PATH}")
    if not os.path.exists(EXCEL_CORREOS):
        errores.append(f"Archivo de correos no existe: {EXCEL_CORREOS}")
    
    return errores

def contar_archivos():
    """Cuenta los archivos XML y PDF disponibles"""
    xml_count = len([f for f in os.listdir(XML_PATH) if f.endswith('.xml')]) if os.path.exists(XML_PATH) else 0
    pdf_count = len([f for f in os.listdir(PDF_PATH) if f.endswith('.pdf')]) if os.path.exists(PDF_PATH) else 0
    return xml_count, pdf_count

def obtener_preview_correos():
    """Obtiene una vista previa de los correos cargados"""
    try:
        df = pd.read_excel(EXCEL_CORREOS)
        return df
    except Exception as e:
        return None

def procesar_nominas():
    """Función principal de procesamiento"""
    st.session_state.logs = []
    st.session_state.resultados = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    logs_container = st.empty()
    
    try:
        # Cargar correos
        status_text.text("📧 Cargando base de correos...")
        correos_por_nombre = leer_correos_excel()
        st.session_state.logs.append("✅ Base de correos cargada correctamente")
        
        # Obtener lista de XMLs
        xml_files = [f for f in os.listdir(XML_PATH) if f.endswith('.xml')]
        total_files = len(xml_files)
        
        if total_files == 0:
            st.error("No se encontraron archivos XML para procesar")
            return
        
        procesados = 0
        exitosos = 0
        errores = 0
        
        for i, xml_file in enumerate(xml_files):
            # Actualizar progress bar
            progress = (i + 1) / total_files
            progress_bar.progress(progress)
            status_text.text(f"📄 Procesando {xml_file} ({i+1}/{total_files})")
            
            xml_path = os.path.join(XML_PATH, xml_file)
            
            # Extraer datos del XML
            nombre, curp = extraer_datos_xml(xml_path)
            
            if not nombre or not curp:
                error_msg = f"❌ Error al extraer datos de {xml_file}"
                st.session_state.logs.append(error_msg)
                errores += 1
                continue
            
            nombre_limpio = limpiar_nombre(nombre)
            
            # Buscar PDF correspondiente
            pdf_path, original_pdf = buscar_pdf_por_curp(curp)
            
            if not pdf_path:
                error_msg = f"⚠️ PDF no encontrado para {nombre} (CURP: {curp})"
                st.session_state.logs.append(error_msg)
                errores += 1
                continue
            
            # Renombrar PDF si es necesario
            nuevo_nombre = f"{nombre_limpio}-{curp}.pdf"
            nuevo_path = os.path.join(PDF_PATH, nuevo_nombre)
            
            if not os.path.exists(nuevo_path):
                os.rename(pdf_path, nuevo_path)
                st.session_state.logs.append(f"📄 Renombrado: {original_pdf} -> {nuevo_nombre}")
            
            # Buscar correo electrónico
            clave = normalizar_nombre_para_busqueda(nombre)
            correo = correos_por_nombre.get(clave)
            
            if not correo:
                error_msg = f"⚠️ Correo no encontrado para: {nombre}"
                st.session_state.logs.append(error_msg)
                errores += 1
                continue
            
            # Enviar correo
            asunto = f"Recibo de Nómina - {nombre}"
            cuerpo = f"""Estimado(a) {nombre},

Por medio del presente reciba un cordial saludo y al mismo tiempo enviamos en archivo adjunto el CFDI con el formato electrónico XML(s) de las remuneraciones cubiertas en el período indicado en el título del correo.

Saludos cordiales."""
            
            try:
                enviar_correo(correo, asunto, cuerpo, [xml_path, nuevo_path])
                success_msg = f"✅ Correo enviado a {nombre} ({correo})"
                st.session_state.logs.append(success_msg)
                exitosos += 1
            except Exception as e:
                error_msg = f"❌ Error al enviar correo a {nombre}: {str(e)}"
                st.session_state.logs.append(error_msg)
                errores += 1
            
            procesados += 1
            
            # Actualizar logs en tiempo real
            with logs_container.container():
                for log in st.session_state.logs[-5:]:  # Mostrar últimos 5 logs
                    if "✅" in log:
                        st.success(log)
                    elif "❌" in log:
                        st.error(log)
                    elif "⚠️" in log:
                        st.warning(log)
                    else:
                        st.info(log)
            
            # Pequeña pausa para ver el progreso
            time.sleep(0.1)
        
        # Resultados finales
        st.session_state.resultados = {
            'total': total_files,
            'procesados': procesados,
            'exitosos': exitosos,
            'errores': errores,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        st.session_state.procesamiento_completado = True
        progress_bar.progress(1.0)
        status_text.text("🎉 Procesamiento completado")
        
    except Exception as e:
        st.error(f"Error durante el procesamiento: {str(e)}")

# INTERFAZ PRINCIPAL
st.markdown('<h1 class="main-header">💼 Sistema de Nóminas Automático</h1>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("📊 Panel de Control")
    
    # Verificación de configuración
    errores_config = verificar_configuracion()
    
    if errores_config:
        st.error("❌ Configuración incompleta")
        for error in errores_config:
            st.write(f"• {error}")
    else:
        st.success("✅ Configuración correcta")
    
    st.divider()
    
    # Contadores de archivos
    xml_count, pdf_count = contar_archivos()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("XMLs", xml_count)
    with col2:
        st.metric("PDFs", pdf_count)
    
    st.divider()
    
    # Configuración actual
    st.subheader("📁 Rutas configuradas")
    st.write(f"**XML:** `{XML_PATH}`")
    st.write(f"**PDF:** `{PDF_PATH}`")
    st.write(f"**Correos:** `{EXCEL_CORREOS}`")

# Contenido principal
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
        st.success(f"✅ Archivo cargado correctamente - {len(df_correos)} registros")
        
        # Mostrar estadísticas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total empleados", len(df_correos))
        with col2:
            correos_validos = df_correos['Correo'].notna().sum()
            st.metric("Correos válidos", correos_validos)
        with col3:
            correos_faltantes = len(df_correos) - correos_validos
            st.metric("Correos faltantes", correos_faltantes)
        
        # Vista previa de datos
        st.subheader("Vista previa de datos")
        st.dataframe(df_correos.head(10), use_container_width=True)
        
        # Filtro de búsqueda
        if len(df_correos) > 0:
            busqueda = st.text_input("🔍 Buscar empleado por nombre")
            if busqueda:
                filtrado = df_correos[df_correos['Nombre'].str.contains(busqueda, case=False, na=False)]
                st.dataframe(filtrado, use_container_width=True)
    else:
        st.error("❌ No se pudo cargar el archivo de correos")

with tab3:
    st.header("🚀 Procesamiento de Nóminas")
    
    if errores_config:
        st.error("No se puede procesar debido a errores de configuración")
    elif xml_count == 0:
        st.warning("No hay archivos XML para procesar")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.info(f"📊 **Archivos listos para procesar:** {xml_count} XMLs y {pdf_count} PDFs")
            
        with col2:
            if st.button("🚀 Iniciar Procesamiento", type="primary", width='stretch'):
                procesar_nominas()
        
        # Mostrar logs en tiempo real si hay procesamiento activo
        if st.session_state.logs:
            st.subheader("📝 Registro de Actividad")
            
            # Crear contenedor scrollable para logs
            with st.container():
                for log in reversed(st.session_state.logs[-10:]):  # Últimos 10 logs
                    if "✅" in log:
                        st.success(log)
                    elif "❌" in log:
                        st.error(log)
                    elif "⚠️" in log:
                        st.warning(log)
                    else:
                        st.info(log)

with tab4:
    st.header("📋 Resultados del Procesamiento")
    
    if st.session_state.procesamiento_completado and st.session_state.resultados:
        resultados = st.session_state.resultados
        
        # Métricas de resumen
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Procesados", resultados['total'])
        with col2:
            st.metric("Exitosos", resultados['exitosos'], delta=resultados['exitosos'])
        with col3:
            st.metric("Con Errores", resultados['errores'], delta=resultados['errores'])
        with col4:
            porcentaje_exito = (resultados['exitosos'] / resultados['total'] * 100) if resultados['total'] > 0 else 0
            st.metric("% Éxito", f"{porcentaje_exito:.1f}%")
        
        # Gráfico de resultados
        if resultados['total'] > 0:
            df_grafico = pd.DataFrame({
                'Estado': ['Exitosos', 'Con Errores'],
                'Cantidad': [resultados['exitosos'], resultados['errores']]
            })
            
            st.subheader("📊 Distribución de Resultados")
            st.bar_chart(df_grafico.set_index('Estado'))
        
        # Timestamp
        st.info(f"🕐 Último procesamiento: {resultados['timestamp']}")
        
        # Botón para nuevo procesamiento
        if st.button("🔄 Nuevo Procesamiento", type="secondary"):
            st.session_state.procesamiento_completado = False
            st.session_state.resultados = []
            st.session_state.logs = []
            st.rerun()
    else:
        st.info("👆 Aún no se ha ejecutado ningún procesamiento. Ve a la pestaña 'Procesamiento' para comenzar.")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.8em;'>"
    "💼 Sistema de Nóminas Automático | Desarrollado con Streamlit"
    "</div>", 
    unsafe_allow_html=True
)
