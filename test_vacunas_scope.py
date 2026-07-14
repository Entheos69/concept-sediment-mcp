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
    original = hq.load_vcm_directives
    hq.load_vcm_directives = lambda session=None: (CONTROLES, "test")
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
        hq.load_vcm_directives = original
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

    directivas, _ = hq.load_vcm_directives()
    for vcm in directivas:
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


def test_reason_distingue_decaido_de_ausente():
    """El motivo debe separar 'nunca se sedimento' de 'existe pero decayo'.

    Antes, ambos casos devolvian "Sin representacion en el grafo" — falso para el
    segundo: SI hay representacion, esta dormida. Son acciones distintas
    (sedimentar de cero vs. reconsolidar).

    No escribe en BD: apunta una vacuna sintetica a un concepto que ya esta
    dormant en el grafo, con un min_weight inalcanzable.
    """
    controles = [
        # Concepto que existe y esta dormant (fractura conocida del grafo).
        {
            "name": "Deriva de dependencias sin pin",
            "scope": "global",
            "category": "ctl_decaido",
            "severity": "high",
            "directive": "control: concepto existente pero dormido",
            "min_weight": 0.1,  # bajisimo: si estuviera active, no ladraria
            "failure_history": "control",
        },
        # Concepto que no existe en absoluto.
        {
            "name": "zzz-jamas-sedimentado",
            "scope": "global",
            "category": "ctl_ausente",
            "severity": "high",
            "directive": "control: nunca sedimentado",
            "min_weight": 0.1,
            "failure_history": "control",
        },
    ]

    original = hq.load_vcm_directives
    hq.load_vcm_directives = lambda session=None: (controles, "test")
    try:
        por_categoria = {v["category"]: v for v in hq.get_missing_vaccines(None)}
    finally:
        hq.load_vcm_directives = original

    ok = True

    decaido = por_categoria.get("ctl_decaido")
    if not decaido:
        print("  [ERROR] la vacuna sobre un concepto dormant no ladro")
        ok = False
    elif not decaido["reason"].startswith("Representacion decaida"):
        print(f"  [ERROR] concepto dormant reportado como: {decaido['reason']!r}")
        ok = False
    else:
        print(f"  [OK] dormant -> {decaido['reason'][:72]}...")
        print(f"       found_status={decaido['found_status']!r} "
              f"found_weight={decaido['found_weight']}")

    ausente = por_categoria.get("ctl_ausente")
    if not ausente:
        print("  [ERROR] la vacuna sin concepto no ladro")
        ok = False
    elif ausente["reason"] != "Sin representacion en el grafo":
        print(f"  [ERROR] concepto ausente reportado como: {ausente['reason']!r}")
        ok = False
    else:
        print(f"  [OK] ausente -> {ausente['reason']!r} "
              f"(found_status={ausente['found_status']!r})")

    return ok


if __name__ == "__main__":
    print("[TEST 1] Scope de vacunas project_specific (controles)")
    r1 = test_scope_project_specific()
    print("[TEST 2] Sin falsos positivos con directivas reales")
    r2 = test_sin_falsos_positivos_reales()
    print("[TEST 3] El motivo distingue decaido de ausente")
    r3 = test_reason_distingue_decaido_de_ausente()
    print()
    if r1 and r2 and r3:
        print("[OK] Todos los tests pasaron")
        sys.exit(0)
    print("[ERROR] Hay tests fallidos")
    sys.exit(1)
