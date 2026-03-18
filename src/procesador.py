"""
procesador.py — Lógica de procesamiento de nóminas.

Responsabilidades:
- Leer y parsear el Excel de correos.
- Extraer datos de archivos XML (CFDI).
- Construir índice de PDFs por CURP (O(n) lectura única al inicio).
- Renombrar PDFs de forma segura (sin pérdida de datos ante crashes).
- Orquestar el procesamiento completo (sin dependencias de UI).
"""

import os
import re
import shutil
import smtplib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable

import pandas as pd
from PyPDF2 import PdfReader

from config import XML_PATH, PDF_PATH, EXCEL_CORREOS
from correo import enviar_correo
from logger import obtener_logger
from utilidades import limpiar_nombre, normalizar_nombre_para_busqueda

log = obtener_logger(__name__)

# Patrón RFC 5322 simplificado — cubre el 99.9% de correos reales
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

COLUMNAS_REQUERIDAS = {"Nombre", "Correo"}


# ------------------------------------------------------------------
# Tipos de resultado
# ------------------------------------------------------------------

class EstadoNomina(Enum):
    EXITOSO          = auto()
    ERROR_XML        = auto()
    PDF_NO_ENCONTRADO = auto()
    ERROR_RENAME     = auto()
    CORREO_NO_ENCONTRADO = auto()
    ERROR_SMTP_AUTH  = auto()  # Señal especial: abortar todo el procesamiento
    ERROR_SMTP       = auto()
    ERROR_ARCHIVO    = auto()
    ERROR_VALIDACION = auto()


@dataclass
class ResultadoNomina:
    """
    Resultado del procesamiento de un único XML/empleado.
    Desacopla completamente la lógica de negocio de la capa de UI:
    app.py y main.py reciben esta estructura y deciden cómo mostrarla.
    """
    xml_file: str
    estado: EstadoNomina
    mensaje: str
    nombre: str = ""
    correo: str = ""

    @property
    def exitoso(self) -> bool:
        return self.estado == EstadoNomina.EXITOSO

    @property
    def es_error_fatal(self) -> bool:
        """Si True, el procesamiento completo debe detenerse."""
        return self.estado == EstadoNomina.ERROR_SMTP_AUTH


# Tipo del callback de progreso: recibe (procesados, total, resultado_actual)
CallbackProgreso = Callable[[int, int, ResultadoNomina], None]


# ------------------------------------------------------------------
# Orquestador principal
# ------------------------------------------------------------------

def ejecutar_procesamiento(
    correos_por_nombre: dict[str, str],
    indice_pdfs: dict[str, Path],
    on_progreso: CallbackProgreso | None = None,
) -> list[ResultadoNomina]:
    """
    Procesa todos los XMLs del directorio configurado.

    Recibe los datos ya cargados (correos e índice de PDFs) para
    evitar releer disco en cada llamada y permitir testing sin I/O.

    Args:
        correos_por_nombre: {nombre_normalizado: correo} del Excel.
        indice_pdfs:        {curp: Path_al_pdf} construido por construir_indice_pdfs().
        on_progreso:        Callback opcional llamado después de cada XML.
                            Útil para actualizar barras de progreso en UI.

    Returns:
        Lista de ResultadoNomina, uno por XML encontrado.
        El caller decide cómo presentar o loggear cada resultado.

    Note:
        Si se encuentra un ERROR_SMTP_AUTH, el procesamiento se detiene
        inmediatamente — no tiene sentido reintentar con credenciales inválidas.
    """
    xml_files = [f for f in os.listdir(XML_PATH) if f.endswith(".xml")]
    total = len(xml_files)
    resultados: list[ResultadoNomina] = []

    for i, xml_file in enumerate(xml_files):
        resultado = _procesar_xml(xml_file, correos_por_nombre, indice_pdfs)
        resultados.append(resultado)

        # Persistir en archivo — sobrevive recargas de Streamlit
        if resultado.exitoso:
            log.info("[%d/%d] %s", i + 1, total, resultado.mensaje)
        elif resultado.es_error_fatal:
            log.critical("[%d/%d] %s", i + 1, total, resultado.mensaje)
        else:
            log.warning("[%d/%d] %s", i + 1, total, resultado.mensaje)

        if on_progreso:
            on_progreso(i + 1, total, resultado)

        if resultado.es_error_fatal:
            log.critical("Procesamiento abortado por error de autenticación.")
            break

    return resultados


