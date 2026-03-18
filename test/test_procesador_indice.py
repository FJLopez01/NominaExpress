"""
tests/test_procesador_indice.py

Cobertura de construir_indice_pdfs():
- Indexa correctamente un PDF con CURP válido.
- Ignora archivos que no son .pdf.
- Omite PDFs sin CURP reconocible (sin crash).
- Maneja PDFs corruptos sin detener el indexado.
- Detecta y reporta CURPs duplicados entre archivos.
- Verifica que cada PDF se lee exactamente una vez (garantía O(n)).

Ejecutar:
    pytest tests/test_procesador_indice.py -v
"""

from pathlib import Path
from unittest.mock import call, patch, MagicMock

import pytest

from procesador import construir_indice_pdfs, _extraer_texto_pdf

# CURP de prueba con formato oficial válido
CURP_VALIDO = "PEGJ900101HDFRZN01"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def crear_pdf_con_texto(directorio: Path, nombre: str, contenido: str) -> Path:
    """
    Crea un archivo .pdf ficticio cuyo texto extraído será `contenido`.
    No genera un PDF real — mockea PdfReader para devolver el texto dado.
    """
    pdf = directorio / nombre
    pdf.write_bytes(b"%PDF-1.4 mock")
    return pdf


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_pdf_path(tmp_path, monkeypatch):
    monkeypatch.setattr("procesador.PDF_PATH", tmp_path)
    return tmp_path


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestConstruirIndicePdfs:

    def test_indexa_pdf_con_curp_valido(self, tmp_path):
        pdf = tmp_path / "recibo.pdf"
        pdf.write_bytes(b"%PDF mock")

        with patch("procesador._extraer_texto_pdf", return_value=f"Datos del empleado {CURP_VALIDO} más texto"):
            indice = construir_indice_pdfs()

        assert CURP_VALIDO in indice
        assert indice[CURP_VALIDO] == pdf

    def test_ignora_archivos_no_pdf(self, tmp_path):
        (tmp_path / "documento.docx").write_bytes(b"no es pdf")
        (tmp_path / "datos.xlsx").write_bytes(b"tampoco")

        with patch("procesador._extraer_texto_pdf", return_value="") as mock_extraer:
            indice = construir_indice_pdfs()

        mock_extraer.assert_not_called()
        assert len(indice) == 0

    def test_omite_pdf_sin_curp_sin_crash(self, tmp_path):
        pdf = tmp_path / "portada.pdf"
        pdf.write_bytes(b"%PDF mock")

        with patch("procesador._extraer_texto_pdf", return_value="Sin CURP aquí"):
            indice = construir_indice_pdfs()

        assert len(indice) == 0

    def test_omite_pdf_corrupto_sin_detener_indexado(self, tmp_path):
        pdf_bueno = tmp_path / "bueno.pdf"
        pdf_malo = tmp_path / "corrupto.pdf"
        pdf_bueno.write_bytes(b"%PDF mock")
        pdf_malo.write_bytes(b"datos corruptos")

        def extraer_segun_archivo(ruta):
            if ruta.name == "corrupto.pdf":
                raise Exception("PDF dañado")
            return f"Empleado {CURP_VALIDO}"

        with patch("procesador._extraer_texto_pdf", side_effect=extraer_segun_archivo):
            indice = construir_indice_pdfs()

        # El bueno se indexó, el malo se saltó sin crash
        assert CURP_VALIDO in indice
        assert len(indice) == 1

    def test_detecta_curp_duplicado_entre_pdfs(self, tmp_path, capsys):
        pdf1 = tmp_path / "recibo1.pdf"
        pdf2 = tmp_path / "recibo2.pdf"
        pdf1.write_bytes(b"%PDF mock")
        pdf2.write_bytes(b"%PDF mock")

        with patch("procesador._extraer_texto_pdf", return_value=f"Empleado {CURP_VALIDO}"):
            indice = construir_indice_pdfs()

        # Solo uno de los dos debe estar en el índice
        assert len(indice) == 1
        assert CURP_VALIDO in indice

        # Debe haber advertido sobre el duplicado
        salida = capsys.readouterr().out
        assert "duplicado" in salida.lower()

    def test_cada_pdf_se_lee_exactamente_una_vez(self, tmp_path):
        """
        Garantía de complejidad O(n): _extraer_texto_pdf debe llamarse
        exactamente N veces para N PDFs, sin importar cuántos XMLs
        haya que procesar después.
        """
        for i in range(5):
            (tmp_path / f"recibo_{i}.pdf").write_bytes(b"%PDF mock")

        with patch("procesador._extraer_texto_pdf", return_value="sin curp") as mock_extraer:
            construir_indice_pdfs()

        assert mock_extraer.call_count == 5

    def test_directorio_vacio_retorna_indice_vacio(self, tmp_path):
        indice = construir_indice_pdfs()
        assert indice == {}


class TestExtraerTextoPdf:

    def test_concatena_texto_de_todas_las_paginas(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF mock")

        pagina1 = MagicMock()
        pagina1.extract_text.return_value = "Página uno"
        pagina2 = MagicMock()
        pagina2.extract_text.return_value = "Página dos"

        mock_reader = MagicMock()
        mock_reader.pages = [pagina1, pagina2]

        with patch("procesador.PdfReader", return_value=mock_reader):
            resultado = _extraer_texto_pdf(pdf)

        assert "Página uno" in resultado
        assert "Página dos" in resultado

    def test_pagina_sin_texto_no_falla(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF mock")

        pagina = MagicMock()
        pagina.extract_text.return_value = None  # PyPDF2 puede retornar None

        mock_reader = MagicMock()
        mock_reader.pages = [pagina]

        with patch("procesador.PdfReader", return_value=mock_reader):
            resultado = _extraer_texto_pdf(pdf)

        assert resultado == ""