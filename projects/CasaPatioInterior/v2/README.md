# Casa con patio interior — v2

Vivienda unifamiliar de dos pisos con patio interior, envolvente 13,00 × 14,00 m.
**v2 reconstruye el proyecto desde los documentos base** (`sources/Test/`) con la cadena
del repo: FreeCAD (objetos Arch) → medición con `tools/area_calc.py` → DXF/PDF dibujados
**desde el modelo medido**. Hereda de v0 solo la geometría fuente
(`../plans/casa_rev_h.json`, importada, no copiada) y el `site.json` sin cambios.

## Qué cambia respecto de v0 y por qué

| v0 (rev. H) | v2 |
|-------------|----|
| Modelo = JSON → mallas Blender/OBJ. Sin objetos Arch. | Modelo FreeCAD con Arch: 49 muros (45 + 4 hastiales), 55 vanos (Window/Door), 2 losas, 2 cubiertas, escalera (2 tramos Arch), 30 Space. |
| `calcs/model_extract.json` generado desde el JSON (`json_to_extract.py`). | Medido sobre el FCStd con `area_calc.extract()` + `plans/measure_v2.py`. |
| DXF dibujados desde el JSON (`json_to_dxf.py`); `render_check` BLOQUEADO (DXF fuera de `exports/`, sin PDF). | DXF dibujados desde cortes del FCStd (`export_slices.py` → `make_dxf.py`) en `exports/`, más PDF. `render_check`: OK. |
| Los recintos eran 2 "Space" ficticios por nivel (altura de nivel). Cuadro de superficies no re-derivable; superficies marcadas "(s/doc)". | 29 recintos con polígono propio, medidos. Cada área a ejes coincide con el documento (±0,01 m²). |
| Puntos de rótulo de `recintos.json` aproximados; varios no coinciden con el documento (p. ej. Hall de Acceso cae en el porche). | Rótulos tomados de las coordenadas del SVG del documento (x = 100 + 34·X, y = 579,2 − 34·Y, calibrado con los ejes). |
| OBJ sin normales (`vn` = 0). | `exports/casa_v2.obj` con 4 360 normales. |
| Altura bajo cubierta en p2 sin medir. | Medida con rayos verticales contra losa y cubierta (ver Alturas). |

**Se refuta una afirmación de v0.** `plans/recintos.json` decía que los polígonos de recinto
"no son reconstruibles" (18 de 26 con diferencias > 1,5 m²). Los recintos del documento sí se
reconstruyen: los cerrados por muros salen de los ejes; los de planta abierta (espacio libre,
galerías, comedor/living) con las cotas del documento. `derive_recintos.py` se detiene si un
área o un rótulo no cuadra.

## Marco de coordenadas — decisión que necesita tu confirmación

`CLAUDE.md` fija **+X este, +Y sur, +Z arriba**. Ese sistema es **levógiro**: FreeCAD es
dextrógiro, y representarlo obliga a espejar el edificio. v2 usa **+X este, +Y norte, +Z
arriba, origen en la esquina NO de la envolvente a nivel NPT** (el edificio ocupa
Y = −14 … 0). Es dextrógiro, no espeja nada, y el plano sale con norte arriba.
El origen es provisional: no hay levantamiento del sitio. El norte es el del documento
rev. G (flecha en las láminas); no está verificado en terreno.

## Superficies (m²)

| Nivel | Documento (a ejes) | A ejes, derivado | Útil medida (Space) | Losa medida |
|-------|--------------------|------------------|---------------------|-------------|
| Primer piso — recintos interiores | 152,04 | 152,04 | 130,61 | 155,64 |
| Segundo piso — recintos interiores | 111,12 | 111,12 | 96,24 | 105,65 |

"A ejes" y "útil" miden cosas distintas (la útil descuenta la huella de muros); la
diferencia no es un error. Exteriores (porche, patios, paso) no suman.

`delimitacion` en `plans/recintos_v2.json`: los recintos cerrados por muros (≥ 99 % del
perímetro sobre un eje) figuran como `muros`; el resto como **`inferida`**: parte de su borde
no es un muro (galerías, espacio libre, comedor/living, escalera p2, exteriores). Sus áreas
cuadran con el documento, pero esa línea de división es una inferencia de las cotas, no
geometría construida.

## Alturas libres (medidas)

