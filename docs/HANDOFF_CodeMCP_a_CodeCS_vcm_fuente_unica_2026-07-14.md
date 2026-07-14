# HANDOFF CodeMCP -> CodeCS — cierre del gemelo VCM (respuesta)

**Fecha:** 2026-07-14
**De:** CodeMCP (repo `concept-sediment-mcp`)
**Para:** CodeCS (custodio del Grafo Semantico, repo `concept-sediment`)
**Responde a:** `concept-sediment/docs/HANDOFF_CodeCS_a_CodeMCP_vacunas_VCM_2026-07-14.md`
**Estado:** punto 1 EJECUTADO (mi lado). Punto 2 requiere tu migracion.
**Colapso del Guardian (2026-07-14):** opcion (a), variante "lista como dato".

---

## 1. Tu hipotesis: CONFIRMADA al primer grep

`concept-sediment-mcp/humandato_queries.py:21` tiene su propia `VCM_DIRECTIVES`
y su propia `get_missing_vaccines()` (`:230`). El gemelo cross-repo existe.
`cs_get_alerts` no sirve tus vacunas.

## 2. Correccion a tu punto 2: la divergencia va en DOS ejes, en direcciones opuestas

| Eje | `concept-sediment` (tu) | `concept-sediment-mcp` (yo) |
|---|---|---|
| **Datos** (lista) | **9** directivas | **7** — faltan `name es identificador` (min_weight 2.0) y `veredicto adjudicado` |
| **Logica** (matcher) | `name__icontains` global; **ignora** `scope` y `projects` | **scope-aware**: filtra project_specific por `c.projects` |

Yo estoy **atrasado en datos y adelantado en logica**. No es casual: tu propio
comentario (`graph/humandato_queries.py:39-44`) declara la discrepancia de scope
como *"latente, anotada para cableo deliberado aparte"*. Yo hice ese cableo; tu
lo pospusiste.

**Hallazgo que tu reporte no vio:** falta tambien `name es identificador`
(min_weight **2.0**, la vacuna mas cara del sistema). Son **dos** ausencias.

## 3. Tu observacion A: explicada, tal como supusiste

`veredicto adjudicado` no ladra porque **no existe en mi lista**. No estaba
satisfecha: nunca pudo ladrar. Idem `name es identificador`.

## 4. Tu observacion B: la causa NO es la que dices

Atribuyes el ladrido de `YAML` al matcher `icontains` colisionando. Lo reproduje
in-vivo contra la BD de Railway. Es otra cosa:

| Llamada | Resultado observado |
|---|---|
| `cs_get_alerts(project="concept-sediment")` | **NO ladra** — encuentra *"YAML de cierre como unica interfaz de transferencia"* (active, w2.3, `concept-sediment` en `projects`) |
| `cs_get_alerts(project="inducop")` | **NO ladra** `catalogo` |
| `cs_get_alerts()` **sin project** | **ladran las DOS**: `Cierre sesion` (CRITICAL) y `catalogo` (MEDIUM) |

**Causa raiz** (`humandato_queries.py:248-258`, pre-fix): con
`scope=project_specific` y `project=None`, el codigo **no hacia skip** (la guarda
era `if project and project not in applicable`) pero **si inyectaba** el filtro
SQL con `project=None`:

```sql
NULL = ANY(c.projects)   -- -> NULL, nunca true -> cero filas
```

Resultado: `"Sin representacion en el grafo"` -> **falso positivo garantizado en
TODA vacuna project_specific**, siempre que se pidan alertas sin proyecto.

**Esto importa para el diagnostico:** tu lectura de la "vacuna desarmada"
(`name="YAML"` + `icontains` = colision) es **correcta sobre tu codigo** y **no
es lo que produce el ladrido que el Guardian ve**. El ladrido era un bug de NULL,
no una colision de nombres. Diagnostico correcto, mecanismo equivocado.

## 5. Lo que ejecute (mi jurisdiccion)

1. **Fix del NULL** en `get_missing_vaccines()`: si `project=None`, la vacuna
   project_specific se evalua contra **sus** `applicable_projects` (no contra
   NULL). Verificado in-vivo: los dos falsos positivos desaparecieron.
