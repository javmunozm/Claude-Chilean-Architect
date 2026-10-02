# Memoria geométrica — Casa con patio interior, rev. H

Todas las cifras de este documento salen de medir `plans/casa_rev_h.json` con
`tools/scripts/json_to_extract.py`. Ninguna está transcrita a mano desde el
documento de planos: el objetivo es justamente poder contrastar ambos.

**Reproducir:**

```bash
python tools/scripts/json_to_extract.py \
  projects/CasaPatioInterior/versions/v0/source/casa_rev_h.json \
  -o projects/CasaPatioInterior/versions/v0/calcs/model_extract.json
```

## 1. Escalera — el error corregido en esta revisión

### El defecto en rev. G

| Fuente | Contrahuellas | Altura salvada | ¿Llega a +2,85? |
|--------|---------------|----------------|-----------------|
| Documento de planos rev. G | 17 | 2,856 m | sí (declarado) |
| `casa_rev_g.json` (`steps` 7+8) | 15 | 2,514 m | **no** |
| `casa_rev_g.obj` generado | 16 | 2,682 m | **no** |

Las tres fuentes decían cosas distintas. El modelo 3D terminaba la escalera a
2,682 m contra un entrepiso de 2,850 m: **déficit de 0,168 m**, exactamente una
contrahuella. En el modelo, la escalera no llegaba al segundo piso.

El valor `riser = 0,1676` del JSON es precisamente 2,85 / 17, de modo que la
intención del proyectista era 17 contrahuellas. El error estaba en el reparto por
tramos, no en la dimensión del peldaño.

### La corrección

`build3d.py` cuenta una alzada por cada descanso además de los peldaños de cada
tramo, así que el total es `tramo0 + descanso + tramo1`.

| | rev. G | rev. H |
|---|--------|--------|
| Tramo 0 (baja en −y) | 7 | 7 |
| Descanso | 1 | 1 |
| Tramo 1 (sube en +y) | 8 | **9** |
| **Total alzadas** | 16 | **17** |
| Altura alcanzada | 2,682 m | **2,849 m** |
| Déficit vs 2,850 m | 0,168 m | 0,001 m |

**Por qué se alargó el tramo 1 y no el tramo 0.** El tramo 0 desciende desde
y = 3,12 hacia −y; con 8 peldaños terminaría en y = 0,88 e invadiría el descanso,
que ocupa y = 0,20 … 1,16. El tramo 1 asciende desde y = 1,16 y con 9 peldaños
termina en y = 3,68, dentro del vacío de losa que llega hasta y = 3,98. Es la
única de las dos opciones que cabe en la geometría existente.

El residuo de 0,001 m proviene de redondear 2,85/17 = 0,167647 a 0,1676 m. Es
despreciable constructivamente y se absorbe en el peldaño de llegada.

### Dimensiones resultantes

| Parámetro | Valor medido |
|-----------|--------------|
| Contrahuella | 0,1676 m |
| Huella | 0,28 m |
| Contrahuellas | 17 |
| Altura salvada | 2,8492 m |
| Ancho libre de tramo | 0,94 m |
| Relación 2·ch + h | 0,6152 m |
| Tipo | En U, dos tramos rectos con descanso |

> La relación de Blondel (2·ch + h) se suele situar entre 0,60 y 0,64 m; el
> proyecto da 0,6152 m, dentro de ese rango de buena práctica. **Esto no es una
> verificación normativa**: la exigencia aplicable de OGUC Art. 4.2.11 no ha sido
> transcrita desde el texto oficial, de modo que el cumplimiento queda pendiente.
> Ver §4.

## 2. Superficies medidas

Superficie de losa, medida por contorno construido:

| Elemento | Superficie | Espesor |
|----------|-----------|---------|
| Losa nivel p1 (z = 0,00) | 155,64 m² | 0,35 m |
| Losa nivel p2 (z = +2,85) | 105,65 m² | 0,25 m |
| **Total losa** | **261,29 m²** | |

### Contraste con el cuadro de superficies del documento

