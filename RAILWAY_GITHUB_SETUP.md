# Railway GitHub Auto-Deploy - Setup Guide

**Servicio:** mcp-server
**Repositorio:** https://github.com/Entheos69/concept-sediment-mcp
**Objetivo:** Configurar auto-deploy en cada `git push`

---

## 🎯 Pasos para conectar GitHub → Railway

### 1️⃣ Abrir Railway Dashboard

Copia y pega esta URL en tu navegador:

```
https://railway.app/project/68399625-d518-40fe-8557-1223c2e84982/service/9e671d20-1f27-41b5-b1d9-2948f249cc40
```

Esto te llevará directo al servicio **mcp-server** en el proyecto **balanced-determination**.

---

### 2️⃣ Ir a Settings del servicio

Una vez en la página del servicio:

1. Click en la pestaña **"Settings"** (arriba a la derecha)
2. Scroll hacia abajo hasta la sección **"Source"**

---

### 3️⃣ Conectar repositorio GitHub

En la sección **Source**, deberías ver:

**Opción A: Si dice "Connect Repo" o "No source connected":**

1. Click en **"Connect Repo"**
2. Railway te pedirá autorizar acceso a tu cuenta GitHub
3. Click en **"Authorize Railway"**
4. Selecciona el repositorio: **`Entheos69/concept-sediment-mcp`**
5. Confirmar

**Opción B: Si ya hay un repo conectado (de deploy manual previo):**

1. Click en **"Disconnect"** o **"Change source"**
2. Seleccionar **"GitHub Repo"**
3. Buscar: `Entheos69/concept-sediment-mcp`
4. Seleccionar el repositorio
5. Confirmar

---

### 4️⃣ Configurar opciones de deploy

Después de conectar el repo, verás opciones de configuración:

**Branch:**
- Seleccionar: `master` (o `main` si renombraste la rama)

**Root Directory:**
- Dejar en blanco o poner: `.` (punto, significa raíz del repo)

**Build Command:** (Opcional - Railway detecta Dockerfile automáticamente)
- Dejar vacío (Railway usa el Dockerfile)

**Start Command:** (Opcional - ya está en railway.toml)
- Dejar vacío (Railway usa `CMD` del Dockerfile)

---

### 5️⃣ Guardar y verificar

1. Click en **"Save"** o **"Deploy"** (si aparece el botón)
2. Railway hará un deploy inicial desde el repo GitHub
3. Espera ~2-3 minutos a que termine el build

**Señales de éxito:**
- En la sección **Source** ahora dice: `GitHub: Entheos69/concept-sediment-mcp`
- En la pestaña **Deployments** aparece un nuevo deployment con icono de GitHub
- El deployment tiene status: **"Success"** (verde)

---

### 6️⃣ Verificar que funciona

Para probar que el auto-deploy está activo:

```bash
# 1. Hacer un cambio pequeño en el repo local
cd C:/Users/ajmon/env/Scripts/concept-sediment-mcp
echo "# Test auto-deploy" >> README.md

# 2. Commit y push
git add README.md
git commit -m "test: verificar auto-deploy desde GitHub"
git push

# 3. Ver logs en Railway
railway logs
# Deberías ver el nuevo deployment iniciar automáticamente
```

**Resultado esperado:**
- Railway detecta el push a GitHub
- Inicia build automáticamente (~1-2 min)
- Deploya la nueva versión
- Servicio actualizado sin `railway up` manual

---

## ✅ Checklist de verificación

Después de completar los pasos, verifica:

- [ ] Railway Dashboard → Service mcp-server → Settings → Source dice: `GitHub: Entheos69/concept-sediment-mcp`
- [ ] Branch configurado: `master`
- [ ] Root directory: `.` o vacío
- [ ] Último deployment tiene icono de GitHub (no icono de CLI)
- [ ] Status del deployment: **Success**
- [ ] Health check funciona: https://mcp-server-production-994a.up.railway.app/health

---

## 🔄 Workflow después de configurar

De ahora en adelante:

```bash
# 1. Hacer cambios en MCP server
cd C:/Users/ajmon/env/Scripts/concept-sediment-mcp
~/check-repo.sh  # Verificar que estás en MCP-SERVER

# 2. Editar archivos
vim server.py  # o cualquier archivo

# 3. Commit y push
git add .
git commit -m "feat: nueva funcionalidad"
git push

# 4. Railway auto-deploya
# ✅ Sin necesidad de 'railway up'
# ✅ Build automático desde GitHub
# ✅ Deploy automático a producción
```

---

## 🚨 Troubleshooting

### Problema: Railway no detecta el push

**Solución:**
1. Ir a Railway Dashboard → Service → Settings → Source
2. Verificar que el webhook está activo
3. En GitHub: Settings → Webhooks → Debe aparecer webhook de Railway
4. Si no existe, reconectar el repositorio en Railway

---

### Problema: Build falla después de conectar GitHub

**Solución:**
1. Verificar que el Dockerfile está en la raíz del repo:
   ```bash
   ls -la C:/Users/ajmon/env/Scripts/concept-sediment-mcp/Dockerfile
   ```
2. Verificar que requirements.txt existe:
   ```bash
   ls -la C:/Users/ajmon/env/Scripts/concept-sediment-mcp/requirements.txt
   ```
3. Ver logs del build fallido en Railway Dashboard → Deployments → Click en el deployment rojo

---

### Problema: "No source connected" pero yo ya hice 'railway up' antes

**Explicación:**
`railway up` hace un deploy **directo desde tu máquina**, no desde GitHub.
Es un método "manual" que no configura auto-deploy.

**Solución:**
Conectar GitHub como se explica en los pasos 1-5.

---

## 📊 Comparación: railway up vs GitHub auto-deploy

| Método | Trigger | Ventajas | Desventajas |
|--------|---------|----------|-------------|
| `railway up` | Manual (ejecutar comando) | Rápido para testing | No hay historial en GitHub |
| GitHub auto-deploy | Automático (`git push`) | CI/CD completo, historial, rollback | Requiere setup inicial |

**Recomendación:** Usar GitHub auto-deploy para producción.

---

## 🎉 Resultado final

Una vez configurado:

```
Tu máquina local
      │
      │ git push
      ▼
GitHub: concept-sediment-mcp
      │
      │ webhook automático
      ▼
Railway: mcp-server
      │
      │ build + deploy
      ▼
Producción: https://mcp-server-production-994a.up.railway.app
```

**¡Auto-deploy configurado! 🚀**

---

**Fecha de creación:** 2026-03-30
**Autor:** Setup guide para auto-deploy Railway + GitHub
