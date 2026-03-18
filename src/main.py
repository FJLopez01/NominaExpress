"""
main.py — Modo CLI para procesamiento de nóminas.

Uso:
    python main.py

Alternativa recomendada para uso diario:
    streamlit run app.py
"""

from procesador import (
    EstadoNomina,
    ResultadoNomina,
    construir_indice_pdfs,
    ejecutar_procesamiento,
    leer_correos_excel,
)


def on_progreso(procesados: int, total: int, resultado: ResultadoNomina) -> None:
    """Imprime el progreso en consola después de cada XML."""
    icono = "✅" if resultado.exitoso else ("⚠️" if resultado.estado in {
        EstadoNomina.PDF_NO_ENCONTRADO,
        EstadoNomina.CORREO_NO_ENCONTRADO,
    } else "❌")
    print(f"  [{procesados}/{total}] {icono} {resultado.mensaje}")


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Cargar datos — una sola vez antes del procesamiento
    # ------------------------------------------------------------------
    print("📧 Cargando base de correos...")
    correos_por_nombre = leer_correos_excel()
    print(f"   {len(correos_por_nombre)} registros cargados.")

    print("📂 Indexando PDFs...")
    indice_pdfs = construir_indice_pdfs()
    print(f"   {len(indice_pdfs)} PDFs indexados.")

    # ------------------------------------------------------------------
    # 2. Ejecutar procesamiento — lógica pura en procesador.py
    # ------------------------------------------------------------------
    print("\n🚀 Iniciando procesamiento...\n")

    resultados = ejecutar_procesamiento(correos_por_nombre, indice_pdfs, on_progreso)

    # ------------------------------------------------------------------
    # 3. Detectar error fatal
    # ------------------------------------------------------------------
    if any(r.estado == EstadoNomina.ERROR_SMTP_AUTH for r in resultados):
        print("\n🔐 Error de autenticación con Gmail.")
        print("   Verifica EMAIL_SENDER y EMAIL_PASSWORD en tu archivo .env")
        raise SystemExit(1)

    # ------------------------------------------------------------------
    # 4. Resumen final
    # ------------------------------------------------------------------
    total    = len(resultados)
    exitosos = sum(1 for r in resultados if r.exitoso)
    errores  = total - exitosos

    print(f"\n{'─' * 40}")
    print(f"📊 Resumen:")
    print(f"   Total:       {total}")
    print(f"   ✅ Exitosos: {exitosos}")
    print(f"   ❌ Errores:  {errores}")
    print(f"{'─' * 40}")

    if errores > 0:
        raise SystemExit(1)  # Exit code no-cero para scripts/CI


if __name__ == "__main__":
    main()