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
Hora: [hora] hrs | Período: [mañana/tarde]

RESUMEN EJECUTIVO
[8-12 líneas explicando los eventos más importantes del período]

GOBIERNO Y POLÍTICA NACIONAL

[Para cada noticia:]
[PRIORIDAD: ALTA / MEDIA / CONTEXTO]
TITULAR: [título de la noticia]
[3-5 párrafos con: qué ocurrió, quién declaró, contexto político, relevancia, consecuencias posibles]
Fuentes: [medios que lo reportaron]
---

ECONOMÍA Y NEGOCIOS

[Mismo formato, todas las noticias económicas relevantes]

INDICADORES DEL DÍA
Dólar: $[valor] pesos | Variación: [%]
Cobre: $[valor] la libra | Variación: [%]
Petróleo Brent: $[valor] USD/barril
Bolsa (IPSA): [valor] | Variación: [%]
[Análisis breve de los mercados]

NOTICIAS INTERNACIONALES CON IMPACTO EN CHILE

[Mismo formato, enfocado en cómo afectan a Chile]

ACTIVIDAD EN REDES SOCIALES
[Solo si hay declaraciones relevantes de figuras públicas verificadas]

ANEXO DE FUENTES
[Lista completa de todas las fuentes utilizadas con sus titulares]
"""


def get_periodo() -> str:
    now = datetime.now(CHILE_TZ)
    return "MAÑANA (08:00)" if now.hour < 13 else "TARDE (17:00)"


def generate_report() -> str:
    """Llama a la API de Claude con web_search para generar el reporte completo."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    now     = datetime.now(CHILE_TZ)
    fecha   = now.strftime("%A %d de %B de %Y")
    hora    = now.strftime("%H:%M")
    periodo = get_periodo()

    user_prompt = f"""Genera el REPORTE DE {periodo} del {fecha} a las {hora} hrs (Santiago de Chile).

USA la herramienta de búsqueda web extensivamente para obtener TODAS las noticias relevantes de hoy.

Realiza búsquedas específicas en:
- "Chile noticias gobierno Kast hoy"
- "Chile política congreso hoy {fecha}"
- "Chile economía dólar cobre hoy"
- "Chile noticias {fecha}"
- Emol, La Tercera, Cooperativa, Diario Financiero noticias del día
- Noticias internacionales que impacten a Chile (guerra Medio Oriente, EEUU aranceles, precio cobre)

NO te limites en extensión. Incluye TODAS las noticias relevantes que encuentres.
Para cada noticia importante escribe al menos 3 párrafos de contexto y análisis.
Sigue exactamente la estructura definida en el sistema."""

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


