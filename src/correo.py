"""
correo.py — Módulo de envío de correos vía Microsoft Graph API.

Reemplaza la implementación SMTP anterior por Graph API con autenticación
OAuth2 (Client Credentials Flow). Esto es más robusto que SMTP porque:
  - No depende de contraseñas de aplicación que expiran o se revocan.
  - No se rompe cuando el administrador cambia políticas SMTP de M365.
  - Usa el estándar moderno recomendado por Microsoft.
  - Los correos salen desde el buzón real del remitente, no de un relay.

Responsabilidad única: construir y enviar el mensaje.
Si algo falla, lanza la excepción para que el caller decida qué hacer.
"""

import base64
import json
from pathlib import Path

import msal
import requests

from config import AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, EMAIL_SENDER

# Límite conservador por debajo del máximo de Graph API (150 MB)
MAX_ADJUNTO_BYTES = 20 * 1024 * 1024  # 20 MB

# Scope requerido para enviar correo como usuario específico
_GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]
_GRAPH_SEND_URL = f"https://graph.microsoft.com/v1.0/users/{EMAIL_SENDER}/sendMail"


class GraphAuthError(Exception):
    """Credenciales de Azure AD inválidas o permisos insuficientes."""


class GraphSendError(Exception):
    """Error al enviar el correo a través de Graph API."""


def enviar_correo(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    archivos_adjuntos: list[str],
) -> None:
    """
    Construye y envía un correo con los archivos adjuntos indicados,
    usando Microsoft Graph API con autenticación OAuth2.

    Args:
        destinatario:      Dirección de correo del receptor.
        asunto:            Asunto del mensaje.
        cuerpo:            Cuerpo del mensaje en texto plano.
        archivos_adjuntos: Lista de rutas absolutas a los archivos a adjuntar.

    Raises:
        FileNotFoundError:  Si algún archivo adjunto no existe.
        ValueError:         Si algún adjunto supera el límite de tamaño.
        GraphAuthError:     Si las credenciales de Azure AD son inválidas.
        GraphSendError:     Si Graph API rechaza el envío por cualquier otra razón.
    """
    _validar_adjuntos(archivos_adjuntos)
    token = _obtener_token()
    payload = _construir_payload(destinatario, asunto, cuerpo, archivos_adjuntos)
    _enviar_via_graph(token, payload)


# ------------------------------------------------------------------
# Autenticación
# ------------------------------------------------------------------

def _obtener_token() -> str:
    """
    Obtiene un access token de Azure AD usando Client Credentials Flow.
    MSAL cachea el token automáticamente hasta que expira (normalmente 1 hora).
    """
    app = msal.ConfidentialClientApplication(
        client_id=AZURE_CLIENT_ID,
        client_credential=AZURE_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{AZURE_TENANT_ID}",
    )

    resultado = app.acquire_token_for_client(scopes=_GRAPH_SCOPES)

    if "access_token" not in resultado:
        error = resultado.get("error", "unknown_error")
        descripcion = resultado.get("error_description", "Sin descripción")
        raise GraphAuthError(
            f"No se pudo obtener token de Azure AD.\n"
            f"Error: {error}\n"
            f"Descripción: {descripcion}\n\n"
            f"Verifica AZURE_TENANT_ID, AZURE_CLIENT_ID y AZURE_CLIENT_SECRET en .env"
        )

    return resultado["access_token"]


# ------------------------------------------------------------------
# Construcción del payload
# ------------------------------------------------------------------

def _construir_payload(
    destinatario: str,
    asunto: str,
    cuerpo: str,
    archivos_adjuntos: list[str],
) -> dict:
    """
    Construye el payload JSON para Graph API /sendMail.
    Separado del envío para facilitar testing sin red.
    """
    adjuntos_json = [
        _archivo_a_adjunto(ruta) for ruta in archivos_adjuntos
    ]

    return {
        "message": {
            "subject": asunto,
            "body": {
                "contentType": "Text",
                "content": cuerpo,
            },
            "toRecipients": [
                {"emailAddress": {"address": destinatario}}
            ],
            "attachments": adjuntos_json,
        },
        "saveToSentItems": True,  # El correo queda en la bandeja de enviados
    }


def _archivo_a_adjunto(ruta: str) -> dict:
    """Convierte una ruta de archivo al formato de adjunto de Graph API."""
    path = Path(ruta)
    contenido_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")

    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": path.name,
        "contentType": _inferir_content_type(path),
        "contentBytes": contenido_b64,
    }


def _inferir_content_type(path: Path) -> str:
    tipos = {
        ".pdf": "application/pdf",
        ".xml": "application/xml",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return tipos.get(path.suffix.lower(), "application/octet-stream")


# ------------------------------------------------------------------
# Envío
# ------------------------------------------------------------------

def _enviar_via_graph(token: str, payload: dict) -> None:
    """
    Realiza el POST a Graph API. Lanza excepción con mensaje claro
    si la respuesta no es 202 Accepted.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    respuesta = requests.post(
        _GRAPH_SEND_URL,
        headers=headers,
        data=json.dumps(payload),
        timeout=30,
    )

    # Graph API retorna 202 Accepted para envío exitoso
    if respuesta.status_code == 202:
        return

    # Errores de autenticación — señal para abortar el procesamiento completo
    if respuesta.status_code in (401, 403):
        raise GraphAuthError(
            f"Error de autenticación con Graph API (HTTP {respuesta.status_code}).\n"
            f"Verifica que la app en Azure AD tenga el permiso 'Mail.Send'.\n"
            f"Detalle: {respuesta.text}"
        )

    # Cualquier otro error HTTP
    raise GraphSendError(
        f"Graph API rechazó el envío (HTTP {respuesta.status_code}).\n"
        f"Destinatario: {payload['message']['toRecipients'][0]['emailAddress']['address']}\n"
        f"Detalle: {respuesta.text}"
    )


# ------------------------------------------------------------------
# Validación de adjuntos (igual que antes, independiente del proveedor)
# ------------------------------------------------------------------

def _validar_adjuntos(archivos: list[str]) -> None:
    """
    Verifica existencia y tamaño de cada adjunto antes de conectarse,
    fallando rápido con mensajes claros.
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