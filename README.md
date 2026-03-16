# 📰 Bot de Noticias Chile — Guía de Instalación

Este bot genera reportes automáticos de noticias chilenas y los envía por WhatsApp,
dos veces al día (8:00 AM y 5:00 PM Santiago), completamente gratis usando GitHub Actions.

---

## 📋 Resumen de lo que necesitas

| Cosa                  | Para qué sirve                        | ¿Cuesta algo?              |
|-----------------------|---------------------------------------|----------------------------|
| Cuenta en GitHub      | Almacenar el código y ejecutarlo      | Gratis                     |
| API Key de Anthropic  | Que Claude genere los reportes        | ~$0.01 por reporte         |
| Cuenta en Twilio      | Enviar mensajes a WhatsApp            | Gratis (sandbox)           |

---

## 🚀 PASO 1 — Crear tu repositorio en GitHub

1. Ve a **https://github.com** y crea una cuenta si no tienes
2. Haz clic en el botón verde **"New"** para crear un repositorio
3. Nómbralo: `bot-noticias-chile`
4. Márcalo como **Privado** (para proteger tus claves)
5. Haz clic en **"Create repository"**

---

## 📁 PASO 2 — Subir los archivos

Tienes 3 archivos que subir. El más fácil es hacerlo directo desde el navegador:

### Subir `bot.py`
1. En tu repositorio, haz clic en **"Add file" → "Create new file"**
2. En el nombre escribe: `bot.py`
3. Pega el contenido del archivo `bot.py`
4. Haz clic en **"Commit changes"**

### Subir `requirements.txt`
1. **"Add file" → "Create new file"**
2. Nombre: `requirements.txt`
3. Pega el contenido (son 2 líneas)
4. **"Commit changes"**

### Subir el workflow (¡importante la carpeta!)
1. **"Add file" → "Create new file"**
2. En el nombre escribe exactamente: `.github/workflows/schedule.yml`
   *(GitHub creará las carpetas automáticamente)*
3. Pega el contenido del archivo `schedule.yml`
4. **"Commit changes"**

---

## 🔑 PASO 3 — Obtener tu API Key de Anthropic

1. Ve a **https://console.anthropic.com**
2. Crea una cuenta con tu email
3. En el menú izquierdo, haz clic en **"API Keys"**
4. Haz clic en **"Create Key"**
5. Copia la clave (empieza con `sk-ant-...`) — **guárdala en un lugar seguro**
6. Agrega crédito en **"Billing"**: con $5 dólares tienes para varios meses

---

## 📱 PASO 4 — Configurar Twilio para WhatsApp

### 4a. Crear cuenta en Twilio
1. Ve a **https://www.twilio.com** y regístrate gratis
2. Verifica tu número de teléfono cuando te lo pidan

### 4b. Activar el Sandbox de WhatsApp
1. En el panel de Twilio, busca en el menú: **Messaging → Try it out → Send a WhatsApp message**
2. Verás un número de Twilio (ej: `+1 415 523 8886`) y un código como `join [palabra]-[palabra]`
3. **Desde tu WhatsApp**, envía ese código al número de Twilio
   - Ejemplo: envía el mensaje `join pretty-tiger` al `+14155238886`
4. Recibirás un mensaje de confirmación de WhatsApp

### 4c. Obtener tus credenciales de Twilio
1. Ve al **Dashboard principal** de Twilio
2. Copia:
   - **Account SID** (empieza con `AC...`)
   - **Auth Token** (haz clic en "Reveal" para verlo)
3. El número "From" de WhatsApp es: `whatsapp:+14155238886` (el número del Sandbox)
4. Tu número "To" es: `whatsapp:+569XXXXXXXX` (tu número con código de país)

---

## 🔒 PASO 5 — Guardar las claves en GitHub (Secrets)

Nunca escribas las claves directamente en el código. GitHub tiene una bóveda segura:

1. En tu repositorio, ve a **Settings** (arriba a la derecha)
2. En el menú izquierdo: **Secrets and variables → Actions**
3. Haz clic en **"New repository secret"** para cada una:

| Nombre del Secret        | Valor                                    |
|--------------------------|------------------------------------------|
| `ANTHROPIC_API_KEY`      | `sk-ant-...` (tu key de Anthropic)       |
| `TWILIO_ACCOUNT_SID`     | `AC...` (de Twilio Dashboard)            |
| `TWILIO_AUTH_TOKEN`      | El token de Twilio                       |
| `TWILIO_WHATSAPP_FROM`   | `whatsapp:+14155238886`                  |
| `WHATSAPP_TO`            | `whatsapp:+56912345678` (tu número)      |

---

## ✅ PASO 6 — Probar que todo funciona

1. Ve a la pestaña **"Actions"** en tu repositorio
2. En el menú izquierdo, haz clic en **"📰 Bot Noticias Chile"**
3. Haz clic en **"Run workflow" → "Run workflow"** (botón verde)
4. Espera 2-3 minutos
5. Si aparece un ✅ verde: ¡éxito! Revisa tu WhatsApp
6. Si aparece ❌ rojo: haz clic en el job fallido para ver el error

---

## ⏰ Horarios automáticos

El bot corre automáticamente:
- **8:00 AM** todos los días (horario Santiago)
- **5:00 PM** todos los días (horario Santiago)

> **Nota sobre horario de invierno (mayo–agosto):**
> En esos meses, Chile cambia a UTC-4. Para mantener los horarios exactos,
> cambia en el archivo `schedule.yml`:
> - `"0 11 * * *"` → `"0 12 * * *"` (8 AM invierno)
> - `"0 20 * * *"` → `"0 21 * * *"` (5 PM invierno)

---

## ❓ Problemas frecuentes

**No me llega el WhatsApp:**
→ ¿Enviaste el código de activación al número de Twilio desde tu WhatsApp?
→ El sandbox de Twilio expira cada 72 horas. Hay que reenviar el código de activación.

**Error en GitHub Actions:**
→ Ve a Actions → haz clic en el job rojo → busca la línea en rojo con el error.

**"API key invalid":**
→ Revisa que copiaste la key completa en el Secret de GitHub.

**Quiero recibir el reporte en otro número también:**
→ Duplica la llamada a `send_whatsapp()` en el bot con otro número.

---

## 💰 ¿Cuánto cuesta?

- **GitHub Actions**: Gratis (2.000 minutos/mes incluidos; el bot usa ~3 min/día = 180 min/mes)
- **Anthropic API**: ~$0.005–$0.01 por reporte × 2 diarios × 30 días ≈ **$0.60–$1.00 USD/mes**
- **Twilio Sandbox**: Gratis (con límites). Para uso en producción sin expirar: ~$0.005 USD/mensaje

---

## 🔧 Personalización

Para cambiar el foco del reporte, edita la variable `SYSTEM_PROMPT` en `bot.py`.
Para cambiar los horarios, edita las líneas `cron:` en `schedule.yml`.
