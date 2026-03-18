"""
tests/test_ejecutar_procesamiento.py

Cobertura de ejecutar_procesamiento() y _procesar_xml().

Estos tests verifican el flujo completo de negocio sin tocar
disco real ni red: todos los I/O están mockeados.
El objetivo es documentar y proteger cada rama de decisión
del orquestador.

Ejecutar:
    pytest tests/test_ejecutar_procesamiento.py -v
"""

import smtplib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from procesador import EstadoNomina, ejecutar_procesamiento

# ------------------------------------------------------------------
# Constantes de prueba
# ------------------------------------------------------------------

CURP        = "PEGJ900101HDFRZN01"
NOMBRE      = "JUAN PÉREZ GARCÍA"
NOMBRE_NORM = "JUANPEREZGARCIA"
CORREO      = "juan.perez@empresa.com"
XML_FILE    = "nomina_juan.xml"
PDF_PATH_MOCK = Path("/fake/pdfs/recibo_juan.pdf")


# ------------------------------------------------------------------
# Fixtures base
# ------------------------------------------------------------------

@pytest.fixture
def correos() -> dict[str, str]:
    return {NOMBRE_NORM: CORREO}


@pytest.fixture
def indice_pdfs(tmp_path) -> dict[str, Path]:
    pdf = tmp_path / "recibo_juan.pdf"
    pdf.write_bytes(b"%PDF mock")
    return {CURP: pdf}


@pytest.fixture(autouse=True)
def patch_xml_path(tmp_path, monkeypatch):
    """Redirige XML_PATH al directorio temporal."""
    monkeypatch.setattr("procesador.XML_PATH", tmp_path)
    return tmp_path


@pytest.fixture
def xml_valido(tmp_path) -> Path:
    """Crea un XML con la estructura CFDI válida."""
    xml = tmp_path / XML_FILE
    xml.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:nomina12="http://www.sat.gob.mx/nomina12">
  <cfdi:Receptor Nombre="{NOMBRE}"/>
  <cfdi:Complemento>
    <nomina12:Nomina>
      <nomina12:Receptor Curp="{CURP}"/>
    </nomina12:Nomina>
  </cfdi:Complemento>
