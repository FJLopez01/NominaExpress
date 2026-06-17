"""
procesador.py — Lógica de procesamiento de nóminas.

Responsabilidades:
  - Leer y parsear el Excel de correos (columnas case-insensitive).
  - Extraer datos completos de archivos XML (CFDI 4.0).
  - Construir índice de PDFs por CURP O(n).
  - Verificar idempotencia por UUID antes de cada envío.
  - Renombrar PDFs de forma segura.
  - Registrar cada envío exitoso en SQLite.
  - Orquestar el procesamiento completo sin dependencias de UI.

Cambios respecto a la versión anterior:
  - PyPDF2 → pypdf (sucesor oficial mantenido activamente).
  - Excepciones específicas en extraer_datos_xml (no captura Exception genérica).
  - Columnas del Excel normalizadas a Title Case (acepta "nombre", "NOMBRE", etc.).
  - Cuerpo del correo leído desde plantilla externa (templates/plantilla_correo.txt).
  - Idempotencia por UUID: si un recibo ya fue enviado, se salta sin error.
  - Datos completos del XML extraídos para registro en BD y cuerpo del correo.
"""

import os
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable

import pandas as pd
from pypdf import PdfReader  # ← pypdf, no PyPDF2

from config import XML_PATH, PDF_PATH, EXCEL_CORREOS, leer_plantilla_correo
from correo import enviar_correo, GraphAuthError, GraphSendError
from database import ya_fue_enviado, registrar_envio
from logger import obtener_logger
from utilidades import limpiar_nombre, normalizar_nombre_para_busqueda

log = obtener_logger(__name__)

# RFC 5322 simplificado
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

# Columnas requeridas en el Excel (se validan después de normalizar a Title Case)
COLUMNA_NOMBRE = "Nombre"
COLUMNA_CORREO = "Correo"
COLUMNAS_REQUERIDAS = {COLUMNA_NOMBRE, COLUMNA_CORREO}


# ------------------------------------------------------------------
# Tipos de resultado
# ------------------------------------------------------------------

class EstadoNomina(Enum):
    EXITOSO               = auto()
    YA_ENVIADO            = auto()   # Nuevo: UUID ya registrado en BD
    ERROR_XML             = auto()
    PDF_NO_ENCONTRADO     = auto()
    ERROR_RENAME          = auto()
    CORREO_NO_ENCONTRADO  = auto()
    ERROR_AUTH_GRAPH      = auto()   # Reemplaza ERROR_SMTP_AUTH
    ERROR_ENVIO           = auto()   # Reemplaza ERROR_SMTP
    ERROR_ARCHIVO         = auto()
    ERROR_VALIDACION      = auto()


@dataclass
class ResultadoNomina:
    """
    Resultado del procesamiento de un único XML/empleado.
    Desacopla completamente la lógica de negocio de la capa de UI.
    """
    xml_file: str
    estado: EstadoNomina
    mensaje: str
    nombre: str = ""
    correo: str = ""
    uuid: str = ""

    @property
    def exitoso(self) -> bool:
        return self.estado in (EstadoNomina.EXITOSO, EstadoNomina.YA_ENVIADO)

    @property
    def es_error_fatal(self) -> bool:
        """Si True, el procesamiento completo debe detenerse."""
        return self.estado == EstadoNomina.ERROR_AUTH_GRAPH


CallbackProgreso = Callable[[int, int, "ResultadoNomina"], None]


# ------------------------------------------------------------------
# Datos completos del XML
# ------------------------------------------------------------------

