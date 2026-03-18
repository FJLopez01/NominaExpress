"""
tests/test_correo.py

Cobertura:
- _construir_mensaje: verifica headers y adjuntos sin abrir conexión SMTP.
- _validar_adjuntos: verifica que falle correctamente ante archivo inexistente
o demasiado grande.
- enviar_correo: verifica que SMTPAuthenticationError se propaga al caller
(este es el bug que se estaba silenciando).

Ejecutar:
    pytest tests/test_correo.py -v
"""

import smtplib
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from correo import MAX_ADJUNTO_BYTES, _construir_mensaje, _validar_adjuntos, enviar_correo


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def adjunto_valido(tmp_path: Path) -> Path:
    """Crea un archivo temporal pequeño que simula un PDF real."""
    f = tmp_path / "recibo.pdf"
    f.write_bytes(b"%PDF-1.4 contenido de prueba")
    return f


@pytest.fixture
def adjunto_gigante(tmp_path: Path) -> Path:
    """Crea un archivo que supera el límite de tamaño."""
    f = tmp_path / "enorme.pdf"
    f.write_bytes(b"x" * (MAX_ADJUNTO_BYTES + 1))
    return f


# ------------------------------------------------------------------
# Tests de _validar_adjuntos
# ------------------------------------------------------------------

class TestValidarAdjuntos:

    def test_archivo_inexistente_lanza_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="no encontrado"):
            _validar_adjuntos(["/ruta/que/no/existe.pdf"])

    def test_archivo_demasiado_grande_lanza_value_error(self, adjunto_gigante):
        with pytest.raises(ValueError, match="supera el límite"):
            _validar_adjuntos([str(adjunto_gigante)])

    def test_archivo_valido_no_lanza_excepcion(self, adjunto_valido):
        _validar_adjuntos([str(adjunto_valido)])  # No debe lanzar nada

    def test_multiples_adjuntos_falla_en_el_primero_invalido(self, adjunto_valido):
        with pytest.raises(FileNotFoundError):
            _validar_adjuntos([str(adjunto_valido), "/no/existe.xml"])


# ------------------------------------------------------------------
# Tests de _construir_mensaje
# ------------------------------------------------------------------

class TestConstruirMensaje:

    def test_headers_correctos(self, adjunto_valido):
        msg = _construir_mensaje(
            destinatario="empleado@empresa.com",
            asunto="Recibo de Nómina",
            cuerpo="Estimado empleado...",
            archivos_adjuntos=[str(adjunto_valido)],
        )
        assert msg["To"] == "empleado@empresa.com"
        assert msg["Subject"] == "Recibo de Nómina"

    def test_adjunto_incluido_en_mensaje(self, adjunto_valido):
        msg = _construir_mensaje(
            destinatario="empleado@empresa.com",
            asunto="Test",
            cuerpo="Cuerpo",
            archivos_adjuntos=[str(adjunto_valido)],
        )
        # MIMEMultipart: parte 0 = cuerpo texto, parte 1 = adjunto
        partes = msg.get_payload()
        assert len(partes) == 2
        adjunto_part = partes[1]
        assert adjunto_valido.name in adjunto_part.get("Content-Disposition", "")

    def test_sin_adjuntos_solo_cuerpo(self):
        msg = _construir_mensaje("a@b.com", "Asunto", "Cuerpo", [])
        assert len(msg.get_payload()) == 1  # Solo el texto


# ------------------------------------------------------------------
# Tests de enviar_correo (mock SMTP — sin red)
# ------------------------------------------------------------------

class TestEnviarCorreo:

    @patch("correo.smtplib.SMTP")
    def test_envio_exitoso_llama_send_message(self, mock_smtp_class, adjunto_valido):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        enviar_correo(
            destinatario="empleado@empresa.com",
            asunto="Nómina",
            cuerpo="Texto",
            archivos_adjuntos=[str(adjunto_valido)],
        )

        mock_server.starttls.assert_called_once()
        mock_server.send_message.assert_called_once()

    @patch("correo.smtplib.SMTP")
    def test_smtp_auth_error_se_propaga(self, mock_smtp_class, adjunto_valido):
        """
        Este test documenta el bug original:
        SMTPAuthenticationError NO debe ser silenciado por correo.py.
        El caller debe recibirlo para poder abortar el procesamiento.
        """
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Invalid credentials")

        with pytest.raises(smtplib.SMTPAuthenticationError):
            enviar_correo(
                destinatario="empleado@empresa.com",
                asunto="Nómina",
                cuerpo="Texto",
                archivos_adjuntos=[str(adjunto_valido)],
            )

    @patch("correo.smtplib.SMTP")
    def test_smtp_exception_generica_se_propaga(self, mock_smtp_class, adjunto_valido):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        mock_server.send_message.side_effect = smtplib.SMTPException("Timeout")

        with pytest.raises(smtplib.SMTPException):
            enviar_correo(
                destinatario="empleado@empresa.com",
                asunto="Nómina",
                cuerpo="Texto",
                archivos_adjuntos=[str(adjunto_valido)],
            )

    def test_archivo_inexistente_lanza_antes_de_conectar(self):
        """
        Verifica que la validación ocurre ANTES de abrir la conexión SMTP.
        No debe haber ningún intento de conexión si los adjuntos no existen.
        """
        with patch("correo.smtplib.SMTP") as mock_smtp:
            with pytest.raises(FileNotFoundError):
                enviar_correo("a@b.com", "Asunto", "Cuerpo", ["/no/existe.pdf"])
            mock_smtp.assert_not_called()