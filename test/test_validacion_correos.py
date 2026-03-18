"""
tests/test_validacion_correos.py

Cobertura de _es_correo_valido() y la validación integrada
en leer_correos_excel().

Ejecutar:
    pytest tests/test_validacion_correos.py -v
"""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from procesador import _es_correo_valido, leer_correos_excel


# ------------------------------------------------------------------
# Tests de _es_correo_valido
# ------------------------------------------------------------------

class TestEsCorreoValido:

    @pytest.mark.parametrize("correo", [
        "juan.perez@empresa.com",
        "maria.lopez@gmail.com",
        "empleado+nomina@corporativo.com.mx",
        "a@b.co",
        "user123@dominio.org",
    ])
    def test_correos_validos(self, correo):
        assert _es_correo_valido(correo) is True

    @pytest.mark.parametrize("correo", [
        "",                         # Vacío
        "   ",                      # Solo espacios
        "sin_arroba",               # Sin @
        "sin_dominio@",             # Sin dominio
        "@sin_usuario.com",         # Sin usuario
        "dos@@arrobas.com",         # Doble @
        "con espacios@dominio.com", # Espacios
        "juan.perezempresa.com",    # Falta @
        "nan",                      # Pandas NaN convertido a string
    ])
    def test_correos_invalidos(self, correo):
        assert _es_correo_valido(correo) is False


# ------------------------------------------------------------------
# Tests de leer_correos_excel con validación integrada
# ------------------------------------------------------------------

class TestLeerCorreosExcelValidacion:

    def _crear_excel(self, tmp_path: Path, filas: list[dict]) -> Path:
        ruta = tmp_path / "correos.xlsx"
        pd.DataFrame(filas).to_excel(ruta, index=False)
        return ruta

    @patch("procesador.EXCEL_CORREOS")
    def test_excluye_correos_invalidos_sin_crash(self, mock_path, tmp_path):
        ruta = self._crear_excel(tmp_path, [
            {"Nombre": "JUAN PEREZ",  "Correo": "juan@empresa.com"},    # válido
            {"Nombre": "MARIA LOPEZ", "Correo": "correo_sin_arroba"},   # inválido
            {"Nombre": "CARLOS RUIZ", "Correo": ""},                    # vacío
        ])
        mock_path.__str__ = lambda s: str(ruta)
        mock_path.__fspath__ = lambda s: str(ruta)

        with patch("procesador.EXCEL_CORREOS", ruta):
            resultado = leer_correos_excel()

        # Solo el válido debe aparecer
        assert len(resultado) == 1
        assert "JUANPEREZ" in resultado

    @patch("procesador.EXCEL_CORREOS")
    def test_todos_validos_retorna_todos(self, mock_path, tmp_path):
        ruta = self._crear_excel(tmp_path, [
            {"Nombre": "JUAN PEREZ",   "Correo": "juan@empresa.com"},
            {"Nombre": "MARIA LOPEZ",  "Correo": "maria@empresa.com"},
        ])
        with patch("procesador.EXCEL_CORREOS", ruta):
            resultado = leer_correos_excel()

        assert len(resultado) == 2

    @patch("procesador.EXCEL_CORREOS")
    def test_correos_invalidos_generan_warning_en_log(self, mock_path, tmp_path, caplog):
        import logging
        ruta = self._crear_excel(tmp_path, [
            {"Nombre": "JUAN PEREZ",  "Correo": "juan@empresa.com"},
            {"Nombre": "MARIA LOPEZ", "Correo": "no_es_correo"},
        ])
        with patch("procesador.EXCEL_CORREOS", ruta):
            with caplog.at_level(logging.WARNING, logger="nominas"):
                leer_correos_excel()

        assert any("inválido" in msg.lower() or "invalido" in msg.lower()
                   for msg in caplog.messages)

    @patch("procesador.EXCEL_CORREOS")
    def test_columnas_faltantes_lanza_value_error(self, mock_path, tmp_path):
        ruta = self._crear_excel(tmp_path, [
            {"nombre_empleado": "JUAN", "email": "juan@empresa.com"},  # columnas incorrectas
        ])
        with patch("procesador.EXCEL_CORREOS", ruta):
            with pytest.raises(ValueError, match="Columnas faltantes"):
                leer_correos_excel()

    @patch("procesador.EXCEL_CORREOS")
    def test_correo_con_espacios_extremos_se_normaliza(self, mock_path, tmp_path):
        ruta = self._crear_excel(tmp_path, [
            {"Nombre": "JUAN PEREZ", "Correo": "  juan@empresa.com  "},
        ])
        with patch("procesador.EXCEL_CORREOS", ruta):
            resultado = leer_correos_excel()

        assert resultado.get("JUANPEREZ") == "juan@empresa.com"