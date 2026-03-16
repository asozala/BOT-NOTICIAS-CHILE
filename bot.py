"""
Bot de Monitoreo de Noticias Chile - VERSION FINAL
- Usa claude-haiku (15x mas barato que sonnet)
- Envia el reporte como mensajes de texto por WhatsApp
- Sin dependencia de servicios externos de subida
"""

import anthropic
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from twilio.rest import Client as TwilioClient

# ── Credenciales ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = os.environ["TWILIO_WHATSAPP_FROM"]
WHATSAPP_TO        = os.environ["WHATSAPP_TO"]

CHILE_TZ = ZoneInfo("America/Santiago")

# ── Prompt del sistema ────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Eres un agente de monitoreo de noticias de Chile.
Generas reportes diarios completos y verificables sobre politica y economia chilena.

FOCO PRIORITARIO:
1. Gobierno de Kast: declaraciones, anuncios, politicas, gabinete, ministros.
2. Politica nacional: Congreso, proyectos de ley, partidos politicos.
3. Economia: dolar, cobre, inflacion, Banco Central, mineria (cobre/litio).
4. Internacional con impacto en Chile: EEUU, China, commodities, region.

FUENTES: El Mercurio, La Tercera, Diario Financiero, Emol, El Mostrador,
BioBioChile, Cooperativa, T13, CNN Chile, Ex-Ante, Ciper Chile.

REGLAS CRITICAS:
- Jamas inventar noticias, citas ni fuentes.
- Solo reportar informacion verificable en medios confiables.
- Estilo claro, profesional, neutral y analitico.

ESTRUCTURA EXACTA (usa exactamente estos encabezados):

--- REPORTE NOTICIAS CHILE ---
Fecha: [fecha]  Hora: [hora] hrs

== RESUMEN EJECUTIVO ==
[6-8 lineas con los eventos mas importantes del dia]

== GOBIERNO Y POLITICA ==

[ALTA] Titular de la noticia
Que ocurrio, quien lo anuncio, contexto y consecuencias.
Fuente: [medio/s]

[MEDIA] Titular de la noticia
Descripcion breve.
Fuente: [medio/s]

== ECONOMIA ==

[ALTA] Titular
Descripcion.
Fuente: [medio/s]

Indicadores: Dolar $[val] | Cobre $[val]/lb | Petroleo $[val] | IPSA [val]

== INTERNACIONAL ==

[MEDIA] Titular
Como impacta a Chile.
Fuente: [medio/s]

--- FIN DEL REPORTE ---"""


def get_periodo():
    now = datetime.now(CHILE_TZ)
    return "MANANA" if now.hour < 13 else "TARDE"


def generate_report() -> str:
    """Genera el reporte usando Claude Haiku con busqueda web."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    now    = datetime.now(CHILE_TZ)
    fecha  = now.strftime("%d/%m/%Y")
    hora   = now.strftime("%H:%M")

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",   # Haiku: ~15x mas barato que Sonnet
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": (
                f"Genera el REPORTE DE {get_periodo()} del {fecha} a las {hora} hrs.\n\n"
                "Busca en la web las noticias mas importantes de Chile de hoy:\n"
                "1. Noticias politicas del gobierno Kast\n"
                "2. Economia chilena: dolar, cobre, mercados\n"
                "3. Congreso: proyectos y votaciones del dia\n"
                "4. Noticias internacionales que afecten a Chile\n\n"
                "Incluye todas las noticias relevantes que encuentres."
            )
        }],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text
    return text.strip()


def send_whatsapp_report(report: str, fecha: str) -> None:
    """
    Envia el reporte por WhatsApp dividido en partes de 1400 caracteres.
    Twilio Sandbox tiene limite de 1600 chars — usamos 1400 para tener margen.
    """
    twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    MAX_CHARS = 1400
    parts     = []
    lines     = report.split("\n")
    current   = ""

    # Divide por lineas para no cortar palabras a la mitad
    for line in lines:
        if len(current) + len(line) + 1 > MAX_CHARS:
            if current.strip():
                parts.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"

    if current.strip():
        parts.append(current.strip())

    total = len(parts)
    print(f"  Enviando {total} mensajes...")

    for i, part in enumerate(parts, 1):
        # Encabezado solo en el primer mensaje
        if i == 1:
            body = f"📰 *Reporte Noticias Chile*\n_{fecha}_\n\n{part}"
        else:
            body = f"📰 *[{i}/{total}]*\n\n{part}"

        twilio.messages.create(
            from_=TWILIO_FROM,
            to=WHATSAPP_TO,
            body=body,
        )
        print(f"  ✓ Mensaje {i}/{total} enviado")


def main():
    now = datetime.now(CHILE_TZ)
    print("=" * 50)
    print("  BOT NOTICIAS CHILE")
    print(f"  {now.strftime('%d/%m/%Y %H:%M')} hrs (Santiago)")
    print("=" * 50)

    fecha_display = now.strftime("%A %d de %B de %Y, %H:%M hrs")

    # 1. Generar reporte
    print("\n[1/2] Generando reporte (Claude Haiku + web)...")
    try:
        report = generate_report()
        print(f"  ✓ Reporte generado ({len(report)} caracteres)")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        sys.exit(1)

    # 2. Enviar por WhatsApp
    print("\n[2/2] Enviando por WhatsApp...")
    try:
        send_whatsapp_report(report, fecha_display)
        print("  ✓ Envio completado")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        sys.exit(1)

    print("\n✅ Bot finalizado correctamente")


if __name__ == "__main__":
    main()