| Zona | Mínima | Máxima | Qué la fija |
|------|--------|--------|-------------|
| p1, ala principal | 2,600 m | 2,600 m | cara inferior de la losa p2 |
| p1, ala oriente (cocina, comedor, living) | 2,671 m | 3,333 m | cubierta de una agua |
| p2 (bajo cubierta a dos aguas) | 2,516 m | 4,023 m | cubierta; mínimo junto al muro |

El `Space` modela la altura **mínima**; la máxima queda en `calcs/model_extract.json`
(`clear_height_max`). Cierra el hallazgo 7 de v0.

## Puertas: bisagra y abatimiento

Las 18 puertas tienen decisión registrada (`plans/puertas_v2.json`, anotada también en la
`Description` de cada objeto Door del FCStd) y se dibujan en los DXF con hoja y arco.
Son 15 batientes, 1 de doble hoja y 2 correderas. **Es una convención de diseño, no una
norma**: ningún artículo OGUC sobre puertas está transcrito, así que no se declara cumplimiento.

| Regla | Qué hace |
|-------|----------|
| R1 | Ancho ≥ 2,0 m y alto ≥ 2,3 m → corredera de vidrio (P02 y P03 de p1). |
| R2 | Ancho 1,2–2,0 m → doble hoja, abre hacia el exterior (P05 p1, al paso cubierto). |
| R3 | Acceso principal desde el porche → abre hacia el interior (P01 p1). |
| R3b | Puerta a patio desde una circulación → abre hacia el patio, para no bloquear la galería (P04 p1). |
| R4 | Recinto ↔ circulación → abre hacia el recinto, no hacia el pasillo. |
| R5 | Recinto ↔ baño, clóset o logia → abre hacia el baño, clóset o logia. |
| R6 | La bisagra va en la jamba más cercana a la esquina del recinto: la hoja abierta queda contra el muro. |
| R7 | El arco (radio = ancho libre) debe caer dentro del recinto y no cruzar mobiliario, escalera ni otro arco. Si falla, prueba la otra jamba y luego el otro lado. |
| R8 | Entre dos circulaciones, nunca abre hacia la escalera (P06 p1). |

Resultado: las 18 puertas cumplen R7 sin cruces. La "mano" se informa para quien empuja la
puerta (bisagra a su derecha o izquierda). Dos supuestos que conviene confirmar: que las
puertas de 2,7 y 2,8 m sean correderas (el documento menciona corredera solo para la del
living) y que el ventanal de 1,60 m sea de doble hoja.

## Hallazgos medidos en v2

| # | Hallazgo | Medida | Severidad | Estado |
|---|----------|--------|-----------|--------|
| 1 | **Holgura de cabeza sobre el descanso de la escalera** | **1,259 m** mínimo (la losa del p2 queda sobre el descanso, cota 1,34 m) | grave | **abierto, decisión de diseño** |
| 2 | **La escalera termina 0,30 m antes de la losa del p2** | último peldaño hasta y = 3,68 (doc.); la losa parte en y = 3,98 | grave | **abierto, decisión de diseño** |
| 3 | Escalera llega al nivel | déficit 0,0008 m, 17 contrahuellas × 0,1676 | — | cumple (consistencia geométrica) |
| 4 | Tope de 260 m² sin fuente | losa medida 261,29 m² | abierto | requiere el instrumento de origen |
| 5 | Sin comuna / zona térmica / zona sísmica | `site.json` en null | abierto | requiere dato del usuario |
| 6 | Umbrales OGUC sin transcribir | 36 verificaciones UNVERIFIED | abierto | transcribir desde texto oficial |

Los hallazgos 1 y 2 **no se corrigieron**: cambiar la escalera (rotar el giro, mover el vacío
de losa o prolongar el piso) es una decisión de diseño que altera programa y estructura. No
se cita un mínimo normativo de holgura porque no está transcrito.

## Cumplimiento normativo (arranca vacío; v2 no hereda veredictos)

| Norma | Estado | Detalle | Fecha |
|-------|--------|---------|-------|
| Consistencia geométrica de la escalera | CUMPLE | déficit 0,0008 m, máx. 0,005 | 2026-10-01 |
| OGUC 4.1.1 / 4.1.2 / 4.2 / 4.2.11 | INCONCLUSO | umbrales sin transcribir; mediciones sin contra qué juzgar | 2026-10-01 |
| OGUC 4.1.10 térmica | SKIP | falta comuna y tabla por zona | — |
| NCh 433 | PENDIENTE | requiere calculista | — |

