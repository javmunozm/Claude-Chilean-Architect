# Casa con patio interior — v4

**Desciende de:** v3 (`../v3/`). Índice de versiones: `../../README.md`.

v4 no cambia la casa: cambia **el juego de planos**. La geometría, los recintos y las 18
puertas son los de v3 (medido el 2026-10-04: `model_extract.json` y `puertas_v4.json`
idénticos a los de v3). Lo nuevo es lo que una revisión del 2026-10-04 encontró faltante
frente a lo que entrega un arquitecto y frente al propio documento de origen (rev. G, que
trae elevaciones y un dibujo de cubierta que v2/v3 no producían).

## Qué cambia respecto de v3

| v3 | v4 |
|----|----|
| 2 láminas: plantas del primer y segundo piso | **5 láminas**: plantas p1 y p2, planta de cubierta, elevaciones (4), cortes A-A y B-B |
| PDF de 172 x 122 mm aunque la viñeta decía «1:50 (A2)»: impreso salía a ~1:172 | PDF a **tamaño A2 real (594 x 420 mm)**: se imprime y se mide a la escala de la viñeta |
| Fecha y revisión escritas a mano en el script | Fecha del día en que se genera; revisión `v4-A` |
| Viñeta sin propietario, arquitecto, dirección ni número de lámina | Viñeta con proyecto, propietario, arquitecto y registro (`source/proyecto.json`), dirección, rol y comuna (`site.json`), escala, papel, fecha, revisión y **lámina N / 5**. Un dato en null se imprime «por definir» |
| DXF sin presentación de impresión | Cada DXF trae la presentación `A2 1-50` o `A2 1-100` con su ventana a escala |
| Sin líneas de corte | Plantas con las líneas de corte A-A y B-B |

Causa medida del PDF fuera de escala: `finalize()` del dibujo de ezdxf reduce la figura de
matplotlib a ~6,8 x 4,8 pulgadas; v4 la devuelve al tamaño del papel después de dibujar
(`scripts/lamina.py`). v2 y v3 conservan el defecto: sus PDF no están a escala.

## Juego de láminas (`exports/planos_v4.pdf`, DXF en `exports/drawings/`)

| N | Lámina | Escala | Contenido | De dónde sale |
|---|--------|--------|-----------|---------------|
| 1 | Planta primer piso | 1:50 | muros, vanos con abatimiento, ejes, cotas, recintos, cuadro de superficies y de vanos, líneas de corte | corte del FCStd a +1,20 m (`export_slices.py`) |
| 2 | Planta segundo piso | 1:50 | ídem | ídem |
| 3 | Planta de cubierta | 1:50 | aguas, cumbrera, borde del patio, flechas de escurrimiento con pendiente (35,7 % y 19,0 %) | vista superior del FCStd (`export_views.py`); pendientes calculadas de cumbrera y alero del JSON |
| 4 | Elevaciones sur, norte, oriente y poniente | 1:100 | fachadas sin líneas ocultas, terreno, niveles NPT ±0,00, +2,85 y cumbrera +7,10 | proyección del FCStd (`TechDraw.projectEx`) |
| 5 | Cortes A-A y B-B | 1:50 | sección con poché, escalera, losas, cubiertas, niveles | FCStd recortado por el plano (A-A: X = 1,67 m; B-B: Y = −4,50 m) |

Todas las líneas salen del modelo: no se dibuja nada a mano. Lo que el modelo no tiene,
no aparece.

## Lo que el juego todavía no tiene

| Falta | Por qué | Qué se necesita |
|-------|---------|-----------------|
| Plano de ubicación y emplazamiento (deslindes, distanciamientos, rasantes) | no hay sitio definido: dirección, rol, comuna y deslindes en null | datos del terreno y certificado de informaciones previas |
| Canales y bajadas de aguas lluvias, terminaciones de fachada | no están en el modelo | modelarlos |
| Detalles constructivos (escalera, encuentros, aislación) | no hay método automático | dibujo de detalle |
| Especificaciones técnicas (EETT) | `spec-writer` no se ha ejecutado | correr `spec-writer` sobre v4 |
| Cálculo estructural e instalaciones | el repo no tiene software de cálculo estructural | calculista y proyectistas de especialidad |
| Veredicto normativo | umbrales OGUC sin transcribir | transcribir desde el texto oficial |