def _procesar_xml(
    xml_file: str,
    correos_por_nombre: dict[str, str],
    indice_pdfs: dict[str, Path],
) -> ResultadoNomina:
    """Procesa un único XML y retorna su resultado. Sin efectos de UI."""
    xml_path = str(XML_PATH / xml_file)

    # Extraer datos del XML
    nombre, curp = extraer_datos_xml(xml_path)
    if not nombre or not curp:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_XML,
            mensaje=f"No se pudieron extraer datos de {xml_file}",
        )

    # Buscar PDF en el índice
    pdf_path = indice_pdfs.get(curp)
    if not pdf_path:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.PDF_NO_ENCONTRADO,
            mensaje=f"PDF no encontrado para {nombre} (CURP: {curp})",
            nombre=nombre,
        )

    # Renombrar PDF
    nombre_limpio = limpiar_nombre(nombre)
    try:
        nuevo_path = renombrar_pdf_seguro(str(pdf_path), nombre_limpio, curp)
    except (FileNotFoundError, RuntimeError) as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_RENAME,
            mensaje=f"Error al renombrar PDF para {nombre}: {e}",
            nombre=nombre,
        )

    # Buscar correo
    clave = normalizar_nombre_para_busqueda(nombre)
    correo = correos_por_nombre.get(clave)
    if not correo:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.CORREO_NO_ENCONTRADO,
            mensaje=f"Correo no encontrado para: {nombre}",
            nombre=nombre,
        )

    # Enviar correo
    asunto = f"Recibo de Nómina - {nombre}"
    cuerpo = (
        f"Estimado(a) {nombre},\n\n"
        "Por medio del presente reciba un cordial saludo y al mismo tiempo "
        "enviamos en archivo adjunto el CFDI con el formato electrónico XML(s) "
        "de las remuneraciones cubiertas en el período indicado en el título "
        "del correo.\n\n"
        "Saludos cordiales."
    )

    try:
        enviar_correo(correo, asunto, cuerpo, [xml_path, str(nuevo_path)])
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.EXITOSO,
            mensaje=f"Correo enviado a {nombre} ({correo})",
            nombre=nombre,
            correo=correo,
        )

    except smtplib.SMTPAuthenticationError:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_SMTP_AUTH,
            mensaje="Credenciales de Gmail inválidas. Verifica EMAIL_SENDER y EMAIL_PASSWORD en .env",
            nombre=nombre,
        )

    except smtplib.SMTPException as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_SMTP,
            mensaje=f"Error SMTP para {nombre}: {e}",
            nombre=nombre,
        )

    except FileNotFoundError as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_ARCHIVO,
            mensaje=f"Archivo no encontrado para {nombre}: {e}",
            nombre=nombre,
        )

    except ValueError as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_VALIDACION,
            mensaje=f"Error de validación para {nombre}: {e}",
            nombre=nombre,
        )


# ------------------------------------------------------------------
# Excel de correos
# ------------------------------------------------------------------

def leer_correos_excel() -> dict[str, str]:
    df = pd.read_excel(EXCEL_CORREOS)
    df.columns = df.columns.str.strip()

    faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El archivo Excel debe contener las columnas: {COLUMNAS_REQUERIDAS}. "
            f"Columnas faltantes: {faltantes}. "
            f"Columnas encontradas: {set(df.columns)}"
        )

    df["Nombre"] = df["Nombre"].astype(str)
    df["Nombre_normalizado"] = df["Nombre"].apply(normalizar_nombre_para_busqueda)

    # Validar formato de cada correo antes de construir el diccionario.
    # Los inválidos se excluyen con un warning — no detienen la carga completa.
    invalidos = []
    validos_mask = []

    for _, fila in df.iterrows():
        correo = str(fila["Correo"]).strip() if pd.notna(fila["Correo"]) else ""
        if _es_correo_valido(correo):
            validos_mask.append(True)
        else:
            invalidos.append((fila["Nombre"], correo))
            validos_mask.append(False)

    if invalidos:
        for nombre, correo in invalidos:
            log.warning(
                "Correo inválido o vacío para '%s': '%s' — se excluye del procesamiento.",
                nombre, correo,
            )
        log.warning(
            "%d registro(s) excluidos por correo inválido. "
            "Revisa el archivo: %s",
            len(invalidos), EXCEL_CORREOS,
        )

    df_valido = df[validos_mask]
    log.info("Base de correos cargada: %d válidos, %d excluidos.", len(df_valido), len(invalidos))

    return dict(zip(df_valido["Nombre_normalizado"], df_valido["Correo"].str.strip()))


def _es_correo_valido(correo: str) -> bool:
    """Valida formato básico de dirección de correo electrónico."""
    return bool(correo and _EMAIL_REGEX.match(correo))


# ------------------------------------------------------------------
# XML
# ------------------------------------------------------------------

def extraer_datos_xml(xml_file: str) -> tuple[str | None, str | None]:
    namespaces = {
        "cfdi": "http://www.sat.gob.mx/cfd/4",
        "nomina12": "http://www.sat.gob.mx/nomina12",
    }
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        nombre = root.find(".//cfdi:Receptor", namespaces).attrib.get("Nombre")
        curp = root.find(".//nomina12:Receptor", namespaces).attrib.get("Curp").upper()
        return nombre, curp
    except Exception as e:
        log.error("Error al parsear XML '%s': %s", xml_file, e)
        return None, None


# ------------------------------------------------------------------
# PDF — índice
# ------------------------------------------------------------------

