"""
Bot de Monitoreo de Noticias Chile
Genera reportes automáticos 2x por día y los envía por WhatsApp via Twilio.
"""

import anthropic
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

# ─── Configuración ────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY   = os.environ["ANTHROPIC_API_KEY"]
TWILIO_ACCOUNT_SID  = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN   = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM         = os.environ["TWILIO_WHATSAPP_FROM"]   # "whatsapp:+14155238886"
WHATSAPP_TO         = os.environ["WHATSAPP_TO"]             # "whatsapp:+56912345678"

CHILE_TZ = ZoneInfo("America/Santiago")

# ─── Prompt del sistema ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres un agente automatizado de monitoreo y análisis de noticias sobre Chile.
Tu función es revisar, analizar y sintetizar información de múltiples fuentes confiables y generar
reportes claros y completos.

Tu objetivo es entregar un informe diario preciso, verificable y sin información inventada sobre los
principales eventos políticos, económicos y sociales relevantes para Chile.

FOCO PRINCIPAL:
1. Gobierno de José Antonio Kast: declaraciones, anuncios, políticas, cambios de gabinete, ministros.
2. Política nacional: debates legislativos, proyectos de ley, conflictos políticos.
3. Economía: crecimiento, inflación, Banco Central, reformas tributarias, minería (cobre/litio).
4. Internacional con impacto en Chile: decisiones de EEUU/China, precios commodities, geopolítica.

FUENTES A CONSULTAR: El Mercurio, La Tercera, Diario Financiero, Emol, El Mostrador, BioBioChile,
Cooperativa, T13, CNN Chile, Ex-Ante, Ciper Chile, La Segunda, Radio Agricultura.

REGLAS CRÍTICAS:
- Nunca inventar noticias, citas ni fuentes.
- Solo reportar información verificable en medios confiables.
- Estilo: claro, profesional, neutral, analítico.

ESTRUCTURA OBLIGATORIA DEL REPORTE (usa exactamente estos encabezados):

📋 REPORTE DIARIO – MONITOREO NOTICIAS CHILE
Fecha: [fecha]
Hora: [hora] hrs

📌 RESUMEN EJECUTIVO
[5-8 líneas con los eventos más importantes]

🔴 PRINCIPALES NOTICIAS

[Para cada noticia (máx 7):]
[N°] [PRIORIDAD: 🔴Alta / 🟡Media / 🟢Contexto] TITULAR
▸ [Descripción: qué ocurrió, quién, contexto, relevancia, consecuencias]
▸ Fuente: [medio/s]

🌐 INTERNACIONAL RELEVANTE PARA CHILE

[Mismo formato, máx 3 noticias]

⚠️ ALERTA DE MERCADOS
Dólar: $[valor] | Cobre: $[valor] | Petróleo Brent: $[valor]
[Una línea de contexto si hay movimientos relevantes]
"""


def get_report_type() -> str:
    """Determina si es reporte de mañana o tarde según la hora en Chile."""
    now = datetime.now(CHILE_TZ)
    return "mañana (08:00)" if now.hour < 13 else "tarde (17:00)"


def generate_report() -> str:
    """Llama a la API de Claude con web_search para generar el reporte."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    now       = datetime.now(CHILE_TZ)
    fecha     = now.strftime("%A %d de %B de %Y")
    hora      = now.strftime("%H:%M")
    tipo      = get_report_type()

    user_prompt = f"""Genera el REPORTE DE {tipo.upper()} del {fecha} a las {hora} hrs (hora Santiago).

Usa la herramienta de búsqueda web para obtener las noticias más recientes de hoy sobre Chile.
Busca en múltiples fuentes chilenas: Emol, La Tercera, Cooperativa, El Mostrador, Diario Financiero,
BioBioChile, T13, Ex-Ante, CNN Chile.

Busca específicamente:
1. Noticias del gobierno de Kast (declaraciones, anuncios, medidas económicas)
2. Debates en el Congreso (proyectos de ley, votaciones)
3. Indicadores económicos del día (dólar, cobre, petróleo, inflación)
4. Noticias internacionales con impacto en Chile (especialmente conflicto Medio Oriente y precios commodities)

Sigue exactamente la estructura del reporte definida en el sistema.
Incluye solo hechos verificables. Sé preciso con cifras y nombres."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extrae solo los bloques de texto de la respuesta
    report_text = ""
    for block in response.content:
        if block.type == "text":
            report_text += block.text

    return report_text.strip()


def send_whatsapp(message: str) -> None:
    """Envía el reporte por WhatsApp usando Twilio."""
    from twilio.rest import Client

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    # WhatsApp tiene límite de 4096 caracteres por mensaje.
    # Si el reporte es más largo, lo dividimos en partes.
    MAX_LEN = 4000
    parts = [message[i:i+MAX_LEN] for i in range(0, len(message), MAX_LEN)]

    total = len(parts)
    for idx, part in enumerate(parts, 1):
        prefix = f"📰 *Parte {idx}/{total}*\n\n" if total > 1 else ""
        client.messages.create(
            from_=TWILIO_FROM,
            to=WHATSAPP_TO,
            body=prefix + part,
        )
        print(f"  ✓ Mensaje {idx}/{total} enviado")


def main():
    print("=" * 60)
    print("  BOT NOTICIAS CHILE")
    now = datetime.now(CHILE_TZ)
    print(f"  {now.strftime('%d/%m/%Y %H:%M')} hrs (Santiago)")
    print("=" * 60)

    print("\n[1/2] Generando reporte con Claude + búsqueda web...")
    try:
        report = generate_report()
        print(f"  ✓ Reporte generado ({len(report)} caracteres)")
    except Exception as e:
        print(f"  ✗ Error generando reporte: {e}")
        sys.exit(1)

    print("\n[2/2] Enviando por WhatsApp...")
    try:
        send_whatsapp(report)
        print("  ✓ Envío completado")
    except Exception as e:
        print(f"  ✗ Error enviando WhatsApp: {e}")
        sys.exit(1)

    print("\n✅ Bot finalizado exitosamente")


if __name__ == "__main__":
    main()
