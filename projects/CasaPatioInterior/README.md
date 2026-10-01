# Casa con patio interior

Vivienda unifamiliar de dos pisos con patio interior, envolvente 13,00 × 14,00 m,
cumbrera a +7,10 m. Anteproyecto de arquitectura, **rev. H**.

Origen: archivos `casa_rev_g` + `croquis-a-3d.skill` entregados en `sources/Test/`.
Esta revisión corrige la escalera y separa lo medido de lo declarado.

## Sitio

- **Dirección / Rol:** por definir
- **Emplazamiento:** entorno de **Concepción**, Gran Concepción, Región del Biobío
  (indicación del usuario, 2026-10-01)
- **Comuna / PRC:** por definir
- **Zona térmica (OGUC 4.1.10 / DS 15/2024, zonas A–I):** por definir. Pista sin
  verificar: comuna de Concepción → E.
- **Zona sísmica (NCh 433) / suelo (DS 61):** por definir. Pista sin verificar:
  comuna de Concepción → zona 3. El suelo exige estudio geotécnico.

> Saber que el sitio está cerca de Concepción no basta para verificar. La zona
> térmica y la sísmica se definen **por comuna**, y el PRMC y el PPDA aplican
> según la comuna. Instrumentos, comunas y estado de verificación están en
> [`docs/region_concepcion.md`](../../docs/region_concepcion.md). Mientras
> `site.json` no tenga comuna, las reglas térmicas no emiten veredicto.
>
> Los metadatos del archivo original mencionaban Chillán; corresponden a la
> ubicación del usuario al generar la skill, no al emplazamiento, y fueron
> descartados deliberadamente.

## Programa

- **Tipo:** vivienda unifamiliar aislada
- **Pisos:** 2
- **Superficie edificada declarada:** 263,16 m² (ver contraste abajo)
- **Superficie de losa medida:** 261,29 m²

### Recintos declarados en el documento

Primer piso: hall de acceso, living, comedor, cocina, logia, dormitorio 1,
baño 1, baño 2, clóset, vestíbulo de escalera, tres galerías, patio interior.

Segundo piso: dormitorio principal con walk-in clóset y baño principal,
dormitorios 4 y 5, baño 3, sala de estar, tres pasarelas.

> Estas superficies **no son re-derivables** desde el modelo: el JSON contiene
> muros, vanos y losas, pero no polígonos de recinto. Son datos declarados.

## Cuadro de superficies

| | Documento | Geometría medida | Diferencia |
|---|-----------|------------------|-----------|
| Primer piso | 152,04 m² | 155,64 m² | +3,60 m² |
| Segundo piso | 111,12 m² | 105,65 m² | −5,47 m² |
| **Total** | **263,16 m²** | **261,29 m²** | −1,87 m² |

Las columnas miden cosas distintas: el cuadro descuenta patios, pasos y vacíos no
computables; la losa es el contorno construido. La diferencia de +3,60 m² en el
primer piso coincide exactamente con el porche de acceso.

## Alturas

| Nivel | Cota | Altura libre |
|-------|------|-------------|
| Primer piso | +0,00 | 2,60 m |
| Segundo piso | +2,85 | 2,50 m |
| Cumbrera | +7,10 | — |

## Registro de cumplimiento normativo

| Norma | Artículo | Estado | Verificado por | Fecha |
|-------|----------|--------|----------------|-------|
| Consistencia geométrica | escalera vs entrepiso | **CUMPLE** | `norm_check.py` (déficit 0,001 m) | 2026-09-18 |
| OGUC | Art. 4.1.1 altura de locales | INCONCLUSO | umbral no transcrito | 2026-09-18 |
| OGUC | Art. 4.2.11 escaleras | INCONCLUSO | umbral no transcrito | 2026-09-18 |
| OGUC | Art. 4.1.10 térmica (texto DS 15/2024, zonas A–I) | INCONCLUSO | tabla no transcrita; falta comuna | 2026-10-01 |
| PPDA Concepción Metropolitano | DS 6/2018 MMA, estándar vivienda nueva | PENDIENTE | aplica solo si la comuna está en el PPDA; tabla no transcrita | 2026-10-01 |
| PRMC | áreas de riesgo (tsunami, inundación, remoción, incendio) | PENDIENTE | requiere predio y lámina de riesgos | 2026-10-01 |
| OGUC | Art. 4.1.2 iluminación y ventilación | DECLARADO | afirmado en el documento, no verificado aquí | — |
| OGUC | Art. 4.1.4 ventilación baños/cocina | DECLARADO | afirmado en el documento, no verificado aquí | — |
| NCh 433 + DS 61 | diseño sísmico; clasificación de suelo | PENDIENTE | requiere estudio geotécnico y calculista; no hay solver | — |

