"""
Bot de Monitoreo de Noticias Chile
Genera un PDF completo y lo envía por WhatsApp via Twilio.
"""

import anthropic
import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from fpdf import FPDF

# ─── Configuración ────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = os.environ["TWILIO_WHATSAPP_FROM"]
WHATSAPP_TO        = os.environ["WHATSAPP_TO"]

CHILE_TZ = ZoneInfo("America/Santiago")

# ─── Prompt del sistema ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres un agente automatizado de monitoreo y análisis de noticias sobre Chile.
Generas reportes diarios completos, precisos y verificables sobre política, economía y sociedad.

FOCO PRINCIPAL:
1. Gobierno de José Antonio Kast: declaraciones, anuncios, políticas, gabinete, ministros, Congreso.
2. Política nacional: debates legislativos, proyectos de ley, partidos, elecciones.
3. Economía chilena: crecimiento, inflación, Banco Central, minería (cobre/litio), inversión, mercados.
4. Internacional con impacto en Chile: EEUU, China, commodities, geopolítica regional.

FUENTES: El Mercurio, La Tercera, Diario Financiero, Emol, El Mostrador, BioBioChile,
Cooperativa, T13, CNN Chile, Ex-Ante, Ciper Chile, La Segunda, Radio Agricultura.

REGLAS CRÍTICAS:
- Nunca inventar noticias, citas ni fuentes.
- Solo reportar información verificable.
- Estilo: claro, profesional, neutral, analítico.
- Sin límite de extensión: incluye TODAS las noticias relevantes del período.

ESTRUCTURA OBLIGATORIA:

REPORTE DIARIO - MONITOREO NOTICIAS CHILE
Fecha: [fecha completa]
Hora: [hora] hrs

=== RESUMEN EJECUTIVO ===
[8-12 líneas explicando los eventos más importantes]

=== GOBIERNO Y POLÍTICA NACIONAL ===

[Para cada noticia:]
>> TITULAR: [título]
Prioridad: ALTA / MEDIA / CONTEXTO
[3-5 párrafos con: qué ocurrió, quién declaró, contexto, relevancia, consecuencias]
Fuentes: [medios]
---

=== ECONOMÍA Y NEGOCIOS ===

[Mismo formato]

=== INDICADORES DEL DÍA ===
Dólar: $[valor] | Cobre: $[valor] | Petróleo Brent: $[valor] | IPSA: [valor]
[Análisis breve]

=== NOTICIAS INTERNACIONALES ===

[Mismo formato]

