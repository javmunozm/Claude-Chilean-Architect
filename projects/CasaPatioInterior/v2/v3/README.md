# Casa con patio interior — v3

Vivienda unifamiliar de dos pisos con patio interior, envolvente 13,00 × 14,00 m.
**v3 rehace el proyecto desde `sources/Test/`** con el sistema actualizado
(2026-10-02): `tools/cubierta.py`, `tools/puertas.py`, `tools/scripts/verificar_modelo3d.py`.
Descende de v2 (`projects/CasaPatioInterior/v2/`), que queda intacta, igual que v0.

## Qué cambia respecto de v2 y por qué

**Geometría: nada.** Se reconstruyó todo (recintos, FCStd, medición, cortes, puertas,
DXF/PDF, OBJ) con los scripts de v2 copiados a `v3/plans/` y con las rutas ajustadas
a la nueva profundidad. Medido el 2026-10-02: el `calcs/model_extract.json` de v3 es
idéntico al de v2 salvo nombre de proyecto y ruta de origen, y las 18 decisiones de
puerta de `puertas_v3.json` son idénticas a las de v2. Es decir, **el sistema
actualizado reproduce v2 de forma determinista**; v3 aporta una cadena completa
re-ejecutada y verificada con las herramientas nuevas, no un diseño distinto.

| Qué | v2 | v3 |
|-----|----|----|
| Fuente de geometría | `../plans/casa_rev_h.json` (v0) | igual, importada desde v0 (`../../plans/`) |
| Recintos | `recintos_v2.json` | `recintos_v3.json`, rederivado del documento `sources/Test/planos_vivienda_rev_G.html`; 30 recintos, áreas a ejes ± 0,01 m² del documento |
| Cubierta, encuentros de muros | `tools/cubierta.py` | igual |
| Puertas | `tools/puertas.py` | igual; 18 puertas, 0 generadas |
| Verificación 3D | corrida tras el cambio de cubierta | corrida sobre el OBJ de v3 (ver abajo) |

## Fuente: qué se usó de `sources/Test`

- `planos_vivienda_rev_G.html`: rótulos y superficies declaradas de los recintos.
- `casa_rev_g.obj`: referencia para contrastar el OBJ de v3 (abajo).
- `croquis-a-3d.skill`: su `examples/casa_rev_g.json` es idéntico al `plans/casa_rev_g.json`
  de v0 (medido).

**La geometría de v3 viene de rev. H, no de rev. G.** Medido: rev. H difiere de rev. G en
solo tres cosas: metadatos de ubicación, voladizo de las bandas de cubierta sobre el patio
(rev. G: 9,25 / 10,45; rev. H: 8,75 / 9,95) y el tramo 1 de la escalera (rev. G: 8
peldaños; rev. H: 9). Con 8 peldaños la escalera no alcanza el segundo piso (déficit
0,168 m, hallazgo 1 de v0). Si prefieres reconstruir desde rev. G tal cual, hay que decidirlo:
nacería con ese error.

## Marco de coordenadas

Igual que v2, por decisión del usuario (2026-10-02): **+X este, +Y norte, +Z arriba**, origen
en la esquina NO de la envolvente a nivel NPT (el edificio ocupa Y = −14 … 0). Difiere de
`CLAUDE.md` (+Y sur, levógiro); ver `../README.md`. El norte es el del documento rev. G,
no verificado en terreno.

## Contraste con el OBJ original (`sources/Test/casa_rev_g.obj`)

Medido sobre los vértices de ambos OBJ:

| Grupo | Test rev. G | v3 |
|-------|-------------|----|
| Losa | x 0…13, z 0…14, cota −0,35…2,85 | idéntico |
| Cubierta | x −0,4…13,4, z −0,4…14,4, cota 2,55…7,10 | idéntico |
| Muro | cota 0…7,10 | cota 0…6,88 (el cierre bajo cubierta termina bajo el faldón; la cumbrera de cubierta sí llega a 7,10) |
| Terreno | z −9…24 | z −10…23: **desplazado 1 m en ese eje; no investigado**, el sitio no está definido |

## Superficies (m²)

Iguales a v2: losa medida 261,29; espacio útil 256,81 (suma de los `Space`); útil p1 130,61;
ventanas 72,74; volumen de muros 77,114 m³. Documento a ejes: p1 152,04 y p2 111,12.

## Verificación (2026-10-02)

