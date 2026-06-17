"""
main.py — Modo CLI para procesamiento de nóminas.

Útil para automatización o ejecución programada (tarea de Windows, cron).

Uso:
    python src/main.py

Alternativa recomendada para uso diario con interfaz visual:
    streamlit run src/app.py
"""

from database import inicializar_db
from procesador import (
    EstadoNomina,
    ResultadoNomina,
    construir_indice_pdfs,
    ejecutar_procesamiento,
    leer_correos_excel,
)


def on_progreso(procesados: int, total: int, resultado: ResultadoNomina) -> None:
    """Imprime el progreso en consola después de cada XML."""
    if resultado.estado == EstadoNomina.EXITOSO:
        icono = "✅"
    elif resultado.estado == EstadoNomina.YA_ENVIADO:
        icono = "⏭️"
    elif resultado.estado in {
        EstadoNomina.PDF_NO_ENCONTRADO,
        EstadoNomina.CORREO_NO_ENCONTRADO,
    }:
        icono = "⚠️"
    else:
        icono = "❌"

    print(f"  [{procesados}/{total}] {icono} {resultado.mensaje}")


def main() -> None:
    # Inicializar BD (idempotente — crea el esquema si no existe)
    inicializar_db()

    # 1. Cargar datos — una sola vez antes del procesamiento
    print("📧 Cargando base de correos...")
    correos_por_nombre = leer_correos_excel()
    print(f"   {len(correos_por_nombre)} registros cargados.")

    print("📂 Indexando PDFs...")
    indice_pdfs = construir_indice_pdfs()
    print(f"   {len(indice_pdfs)} PDFs indexados.")

    # 2. Ejecutar procesamiento
    print("\n🚀 Iniciando procesamiento...\n")
    resultados = ejecutar_procesamiento(correos_por_nombre, indice_pdfs, on_progreso)

    # 3. Detectar error fatal de autenticación
    if any(r.estado == EstadoNomina.ERROR_AUTH_GRAPH for r in resultados):
        print("\n🔐 Error de autenticación con Azure AD.")
        print("   Verifica AZURE_TENANT_ID, AZURE_CLIENT_ID y AZURE_CLIENT_SECRET en .env")
        print("   Consulta la guía en docs/configurar_azure_ad.md")
        raise SystemExit(1)

    # 4. Resumen final
    total     = len(resultados)
    enviados  = sum(1 for r in resultados if r.estado == EstadoNomina.EXITOSO)
    omitidos  = sum(1 for r in resultados if r.estado == EstadoNomina.YA_ENVIADO)
    errores   = sum(1 for r in resultados if not r.exitoso)

    print(f"\n{'─' * 45}")
    print(f"📊 Resumen:")
    print(f"   Total procesados:  {total}")
    print(f"   ✅ Enviados:       {enviados}")
    print(f"   ⏭️  Ya enviados:    {omitidos}  (omitidos — idempotencia)")
    print(f"   ❌ Errores:        {errores}")
    print(f"{'─' * 45}")

    if errores > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()