=== FUENTES CONSULTADAS ===
[Lista de todos los medios y artículos usados]
"""


def get_periodo() -> str:
    now = datetime.now(CHILE_TZ)
    return "MAÑANA (08:00)" if now.hour < 13 else "TARDE (17:00)"


def generate_report() -> str:
    """Llama a Claude con web_search para generar el reporte completo."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    now     = datetime.now(CHILE_TZ)
    fecha   = now.strftime("%A %d de %B de %Y")
    hora    = now.strftime("%H:%M")
    periodo = get_periodo()

    user_prompt = f"""Genera el REPORTE DE {periodo} del {fecha} a las {hora} hrs (Santiago de Chile).

Usa la herramienta de búsqueda web para obtener TODAS las noticias relevantes de hoy.

Busca activamente:
- Noticias del gobierno Kast y política chilena hoy
- Economía chilena: dólar, cobre, mercados hoy
- Congreso chileno: votaciones y proyectos de ley hoy
- Noticias internacionales que impacten a Chile hoy

NO te limites en extensión. Incluye todas las noticias relevantes que encuentres.
Sigue exactamente la estructura definida."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    report_text = ""
    for block in response.content:
        if block.type == "text":
            report_text += block.text

    return report_text.strip()


def sanitize(text: str) -> str:
    """Limpia caracteres que fpdf no puede renderizar."""
    replacements = {
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00b7": "*",
        "\u25b8": ">", "\u25ba": ">", "\u2022": "*", "\u00bb": ">>",
        "\u00ab": "<<", "\u2192": "->", "\u2190": "<-",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    # Elimina cualquier caracter no-latin1
    return text.encode("latin-1", errors="replace").decode("latin-1")


def create_pdf(report_text: str, filepath: str) -> None:
    """Genera un PDF limpio y robusto con el reporte."""

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)  # left, top, right — márgenes seguros
    pdf.add_page()

    now = datetime.now(CHILE_TZ)

    # ── Portada / encabezado ──────────────────────────────────────────────────
    pdf.set_fill_color(180, 0, 0)
    pdf.rect(0, 0, 210, 22, "F")

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(15, 5)
    pdf.cell(130, 8, "REPORTE NOTICIAS CHILE", ln=0)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(15, 14)
    pdf.cell(180, 6, now.strftime("Generado el %d/%m/%Y a las %H:%M hrs  |  Santiago de Chile"), ln=0)

    pdf.set_text_color(30, 30, 30)
    pdf.set_y(28)

    # ── Cuerpo del reporte ────────────────────────────────────────────────────
    lines = report_text.split("\n")

    for raw_line in lines:
        line = sanitize(raw_line)
        stripped = line.strip()

        if not stripped:
            pdf.ln(2)
            continue

        # Título principal
        if stripped.startswith("REPORTE DIARIO") or stripped.startswith("REPORTE DE"):
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(180, 0, 0)
            pdf.multi_cell(0, 7, stripped)
            pdf.ln(1)

        # Fecha / Hora
        elif stripped.startswith("Fecha:") or stripped.startswith("Hora:"):
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 5, stripped)

        # Encabezados de sección === ... ===
        elif stripped.startswith("===") and stripped.endswith("==="):
            titulo_sec = stripped.replace("=", "").strip()
            pdf.ln(5)
            pdf.set_fill_color(240, 240, 240)
            pdf.set_draw_color(180, 0, 0)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(180, 0, 0)
            # Rectángulo de fondo
            y_pos = pdf.get_y()
            pdf.set_fill_color(240, 240, 240)
            pdf.rect(15, y_pos, 180, 8, "F")
            pdf.set_fill_color(180, 0, 0)
            pdf.rect(15, y_pos, 3, 8, "F")
            pdf.set_xy(20, y_pos)
            pdf.cell(170, 8, titulo_sec, ln=1)
            pdf.ln(2)

        # Titular de noticia >> TITULAR:
        elif stripped.startswith(">> TITULAR:") or stripped.startswith(">>TITULAR:"):
            titulo = stripped.replace(">> TITULAR:", "").replace(">>TITULAR:", "").strip()
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 6, titulo)
            pdf.ln(1)

        # Prioridad
        elif stripped.startswith("Prioridad:"):
            if "ALTA" in stripped.upper():
                pdf.set_text_color(180, 0, 0)
                label = "| ALTA RELEVANCIA"
            elif "MEDIA" in stripped.upper():
                pdf.set_text_color(200, 100, 0)
                label = "| RELEVANCIA MEDIA"
            else:
                pdf.set_text_color(60, 130, 60)
                label = "| CONTEXTO"
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(0, 5, label, ln=1)
            pdf.set_text_color(30, 30, 30)
            pdf.ln(1)

        # Fuentes
        elif stripped.startswith("Fuentes:") or stripped.startswith("Fuente:"):
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 5, stripped)
            pdf.set_text_color(30, 30, 30)

        # Separador ---
        elif stripped == "---":
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(3)

        # Indicadores de mercado
        elif stripped.startswith("Dólar:") or stripped.startswith("Dollar:"):
            pdf.set_fill_color(245, 245, 245)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 6, stripped, fill=True)

        # Texto normal
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 5, stripped)

    # ── Pie de página final ───────────────────────────────────────────────────
    pdf.ln(8)
    pdf.set_draw_color(180, 0, 0)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, "Generado automaticamente por Bot Noticias Chile  |  Solo para uso interno", align="C")

    pdf.output(filepath)


def upload_pdf(filepath: str) -> str:
    """Sube el PDF a transfer.sh y retorna la URL pública."""
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        response = requests.put(
            f"https://transfer.sh/{filename}",
            data=f,
            headers={"Max-Days": "1"},
            timeout=60,
        )
    response.raise_for_status()
    return response.text.strip()


def send_whatsapp_pdf(pdf_url: str, fecha: str) -> None:
    """Envía el PDF por WhatsApp usando Twilio."""
    from twilio.rest import Client

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        from_=TWILIO_FROM,
        to=WHATSAPP_TO,
        media_url=[pdf_url],
        body=f"Reporte Noticias Chile\n{fecha}\n\nReporte completo adjunto. Link valido 24 hrs.",
    )
    print(f"  Enviado: {pdf_url}")


def main():
    print("=" * 60)
    print("  BOT NOTICIAS CHILE")
    now = datetime.now(CHILE_TZ)
    print(f"  {now.strftime('%d/%m/%Y %H:%M')} hrs (Santiago)")
    print("=" * 60)

    fecha_display = now.strftime("%A %d de %B de %Y, %H:%M hrs")

    print("\n[1/3] Generando reporte con Claude + busqueda web...")
    try:
        report = generate_report()
        print(f"  OK - Reporte generado ({len(report)} caracteres)")
    except Exception as e:
        print(f"  ERROR generando reporte: {e}")
        sys.exit(1)

    print("\n[2/3] Creando PDF...")
    pdf_path = f"/tmp/reporte_chile_{now.strftime('%Y%m%d_%H%M')}.pdf"
    try:
        create_pdf(report, pdf_path)
        size_kb = os.path.getsize(pdf_path) // 1024
        print(f"  OK - PDF creado ({size_kb} KB)")
    except Exception as e:
        print(f"  ERROR creando PDF: {e}")
        sys.exit(1)

    print("\n[3/3] Subiendo PDF y enviando por WhatsApp...")
    try:
        pdf_url = upload_pdf(pdf_path)
        print(f"  OK - PDF subido: {pdf_url}")
        send_whatsapp_pdf(pdf_url, fecha_display)
        print("  OK - WhatsApp enviado")
    except Exception as e:
        print(f"  ERROR enviando: {e}")
        sys.exit(1)

    print("\nBot finalizado exitosamente")


if __name__ == "__main__":
    main()
