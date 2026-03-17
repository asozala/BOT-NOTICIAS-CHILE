"""
Bot Monitor Noticias Chile
  python bot.py full   -> reporte completo + GitHub Pages + WhatsApp
  python bot.py alert  -> busca urgentes + WhatsApp si hay algo importante
"""

import anthropic
import os, sys, json, base64, requests
from datetime import datetime
from zoneinfo import ZoneInfo
from twilio.rest import Client as TwilioClient

# ── Credenciales ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM        = os.environ["TWILIO_WHATSAPP_FROM"]
WHATSAPP_TO        = os.environ["WHATSAPP_TO"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GITHUB_REPO        = os.environ["GITHUB_REPOSITORY"]   # automatico en Actions

CHILE_TZ = ZoneInfo("America/Santiago")

# ── Prompts ───────────────────────────────────────────────────────────────────

PROMPT_FULL = """Eres un sistema profesional de media monitoring politico en Chile.
Busca noticias sobre el gobierno de Jose Antonio Kast publicadas HOY.

MEDIOS PRIORITARIOS (busca aunque tengan paywall):
El Mercurio, La Tercera, La Segunda, Diario Financiero, Ex-Ante,
Emol, El Libero, Pulso, BioBioChile, Cooperativa.

FUENTES DE X (Twitter) — OBLIGATORIO buscar estas cuentas:
- @ElMercurio_cl  → incluir como medio "El Mercurio (via @ElMercurio_cl)"
- @lasegunda      → incluir como medio "La Segunda (via @lasegunda)"
Busca sus tweets de hoy sobre el gobierno de Kast. Los tweets son publicos y no tienen paywall.

CONTENIDO: Declaraciones de Kast y ministros, anuncios, proyectos de ley,
reformas, crisis politicas, polemicas, evaluaciones del gobierno.

REGLAS CRITICAS:
1. Responde UNICAMENTE con JSON valido. Sin texto extra. Sin markdown.
2. Maximo 3 noticias por medio.
3. Si puedes leer el articulo completo: escribe 2 oraciones de resumen.
4. Si el articulo tiene paywall: incluye titular y link, resumen = "Articulo de pago."
5. Para noticias de X/Twitter: usa el texto del tweet como resumen.
6. Incluye la hora de publicacion de cada noticia si la conoces (formato HH:MM).
7. El JSON debe estar COMPLETO y bien cerrado.

Estructura exacta:
{
  "fecha": "DD/MM/YYYY",
  "hora": "HH:MM",
  "medios": [
    {
      "nombre": "Nombre del Medio",
      "noticias": [
        {
          "titular": "Titular completo",
          "fecha": "DD/MM/YYYY",
          "hora": "HH:MM",
          "autor": "Autor o cadena vacia",
          "resumen": "2 oraciones de resumen, o Articulo de pago.",
          "link": "https://url.cl",
          "paywall": false,
          "fuente_x": false
        }
      ]
    }
  ]
}

Usa paywall: true cuando no puedas leer el contenido.
Usa fuente_x: true para noticias obtenidas desde X/Twitter.
Incluye SIEMPRE los titulares aunque no puedas leer la nota.
"""

PROMPT_ALERT = """Eres un monitor de noticias urgentes del gobierno de Chile.
Busca noticias IMPORTANTES publicadas en las ultimas 3 horas sobre
el gobierno de Jose Antonio Kast en los medios chilenos.

Considera importante: anuncios presidenciales, crisis politica, medidas economicas
urgentes, cambios de gabinete, proyectos de ley enviados al Congreso,
declaraciones polemicas de ministros.

Si hay noticias importantes, responde EXACTAMENTE asi (sin texto extra):
ALERTA
[Nombre del medio]: [Titular completo]
[Nombre del medio]: [Titular completo]

Si NO hay noticias importantes nuevas en las ultimas 3 horas, responde EXACTAMENTE:
SIN_NOVEDADES"""


# ── Generacion de contenido ───────────────────────────────────────────────────

def generate_full_report() -> dict:
    """Genera reporte completo. Retorna dict con estructura de medios y noticias."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    now    = datetime.now(CHILE_TZ)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        system=PROMPT_FULL,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": (
                f"Fecha actual: {now.strftime('%d/%m/%Y')} "
                f"Hora: {now.strftime('%H:%M')} hrs (Santiago).\n\n"
                "Busca todas las noticias de HOY sobre el gobierno de Kast.\n"
                "1. Busca en medios: El Mercurio, La Tercera, Diario Financiero, "
                "Emol, Cooperativa, Ex-Ante, El Libero, BioBioChile.\n"
                "2. Busca OBLIGATORIAMENTE en X/Twitter: tweets de @ElMercurio_cl "
                "y @lasegunda de hoy sobre Kast o el gobierno.\n"
                "Responde SOLO con el JSON. Sin ningun texto adicional."
            )
        }],
    )

    raw = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw += block.text

    raw = raw.strip()

    # Extraer JSON aunque haya texto alrededor
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]

    # Intento 1: JSON completo
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Intento 2: el JSON fue truncado — reconstruir lo que este completo
    # Buscar la ultima noticia completa (ultimo "}" antes del corte)
    # Cerrar el JSON manualmente
    try:
        # Contar llaves abiertas para saber cuantas hay que cerrar
        depth = 0
        last_valid_pos = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(raw):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
            if not in_string:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        last_valid_pos = i + 1

        if last_valid_pos > 0:
            truncated = raw[:last_valid_pos]
            # Cerrar arrays y objetos abiertos
            depth2 = 0
            brackets = []
            in_str2 = False
            esc2 = False
            for ch in truncated:
                if esc2: esc2 = False; continue
                if ch == '\\' and in_str2: esc2 = True; continue
                if ch == '"': in_str2 = not in_str2
                if not in_str2:
                    if ch in '{[': brackets.append(ch)
                    elif ch in '}]': brackets.pop() if brackets else None
            closing = ""
            for b in reversed(brackets):
                closing += "}" if b == "{" else "]"
            fixed = truncated + closing
            result = json.loads(fixed)
            print("  Advertencia: JSON truncado, recuperados datos parciales")
            return result
    except Exception:
        pass

    raise Exception(f"JSON invalido.\nRespuesta recibida: {raw[:300]}")


def check_breaking_news() -> str | None:
    """
    Busca noticias urgentes de las ultimas 3 horas.
    Retorna string con alertas, o None si no hay novedades.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    now    = datetime.now(CHILE_TZ)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=PROMPT_ALERT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": (
                f"Son las {now.strftime('%H:%M')} hrs del "
                f"{now.strftime('%d/%m/%Y')} en Santiago.\n"
                "Busca noticias urgentes del gobierno de Kast de las ultimas 3 horas."
            )
        }],
    )

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    text = text.strip()

    if not text or "SIN_NOVEDADES" in text:
        return None
    if "ALERTA" in text:
        return text.replace("ALERTA", "").strip()
    return None