## Verificación (2026-10-04)

| Paso | Resultado |
|------|-----------|
| `build_model.py` | `BUILD OK` |
| Extract y puertas | idénticos a v3 |
| `verificar_modelo3d.py --desfase-y 14` | OK: 0 m² sin techo, 0 rayos escapan, cubierta cerrada |
| `render_check.py --require dxf,pdf,png` | GATE OK |
| `norm_check.py` | INCONCLUSO: PASS 1, FAIL 0, UNVERIFIED 36, SKIP 113 |
| PDF | 5 páginas de 594,0 x 420,0 mm (medido sobre el MediaBox) |
| Láminas | revisadas a ojo (PNG en `exports/drawings/`) |

## Hallazgos abiertos

Los de v3 siguen abiertos (holgura de escalera 1,259 m; escalera que termina 0,30 m antes
de la losa; tope de 260 m² sin fuente; sitio sin comuna; umbrales sin transcribir). El
corte A-A muestra la escalera bajo la losa del segundo piso, que es donde se mide la
holgura de 1,259 m.

## Archivos

```
source/proyecto.json         nombre, etapa, propietario, arquitecto (viñeta); null = por definir
scripts/                     macros propias de v4: las de v3 más
  lamina.py                  marco A2, viñeta, numeración, PDF a escala, presentación DXF
  export_views.py            (FreeCAD) cubierta, elevaciones y cortes por proyección
  make_views.py              láminas 3 a 5 y el PDF de las 5 láminas
calcs/views_data.json        segmentos y poché de cada vista, en metros
exports/planos_v4.pdf        juego completo, A2 real
exports/drawings/            planta_p1, planta_p2, cubierta, elevaciones, cortes (.dxf + .png)
exports/model/               casa_v4.FCStd (FUENTE DE VERDAD), casa_v4.obj/.mtl
exports/renders/             vistas 3D de control
```

## Regenerar

Desde la raíz del repo. Los primeros pasos son los de v3 (ver `../v3/README.md`).

```bash
P=projects/CasaPatioInterior/versions/v4; M=$PWD/$P/exports/model/casa_v4.FCStd
export PYTHONIOENCODING=utf-8; F="E:/FreeCAD/bin/freecadcmd.exe"
V2_DIR=$PWD/$P BUILD_OUT=$M "$F" $P/scripts/build_model.py
V2_DIR=$PWD/$P MEASURE_MODEL=$M MEASURE_OUT=$PWD/$P/calcs/model_extract.json "$F" $P/scripts/measure_v4.py
V2_DIR=$PWD/$P EXPORT_MODEL=$M EXPORT_OUT=$PWD/$P/calcs/plan_data.json "$F" $P/scripts/export_slices.py
python $P/scripts/derive_puertas.py
V2_DIR=$PWD/$P ANNOTATE_MODEL=$M "$F" $P/scripts/annotate_doors.py
V2_DIR=$PWD/$P VIEWS_MODEL=$M VIEWS_OUT=$PWD/$P/calcs/views_data.json "$F" $P/scripts/export_views.py
python $P/scripts/make_dxf.py          # plantas (DXF)
python $P/scripts/make_views.py        # cubierta, elevaciones, cortes y el PDF de las 5 láminas
V2_DIR=$PWD/$P EXPORT_MODEL=$M EXPORT_OBJ=$PWD/$P/exports/model/casa_v4.obj "$F" $P/scripts/export_obj.py
python tools/scripts/verificar_modelo3d.py $P/exports/model/casa_v4.obj \
  --spec projects/CasaPatioInterior/versions/v0/source/casa_rev_h.json \
  --recintos $P/calcs/recintos_v4.json --desfase-y 14
python tools/norm_check.py $P/calcs/model_extract.json --site projects/CasaPatioInterior/site.json
python tools/render_check.py $P --require dxf,pdf,png
```

`calcs/recintos_v4.json` es copia del de v3 (misma geometría): `derive_recintos.py` con
otra versión de shapely reordena vértices (ver `../v2/README.md`).

## Estado

`review` — juego de 5 láminas a escala, verificado; faltan emplazamiento (sin sitio),
detalles, EETT y especialidades; cumplimiento normativo pendiente.