| Paso | Resultado |
|------|-----------|
| `build_model.py` | `BUILD OK` |
| `tools/norm_check.py` | **INCONCLUSO**: PASS 1, FAIL 0, UNVERIFIED 36, SKIP 113. El único PASS es consistencia geométrica de la escalera (déficit 0,001 m) |
| `tools/render_check.py` | GATE OK: PDF existente y vigente. Verificarlo con `--require dxf,pdf,png` no se corrió |
| `verificar_modelo3d.py --desfase-y 14` | **OK**: 0,00 m² sin techo en p1 y p2; 0 de 11 848 y 0 de 22 036 rayos escapan; 0 de 132 aristas de cubierta sin pareja; superficies coincidentes 0,144 m² (pavimento del porche dentro de la losa, dato del JSON) |
| Vistas | Revisadas a ojo: `exports/vistas/3d_noreste.png`, `3d_suroeste.png`, `planta_p1.png`, `planta_p2.png` |

El veredicto normativo no es PASS: los umbrales OGUC siguen sin transcribir y `site.json` no
tiene comuna (ver `docs/region_concepcion.md`).

## Hallazgos abiertos

| # | Hallazgo | Medida | Severidad | Estado |
|---|----------|--------|-----------|--------|
| 1 | Holgura de cabeza sobre el descanso de la escalera | **1,259 m** mínimo | grave | **abierto, decisión de diseño**. Se reproduce como en el documento, por indicación del usuario (2026-10-02) |
| 2 | La escalera termina antes de la losa del p2 | **0,30 m** | grave | **abierto, decisión de diseño**, igual que el anterior |
| 3 | Tope de 260 m² sin fuente | losa 261,29 m² | abierto | requiere el instrumento de origen |
| 4 | Sin comuna, zona térmica ni zona sísmica | `site.json` en null | abierto | requiere dato del usuario |
| 5 | Umbrales OGUC sin transcribir | 36 UNVERIFIED | abierto | transcribir desde texto oficial |
| 6 | Terreno del OBJ desplazado 1 m respecto del original | ver contraste | menor | abierto, sin investigar |
| 7 | Sin cortes, elevaciones ni planta de cubierta | — | menor | abierto (v0 y v2 tampoco los tenían) |

## Archivos

```
plans/casa_v3.FCStd        modelo FreeCAD (Arch), FUENTE DE VERDAD de v3
plans/recintos_v3.json     polígonos de recinto derivados del documento
plans/puertas_v3.json      decisión por puerta
plans/*.py                 scripts copiados de v2, con rutas de v3
calcs/model_extract.json   medido
calcs/plan_data.json       geometría de los planos
exports/planta_p1.dxf, planta_p2.dxf, planos_v3.pdf, casa_v3.obj/.mtl
exports/vistas/            PNG de control
site.json                  copia sin cambios de v0 (comuna sin definir)
```

## Regenerar

Desde la raíz del repo; `PYTHONIOENCODING=utf-8` evita el fallo silencioso de `freecadcmd`
con «Baño» (ver `docs/lessons.md`).

```bash
P=projects/CasaPatioInterior/v2/v3; export PYTHONIOENCODING=utf-8; F="E:/FreeCAD/bin/freecadcmd.exe"
python $P/plans/derive_recintos.py
V2_DIR=$P BUILD_OUT=$PWD/$P/plans/casa_v3.FCStd "$F" $P/plans/build_model.py
V2_DIR=$P MEASURE_MODEL=$PWD/$P/plans/casa_v3.FCStd MEASURE_OUT=$PWD/$P/calcs/model_extract.json "$F" $P/plans/measure_v3.py
V2_DIR=$P EXPORT_MODEL=$PWD/$P/plans/casa_v3.FCStd EXPORT_OUT=$PWD/$P/calcs/plan_data.json "$F" $P/plans/export_slices.py
python $P/plans/derive_puertas.py
V2_DIR=$P ANNOTATE_MODEL=$PWD/$P/plans/casa_v3.FCStd "$F" $P/plans/annotate_doors.py
python $P/plans/make_dxf.py
V2_DIR=$P EXPORT_MODEL=$PWD/$P/plans/casa_v3.FCStd EXPORT_OBJ=$PWD/$P/exports/casa_v3.obj "$F" $P/plans/export_obj.py
python tools/scripts/verificar_modelo3d.py $P/exports/casa_v3.obj --spec projects/CasaPatioInterior/plans/casa_rev_h.json --recintos $P/plans/recintos_v3.json --desfase-y 14
VISTAS_OBJ=$PWD/$P/exports/casa_v3.obj VISTAS_OUT=$PWD/$P/exports/vistas blender --background --python tools/scripts/vistas_obj.py
python tools/norm_check.py $P/calcs/model_extract.json --site $P/site.json
python tools/render_check.py $P
```

## Estado

`review` — geometría reconstruida, medida y verificada en 3D; cumplimiento normativo
pendiente de transcribir umbrales y de definir comuna; dos hallazgos de escalera abiertos.