def construir_indice_pdfs() -> dict[str, Path]:
    """
    Lee cada PDF del directorio UNA SOLA VEZ y construye un índice
    {curp: ruta_pdf}. Debe llamarse una vez al inicio del procesamiento
    y reutilizarse para todas las búsquedas.

    Complejidad: O(n) — cada PDF se lee exactamente una vez,
    independientemente de cuántos XMLs haya que procesar.
    Antes (buscar_pdf_por_curp): O(n²) — cada XML relanzaba
    una lectura completa de todos los PDFs.

    Returns:
        Diccionario {curp_en_mayusculas: Path_al_pdf}.
        PDFs que no contienen CURP válido o son ilegibles se omiten
        con un warning, sin detener el procesamiento.

    Note:
        Asume un PDF por empleado. Si un PDF contiene múltiples CURPs,
        todos quedan indexados apuntando al mismo archivo.
    """
    # Patrón oficial CURP del SAT:
    # 4 letras + 6 dígitos fecha + H/M + 2 letras estado +
    # 3 letras apellidos/nombre + 1 alfanumérico + 1 dígito verificador
    patron_curp = re.compile(r"[A-Z]{4}\d{6}[HM][A-Z]{2}[A-Z]{3}[A-Z0-9]\d")

    indice: dict[str, Path] = {}
    archivos_no_procesados: list[str] = []

    for pdf_file in Path(PDF_PATH).iterdir():
        if pdf_file.suffix.lower() != ".pdf":
            continue

        try:
            contenido = _extraer_texto_pdf(pdf_file)
            curps_encontrados = patron_curp.findall(contenido)

            if not curps_encontrados:
                archivos_no_procesados.append(pdf_file.name)
                continue

            for curp in curps_encontrados:
                if curp in indice:
                    log.warning(
                        "CURP duplicado '%s' en '%s' (ya indexado desde '%s') — se conserva el primero.",
                        curp, pdf_file.name, indice[curp].name,
                    )
                else:
                    indice[curp] = pdf_file

        except Exception as e:
            log.error("PDF inválido '%s': %s", pdf_file.name, e)

    if archivos_no_procesados:
        log.warning(
            "%d PDF(s) sin CURP reconocible (portadas u otros documentos): %s",
            len(archivos_no_procesados),
            ", ".join(archivos_no_procesados),
        )

    log.info("Índice de PDFs construido: %d CURPs indexados.", len(indice))
    return indice


def _extraer_texto_pdf(ruta: Path) -> str:
    """
    Extrae todo el texto de un PDF.
    Separada de construir_indice_pdfs para facilitar testing y
    para poder extenderse con OCR en el futuro si se necesita.
    """
    contenido = []
    with open(ruta, "rb") as f:
        reader = PdfReader(f)
        for page in reader.pages:
            texto = page.extract_text()
            if texto:
                contenido.append(texto)
    return "\n".join(contenido)


# ------------------------------------------------------------------
# PDF — renombrado seguro
# ------------------------------------------------------------------

def renombrar_pdf_seguro(origen: str, nombre_limpio: str, curp: str) -> Path:
    """
    Renombra un PDF usando copy+delete en lugar de rename.

    Estrategia:
        1. Calcular la ruta destino.
        2. Si ya existe, retornarla sin hacer nada (idempotente).
        3. Copiar el original al destino (shutil.copy2 preserva metadatos).
        4. Verificar que la copia existe y no está vacía.
        5. Solo entonces borrar el original.

    De esta forma, ante cualquier crash entre los pasos 3 y 5,
    el archivo original sigue intacto y la operación es segura
    de reintentar.

    Args:
        origen:        Ruta absoluta al PDF original.
        nombre_limpio: Nombre del empleado ya normalizado (sin tildes, sin espacios).
        curp:          CURP del empleado en mayúsculas.

    Returns:
        Path al archivo en su ubicación final (renombrado o ya existente).

    Raises:
        RuntimeError: Si la copia falla o el archivo destino queda corrupto.
    """
    origen_path = Path(origen)
    destino_path = Path(PDF_PATH) / f"{nombre_limpio}-{curp}.pdf"

    # Caso 1: ya fue renombrado en una ejecución anterior → idempotente
    if destino_path.exists():
        return destino_path

    # Caso 2: el origen desapareció entre buscar_pdf_por_curp y este punto
    if not origen_path.exists():
        raise FileNotFoundError(
            f"El PDF original ya no existe en la ruta esperada: {origen_path}\n"
            f"Es posible que haya sido movido o renombrado por otra ejecución."
        )

    try:
        # Paso 3: copiar preservando metadatos (fecha modificación, etc.)
        shutil.copy2(str(origen_path), str(destino_path))

        # Paso 4: verificar integridad mínima antes de borrar el original
        if not destino_path.exists() or destino_path.stat().st_size == 0:
            raise RuntimeError(
                f"La copia de '{origen_path.name}' resultó vacía o no existe. "
                f"El original no fue eliminado."
            )

        # Paso 5: borrar el original solo si la copia es válida
        origen_path.unlink()

        return destino_path

    except Exception as e:
        # Limpiar copia parcial si algo salió mal en el paso 3 o 4
        if destino_path.exists():
            destino_path.unlink()
        raise RuntimeError(
            f"Error al renombrar '{origen_path.name}' → '{destino_path.name}': {e}\n"
            f"El archivo original no fue modificado."
        ) from e