@dataclass
class DatosXML:
    """Todos los campos relevantes extraídos de un CFDI de nómina."""
    nombre: str
    curp: str
    uuid: str
    num_empleado: str
    rfc_receptor: str
    periodo_inicio: str
    periodo_fin: str
    total: str


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

    Args:
        correos_por_nombre: {nombre_normalizado: correo} del Excel.
        indice_pdfs:        {curp: Path_al_pdf} construido por construir_indice_pdfs().
        on_progreso:        Callback opcional llamado después de cada XML.

    Returns:
        Lista de ResultadoNomina, uno por XML encontrado.

    Note:
        Si se encuentra un ERROR_AUTH_GRAPH, el procesamiento se detiene
        inmediatamente — no tiene sentido reintentar con credenciales inválidas.
    """
    xml_files = sorted(f for f in os.listdir(XML_PATH) if f.endswith(".xml"))
    total = len(xml_files)
    resultados: list[ResultadoNomina] = []
    plantilla = leer_plantilla_correo()

    for i, xml_file in enumerate(xml_files):
        resultado = _procesar_xml(xml_file, correos_por_nombre, indice_pdfs, plantilla)
        resultados.append(resultado)

        nivel_log = "info" if resultado.exitoso else (
            "critical" if resultado.es_error_fatal else "warning"
        )
        getattr(log, nivel_log)("[%d/%d] %s", i + 1, total, resultado.mensaje)

        if on_progreso:
            on_progreso(i + 1, total, resultado)

        if resultado.es_error_fatal:
            log.critical("Procesamiento abortado: credenciales de Azure AD inválidas.")
            break

    return resultados


def _procesar_xml(
    xml_file: str,
    correos_por_nombre: dict[str, str],
    indice_pdfs: dict[str, Path],
    plantilla: str,
) -> ResultadoNomina:
    """Procesa un único XML. Sin efectos de UI."""
    xml_path = str(XML_PATH / xml_file)

    # 1. Extraer datos del XML
    datos = extraer_datos_xml(xml_path)
    if datos is None:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_XML,
            mensaje=f"No se pudieron extraer datos de {xml_file}",
        )

    # 2. Idempotencia: saltar si este UUID ya fue enviado
    if ya_fue_enviado(datos.uuid):
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.YA_ENVIADO,
            mensaje=f"Ya enviado anteriormente: {datos.nombre} (UUID: {datos.uuid[:8]}...)",
            nombre=datos.nombre,
            uuid=datos.uuid,
        )

    # 3. Buscar PDF por CURP
    pdf_path = indice_pdfs.get(datos.curp)
    if not pdf_path:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.PDF_NO_ENCONTRADO,
            mensaje=f"PDF no encontrado para {datos.nombre} (CURP: {datos.curp})",
            nombre=datos.nombre,
            uuid=datos.uuid,
        )

    # 4. Renombrar PDF
    nombre_limpio = limpiar_nombre(datos.nombre)
    try:
        nuevo_pdf_path = renombrar_pdf_seguro(str(pdf_path), nombre_limpio, datos.curp)
    except (FileNotFoundError, RuntimeError) as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_RENAME,
            mensaje=f"Error al renombrar PDF para {datos.nombre}: {e}",
            nombre=datos.nombre,
            uuid=datos.uuid,
        )

    # 5. Buscar correo
    clave = normalizar_nombre_para_busqueda(datos.nombre)
    correo = correos_por_nombre.get(clave)
    if not correo:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.CORREO_NO_ENCONTRADO,
            mensaje=f"Correo no encontrado para: {datos.nombre}",
            nombre=datos.nombre,
            uuid=datos.uuid,
        )

    # 6. Construir cuerpo del correo desde plantilla
    asunto = f"Recibo de Nómina — {datos.nombre} ({datos.periodo_inicio} al {datos.periodo_fin})"
    cuerpo = plantilla.format(
        nombre=datos.nombre,
        fecha_inicial=datos.periodo_inicio,
        fecha_final=datos.periodo_fin,
        total=datos.total,
    )

    # 7. Enviar correo
    try:
        enviar_correo(correo, asunto, cuerpo, [xml_path, str(nuevo_pdf_path)])

    except GraphAuthError as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_AUTH_GRAPH,
            mensaje=f"Error de autenticación con Azure AD: {e}",
            nombre=datos.nombre,
            uuid=datos.uuid,
        )

    except GraphSendError as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_ENVIO,
            mensaje=f"Error al enviar correo para {datos.nombre}: {e}",
            nombre=datos.nombre,
            uuid=datos.uuid,
        )

    except FileNotFoundError as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_ARCHIVO,
            mensaje=f"Archivo no encontrado para {datos.nombre}: {e}",
            nombre=datos.nombre,
            uuid=datos.uuid,
        )

    except ValueError as e:
        return ResultadoNomina(
            xml_file=xml_file,
            estado=EstadoNomina.ERROR_VALIDACION,
            mensaje=f"Error de validación para {datos.nombre}: {e}",
            nombre=datos.nombre,
            uuid=datos.uuid,
        )

    # 8. Registrar envío exitoso en SQLite
    registrar_envio(
        uuid=datos.uuid,
        num_empleado=datos.num_empleado,
        rfc_receptor=datos.rfc_receptor,
        curp=datos.curp,
        nombre=datos.nombre,
        periodo_inicio=datos.periodo_inicio,
        periodo_fin=datos.periodo_fin,
        total=datos.total,
        correo=correo,
        xml_file=xml_file,
        pdf_file=nuevo_pdf_path.name,
    )

    return ResultadoNomina(
        xml_file=xml_file,
        estado=EstadoNomina.EXITOSO,
        mensaje=f"Correo enviado a {datos.nombre} ({correo})",
        nombre=datos.nombre,
        correo=correo,
        uuid=datos.uuid,
    )


# ------------------------------------------------------------------
# Excel de correos — columnas case-insensitive
# ------------------------------------------------------------------

def leer_correos_excel() -> dict[str, str]:
    """
    Lee el Excel de correos y retorna {nombre_normalizado: correo}.

    Acepta columnas con cualquier capitalización:
      "nombre", "NOMBRE", "Nombre" → todos son válidos.
    Los correos con formato inválido se excluyen con warning.
    """
    df = pd.read_excel(EXCEL_CORREOS)

    # Normalizar nombres de columna: strip + Title Case
    # Esto acepta "nombre", "NOMBRE", "Correo Electrónico" si el cliente
    # tiene el Excel con formato distinto. Ajusta COLUMNAS_REQUERIDAS si cambia.
    df.columns = df.columns.str.strip().str.title()

    faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El archivo Excel debe contener las columnas: {COLUMNAS_REQUERIDAS}. "
            f"Columnas faltantes: {faltantes}. "
            f"Columnas encontradas: {set(df.columns)}"
        )

    df[COLUMNA_NOMBRE] = df[COLUMNA_NOMBRE].astype(str)
    df["_clave"] = df[COLUMNA_NOMBRE].apply(normalizar_nombre_para_busqueda)

    # Validar correos
    validos_mask = []
    invalidos = []

    for _, fila in df.iterrows():
        correo = str(fila[COLUMNA_CORREO]).strip() if pd.notna(fila[COLUMNA_CORREO]) else ""
        if _es_correo_valido(correo):
            validos_mask.append(True)
        else:
            invalidos.append((fila[COLUMNA_NOMBRE], correo))
            validos_mask.append(False)

    if invalidos:
        for nombre, correo in invalidos:
            log.warning(
                "Correo inválido o vacío para '%s': '%s' — excluido del procesamiento.",
                nombre, correo,
            )
        log.warning(
            "%d registro(s) excluidos por correo inválido. Revisa: %s",
            len(invalidos), EXCEL_CORREOS,
        )

    df_valido = df[validos_mask]
    log.info(
        "Base de correos cargada: %d válidos, %d excluidos.",
        len(df_valido), len(invalidos),
    )

    return dict(zip(df_valido["_clave"], df_valido[COLUMNA_CORREO].str.strip()))


def _es_correo_valido(correo: str) -> bool:
    return bool(correo and _EMAIL_REGEX.match(correo))


# ------------------------------------------------------------------
# XML — extracción completa de datos
# ------------------------------------------------------------------

_NS = {
    "cfdi":     "http://www.sat.gob.mx/cfd/4",
    "nomina12": "http://www.sat.gob.mx/nomina12",
    "tfd":      "http://www.sat.gob.mx/TimbreFiscalDigital",
}


def extraer_datos_xml(xml_file: str) -> DatosXML | None:
    """
    Extrae todos los campos relevantes de un CFDI de nómina.

    Retorna None si el XML está malformado o le falta estructura esperada.
    Nunca propaga excepciones — el caller recibe None como señal de error.

    Campos extraídos:
      - Nombre, CURP del receptor
      - UUID del TimbreFiscalDigital
      - NumEmpleado, RFC del receptor
      - FechaInicialPago, FechaFinalPago
      - Total del comprobante
    """
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()

        receptor_cfdi    = root.find(".//cfdi:Receptor", _NS)
        receptor_nomina  = root.find(".//nomina12:Receptor", _NS)
        nomina           = root.find(".//nomina12:Nomina", _NS)
        tfd              = root.find(".//tfd:TimbreFiscalDigital", _NS)

        # Validar que todos los nodos requeridos existan antes de leer atributos
        if any(nodo is None for nodo in [receptor_cfdi, receptor_nomina, nomina, tfd]):
            log.error(
                "XML '%s' incompleto: falta uno o más nodos requeridos "
                "(cfdi:Receptor, nomina12:Receptor, nomina12:Nomina, tfd:TimbreFiscalDigital).",
                xml_file,
            )
            return None

        return DatosXML(
            nombre         = receptor_cfdi.attrib["Nombre"],
            curp           = receptor_nomina.attrib["Curp"].upper(),
            uuid           = tfd.attrib["UUID"],
            num_empleado   = receptor_nomina.attrib.get("NumEmpleado", ""),
            rfc_receptor   = receptor_cfdi.attrib.get("Rfc", ""),
            periodo_inicio = nomina.attrib.get("FechaInicialPago", ""),
            periodo_fin    = nomina.attrib.get("FechaFinalPago", ""),
            total          = root.attrib.get("Total", ""),
        )

    except ET.ParseError as e:
        log.error("XML malformado '%s': %s", xml_file, e)
        return None

    except KeyError as e:
        log.error("Atributo faltante en XML '%s': %s", xml_file, e)
        return None

    except FileNotFoundError:
        log.error("Archivo XML no encontrado: '%s'", xml_file)
        return None


# ------------------------------------------------------------------
# PDF — índice O(n)
# ------------------------------------------------------------------

def construir_indice_pdfs() -> dict[str, Path]:
    """
    Lee cada PDF del directorio UNA SOLA VEZ y construye {curp: ruta_pdf}.
    Complejidad O(n) — reutilizar para todas las búsquedas.
    """
    patron_curp = re.compile(r"[A-Z]{4}\d{6}[HM][A-Z]{2}[A-Z]{3}[A-Z0-9]\d")

    indice: dict[str, Path] = {}
    sin_curp: list[str] = []

    for pdf_file in Path(PDF_PATH).iterdir():
        if pdf_file.suffix.lower() != ".pdf":
            continue

        try:
            contenido = _extraer_texto_pdf(pdf_file)
            curps = patron_curp.findall(contenido)

            if not curps:
                sin_curp.append(pdf_file.name)
                log.warning("PDF '%s' no contiene CURP válido — omitido.", pdf_file.name)
                continue

            for curp in curps:
                if curp in indice:
                    log.warning(
                        "CURP duplicado '%s' en '%s' (ya indexado desde '%s') — se conserva el primero.",
                        curp, pdf_file.name, indice[curp].name,
                    )
                else:
                    indice[curp] = pdf_file

        except Exception as e:
            log.error("Error al procesar PDF '%s': %s", pdf_file.name, e)

    log.info(
        "Índice de PDFs construido: %d CURPs indexados, %d sin CURP.",
        len(indice), len(sin_curp),
    )
    return indice


def _extraer_texto_pdf(ruta: Path) -> str:
    """Extrae todo el texto de un PDF usando pypdf."""
    contenido = []
    with open(ruta, "rb") as f:
        reader = PdfReader(f)
        for page in reader.pages:
            texto = page.extract_text()
            if texto:
                contenido.append(texto)
    return "\n".join(contenido)


# ------------------------------------------------------------------
# PDF — renombrado seguro (sin cambios de lógica)
# ------------------------------------------------------------------

def renombrar_pdf_seguro(origen: str, nombre_limpio: str, curp: str) -> Path:
    """
    Renombra un PDF usando copy+delete.
    Idempotente: si el destino ya existe, retorna sin hacer nada.

    Raises:
        FileNotFoundError: Si el origen desapareció entre la indexación y este punto.
        RuntimeError:      Si la copia falla o el archivo destino queda corrupto.
    """
    origen_path  = Path(origen)
    destino_path = Path(PDF_PATH) / f"{nombre_limpio}-{curp}.pdf"

    if destino_path.exists():
        return destino_path

    if not origen_path.exists():
        raise FileNotFoundError(
            f"El PDF original ya no existe: {origen_path}\n"
            f"Puede haber sido movido por otra ejecución."
        )

    try:
        shutil.copy2(str(origen_path), str(destino_path))

        if not destino_path.exists() or destino_path.stat().st_size == 0:
            raise RuntimeError(
                f"La copia de '{origen_path.name}' resultó vacía o no existe. "
                f"El original no fue eliminado."
            )

        origen_path.unlink()
        return destino_path

    except Exception as e:
        if destino_path.exists():
            destino_path.unlink()
        raise RuntimeError(
            f"Error al renombrar '{origen_path.name}' → '{destino_path.name}': {e}\n"
            f"El archivo original no fue modificado."
        ) from e