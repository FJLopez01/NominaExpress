"""
config.py — Configuración global del sistema.

Todas las credenciales y rutas se leen desde variables de entorno.
Para desarrollo local, crea un archivo .env basado en .env.example.
NUNCA escribas valores reales directamente en este archivo.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carga el archivo .env si existe (entorno local).
# En producción/CI las variables deben estar definidas en el sistema.
load_dotenv()


# ------------------------------------------------------------------
# Helpers internos
# ------------------------------------------------------------------

def _requerir(nombre: str) -> str:
    """
    Obtiene una variable de entorno obligatoria.
    Falla con un mensaje claro si no está definida,
    en lugar de lanzar un KeyError críptico más adelante.
    """
    valor = os.getenv(nombre)
    if not valor:
        raise EnvironmentError(
            f"\n"
            f"  Variable de entorno requerida no encontrada: '{nombre}'\n"
            f"\n"
            f"  Solución:\n"
            f"    1. Copia el archivo de plantilla:  cp .env.example .env\n"
            f"    2. Rellena '{nombre}' con el valor correcto en .env\n"
            f"    3. Reinicia la aplicación.\n"
        )
    return valor


# ------------------------------------------------------------------
# Rutas del sistema
# ------------------------------------------------------------------

BASE_PATH     = Path(_requerir("BASE_PATH"))
XML_PATH      = BASE_PATH / "XML"
PDF_PATH      = BASE_PATH / "PDFs"
EXCEL_CORREOS = BASE_PATH / "correos_colaboradores.xlsx"

# Base de datos SQLite — guarda historial de envíos
DB_PATH = BASE_PATH / "nominas.db"

# Plantilla del cuerpo del correo (editable sin tocar código)
TEMPLATES_DIR    = Path(__file__).parent.parent / "templates"
PLANTILLA_CORREO = TEMPLATES_DIR / "plantilla_correo.txt"


# ------------------------------------------------------------------
# Configuración Microsoft 365 (Graph API)
# ------------------------------------------------------------------
# Para obtener estos valores, sigue la guía en:
# docs/configurar_azure_ad.md

AZURE_TENANT_ID     = _requerir("AZURE_TENANT_ID")      # ID del directorio en Azure AD
AZURE_CLIENT_ID     = _requerir("AZURE_CLIENT_ID")      # ID de la aplicación registrada
AZURE_CLIENT_SECRET = _requerir("AZURE_CLIENT_SECRET")  # Secreto de cliente generado
EMAIL_SENDER        = _requerir("EMAIL_SENDER")          # correo@tuempresa.com (remitente)


# ------------------------------------------------------------------
# Validación de entorno al arrancar
# ------------------------------------------------------------------

def validar_entorno() -> list[str]:
    """
    Verifica que las rutas configuradas existan.
    Retorna lista de errores encontrados (vacía = todo OK).
    """
    errores = []

    if not XML_PATH.exists():
        errores.append(f"Directorio XML no encontrado: {XML_PATH}")
    if not PDF_PATH.exists():
        errores.append(f"Directorio PDF no encontrado: {PDF_PATH}")
    if not EXCEL_CORREOS.exists():
        errores.append(f"Archivo de correos no encontrado: {EXCEL_CORREOS}")
    if not PLANTILLA_CORREO.exists():
        errores.append(f"Plantilla de correo no encontrada: {PLANTILLA_CORREO}")

    return errores


def leer_plantilla_correo() -> str:
    """
    Lee la plantilla del cuerpo del correo desde disco.
    Si no existe, retorna un texto de fallback para no romper el flujo.
    """
    try:
        return PLANTILLA_CORREO.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            "Estimado(a) {nombre},\n\n"
            "Adjunto encontrará su recibo de nómina del período "
            "{fecha_inicial} al {fecha_final}.\n\n"
            "Saludos cordiales."
        )