</cfdi:Comprobante>""", encoding="utf-8")
    return xml


# ------------------------------------------------------------------
# Caso feliz
# ------------------------------------------------------------------

class TestCasoFeliz:

    @patch("procesador.enviar_correo")
    @patch("procesador.renombrar_pdf_seguro")
    def test_procesamiento_exitoso(
        self, mock_rename, mock_enviar, xml_valido, correos, indice_pdfs, tmp_path
    ):
        mock_rename.return_value = tmp_path / f"JUAN_PEREZ_GARCIA-{CURP}.pdf"

        resultados = ejecutar_procesamiento(correos, indice_pdfs)

        assert len(resultados) == 1
        assert resultados[0].estado == EstadoNomina.EXITOSO
        assert resultados[0].nombre == NOMBRE
        assert resultados[0].correo == CORREO
        mock_enviar.assert_called_once()

    @patch("procesador.enviar_correo")
    @patch("procesador.renombrar_pdf_seguro")
    def test_callback_de_progreso_se_llama(
        self, mock_rename, mock_enviar, xml_valido, correos, indice_pdfs, tmp_path
    ):
        mock_rename.return_value = tmp_path / "archivo.pdf"
        llamadas = []

        def on_progreso(procesados, total, resultado):
            llamadas.append((procesados, total))

        ejecutar_procesamiento(correos, indice_pdfs, on_progreso)

        assert llamadas == [(1, 1)]


# ------------------------------------------------------------------
# Ramas de error — cada una debe producir el EstadoNomina correcto
# ------------------------------------------------------------------

class TestRamasDeError:

    def test_xml_ilegible_produce_error_xml(self, tmp_path, correos, indice_pdfs):
        (tmp_path / "malformado.xml").write_text("no es xml", encoding="utf-8")

        resultados = ejecutar_procesamiento(correos, indice_pdfs)

        assert len(resultados) == 1
        assert resultados[0].estado == EstadoNomina.ERROR_XML

    def test_pdf_no_en_indice_produce_pdf_no_encontrado(
        self, xml_valido, correos
    ):
        # Índice vacío — CURP no está
        resultados = ejecutar_procesamiento(correos, indice_pdfs={})

        assert resultados[0].estado == EstadoNomina.PDF_NO_ENCONTRADO

    @patch("procesador.renombrar_pdf_seguro", side_effect=RuntimeError("Disco lleno"))
    def test_error_rename_produce_estado_correcto(
        self, mock_rename, xml_valido, correos, indice_pdfs
    ):
        resultados = ejecutar_procesamiento(correos, indice_pdfs)

        assert resultados[0].estado == EstadoNomina.ERROR_RENAME

    @patch("procesador.renombrar_pdf_seguro")
    def test_correo_no_en_excel_produce_correo_no_encontrado(
        self, mock_rename, xml_valido, indice_pdfs, tmp_path
    ):
        mock_rename.return_value = tmp_path / "archivo.pdf"
        # Diccionario de correos vacío
        resultados = ejecutar_procesamiento(correos={}, indice_pdfs=indice_pdfs)

        assert resultados[0].estado == EstadoNomina.CORREO_NO_ENCONTRADO

    @patch("procesador.enviar_correo", side_effect=smtplib.SMTPException("Timeout"))
    @patch("procesador.renombrar_pdf_seguro")
    def test_error_smtp_generico_produce_estado_correcto(
        self, mock_rename, mock_enviar, xml_valido, correos, indice_pdfs, tmp_path
    ):
        mock_rename.return_value = tmp_path / "archivo.pdf"

        resultados = ejecutar_procesamiento(correos, indice_pdfs)

        assert resultados[0].estado == EstadoNomina.ERROR_SMTP

    @patch("procesador.enviar_correo", side_effect=FileNotFoundError("PDF borrado"))
    @patch("procesador.renombrar_pdf_seguro")
    def test_archivo_no_encontrado_al_enviar(
        self, mock_rename, mock_enviar, xml_valido, correos, indice_pdfs, tmp_path
    ):
        mock_rename.return_value = tmp_path / "archivo.pdf"

        resultados = ejecutar_procesamiento(correos, indice_pdfs)

        assert resultados[0].estado == EstadoNomina.ERROR_ARCHIVO

    @patch("procesador.enviar_correo", side_effect=ValueError("Adjunto muy grande"))
    @patch("procesador.renombrar_pdf_seguro")
    def test_error_validacion_al_enviar(
        self, mock_rename, mock_enviar, xml_valido, correos, indice_pdfs, tmp_path
    ):
        mock_rename.return_value = tmp_path / "archivo.pdf"

        resultados = ejecutar_procesamiento(correos, indice_pdfs)

        assert resultados[0].estado == EstadoNomina.ERROR_VALIDACION


# ------------------------------------------------------------------
# Error fatal — SMTPAuthenticationError aborta el procesamiento
# ------------------------------------------------------------------

class TestErrorFatal:

    @patch("procesador.enviar_correo",
           side_effect=smtplib.SMTPAuthenticationError(535, b"Invalid credentials"))
    @patch("procesador.renombrar_pdf_seguro")
    def test_auth_error_aborta_procesamiento(
        self, mock_rename, mock_enviar, tmp_path, correos, indice_pdfs
    ):
        """
        Con credenciales inválidas no tiene sentido procesar más XMLs.
        El procesamiento debe detenerse tras el primer ERROR_SMTP_AUTH.
        """
        # Crear 3 XMLs — solo el primero debe procesarse
        for i in range(3):
            (tmp_path / f"nomina_{i}.xml").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:nomina12="http://www.sat.gob.mx/nomina12">
  <cfdi:Receptor Nombre="EMPLEADO {i}"/>
  <cfdi:Complemento>
    <nomina12:Nomina>
      <nomina12:Receptor Curp="EMP{i:04d}000101HDFRZN0{i}"/>
    </nomina12:Nomina>
  </cfdi:Complemento>
</cfdi:Comprobante>""", encoding="utf-8")

        mock_rename.return_value = tmp_path / "archivo.pdf"

        # Índice con los 3 CURPs
        indice = {f"EMP{i:04d}000101HDFRZN0{i}": tmp_path / f"pdf_{i}.pdf" for i in range(3)}
        for path in indice.values():
            path.write_bytes(b"%PDF mock")

        resultados = ejecutar_procesamiento(correos, indice)

        # Debe haber parado antes de procesar los 3
        auth_errors = [r for r in resultados if r.estado == EstadoNomina.ERROR_SMTP_AUTH]
        assert len(auth_errors) == 1
        assert len(resultados) < 3

    @patch("procesador.enviar_correo",
           side_effect=smtplib.SMTPAuthenticationError(535, b"Invalid credentials"))
    @patch("procesador.renombrar_pdf_seguro")
    def test_resultado_auth_error_tiene_es_error_fatal_true(
        self, mock_rename, mock_enviar, xml_valido, correos, indice_pdfs, tmp_path
    ):
        mock_rename.return_value = tmp_path / "archivo.pdf"

        resultados = ejecutar_procesamiento(correos, indice_pdfs)

        assert resultados[0].es_error_fatal is True


# ------------------------------------------------------------------
# Múltiples XMLs — conteos correctos
# ------------------------------------------------------------------

class TestMultiplesXmls:

    @patch("procesador.enviar_correo")
    @patch("procesador.renombrar_pdf_seguro")
    def test_multiples_xmls_retorna_un_resultado_por_xml(
        self, mock_rename, mock_enviar, tmp_path, indice_pdfs
    ):
        correos_multi = {}
        for i in range(3):
            curp_i = f"EMP{i:04d}000101HDFRZN0{i}"
            nombre_i = f"EMPLEADO{i}"
            correos_multi[nombre_i] = f"empleado{i}@empresa.com"
            indice_pdfs[curp_i] = tmp_path / f"pdf_{i}.pdf"
            (tmp_path / f"pdf_{i}.pdf").write_bytes(b"%PDF mock")
            mock_rename.return_value = tmp_path / f"pdf_{i}_renamed.pdf"

            (tmp_path / f"nomina_{i}.xml").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:nomina12="http://www.sat.gob.mx/nomina12">
  <cfdi:Receptor Nombre="EMPLEADO {i}"/>
  <cfdi:Complemento>
    <nomina12:Nomina>
      <nomina12:Receptor Curp="{curp_i}"/>
    </nomina12:Nomina>
  </cfdi:Complemento>
</cfdi:Comprobante>""", encoding="utf-8")

        resultados = ejecutar_procesamiento(correos_multi, indice_pdfs)

        assert len(resultados) == 3

    def test_directorio_xml_vacio_retorna_lista_vacia(self, correos, indice_pdfs):
        # tmp_path ya está vacío (no se creó ningún XML en este test)
        resultados = ejecutar_procesamiento(correos, indice_pdfs)
        assert resultados == []