> **INCONCLUSO no es un incumplimiento**: significa que el umbral oficial no ha
> sido transcrito y por tanto no hay contra qué comparar. Procedimiento en
> `docs/norms.md`.

## Hallazgos abiertos

| # | Hallazgo | Severidad | Estado |
|---|----------|-----------|--------|
| 1 | Escalera no alcanzaba el segundo piso (déficit 0,168 m) | **grave** | **corregido en rev. H** |
| 2 | Documento, JSON y OBJ declaraban 17 / 15 / 16 contrahuellas | grave | corregido en rev. H |
| 3 | Tope de 260 m² citado sin indicar su instrumento de origen | **abierto** | requiere fuente |
| 4 | Cuadro de superficies no re-derivable desde el modelo | abierto | faltan polígonos de recinto |
| 5 | OBJ sin normales (`vn 0`) | menor | el 3D ahora se produce en Blender; el OBJ queda solo como intercambio |
| 6 | Visor 3D HTML dependía de three.js por CDN | menor | **resuelto**: el 3D se construye en Blender (`model/casa_rev_h.blend`) |
| 7 | Altura bajo cubierta inclinada en p2 no medida | menor | abierto |
| 8 | Cubierta mal construida en 3D: faldones junto al patio al 152 % y 56 % (no al 35,7 %), cumbrera en +7,32 (no +7,10), entretecho abierto al patio; bandas 2 y 3 del JSON sin voladizo sobre el patio (9,25 y 10,45 en vez de 8,75 y 9,95) | grave | **corregido 2026-10-01**: medido 35,7 % en todos los faldones, cumbrera 7,100, 0 rendijas. Ver `docs/lessons.md` |
| 9 | **Orientación contradictoria.** La convención del repo (+Y sur) pone el norte hacia y = 0, pero el documento de origen titula «ELEVACIÓN FRONTAL · SUR» a la fachada del porche (y = 0), «POSTERIOR · NORTE» a la de y = 14, y `recintos.json` llama «Galería/Pasarela norte» a lo que está en y alto. La flecha de norte de las plantas, el sol de Blender y los nombres de los renders siguen la convención, y por tanto contradicen al documento | **grave** para asoleamiento y térmica | **abierto**: decidir cuál vale. Si el JSON es +Y norte, basta poner `"norte": "+y"` en `meta` para las plantas |
| 10 | El rótulo «Hall de acceso» (`recintos.json`, punto 5,60; 1,15) cae dentro del porche (y 0–1,50), no en el hall, que empieza en y = 1,70 | menor | abierto: el punto es aproximado por definición; falta la delimitación real |
| 11 | Renders en `exports/renders/` anteriores a la corrección de cubierta | menor | abierto: regenerar con el comando de abajo (EEVEE) |

El hallazgo 3 es el más relevante para permisos: el propio documento reconoce
superar ese tope en 3,16 m², y un excedente así depende por completo del criterio
de medición.

## Archivos

```
plans/casa_rev_g.json        modelo original (referencia)
plans/casa_rev_h.json        modelo corregido — FUENTE DE VERDAD
plans/recintos.json          rótulos de recinto (nombres y superficie declarada)

planos/planta_p1.dxf         PLANTA PRIMER PISO acotada y rotulada
planos/planta_p2.dxf         PLANTA SEGUNDO PISO acotada y rotulada
planos/vista_planta_p1.png   vista de control del plano
planos/vista_planta_p2.png   vista de control del plano

model/casa_rev_h.blend       modelo 3D en Blender (geometría paramétrica)
exports/renders/*.png        4 renders desde Blender
exports/casa_rev_h.obj/.mtl  intercambio a otros CAD

calcs/model_extract.json     geometría medida (generada)
calcs/memoria_geometrica.md  memoria de cálculo y detalle del error corregido
```

