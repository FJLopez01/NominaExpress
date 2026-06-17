# Guía: Configurar Microsoft Graph API para envío de correos
## Sistema de Nóminas AGD Legal

Esta guía te lleva desde cero hasta tener el sistema enviando correos
con tu cuenta de Microsoft 365. Solo necesitas acceso al portal de Azure
como administrador (que ya tienes).

Tiempo estimado: 15-20 minutos.

---

## ¿Qué vamos a hacer?

Registrar una "aplicación" en Azure AD que le diga a Microsoft:
*"Este sistema tiene permiso para enviar correos desde la cuenta de nóminas."*

Esto es más seguro que usar una contraseña, porque:
- El permiso es específico: solo puede enviar correos, nada más.
- Si algo sale mal, puedes revocarlo desde Azure sin cambiar contraseñas.
- No expira de forma inesperada como los App Passwords de Gmail.

---

## Paso 1 — Entrar al portal de Azure

1. Abre el navegador y ve a: https://portal.azure.com
2. Inicia sesión con tu cuenta de administrador de M365.
3. En la barra de búsqueda superior, escribe: **Azure Active Directory**
4. Haz clic en el resultado (ícono de escudo azul).

---

## Paso 2 — Registrar la aplicación

1. En el menú izquierdo, haz clic en **"Registros de aplicaciones"**
   (App registrations).
2. Haz clic en **"+ Nuevo registro"** (New registration).
3. Completa el formulario:
   - **Nombre:** `Sistema Nominas AGD Legal`
     (solo para identificarla, no afecta el funcionamiento)
   - **Tipos de cuenta admitidos:** Selecciona la primera opción:
     *"Solo las cuentas de este directorio organizativo"*
   - **URI de redirección:** Déjalo vacío (no aplica para este tipo de app).
4. Haz clic en **"Registrar"**.

✅ **Resultado:** Azure te muestra la pantalla de tu nueva aplicación.

---

## Paso 3 — Copiar los IDs que necesitas

En la pantalla de la aplicación recién creada, copia estos dos valores:

```
AZURE_TENANT_ID  = "Identificador de directorio (inquilino)"
AZURE_CLIENT_ID  = "Id. de aplicación (cliente)"
```

Están en la sección **"Essentials"** o **"Información esencial"** en la parte
superior. Son cadenas con formato: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

Guárdalos en un lugar temporal — los necesitarás al final.

---

## Paso 4 — Crear el secreto de cliente

El secreto es la "contraseña" de la aplicación. Se genera una sola vez.

1. En el menú izquierdo de tu aplicación, haz clic en
   **"Certificados y secretos"** (Certificates & secrets).
2. Haz clic en la pestaña **"Secretos de cliente"** (Client secrets).
3. Haz clic en **"+ Nuevo secreto de cliente"**.
4. Completa:
   - **Descripción:** `nominas-production`
   - **Expira:** Selecciona **24 meses** (renovar cada 2 años).
5. Haz clic en **"Agregar"**.
6. ⚠️ **IMPORTANTE:** Copia el valor de la columna **"Valor"** AHORA.
   Azure solo lo muestra una vez. Si cierras la pantalla, tendrás que
   generar uno nuevo.

```
AZURE_CLIENT_SECRET = "(el valor que acabas de copiar)"
```

---

## Paso 5 — Agregar el permiso de envío de correo

1. En el menú izquierdo, haz clic en **"Permisos de API"** (API permissions).
2. Haz clic en **"+ Agregar un permiso"** (Add a permission).
3. Selecciona **"Microsoft Graph"**.
4. Selecciona **"Permisos de aplicación"** (Application permissions).
   ⚠️ No "Permisos delegados" — elige "Permisos de aplicación".
5. En el buscador, escribe: `Mail.Send`
6. Expande **"Mail"** y marca la casilla **"Mail.Send"**.
7. Haz clic en **"Agregar permisos"**.

Ahora verás `Mail.Send` en la lista pero con estado **"No concedido"**.
Hay un paso más:

8. Haz clic en el botón **"Conceder consentimiento de administrador para
   [nombre de tu organización]"** (Grant admin consent).
9. Confirma haciendo clic en **"Sí"**.

✅ El estado cambia a **"Concedido para [organización]"** con un ✅ verde.

---

## Paso 6 — Configurar el archivo .env

Abre el archivo `.env` en el proyecto (o créalo copiando `.env.example`)
y agrega los cuatro valores:

```env
# ── Rutas del sistema ──────────────────────────────────────────────
BASE_PATH=C:\Nominas\AGDLegal

# ── Microsoft 365 Graph API ────────────────────────────────────────
# Los tres primeros vienen de Azure AD (pasos 3 y 4 de esta guía)
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# La cuenta desde la que saldrán los correos (debe existir en M365)
EMAIL_SENDER=nominas@agdlegal.com
```

**Sobre EMAIL_SENDER:**
- Debe ser una cuenta real de tu M365 (no un alias).
- Puede ser la cuenta de quien ejecuta el sistema, o una cuenta
  dedicada como `nominas@agdlegal.com`.
- Los correos aparecerán en la bandeja de enviados de esa cuenta.

---

## Paso 7 — Verificar que funciona

Ejecuta el sistema en modo de prueba:

```bash
cd nominas-express
pip install -r requirements.txt
streamlit run src/app.py
```

Si ves el panel de control con "✅ Sistema listo", la configuración
es correcta. Si ves un error de Azure AD, revisa que:

1. El AZURE_TENANT_ID tenga exactamente 36 caracteres con guiones.
2. El AZURE_CLIENT_ID tenga exactamente 36 caracteres con guiones.
3. El AZURE_CLIENT_SECRET sea el "Valor" (no el "Id. de secreto").
4. El permiso Mail.Send tenga el ✅ de "Concedido para [organización]".

---

## Preguntas frecuentes

**¿Por qué "Permisos de aplicación" y no "Permisos delegados"?**

Los permisos delegados requieren que un usuario inicie sesión
interactivamente cada vez. Los permisos de aplicación permiten que
el sistema funcione desatendido (sin que nadie tenga que hacer login).
Para un script de nómina que corre en batch, los permisos de aplicación
son la opción correcta.

**¿Qué pasa si el secreto expira?**

El sistema dejará de enviar correos con un error de autenticación.
Azure avisa por correo al administrador 30, 60 y 90 días antes de que
expire. Cuando eso pase, genera un nuevo secreto en el paso 4 y
actualiza AZURE_CLIENT_SECRET en el .env.

**¿Puede la aplicación leer mis correos?**

No. El permiso `Mail.Send` es de solo escritura: permite enviar,
pero no leer. Para leer correos se necesitaría el permiso `Mail.Read`,
que no se agregó aquí.

**¿La cuenta de EMAIL_SENDER puede ser de otro dominio?**

Debe ser una cuenta dentro de tu tenant de M365
(el mismo directorio donde registraste la aplicación).

---

## Resumen de variables de entorno

| Variable             | De dónde viene                  | Ejemplo                              |
|----------------------|---------------------------------|--------------------------------------|
| BASE_PATH            | Tú defines la ruta              | C:\Nominas\AGDLegal                  |
| AZURE_TENANT_ID      | Paso 3 de esta guía             | 12345678-1234-1234-1234-123456789012 |
| AZURE_CLIENT_ID      | Paso 3 de esta guía             | 87654321-4321-4321-4321-210987654321 |
| AZURE_CLIENT_SECRET  | Paso 4 de esta guía             | abc~xyz123...                        |
| EMAIL_SENDER         | Cuenta real de tu M365          | nominas@empresa.com                 |
