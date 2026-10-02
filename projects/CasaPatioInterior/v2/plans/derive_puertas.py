# -*- coding: utf-8 -*-
"""Decide bisagra y abatimiento de cada puerta, y propone las que faltan.

Entradas : v2/calcs/plan_data.json  (cortes del FCStd: vanos, recintos netos, mobiliario, escalera)
           v2/plans/recintos_v2.json (tipo de cada recinto: exterior, circulación, ...)
Salida   : v2/plans/puertas_v2.json

La lógica está en tools/puertas.py (compartida con tools/scripts/json_to_dxf.py):
reglas R1-R8 para el abatimiento cuando el modelo no lo indica, y una puerta
"generada" para cada recinto al que no se llega desde el acceso. Es CONVENCIÓN DE
DISEÑO, no norma: ningún artículo OGUC sobre puertas está transcrito en el repo.

Uso:  python derive_puertas.py
Sale con código 1 si queda algún recinto sin acceso posible.
"""
import json
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2.parents[2] / "tools"))
import puertas  # noqa: E402

DATA = json.loads((V2 / "calcs" / "plan_data.json").read_text(encoding="utf-8"))
REC = json.loads((V2 / "plans" / "recintos_v2.json").read_text(encoding="utf-8"))
OUT = V2 / "plans" / "puertas_v2.json"


def main():
    res = puertas.desde_plan_data(DATA, REC)
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for lv, ds in res["niveles"].items():
        for d in ds:
            gen = "GENERADA " if d.get("generada") else ""
            if d["tipo"] == "corredera":
                print(lv, d["codigo"], gen + "corredera")
            else:
                print(lv, d["codigo"], gen + d["tipo"], "-> abre hacia", d["abre_hacia"],
                      "| bisagra", d["bisagra_mano"], "| esquina %.2f" % d["distancia_a_esquina"],
                      "|", d["regla"], "| cruces:", d["verificacion"]["cruces"] or "-",
                      "| dentro:", d["verificacion"]["arco_dentro_del_recinto"],
                      "| ADV" if "advertencia" in d else "")
    for lv, sin in res["sin_solucion"].items():
        print("SIN ACCESO POSIBLE", lv, sin)
    for lv, rs in res.get("residuales", {}).items():
        for r in rs:
            print("AVISO", lv, r)
    print("escrito", OUT)
    return 1 if res["sin_solucion"] else 0


if __name__ == "__main__":
    sys.exit(main())