def create_pdf(report_text: str, filepath: str) -> None:
    """Genera un PDF bien formateado con el reporte completo."""

    class PDF(FPDF):
        def header(self):
            # Franja superior roja
            self.set_fill_color(180, 0, 0)
            self.rect(0, 0, 210, 18, 'F')
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(255, 255, 255)
            self.set_xy(10, 4)
            self.cell(0, 10, "REPORTE NOTICIAS CHILE", align="L")
            now = datetime.now(CHILE_TZ)
            self.set_font("Helvetica", "", 9)
            self.set_xy(10, 4)
            self.cell(0, 10, now.strftime("%d/%m/%Y  %H:%M hrs"), align="R")
            self.ln(14)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"Generado automáticamente por Bot Noticias Chile  |  Página {self.page_no()}", align="C")

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(14, 22, 14)

    # Paleta de colores
    COLOR_TITULO    = (180, 0, 0)
    COLOR_SECCION   = (220, 40, 40)
    COLOR_ALTA      = (200, 30, 30)
    COLOR_MEDIA     = (210, 120, 0)
    COLOR_CONTEXTO  = (60, 130, 60)
    COLOR_TEXTO     = (30, 30, 30)
    COLOR_GRIS      = (100, 100, 100)
    COLOR_FONDO_SEC = (245, 245, 245)

    lines = report_text.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            pdf.ln(2)
            continue

        # Título principal del reporte
        if stripped.startswith("REPORTE DIARIO") or stripped.startswith("REPORTE DE"):
            pdf.set_font("Helvetica", "B", 15)
            r, g, b = COLOR_TITULO
            pdf.set_text_color(r, g, b)
            pdf.multi_cell(0, 8, stripped)
            pdf.ln(1)

        # Fecha / Hora / Período
        elif stripped.startswith("Fecha:") or stripped.startswith("Hora:"):
            pdf.set_font("Helvetica", "", 9)
            r, g, b = COLOR_GRIS
            pdf.set_text_color(r, g, b)
            pdf.multi_cell(0, 5, stripped)

        # Encabezados de sección (todo mayúsculas)
        elif stripped.isupper() and len(stripped) > 4 and not stripped.startswith("---"):
            pdf.ln(4)
            # Fondo gris claro
            x, y = pdf.get_x(), pdf.get_y()
            pdf.set_fill_color(*COLOR_FONDO_SEC)
            pdf.rect(14, y, 182, 8, 'F')
            # Barra roja izquierda
            pdf.set_fill_color(*COLOR_SECCION)
            pdf.rect(14, y, 3, 8, 'F')
            pdf.set_font("Helvetica", "B", 10)
            r, g, b = COLOR_SECCION
            pdf.set_text_color(r, g, b)
            pdf.set_x(20)
            pdf.cell(0, 8, stripped)
            pdf.ln(6)

        # Etiquetas de prioridad
        elif stripped.startswith("PRIORIDAD:") or stripped.startswith("[PRIORIDAD"):
            if "ALTA" in stripped.upper():
                r, g, b = COLOR_ALTA
                label = "● ALTA RELEVANCIA"
            elif "MEDIA" in stripped.upper():
                r, g, b = COLOR_MEDIA
                label = "● RELEVANCIA MEDIA"
            else:
                r, g, b = COLOR_CONTEXTO
                label = "● CONTEXTO"
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(r, g, b)
            pdf.cell(0, 5, label)
            pdf.ln(4)

        # Titular de noticia
        elif stripped.startswith("TITULAR:"):
            titulo = stripped.replace("TITULAR:", "").strip()
            pdf.set_font("Helvetica", "B", 11)
            r, g, b = COLOR_TEXTO
            pdf.set_text_color(r, g, b)
            pdf.multi_cell(0, 6, titulo)
            pdf.ln(1)

        # Fuentes
        elif stripped.startswith("Fuentes:") or stripped.startswith("Fuente:"):
            pdf.set_font("Helvetica", "I", 8)
            r, g, b = COLOR_GRIS
            pdf.set_text_color(r, g, b)
            pdf.multi_cell(0, 5, stripped)
            pdf.ln(1)

        # Separador
        elif stripped == "---":
            pdf.ln(2)
            pdf.set_draw_color(220, 220, 220)
            pdf.line(14, pdf.get_y(), 196, pdf.get_y())
            pdf.ln(3)

        # Indicadores de mercado (líneas con |)
        elif "|" in stripped and any(k in stripped for k in ["Dólar", "Cobre", "Petróleo", "Bolsa", "IPSA"]):
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(240, 240, 240)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 6, stripped, fill=True)

        # Texto normal
        else:
            pdf.set_font("Helvetica", "", 9)
            r, g, b = COLOR_TEXTO
            pdf.set_text_color(r, g, b)
            pdf.multi_cell(0, 5, stripped)

    pdf.output(filepath)


def upload_pdf(filepath: str) -> str:
    """Sube el PDF a transfer.sh y retorna la URL pública."""
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        response = requests.put(
            f"https://transfer.sh/{filename}",
            data=f,
            headers={
                "Max-Days": "1",
                "Max-Downloads": "5",
            },
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
        body=f"📰 *Reporte Noticias Chile*\n{fecha}\n\nReporte completo adjunto. Disponible por 24 hrs.",
    )
    print(f"  ✓ PDF enviado: {pdf_url}")


def main():
    print("=" * 60)
    print("  BOT NOTICIAS CHILE")
    now = datetime.now(CHILE_TZ)
    print(f"  {now.strftime('%d/%m/%Y %H:%M')} hrs (Santiago)")
    print("=" * 60)

    fecha_display = now.strftime("%A %d de %B de %Y, %H:%M hrs")

    # 1. Generar reporte
    print("\n[1/3] Generando reporte con Claude + búsqueda web...")
    try:
        report = generate_report()
        print(f"  ✓ Reporte generado ({len(report)} caracteres)")
    except Exception as e:
        print(f"  ✗ Error generando reporte: {e}")
        sys.exit(1)

    # 2. Crear PDF
    print("\n[2/3] Creando PDF...")
    pdf_path = f"/tmp/reporte_chile_{now.strftime('%Y%m%d_%H%M')}.pdf"
    try:
        create_pdf(report, pdf_path)
        size_kb = os.path.getsize(pdf_path) // 1024
        print(f"  ✓ PDF creado: {pdf_path} ({size_kb} KB)")
    except Exception as e:
        print(f"  ✗ Error creando PDF: {e}")
        sys.exit(1)

    # 3. Subir y enviar
    print("\n[3/3] Subiendo PDF y enviando por WhatsApp...")
    try:
        pdf_url = upload_pdf(pdf_path)
        print(f"  ✓ PDF subido: {pdf_url}")
        send_whatsapp_pdf(pdf_url, fecha_display)
    except Exception as e:
        print(f"  ✗ Error enviando: {e}")
        sys.exit(1)

    print("\n✅ Bot finalizado exitosamente")


if __name__ == "__main__":
    main()