# ── Generacion HTML ───────────────────────────────────────────────────────────

def build_html(data: dict) -> str:
    """Genera pagina HTML profesional con filtros por medio."""
    now    = datetime.now(CHILE_TZ)
    fecha  = now.strftime("%d de %B de %Y")
    hora   = now.strftime("%H:%M")
    medios = [m["nombre"] for m in data.get("medios", [])]
    total  = sum(len(m.get("noticias", [])) for m in data.get("medios", []))

    # Botones de filtro
    btns = '<button class="btn active" onclick="filtrar(\'all\', this)">Todos</button>\n'
    for medio in medios:
        safe = medio.replace("'", "\\'")
        btns += f'    <button class="btn" onclick="filtrar(\'{safe}\', this)">{medio}</button>\n'

    # Secciones de noticias
    secciones = ""
    for m in data.get("medios", []):
        nombre   = m["nombre"]
        noticias = m.get("noticias", [])
        if not noticias:
            continue

        cards = ""
        for n in noticias:
            autor = f'<span class="meta-item">✍️ {n["autor"]}</span>' if n.get("autor") else ""
            hora_noticia = f'<span class="meta-item">🕐 {n["hora"]}</span>' if n.get("hora") else ""
            link  = (f'<a href="{n["link"]}" target="_blank" class="ver-nota">'
                     f'Ver nota original →</a>') if n.get("link") else ""
            es_paywall = n.get("paywall", False) or n.get("resumen","") == "Articulo de pago."
            es_x       = n.get("fuente_x", False)
            if es_paywall:
                cuerpo = '<span class="paywall-badge">🔒 Artículo de pago — solo disponible en el sitio original</span>'
            else:
                cuerpo = n.get("resumen", "").replace("\n", "<br>")
            fuente_x_badge = '<div class="x-badge">* Fuente: X (<span class="x-handle">' + \
                             (nombre.split("via ")[-1].rstrip(")") if "via " in nombre else "@Twitter") + \
                             '</span>)</div>' if es_x else ""
            cards += f"""
        <article class="card {'paywall-card' if es_paywall else ''}">
          <h3 class="titular">{n.get("titular","")}</h3>
          <div class="meta">
            <span class="meta-item">📅 {n.get("fecha","")}</span>
            {hora_noticia}
            {autor}
          </div>
          <div class="cuerpo">{cuerpo}</div>
          {fuente_x_badge}
          <div class="card-footer">{link}</div>
        </article>"""

        count = len(noticias)
        secciones += f"""
  <section class="seccion" data-medio="{nombre}">
    <div class="seccion-header">
      <h2 class="medio-titulo">{nombre}</h2>
      <span class="badge">{count} noticia{"s" if count != 1 else ""}</span>
    </div>
    {cards}
  </section>"""

    contenido = secciones if secciones else (
        '<div class="vacio">No se encontraron noticias relevantes.</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monitor Noticias Gobierno Chile — {fecha}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     background:#f2f3f5;color:#222;line-height:1.6}}
header{{background:#b71c1c;color:#fff;padding:16px 20px;position:sticky;
        top:0;z-index:100;box-shadow:0 2px 6px rgba(0,0,0,.25)}}
header h1{{font-size:1.2em;font-weight:700}}
header p{{font-size:.82em;opacity:.85;margin-top:3px}}
.stats{{display:inline-block;background:rgba(255,255,255,.2);
        padding:2px 10px;border-radius:12px;font-size:.78em;margin-top:5px}}
.filtros{{background:#fff;padding:12px 20px;border-bottom:1px solid #ddd;
          display:flex;gap:8px;flex-wrap:wrap}}
.btn{{padding:5px 14px;border:2px solid #b71c1c;background:#fff;color:#b71c1c;
      border-radius:20px;cursor:pointer;font-size:.82em;font-weight:600;
      transition:all .15s}}
.btn:hover,.btn.active{{background:#b71c1c;color:#fff}}
main{{max-width:880px;margin:0 auto;padding:20px 14px}}
.seccion{{margin-bottom:32px}}
.seccion-header{{display:flex;align-items:center;justify-content:space-between;
                 border-bottom:3px solid #b71c1c;padding-bottom:8px;margin-bottom:14px}}
.medio-titulo{{font-size:1.2em;font-weight:700;color:#b71c1c;text-transform:uppercase;
               letter-spacing:.5px}}
.badge{{background:#b71c1c;color:#fff;padding:2px 10px;border-radius:12px;
        font-size:.78em;font-weight:600}}
.card{{background:#fff;border-radius:8px;padding:18px;margin-bottom:12px;
       box-shadow:0 1px 4px rgba(0,0,0,.08);border-left:4px solid #b71c1c}}
.titular{{font-size:1em;font-weight:700;color:#111;margin-bottom:7px}}
.meta{{display:flex;gap:14px;font-size:.78em;color:#777;margin-bottom:10px;
       flex-wrap:wrap}}
.cuerpo{{font-size:.9em;color:#333;line-height:1.7;margin-bottom:10px}}
.card-footer{{border-top:1px solid #f0f0f0;padding-top:8px}}
.ver-nota{{color:#b71c1c;text-decoration:none;font-size:.83em;font-weight:600}}
.ver-nota:hover{{text-decoration:underline}}
.paywall-badge{{display:inline-block;background:#fff8e1;color:#795548;
               padding:6px 10px;border-radius:6px;font-size:.85em;
               border:1px solid #ffe082}}
.paywall-card{{border-left-color:#ff8f00;opacity:.9}}
.x-badge{{font-size:.78em;color:#888;margin-top:6px;font-style:italic}}
.x-handle{{color:#1da1f2;font-weight:600;font-style:normal}}
.vacio{{text-align:center;padding:60px 20px;color:#999}}
footer{{text-align:center;padding:18px;color:#aaa;font-size:.78em;
        border-top:1px solid #e0e0e0;margin-top:12px}}
@media(max-width:600px){{header h1{{font-size:1em}}.card{{padding:12px}}}}
</style>
</head>
<body>
<header>
  <h1>🇨🇱 Monitor Noticias Gobierno Chile</h1>
  <p>Última actualización: {fecha} — {hora} hrs (Santiago)</p>
  <span class="stats">{total} noticias · {len(medios)} medios monitoreados</span>
</header>

<div class="filtros">
  {btns}
</div>

<main id="main">
{contenido}
</main>

<footer>Monitor Noticias Chile — Generado el {fecha} a las {hora} hrs · Solo uso interno</footer>

<script>
function filtrar(medio, btn) {{
  document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.seccion').forEach(s => {{
    s.style.display = (medio === 'all' || s.dataset.medio === medio) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


# ── GitHub Pages ──────────────────────────────────────────────────────────────

def push_html(html: str) -> str:
    """
    Sube docs/index.html al repositorio via GitHub API.
    Retorna la URL de GitHub Pages.
    """
    owner, repo_name = GITHUB_REPO.split("/")
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    api_url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/docs/index.html"
    content_b64 = base64.b64encode(html.encode("utf-8")).decode("utf-8")
    now_str     = datetime.now(CHILE_TZ).strftime("%Y-%m-%d %H:%M")

    # Obtener SHA si el archivo ya existe
    sha = None
    r = requests.get(api_url, headers=headers, timeout=30)
    if r.status_code == 200:
        sha = r.json().get("sha")

    payload = {
        "message": f"Actualizar reporte {now_str}",
        "content": content_b64,
        "branch":  "main",
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(api_url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()

    return f"https://{owner}.github.io/{repo_name}/"


# ── WhatsApp ──────────────────────────────────────────────────────────────────

def send_whatsapp(body: str) -> None:
    TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN).messages.create(
        from_=TWILIO_FROM,
        to=WHATSAPP_TO,
        body=body,
    )


# ── Modos de ejecucion ────────────────────────────────────────────────────────

def run_full():
    """Reporte completo: genera → publica → notifica."""
    now = datetime.now(CHILE_TZ)
    print(f"\n[1/3] Generando reporte completo...")
    data  = generate_full_report()
    total = sum(len(m.get("noticias",[])) for m in data.get("medios",[]))
    nmed  = len(data.get("medios",[]))
    print(f"  OK — {total} noticias de {nmed} medios")

    print(f"\n[2/3] Publicando en GitHub Pages...")
    html = build_html(data)
    url  = push_html(html)
    print(f"  OK — {url}")

    print(f"\n[3/3] Enviando notificacion WhatsApp...")
    fecha_str = now.strftime("%d/%m/%Y %H:%M")

    # Resumen de titulares (max 2 por medio)
    resumen = ""
    for m in data.get("medios", []):
        noticias = m.get("noticias", [])[:2]
        if noticias:
            resumen += f"\n*{m['nombre']}*\n"
            for n in noticias:
                resumen += f"• {n.get('titular','')}\n"

    msg = (
        f"📰 *Monitor Noticias Gobierno Chile*\n"
        f"_{fecha_str} hrs_\n"
        f"_{total} noticias · {nmed} medios_\n"
        f"{resumen}\n"
        f"🔗 Reporte completo:\n{url}"
    )
    send_whatsapp(msg)
    print("  OK — WhatsApp enviado")


def run_alert():
    """Chequeo rapido: busca urgentes, notifica solo si hay algo."""
    now = datetime.now(CHILE_TZ)
    print(f"\n[1/2] Buscando noticias urgentes ({now.strftime('%H:%M')})...")
    alertas = check_breaking_news()

    if not alertas:
        print("  Sin novedades. No se envia mensaje.")
        return

    print(f"  Noticias urgentes encontradas!")
    owner, repo_name = GITHUB_REPO.split("/")
    url = f"https://{owner}.github.io/{repo_name}/"

    print(f"\n[2/2] Enviando alerta WhatsApp...")
    msg = (
        f"🚨 *Alerta Noticias Chile*\n"
        f"_{now.strftime('%H:%M')} hrs_\n\n"
        f"{alertas}\n\n"
        f"🔗 Ver reporte:\n{url}"
    )
    send_whatsapp(msg)
    print("  OK — Alerta enviada")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("full", "alert"):
        print("Uso: python bot.py [full|alert]")
        sys.exit(1)

    mode = sys.argv[1]
    now  = datetime.now(CHILE_TZ)
    print("=" * 50)
    print(f"  BOT NOTICIAS CHILE — {'REPORTE COMPLETO' if mode == 'full' else 'ALERTA'}")
    print(f"  {now.strftime('%d/%m/%Y %H:%M')} hrs (Santiago)")
    print("=" * 50)

    try:
        if mode == "full":
            run_full()
        else:
            run_alert()
        print("\n✅ Bot finalizado correctamente")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        try:
            send_whatsapp(f"Bot Noticias ERROR ({mode}):\n{str(e)[:200]}")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
