"""
logger.py — Logging persistente a archivo.

Centraliza toda la configuración de logging del sistema.
Los logs se escriben simultáneamente a archivo (persistente)
y a consola (visible en tiempo real).

Uso:
    from logger import obtener_logger
    log = obtener_logger(__name__)
    log.info("Correo enviado a juan@empresa.com")
    log.error("PDF no encontrado para CURP: ABC123")
"""

import logging
from datetime import datetime
from pathlib import Path

# ------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------

# Los logs se guardan en logs/nominas_YYYYMMDD.log
# Un archivo por día — fácil de localizar y rotar manualmente
LOGS_DIR = Path(__file__).parent.parent / "logs"

_configurado = False


def _configurar_logging() -> None:
    """
    Configura el sistema de logging una sola vez.
    Llamada automáticamente en la primera invocación de obtener_logger().
    """
    global _configurado
    if _configurado:
        return

    LOGS_DIR.mkdir(exist_ok=True)

    log_file = LOGS_DIR / f"nominas_{datetime.now():%Y%m%d}.log"

    # Formato: timestamp | nivel | módulo | mensaje
    formato = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de archivo — logs persistentes
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formato)
    file_handler.setLevel(logging.DEBUG)

    # Handler de consola — visible en terminal y en Streamlit
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formato)
    console_handler.setLevel(logging.INFO)

    # Logger raíz del proyecto — todos los módulos heredan esta config
    root_logger = logging.getLogger("nominas")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Evitar que los logs se dupliquen si Streamlit recarga el módulo
    root_logger.propagate = False

    _configurado = True


def obtener_logger(nombre: str) -> logging.Logger:
    """
    Retorna un logger configurado para el módulo indicado.

    Args:
        nombre: Normalmente __name__ del módulo que llama.
                Produce logs con prefijo 'nominas.procesador', etc.

    Example:
        log = obtener_logger(__name__)
        log.info("Iniciando procesamiento")
        log.warning("PDF no encontrado para %s", nombre)
        log.error("Error SMTP: %s", str(e))
    """
    _configurar_logging()
    return logging.getLogger(f"nominas.{nombre}")


def ruta_log_actual() -> Path:
    """
    Retorna la ruta al archivo de log del día actual.
    Útil para mostrarla en la UI al usuario.
    """
    return LOGS_DIR / f"nominas_{datetime.now():%Y%m%d}.log"