"""
correo.py — Módulo de envío de correos electrónicos.

Responsabilidad única: construir y enviar el mensaje SMTP.
Esta capa NO maneja errores de negocio: si algo falla, lanza
la excepción para que el caller decida cómo registrarla y
qué hacer con el flujo.
"""

import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import EMAIL_SENDER, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT

# Límite conservador por debajo del máximo de Gmail (25 MB)
# para dejar margen a los headers del mensaje.
MAX_ADJUNTO_BYTES = 20 * 1024 * 1024  # 20 MB


def enviar_correo(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    archivos_adjuntos: list[str],
) -> None:
    """
    Construye y envía un correo con los archivos adjuntos indicados.

    Args:
        destinatario:      Dirección de correo del receptor.
        asunto:            Asunto del mensaje.
        cuerpo:            Cuerpo del mensaje en texto plano.
        archivos_adjuntos: Lista de rutas absolutas a los archivos a adjuntar.

    Raises:
        FileNotFoundError:  Si algún archivo adjunto no existe.
        ValueError:         Si algún adjunto supera el límite de tamaño.
        smtplib.SMTPException: Si ocurre cualquier error durante el envío SMTP.

    Note:
        Esta función NO captura excepciones. El caller es responsable
        de manejarlas y registrarlas según su contexto (UI, CLI, etc.).
    """
    _validar_adjuntos(archivos_adjuntos)

    msg = _construir_mensaje(destinatario, asunto, cuerpo, archivos_adjuntos)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


# ------------------------------------------------------------------
# Helpers privados
# ------------------------------------------------------------------

def _validar_adjuntos(archivos: list[str]) -> None:
    """
    Verifica existencia y tamaño de cada adjunto antes de abrir
    la conexión SMTP, fallando rápido con mensajes claros.
    """
    for ruta in archivos:
        path = Path(ruta)

        if not path.exists():
            raise FileNotFoundError(
                f"Archivo adjunto no encontrado: {ruta}"
            )

        size = path.stat().st_size
        if size > MAX_ADJUNTO_BYTES:
            raise ValueError(
                f"El archivo '{path.name}' ({size / 1024 / 1024:.1f} MB) "
                f"supera el límite permitido de "
                f"{MAX_ADJUNTO_BYTES / 1024 / 1024:.0f} MB."
            )


def _construir_mensaje(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    archivos_adjuntos: list[str],
) -> MIMEMultipart:
    """
    Construye el objeto MIMEMultipart con cuerpo y adjuntos.
    Separado de la lógica SMTP para facilitar testing sin red.
    """
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain"))

    for ruta in archivos_adjuntos:
        nombre_archivo = Path(ruta).name
        part = MIMEBase("application", "octet-stream")

        with open(ruta, "rb") as f:
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{nombre_archivo}"',
        )
        msg.attach(part)

    return msg