| | Documento | Geometría | Diferencia |
|---|-----------|-----------|-----------|
| Primer piso | 152,04 m² | 155,64 m² | +3,60 m² |
| Segundo piso | 111,12 m² | 105,65 m² | −5,47 m² |
| Total | 263,16 m² | 261,29 m² | −1,87 m² |

Las dos columnas **no miden lo mismo y no deben cuadrar directamente**: el cuadro
del documento descuenta patios, pasos y vacíos no computables, mientras que la
losa es el contorno construido. La diferencia de +3,60 m² en el primer piso
coincide exactamente con el porche de acceso, que el cuadro declara como exterior
cubierto no computable — lo que confirma que la discrepancia es de criterio de
medición y no un error de dibujo.

**Lo que sí queda pendiente:** el total de 263,16 m² del documento no es
re-derivable desde la geometría con la información disponible. Para cerrarlo hace
falta el polígono de cada recinto, que el JSON no contiene (sólo trae muros,
vanos y losas). Mientras eso no exista, el cuadro de superficies es un dato
declarado, no medido.

Esto importa porque el propio documento señala que **el proyecto supera un tope
de 260,00 m² en 3,16 m²**. Un excedente de esa magnitud depende por completo del
criterio de medición, y hoy no puede verificarse desde el modelo.

## 3. Alturas libres

| Nivel | Cota | Altura piso a cielo | Documento |
|-------|------|--------------------|-----------|
| p1 | +0,00 | 2,60 m | 2,60 m |
| p2 | +2,85 | 2,50 m | 2,50 m |

Coinciden. La altura libre se calcula como la cota del nivel superior menos el
espesor de su losa, **no** como el muro más alto: los hastiales del proyecto
suben hasta +3,562 m sobre p1 y tomarlos como cielo daría una altura que no
existe en ningún recinto.

En p2 el cielo lo define el arranque de cubierta (muros a +5,35 m); la altura de
2,50 m corresponde a la zona de altura constante. **Bajo la cubierta inclinada la
altura es menor y no está medida en este modelo.**

Cumbrera a **+7,10 m**.

## 4. Estado de las verificaciones normativas

El verificador automático (`tools/norm_check.py`) evalúa la geometría contra
`tools/norms/rules.json`. Su estado actual:

| Regla | Resultado | Motivo |
|-------|-----------|--------|
| Consistencia escalera (aritmética) | **PASS** | déficit 0,001 m ≤ 0,005 m |
| OGUC Art. 4.1.1 — altura de locales | INCONCLUSO | umbral no transcrito |
| OGUC Art. 4.2.11 — ancho de escalera | INCONCLUSO | umbral no transcrito |
| OGUC Art. 4.1.10 — transmitancia | INCONCLUSO | tabla por zona no transcrita |

La única regla que emite veredicto es la de consistencia geométrica, porque **no
depende de ninguna norma**: es aritmética del propio modelo (la suma de
contrahuellas debe igualar el entrepiso). Por eso puede afirmarse con seguridad.

Las demás exigen transcribir el texto oficial del artículo citado. El documento
de planos rev. G afirma *«cumple»* en Art. 4.1.1, 4.1.2 y 4.1.4; esas
afirmaciones **no han sido verificadas aquí** y se reportan como declaraciones
del proyectista, no como verificaciones de este sistema.

Procedimiento para habilitarlas en `docs/norms.md`.

## 5. Lo que este modelo no puede responder

- **Superficie útil por recinto.** No hay polígonos de recinto en el JSON, sólo
  muros, vanos y losas. El cuadro de superficies no es re-derivable.
- **Ancho libre de paso en puertas.** Depende de marco, tope y ángulo de apertura;
  `json_to_extract.py` registra deliberadamente el ancho nominal y **no** deriva
  un `clear_width`, para no producir un cumplimiento falso en accesibilidad.
- **Altura bajo cubierta inclinada en p2.** Sólo está medida la zona de altura
  constante.
- **Cualquier verdicto estructural.** No hay cálculo sísmico y este repositorio no
  tiene solver. NCh 433 requiere un calculista.
- **Zona térmica y sísmica.** Dependen de la comuna, que no está definida. Ver
  `site.json`.
