"""
Test de regresion: scope de vacunas project_specific en get_missing_vaccines().

BUG que cubre (detectado 2026-07-14, via HANDOFF de CodeCS):
    Con scope=project_specific y project=None, el codigo inyectaba el filtro
    SQL con project NULL -> "NULL = ANY(c.projects)" -> NULL -> cero filas ->
    toda vacuna project_specific se reportaba "Sin representacion en el grafo".
    Efecto: cs_get_alerts() sin proyecto ladraba 'Cierre sesion' (CRITICAL) y
    'catalogo' (MEDIUM) como faltantes aunque ambas estaban satisfechas.

Requiere BD (lectura pura, sin escrituras).
"""
import sys

from dotenv import load_dotenv

load_dotenv()

import humandato_queries as hq  # noqa: E402


CONTROLES = [
    # Global inexistente: debe ladrar SIEMPRE, con o sin proyecto.
    {
        "name": "zzz-inexistente-global",
        "scope": "global",
        "category": "ctl_global",
        "severity": "critical",
        "directive": "control",
        "min_weight": 0.3,
        "failure_history": "control",
    },
    # Project-specific inexistente: ladra sin proyecto y en su proyecto
    # aplicable; calla en un proyecto al que NO aplica.
    {
        "name": "zzz-inexistente-ps",
        "scope": "project_specific",
        "applicable_projects": ["concept-sediment"],
        "category": "ctl_ps",
        "severity": "high",
        "directive": "control",
        "min_weight": 0.3,
        "failure_history": "control",
    },
    # Project-specific SATISFECHA: existe "YAML de cierre como unica interfaz
    # de transferencia" (active, w2.3, projects incluye concept-sediment).
    # NO debe ladrar en ningun caso. Esta es la fila que el bug rompia.
    {
        "name": "YAML",
        "scope": "project_specific",
        "applicable_projects": ["concept-sediment"],
        "category": "ctl_satisfecha",
        "severity": "critical",
        "directive": "control",
        "min_weight": 0.7,
        "failure_history": "control",
    },
]

# project -> categorias que DEBEN ladrar
ESPERADO = {
    None: {"ctl_global", "ctl_ps"},
    "concept-sediment": {"ctl_global", "ctl_ps"},
    "inducop": {"ctl_global"},
}


def test_scope_project_specific():
    original = hq.VCM_DIRECTIVES
    hq.VCM_DIRECTIVES = CONTROLES
    ok = True
    try:
        for project, esperado in ESPERADO.items():
            ladran = {v["category"] for v in hq.get_missing_vaccines(project)}
            if ladran == esperado:
                print(f"  [OK] project={project!r}: ladran {sorted(ladran)}")
            else:
                ok = False
                print(
                    f"  [ERROR] project={project!r}: esperado {sorted(esperado)}, "
                    f"obtenido {sorted(ladran)}"
                )
    finally:
        hq.VCM_DIRECTIVES = original
    return ok


def test_sin_falsos_positivos_reales():
    """Con las VCM_DIRECTIVES reales: una vacuna project_specific ladra en la
    consulta SIN proyecto si y solo si ladra en TODOS sus applicable_projects.

    El bug rompia justo este invariante: ladraba sin proyecto (NULL = ANY -> 0
    filas) mientras estaba satisfecha en su proyecto aplicable.
    """
    def ladran(project):
        return {v["directive"] for v in hq.get_missing_vaccines(project)}

    sin_proyecto = ladran(None)
    ok = True

    for vcm in hq.VCM_DIRECTIVES:
        if vcm.get("scope") != "project_specific":
            continue
        aplicables = vcm.get("applicable_projects", [])
        ladra_sin = vcm["directive"] in sin_proyecto
        ladra_en_todos = all(vcm["directive"] in ladran(p) for p in aplicables)

        if ladra_sin == ladra_en_todos:
            estado = "ladra" if ladra_sin else "satisfecha"
            print(f"  [OK] {vcm['name']!r} ({estado}): coherente sin proyecto vs {aplicables}")
        else:
            ok = False
            print(
                f"  [ERROR] {vcm['name']!r}: sin proyecto ladra={ladra_sin}, "
                f"pero en {aplicables} ladra={ladra_en_todos}"
            )
    return ok


if __name__ == "__main__":
    print("[TEST 1] Scope de vacunas project_specific (controles)")
    r1 = test_scope_project_specific()
    print("[TEST 2] Sin falsos positivos con directivas reales")
    r2 = test_sin_falsos_positivos_reales()
    print()
    if r1 and r2:
        print("[OK] Todos los tests pasaron")
        sys.exit(0)
    print("[ERROR] Hay tests fallidos")
    sys.exit(1)
