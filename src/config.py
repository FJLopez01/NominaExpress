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


def _requerir_int(nombre: str) -> int:
    """Igual que _requerir pero convierte a int con mensaje de error claro."""
    valor = _requerir(nombre)
    try:
        return int(valor)
    except ValueError:
        raise EnvironmentError(
            f"La variable de entorno '{nombre}' debe ser un número entero. "
            f"Valor actual: '{valor}'"
        )


# ------------------------------------------------------------------
# Rutas
# ------------------------------------------------------------------

BASE_PATH = Path(_requerir("BASE_PATH"))
XML_PATH  = BASE_PATH / "XML"
PDF_PATH  = BASE_PATH / "PDFs"
EXCEL_CORREOS = BASE_PATH / "correos_colaboradores.xlsx"


# ------------------------------------------------------------------
# Configuración de correo
# ------------------------------------------------------------------

EMAIL_SENDER   = _requerir("EMAIL_SENDER")
EMAIL_PASSWORD = _requerir("EMAIL_PASSWORD")
SMTP_SERVER    = os.getenv("SMTP_SERVER", "smtp.gmail.com")   # Tiene default razonable
SMTP_PORT      = int(os.getenv("SMTP_PORT", "587"))           # Tiene default razonable


# ------------------------------------------------------------------
# Validación de rutas al arrancar
# (falla rápido en vez de explotar a mitad del procesamiento)
# ------------------------------------------------------------------

def validar_entorno() -> list[str]:
    """
    Verifica que las rutas configuradas existan.
    Retorna lista de errores encontrados (vacía = todo OK).
    Separada de la carga de variables para poder usarla
    desde la UI de Streamlit sin detener la app.
    """
    errores = []

    if not XML_PATH.exists():
        errores.append(f"Directorio XML no encontrado: {XML_PATH}")
    if not PDF_PATH.exists():
        errores.append(f"Directorio PDF no encontrado: {PDF_PATH}")
    if not EXCEL_CORREOS.exists():
        errores.append(f"Archivo de correos no encontrado: {EXCEL_CORREOS}")

    return errores