"""
tests/test_procesador_rename.py

Cobertura de renombrar_pdf_seguro():
- Caso feliz: renombra correctamente y borra el original.
- Idempotencia: si el destino ya existe, no hace nada.
- Origen desaparecido: falla con FileNotFoundError claro.
- Crash en copia: el original sobrevive, la copia parcial se limpia.
- Copia vacía: detecta corrupción antes de borrar el original.

Ejecutar:
    pytest tests/test_procesador_rename.py -v
"""

from pathlib import Path
from unittest.mock import patch

import pytest

# La función se importa directamente para testearla sin depender
# de la configuración completa del proyecto.
from procesador import renombrar_pdf_seguro


@pytest.fixture
def pdf_original(tmp_path: Path) -> Path:
    """PDF de prueba con contenido mínimo válido."""
    f = tmp_path / "recibo_original.pdf"
    f.write_bytes(b"%PDF-1.4 contenido de prueba")
    return f


@pytest.fixture(autouse=True)
def patch_pdf_path(tmp_path: Path, monkeypatch):
    """
    Redirige PDF_PATH al directorio temporal para que los tests
    no escriban en el sistema de archivos real del proyecto.
    """
    monkeypatch.setattr("procesador.PDF_PATH", tmp_path)


class TestRenombrarPdfSeguro:

    def test_caso_feliz_renombra_y_borra_original(self, pdf_original):
        nuevo = renombrar_pdf_seguro(
            origen=str(pdf_original),
            nombre_limpio="JUAN_PEREZ_GARCIA",
            curp="PEGJ900101HDFRZN01",
        )

        assert nuevo.exists(), "El archivo destino debe existir"
        assert nuevo.name == "JUAN_PEREZ_GARCIA-PEGJ900101HDFRZN01.pdf"
        assert not pdf_original.exists(), "El original debe haber sido eliminado"

    def test_contenido_preservado(self, pdf_original):
        contenido_original = pdf_original.read_bytes()
        nuevo = renombrar_pdf_seguro(str(pdf_original), "EMPLEADO", "CURP123")
        assert nuevo.read_bytes() == contenido_original

    def test_idempotente_si_destino_ya_existe(self, pdf_original, tmp_path):
        """
        Si el destino ya existe (ejecución anterior completada),
        debe retornar la ruta existente sin tocar nada.
        """
        destino_existente = tmp_path / "EMPLEADO-CURP123.pdf"
        destino_existente.write_bytes(b"contenido previo")

        resultado = renombrar_pdf_seguro(str(pdf_original), "EMPLEADO", "CURP123")

        assert resultado == destino_existente
        assert resultado.read_bytes() == b"contenido previo"  # No sobreescribió
        assert pdf_original.exists()  # El original sigue intacto

    def test_origen_inexistente_lanza_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="ya no existe"):
            renombrar_pdf_seguro(
                str(tmp_path / "fantasma.pdf"),
                "EMPLEADO",
                "CURP123",
            )

    def test_crash_en_copia_limpia_archivo_parcial(self, pdf_original, tmp_path):
        """
        Simula un crash (IOError) durante shutil.copy2.
        El archivo destino parcial debe ser eliminado.
        El original debe sobrevivir intacto.
        """
        with patch("procesador.shutil.copy2", side_effect=IOError("Disco lleno")):
            with pytest.raises(RuntimeError, match="original no fue modificado"):
                renombrar_pdf_seguro(str(pdf_original), "EMPLEADO", "CURP123")

        destino = tmp_path / "EMPLEADO-CURP123.pdf"
        assert not destino.exists(), "No debe quedar archivo parcial"
        assert pdf_original.exists(), "El original debe sobrevivir"

    def test_copia_vacia_no_borra_original(self, pdf_original, tmp_path):
        """
        Simula corrupción silenciosa: copy2 no lanza excepción
        pero genera un archivo de 0 bytes.
        La función debe detectarlo y no borrar el original.
        """
        def copy2_corrupto(src, dst):
            Path(dst).write_bytes(b"")  # Copia vacía

        with patch("procesador.shutil.copy2", side_effect=copy2_corrupto):
            with pytest.raises(RuntimeError, match="vacía"):
                renombrar_pdf_seguro(str(pdf_original), "EMPLEADO", "CURP123")

        assert pdf_original.exists(), "El original debe sobrevivir ante copia vacía"