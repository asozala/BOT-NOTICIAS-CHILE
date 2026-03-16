"""
Bot de Monitoreo de Noticias Chile
Genera un PDF y lo envia por WhatsApp via Twilio.
"""

import anthropic
import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from fpdf import FPDF

ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = os.environ["TWILIO_WHATSAPP_FROM"]
WHATSAPP_TO        = os.environ["WHATSAPP_TO"]

CHILE_TZ = ZoneInfo("America/Santiago")

SYSTEM_PROMPT = """Eres un agente de monitoreo de noticias de Chile. Genera reportes diarios
completos, precisos y verificables sobre politica, economia y sociedad chilena.

FOCO:
1. Gobierno de Kast: declaraciones, anuncios, politicas, gabinete, ministros.
2. Politica nacional: Congreso, proyectos de ley, partidos.
3. Economia: dolar, cobre, inflacion, Banco Central, mineria.
4. Internacional con impacto en Chile.

FUENTES: El Mercurio, La Tercera, Diario Financiero, Emol, El Mostrador,
BioBioChile, Cooperativa, T13, CNN Chile, Ex-Ante.

REGLAS: No inventar noticias. Solo hechos verificables. Estilo neutral y analitico.
Sin limite de extension: incluye TODAS las noticias relevantes.

ESTRUCTURA:

REPORTE DIARIO - MONITOREO NOTICIAS CHILE
Fecha: [fecha]
Hora: [hora] hrs

RESUMEN EJECUTIVO
[8-12 lineas con los eventos mas importantes]

GOBIERNO Y POLITICA NACIONAL

NOTICIA: [titular]
Prioridad: ALTA
[3-5 parrafos: que ocurrio, quien declaro, contexto, relevancia, consecuencias]
Fuentes: [medios]

NOTICIA: [titular]
Prioridad: MEDIA
[descripcion]
Fuentes: [medios]

ECONOMIA Y NEGOCIOS

NOTICIA: [titular]
[descripcion]
Fuentes: [medios]

INDICADORES DEL DIA
Dolar: $[valor] pesos
Cobre: $[valor] la libra
Petroleo Brent: $[valor] USD
IPSA: [valor]
[comentario breve del mercado]

NOTICIAS INTERNACIONALES

NOTICIA: [titular]
[descripcion e impacto en Chile]
Fuentes: [medios]

FUENTES CONSULTADAS
[lista de todos los articulos usados]
"""


def get_periodo():
    now = datetime.now(CHILE_TZ)
    return "MANANA (08:00)" if now.hour < 13 else "TARDE (17:00)"


def generate_report():
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    now   = datetime.now(CHILE_TZ)
    fecha = now.strftime("%A %d de %B de %Y")
    hora  = now.strftime("%H:%M")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": (
                f"Genera el REPORTE DE {get_periodo()} del {fecha} a las {hora} hrs.\n\n"
                "Usa busqueda web para obtener TODAS las noticias relevantes de hoy en Chile.\n"
                "Busca: noticias gobierno Kast hoy, economia Chile hoy, "
                "politica chilena hoy, noticias internacionales que afecten a Chile hoy.\n"
                "No te limites en extension. Incluye todo lo relevante."
            )
        }],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text
    return text.strip()