### Contenido de los planos DXF

Capas separadas, apagables por separado: `A-MURO` `A-MURO-RELL` `A-VANO`
`A-LOSA` `A-ESCA` `A-COTA` `A-TEXT` `A-RECI` `A-SIMB` `A-CUAD`.

Escala 1:100 (lámina A3, presentación «A3 1-100» en el DXF). Los textos usan el
estilo TrueType `ARQ` y tienen una altura mínima de 2 mm en papel. Cada lámina
incluye:
- muros cortados en los vanos, con relleno;
- puertas con hoja y arco, correderas con dos hojas, y ventanas con alféizar y vidrio;
- cadena de cotas parciales por eje de muro, más la cota total;
- rótulo de cada recinto con su superficie;
- códigos de vano (P01, V01…) con su cuadro de vanos;
- escalera con lo que queda sobre el plano de corte en segmentado;
- símbolo de norte, cota de nivel NPT y viñeta.

El abatimiento de las puertas no está en el JSON. Se dibuja por defecto, y la
lámina lo declara en una nota. Para fijarlo, agregue `hinge`/`swing`/`operation`
al vano.

> Las superficies de recinto llevan la marca **(s/doc)**: provienen del cuadro
> del documento rev. G y **no están medidas** desde la geometría. Ver hallazgo 4.

### Regenerar todo

```bash
# 3D en Blender
BUILD_SPEC=projects/CasaPatioInterior/plans/casa_rev_h.json BUILD_OUT=projects/CasaPatioInterior/model/casa_rev_h.blend   blender --background --python tools/scripts/blender_build.py

# renders
RENDER_OUT=projects/CasaPatioInterior/exports/renders   blender --background projects/CasaPatioInterior/model/casa_rev_h.blend   --python tools/scripts/blender_render.py

# planos acotados (escala de impresion 1:100 por defecto)
python tools/scripts/json_to_dxf.py   projects/CasaPatioInterior/plans/casa_rev_h.json   --outdir projects/CasaPatioInterior/planos   --recintos projects/CasaPatioInterior/plans/recintos.json   --escala 100

# vistas de control de los planos
python tools/scripts/dxf_preview.py   projects/CasaPatioInterior/planos/planta_p1.dxf   -o projects/CasaPatioInterior/planos/vista_planta_p1.png

# medicion y verificacion normativa
python tools/scripts/json_to_extract.py   projects/CasaPatioInterior/plans/casa_rev_h.json   -o projects/CasaPatioInterior/calcs/model_extract.json
python tools/norm_check.py   projects/CasaPatioInterior/calcs/model_extract.json   --site projects/CasaPatioInterior/site.json
```

## Enfoques rechazados

| Slug | Qué se probó | Por qué falló (medido) |
|------|--------------|------------------------|
| escalera-tramo0-8 | Alargar el tramo 0 a 8 peldaños | Termina en y=0,88 e invade el descanso (y 0,20–1,16). Se alargó el tramo 1 a 9, que termina en y=3,68 dentro del vacío que llega a 3,98. |

## Versiones

| Versión | Ruta | Qué cambió y por qué |
|---------|------|----------------------|
| rev. G | `plans/casa_rev_g.json` | Original recibido |
| rev. H | `plans/casa_rev_h.json` | Corrige escalera a 17 contrahuellas; limpia metadatos de ubicación |
| rev. H (corr. 2026-10-01) | `plans/casa_rev_h.json` | Bandas 2 y 3 de cubierta: inicio en y = 8,75 y 9,95 (voladizo de 0,25 m sobre el patio, como las bandas 0 y 1). No cambia muros, vanos ni losas: el extract medido es idéntico |

## Estado

`review` — geometría corregida y verificada; cumplimiento normativo pendiente de
transcribir umbrales y de definir comuna.