`norm_check.py`: PASS 1 · FAIL 0 · UNVERIFIED 36 · SKIP 89 → **INCONCLUSO**. (v0 evaluaba 9
UNVERIFIED sobre solo 2 "recintos" ficticios; v2 evalúa cada recinto real.) Espacio Libre,
Logia, Clóset, Walk-in Clóset y Escalera no llevan etiqueta de clasificación (`area_calc`
clasifica por nombre) y por eso no activan reglas; el documento no declara su uso.

## Límites conocidos

- El abatimiento de puertas es un patrón de diseño, sin verificación normativa (ver Puertas). Las hojas solo se dibujan en planta; el modelo 3D no las abre.
- Cotas de planta a eje de muro; `make_dxf.py` exige un muro a ≤ 0,101 m de cada cota y de cada eje.
- `totals.wall_volume` suma por muro y cuenta dos veces los traslapes de esquina.
- Sin cortes ni elevaciones DXF (v0 tampoco los tenía) ni planta de cubierta.
- Las vistas 3D de `exports/vistas/` son de control (Blender Workbench), no renders de presentación.

## Archivos

```
plans/casa_v2.FCStd        modelo FreeCAD (Arch) — FUENTE DE VERDAD de v2
plans/recintos_v2.json     polígonos de recinto derivados y verificados
plans/derive_recintos.py   deriva recintos desde muros + SVG del documento
plans/build_model.py       construye el FCStd
plans/measure_v2.py        medición (area_calc + escalera, losas, alturas)
plans/export_slices.py     cortes del FCStd para los planos
plans/make_dxf.py          DXF + PDF desde los cortes
plans/export_obj.py        OBJ con normales
plans/derive_puertas.py    decide bisagra y abatimiento (reglas R1-R8)
plans/puertas_v2.json      decisión por puerta
plans/annotate_doors.py    escribe la decisión en los objetos Door del FCStd
calcs/model_extract.json   medido
calcs/plan_data.json       geometría de los planos
exports/planta_p1.dxf, planta_p2.dxf, planos_v2.pdf, casa_v2.obj/.mtl
exports/vistas/            PNG de control (planos y 3D)
```

## Regenerar

Desde la raíz del repo (rutas absolutas en las variables que lo piden):

```bash
python projects/CasaPatioInterior/v2/plans/derive_recintos.py
V2_DIR=projects/CasaPatioInterior/v2 BUILD_OUT=$PWD/projects/CasaPatioInterior/v2/plans/casa_v2.FCStd \
  "E:/FreeCAD/bin/freecadcmd.exe" projects/CasaPatioInterior/v2/plans/build_model.py
V2_DIR=projects/CasaPatioInterior/v2 MEASURE_MODEL=$PWD/projects/CasaPatioInterior/v2/plans/casa_v2.FCStd \
  MEASURE_OUT=$PWD/projects/CasaPatioInterior/v2/calcs/model_extract.json \
  "E:/FreeCAD/bin/freecadcmd.exe" projects/CasaPatioInterior/v2/plans/measure_v2.py
V2_DIR=projects/CasaPatioInterior/v2 EXPORT_MODEL=$PWD/projects/CasaPatioInterior/v2/plans/casa_v2.FCStd \
  EXPORT_OUT=$PWD/projects/CasaPatioInterior/v2/calcs/plan_data.json \
  "E:/FreeCAD/bin/freecadcmd.exe" projects/CasaPatioInterior/v2/plans/export_slices.py
python projects/CasaPatioInterior/v2/plans/derive_puertas.py
V2_DIR=projects/CasaPatioInterior/v2 ANNOTATE_MODEL=$PWD/projects/CasaPatioInterior/v2/plans/casa_v2.FCStd   "E:/FreeCAD/bin/freecadcmd.exe" projects/CasaPatioInterior/v2/plans/annotate_doors.py
python projects/CasaPatioInterior/v2/plans/make_dxf.py
python tools/norm_check.py projects/CasaPatioInterior/v2/calcs/model_extract.json --site projects/CasaPatioInterior/v2/site.json
python tools/render_check.py projects/CasaPatioInterior/v2
```

`freecadcmd` traga las excepciones de los scripts importados sin dejar traza: si un script
termina sin imprimir `saved` / `wrote`, ejecútalo dentro de un `try/except` que imprima el
traceback.

## Estado

`review` — geometría reconstruida, medida y exportada; cumplimiento normativo pendiente de
transcribir umbrales y de definir comuna; dos hallazgos de escalera abiertos.