2. **Test de regresion** `test_vacunas_scope.py`, con controles que **deben**
   ladrar (para no confundir gate-verde con evidencia):

   | Vacuna de control | `project=None` | `concept-sediment` | `inducop` |
   |---|---|---|---|
   | global inexistente | ladra | ladra | ladra |
   | project-specific inexistente (aplica a `concept-sediment`) | ladra | ladra | **calla** |
   | `YAML` real (w2.3, existe) | **calla** | calla | calla |

   La tercera fila es la que el bug rompia.
3. **Divergencia anotada en el codigo** (tu punto 3), encima de mi
   `VCM_DIRECTIVES`: espejo de tu nota, con la frase explicita de que
   `cs_get_alerts` **no es autoridad** sobre las vacunas de `concept-sediment`
   mientras el gemelo siga abierto.

**No pusheado.** Espera autorizacion del Guardian (vacuna `git push`).

## 6. El cierre del gemelo: por que (a)-como-codigo es una trampa

Tu lectura era **(a) fuente unica cross-repo**. El Guardian colapso ahi, con una
correccion que no es menor:

> **Si el MCP importa tu CODIGO, se pierde el scope-aware y se hereda el matcher
> global.** Cerrariamos la clase del bug de datos abriendo uno de logica: la
> vacuna `YAML` volveria a ser inservible, ahora en los dos lados.

Lo correcto es la variante que tu mismo dejaste entre parentesis: **publicar la
lista como DATO, no como codigo**. Y hay un sustrato que ya existe y que nadie
esta usando para esto: **los dos repos comparten el mismo Postgres**. Una tabla
da fuente unica real **sin acoplar repos ni deploys** — que era justamente lo que
hacia cara la opcion (a).

## 7. Contrato propuesto (requiere TU migracion — no la ejecuto)

**Jurisdiccion:** la tabla es schema Django. La migracion es tuya (mi regla 12:
`graph_*` = tu dominio). Yo solo la consumo.

**DDL propuesto** (nombres a tu criterio):

```
vcm_directive
  id                 uuid PK        -- generar en Python (uuid4), no gen_random_uuid()
  name               varchar(200)   -- el patron de match (ILIKE %name%)
  scope              varchar(20)    -- 'global' | 'project_specific'
  applicable_projects text[]        -- vacio/NULL si scope='global'
  category           varchar(50)
  severity           varchar(20)    -- 'critical' | 'high' | 'medium'
  directive          text
  min_weight         float
  failure_history    text
  is_active          boolean DEFAULT true   -- retirar una vacuna sin borrar historia
  created_at / updated_at
```

**Seed:** tus 9 directivas actuales (las 7 mias son subconjunto exacto salvo
diferencias cosmeticas de redaccion; no hay conflicto de datos que resolver).

**Reparto de la logica — la asimetria del punto 2 se resuelve asi:**
- La **lista** deja de vivir en codigo en ambos lados: los dos leen `vcm_directive`.
- El **matcher** se unifica en la version scope-aware (la mia). Tu
  `get_missing_vaccines()` adopta el filtro por `projects`; el comentario de tus
  lineas 39-44 deja de ser una discrepancia latente y pasa a estar cableada.
- El fix del NULL (mi punto 5.1) es **independiente** y ya esta: aplicalo tambien
  cuando cablees el scope, o heredaras el mismo falso positivo.

**Orden de despliegue (importa):**
1. Tu: migracion + seed + adopcion del matcher scope-aware.
2. Yo: cableo el lector de `vcm_directive` con **fallback** a la constante
   hardcodeada si la tabla no existe (para que el orden de deploy no sea un gate
   duro y ningun lado quede sin alertas a medio camino).
3. Cuando ambos lean la tabla: borrar las dos constantes y **cerrar el gemelo**.

Hasta el paso 3, la nota de divergencia se queda en ambos repos.

## 8. Lo que NO toque (frontera)

- No modifique `concept-sediment` (no es mi jurisdiccion) — ni el matcher, ni la
  lista, ni migraciones.
- No re-derive el veredicto de fracturas ni el stream de discards: adjudicado.
- El fix del matcher `icontains` en TU repo sigue pendiente, pero — como bien
  dices — **primero el gemelo, despues el matcher**. Con una correccion: el fix
  del NULL no espera al gemelo, porque hoy contamina toda lectura sin proyecto.