def clean(text):
    """Convierte el texto a latin-1 para que fpdf lo pueda renderizar."""
    chars = {
        "\u2019": "'",  "\u2018": "'",  "\u201c": '"',  "\u201d": '"',
        "\u2013": "-",  "\u2014": "-",  "\u2026": "...","\u00b7": "-",
        "\u25b8": ">",  "\u2022": "*",  "\u00bb": ">>", "\u2192": "->",
        "\u00b0": " grados",
        "\u00e9": "e",  "\u00f3": "o",  "\u00ed": "i",  "\u00fa": "u",
        "\u00e1": "a",  "\u00e3": "a",  "\u00f1": "n",
        "\u00c1": "A",  "\u00c9": "E",  "\u00cd": "I",  "\u00d3": "O",
        "\u00da": "U",  "\u00d1": "N",
    }
    for orig, repl in chars.items():
        text = text.replace(orig, repl)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def create_pdf(report_text, filepath):
    """Genera un PDF simple y robusto."""
    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    now    = datetime.now(CHILE_TZ)
    page_w = 170  # ancho util: 210 - 20 - 20

    # ── Encabezado ──────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(180, 0, 0)
    pdf.cell(page_w, 10, "REPORTE NOTICIAS CHILE", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    fecha_str = clean(now.strftime("Generado el %d/%m/%Y a las %H:%M hrs  |  Santiago de Chile"))
    pdf.cell(page_w, 6, fecha_str, new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_draw_color(180, 0, 0)
    pdf.set_line_width(0.5)
    pdf.line(20, pdf.get_y() + 2, 190, pdf.get_y() + 2)
    pdf.ln(6)

    # ── Cuerpo ──────────────────────────────────────────────────────
    for raw in report_text.split("\n"):
        line = clean(raw.strip())
        if not line:
            pdf.ln(2)
            continue

        # Titulo principal
        if line.startswith("REPORTE DIARIO") or line.startswith("REPORTE DE"):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(180, 0, 0)
            pdf.multi_cell(page_w, 7, line)

        # Fecha/Hora
        elif line.startswith("Fecha:") or line.startswith("Hora:"):
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(page_w, 5, line)

        # Encabezados de seccion (TODO MAYUSCULAS)
        elif (line.isupper() and len(line) > 4
              and not line.startswith("NOTICIA")
              and not line.startswith("FUENTE")
              and not line.startswith("PRIORIDAD")):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(255, 255, 255)
            pdf.set_fill_color(180, 0, 0)
            pdf.cell(page_w, 8, "  " + line, new_x="LMARGIN", new_y="NEXT", fill=True)
            pdf.ln(2)
            pdf.set_text_color(30, 30, 30)

        # Titular de noticia
        elif line.startswith("NOTICIA:"):
            titulo = line.replace("NOTICIA:", "").strip()
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(page_w, 6, titulo)

        # Prioridad
        elif line.startswith("Prioridad:"):
            if "ALTA" in line.upper():
                pdf.set_text_color(180, 0, 0)
                label = "[ ALTA RELEVANCIA ]"
            elif "MEDIA" in line.upper():
                pdf.set_text_color(200, 100, 0)
                label = "[ RELEVANCIA MEDIA ]"
            else:
                pdf.set_text_color(60, 130, 60)
                label = "[ CONTEXTO ]"
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(page_w, 5, label, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(30, 30, 30)
            pdf.ln(1)

        # Fuentes
        elif line.startswith("Fuentes:") or line.startswith("Fuente:"):
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(120, 120, 120)
            pdf.multi_cell(page_w, 5, line)
            pdf.set_text_color(30, 30, 30)
            pdf.ln(1)

        # Indicadores de mercado
        elif any(k in line for k in ["Dolar:", "Cobre:", "Petroleo", "IPSA:"]):
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(30, 30, 30)
            pdf.set_fill_color(245, 245, 245)
            pdf.multi_cell(page_w, 6, line, fill=True)

        # Texto normal
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(page_w, 5, line)

    # ── Pie ─────────────────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_draw_color(180, 0, 0)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(page_w, 5, "Generado por Bot Noticias Chile  |  Solo uso interno", align="C")

    pdf.output(filepath)


def upload_pdf(filepath):
    """
    Sube el PDF a file.io (servicio gratuito, link valido 1 descarga / 1 dia).
    Retorna la URL publica del archivo.
    """
    with open(filepath, "rb") as f:
        r = requests.post(
            "https://file.io",
            files={"file": (os.path.basename(filepath), f, "application/pdf")},
            data={"expires": "1d"},
            timeout=60,
        )
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise Exception(f"file.io error: {data}")
    return data["link"]


def send_whatsapp(pdf_url, fecha):
    from twilio.rest import Client
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        from_=TWILIO_FROM,
        to=WHATSAPP_TO,
        media_url=[pdf_url],
        body=f"Reporte Noticias Chile\n{fecha}\n\nReporte completo adjunto. Link valido por 1 descarga.",
    )


def main():
    now = datetime.now(CHILE_TZ)
    print("=" * 55)
    print("  BOT NOTICIAS CHILE")
    print(f"  {now.strftime('%d/%m/%Y %H:%M')} hrs (Santiago)")
    print("=" * 55)

    fecha_display = clean(now.strftime("%A %d de %B de %Y, %H:%M hrs"))

    print("\n[1/3] Generando reporte...")
    try:
        report = generate_report()
        print(f"  OK ({len(report)} caracteres)")
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print("\n[2/3] Creando PDF...")
    pdf_path = f"/tmp/reporte_{now.strftime('%Y%m%d_%H%M')}.pdf"
    try:
        create_pdf(report, pdf_path)
        kb = os.path.getsize(pdf_path) // 1024
        print(f"  OK ({kb} KB)")
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print("\n[3/3] Subiendo PDF y enviando WhatsApp...")
    try:
        url = upload_pdf(pdf_path)
        print(f"  URL: {url}")
        send_whatsapp(url, fecha_display)
        print("  OK - WhatsApp enviado")
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print("\nBot finalizado correctamente.")


if __name__ == "__main__":
    main()
