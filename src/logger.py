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

LOGS_DIR = Path(__file__).parent.parent / "logs"

_configurado = False


def _configurar_logging() -> None:
    global _configurado
    if _configurado:
        return

    LOGS_DIR.mkdir(exist_ok=True)

    log_file = LOGS_DIR / f"nominas_{datetime.now():%Y%m%d}.log"

    formato = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formato)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formato)
    console_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger("nominas")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.propagate = False

    _configurado = True


def obtener_logger(nombre: str) -> logging.Logger:
    """
    Retorna un logger configurado para el módulo indicado.

    Args:
        nombre: Normalmente __name__ del módulo que llama.

    Example:
        log = obtener_logger(__name__)
        log.info("Iniciando procesamiento")
    """
    _configurar_logging()
    return logging.getLogger(f"nominas.{nombre}")


def ruta_log_actual() -> Path:
    """Retorna la ruta al archivo de log del día actual."""
    return LOGS_DIR / f"nominas_{datetime.now():%Y%m%d}.log"