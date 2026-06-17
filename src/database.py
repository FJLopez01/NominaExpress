"""
database.py — Persistencia del historial de envíos en SQLite.

Responsabilidades:
  - Crear el esquema si no existe (idempotente al arrancar).
  - Registrar cada envío exitoso con todos sus datos relevantes.
  - Consultar si un recibo (por UUID) ya fue enviado anteriormente.
  - Proveer historial para la UI.

¿Por qué SQLite y no un archivo JSON o CSV?
  - SQLite viene incluido en Python, sin dependencias extra.
  - Soporta consultas, filtros y ordenamiento sin código manual.
  - Es seguro ante escrituras concurrentes (aunque aquí no aplica).
  - El archivo .db es portable y fácil de respaldar.
  - Soporta hasta terabytes de datos — más que suficiente para nóminas.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import DB_PATH
from logger import obtener_logger

log = obtener_logger(__name__)


# ------------------------------------------------------------------
# Esquema
# ------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS envios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificadores del recibo (del XML)
    uuid            TEXT NOT NULL UNIQUE,   -- UUID del CFDI — garantiza idempotencia
    num_empleado    TEXT,                   -- NumEmpleado del XML (ej: "095")
    rfc_receptor    TEXT,                   -- RFC del empleado  (ej: "LOMD040528PX4")
    curp            TEXT,                   -- CURP del empleado
    nombre          TEXT,                   -- Nombre completo del receptor
    periodo_inicio  TEXT,                   -- FechaInicialPago del XML
    periodo_fin     TEXT,                   -- FechaFinalPago del XML
    total           TEXT,                   -- Total a pagar (como texto para preservar formato)

    -- Datos del envío
    correo          TEXT,                   -- Dirección a la que se envió
    xml_file        TEXT,                   -- Nombre del archivo XML procesado
    pdf_file        TEXT,                   -- Nombre del PDF adjuntado

    -- Metadatos
    fecha_envio     TEXT NOT NULL,          -- ISO 8601: 2025-04-05T10:23:01
    enviado_por     TEXT                    -- Usuario/hostname que ejecutó el proceso
);

CREATE INDEX IF NOT EXISTS idx_envios_uuid         ON envios(uuid);
CREATE INDEX IF NOT EXISTS idx_envios_num_empleado ON envios(num_empleado);
CREATE INDEX IF NOT EXISTS idx_envios_fecha_envio  ON envios(fecha_envio);
"""


# ------------------------------------------------------------------
# Inicialización
# ------------------------------------------------------------------

def inicializar_db() -> None:
    """
    Crea el archivo de base de datos y el esquema si no existen.
    Es seguro llamarla múltiples veces (CREATE TABLE IF NOT EXISTS).
    Se llama automáticamente al arrancar la aplicación.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conexion() as conn:
        conn.executescript(_DDL)
    log.info("Base de datos inicializada: %s", DB_PATH)


# ------------------------------------------------------------------
# Operaciones principales
# ------------------------------------------------------------------

def ya_fue_enviado(uuid: str) -> bool:
    """
    Verifica si un recibo ya fue enviado exitosamente en una ejecución anterior.
    Esto garantiza idempotencia: si el script falla y se vuelve a ejecutar,
    no reenvía los correos que ya salieron.

    Args:
        uuid: UUID del CFDI (campo UUID del TimbreFiscalDigital).

    Returns:
        True si el UUID ya está registrado, False si es nuevo.
    """
    with _conexion() as conn:
        fila = conn.execute(
            "SELECT 1 FROM envios WHERE uuid = ?", (uuid,)
        ).fetchone()
    return fila is not None


def registrar_envio(
    uuid: str,
    num_empleado: str,
    rfc_receptor: str,
    curp: str,
    nombre: str,
    periodo_inicio: str,
    periodo_fin: str,
    total: str,
    correo: str,
    xml_file: str,
    pdf_file: str,
) -> None:
    """
    Guarda un envío exitoso en la base de datos.
    Si el UUID ya existe (por alguna condición de carrera), lo ignora silenciosamente.

    Args:
        Todos los campos del recibo extraídos del XML + datos del envío.
    """
    import socket
    enviado_por = socket.gethostname()
    fecha_envio = datetime.now().isoformat(timespec="seconds")

    with _conexion() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO envios
                (uuid, num_empleado, rfc_receptor, curp, nombre,
                periodo_inicio, periodo_fin, total,
                correo, xml_file, pdf_file, fecha_envio, enviado_por)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid, num_empleado, rfc_receptor, curp, nombre,
                periodo_inicio, periodo_fin, total,
                correo, xml_file, pdf_file, fecha_envio, enviado_por,
            ),
        )

    log.debug("Envío registrado en BD: UUID=%s, empleado=%s", uuid, num_empleado)


def obtener_historial(limite: int = 200) -> list[dict]:
    """
    Retorna los últimos N envíos para mostrar en la UI.

    Args:
        limite: Máximo de registros a retornar (default 200).

    Returns:
        Lista de dicts con todos los campos de cada envío, ordenados
        del más reciente al más antiguo.
    """
    with _conexion() as conn:
        conn.row_factory = sqlite3.Row
        filas = conn.execute(
            """
            SELECT * FROM envios
            ORDER BY fecha_envio DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()

    return [dict(fila) for fila in filas]


def contar_envios_por_periodo(periodo_inicio: str, periodo_fin: str) -> int:
    """
    Cuenta cuántos recibos fueron enviados para un período específico.
    Útil para la UI al mostrar estadísticas de la última nómina procesada.
    """
    with _conexion() as conn:
        fila = conn.execute(
            """
            SELECT COUNT(*) FROM envios
            WHERE periodo_inicio = ? AND periodo_fin = ?
            """,
            (periodo_inicio, periodo_fin),
        ).fetchone()
    return fila[0] if fila else 0


# ------------------------------------------------------------------
# Helper de conexión
# ------------------------------------------------------------------

@contextmanager
def _conexion():
    """
    Context manager que abre y cierra la conexión automáticamente.
    Usa WAL mode para mejor rendimiento en escrituras concurrentes.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()