# Casa con patio interior — v5

**Desciende de:** v4 (`../v4/`). Índice de versiones: `../../README.md`.

v5 no cambia la casa. Agrega lo que el juego de v4 no tenía y que el usuario pidió el
2026-10-04, salvo el terreno, que queda fuera por instrucción del usuario:

- canales y bajadas;
- terminaciones de fachada;
- detalles constructivos;
- EETT;
- cálculo estructural.

Cada una tiene un agente que la produce y un lugar en el flujo de trabajo (`CLAUDE.md`,
`docs/agents.md`). Geometría, recintos y las 18 puertas son los de v4. Medido el
2026-10-04: `model_extract.json` y `puertas_v5.json` son idénticos antes y después de
reconstruir el modelo.

## Qué agrega respecto de v4

| Entrega | Agente | Herramienta | Salida |
|---------|--------|-------------|--------|
| Canales y bajadas | `drainage-designer` | `tools/aguas_lluvias.py` | 8 canales (6 de alero, 2 de encuentro con muro) y 10 bajadas, en el modelo (`Pipe Segment`) y en la lámina 3 con su cuadro; `calcs/aguas_lluvias.json` |
| Terminaciones de fachada | `facade-designer` | `source/terminaciones.json` | 8 partidas, línea de zócalo +0,60 y burbujas en las elevaciones (lámina 4) |
| Cálculo estructural | `structural-calculator` | `tools/estructura.py`, `tools/md_pdf.py` | `exports/memoria_calculo_v5.pdf` (predimensionamiento), `calcs/estructura_calc.json` |
| Detalles constructivos | `detail-drafter` | `scripts/make_details.py` | lámina 6: D1 alero, canal y bajada; D2 encuentro muro–losa; D3 zócalo y fundación; D4 escalera; D5 vano de ventana |
| EETT y cubicación | `spec-writer` | `scripts/make_eett.py` | `exports/eett_v5.pdf`, `exports/cubicacion_v5.csv` (51 partidas, precios vacíos) |

**Todo lo que el documento de origen no define es una PROPUESTA** (`estado: propuesta`)
hasta que el usuario o el arquitecto la confirme. Eso incluye los materiales y colores
(`source/terminaciones.json`) y el sistema estructural (`source/estructura.json`).

## Juego de láminas (`exports/planos_v5.pdf`, 6 láminas A2 a tamaño real)

| N | Lámina | Escala | Nuevo en v5 |
|---|--------|--------|-------------|
| 1–2 | Plantas p1 y p2 | 1:50 | — |
| 3 | Planta de cubierta | 1:50 | bajadas B1–B10, canales C1–C8, cuadro de aguas lluvias |
| 4 | Elevaciones | 1:100 | zócalo, burbujas y leyenda de terminaciones |
| 5 | Cortes A-A y B-B | 1:50 | canales y bajadas visibles en corte |
| 6 | Detalles constructivos | 1:10 y 1:20 | lámina nueva |

Las líneas de los detalles son recortes de los cortes del propio modelo:

- D1, D2, D3 y D5 salen del corte B-B (Y = −4,50 m, muro poniente). Ese plano corta
  la ventana `[0, 7.8, 0.2, 9.6]`.
- D4 sale del corte A-A.

Las capas de terminación (estuco, zócalo) y el esquema de fundación van en capas aparte.
El esquema de fundación **no lleva cotas**: las fija el calculista.

## Predimensionamiento estructural (resumen)

Veredicto **INCONCLUSO**:

- zona sísmica y suelo en null en `site.json`;
- 18 parámetros sin transcribir;
- no es el proyecto de cálculo, que firma un ingeniero civil.

| Elemento | Resultado (peor escenario: zona 3, suelo E) |
|----------|---------------------------------------------|
| Peso sísmico | P = 1721,4 kN; C = 0,182; Q0 = 313,3 kN |
| Muros 1er piso, dirección X | densidad 2,13 %; Q/Va = 0,696 (el más cargado) |
| Viga eje B, luz 6,00 m | wu = 38,64 kN/m; Mu = 173,9 kNm; 0,20 x 0,50 m; As ≈ 11,36 cm² |
| Voladizo del patio, 1,50 m | Mu = 13,39 kNm/m; As ≈ 1,97 cm²/m; losa 0,25 ≥ L/10 |
| Cimientos | 0,14–0,28 m de cálculo según σadm 200–100 kPa: rige el mínimo constructivo |

Verificado a mano: Mu de la viga, Va de muros p1 X y C máximo.

## Hallazgos abiertos

- **Viga del eje B.**
  - El muro que carga es un tabique de 0,12 m, liviano según la propuesta.
  - Se pesó como albañilería (envolvente).
  - Si es liviano, la carga baja. Lo decide el calculista.
- **Detalle D3.** En el modelo, la losa del 1er piso (0,35 m) pasa bajo el muro
  perimetral. Cómo apoya el muro (sobrecimiento) no está modelado.
- **Aguas lluvias.**
  - La verificación hidráulica queda INCONCLUSA: `rainfall_intensity_mm_h` en null.
  - B3 y B6 descargan sobre la cubierta más baja.
  - La disposición final en el terreno queda fuera de alcance (sin terreno).
- **Escalera:** los hallazgos de v2 siguen abiertos (holgura de 1,259 m).

## Verificación (2026-10-04)

| Paso | Resultado |
|------|-----------|
| `build_model.py` | `BUILD OK` (26 sólidos de canales y bajadas) |
| Extract y puertas | idénticos antes y después de la reconstrucción; geometría de la casa igual a v4 |
| `verificar_modelo3d.py --desfase-y 14` | OK: 0 m² sin techo, 0 rayos escapan, 0 aristas abiertas; coincidentes 0,144 m² (losa / pavimento, igual que v4) |
| `render_check.py --require dxf,pdf,png` | GATE OK |
| `norm_check.py` | INCONCLUSO: PASS 1, FAIL 0, UNVERIFIED 36, SKIP 113 |
| PDF de láminas | 6 páginas A2 (1683,78 x 1190,55 pt), numeradas 1/6 a 6/6, revisadas a ojo |
| Memoria y EETT | PDF A4 de 3 y 4 páginas, revisados a ojo |

## Lo que todavía falta

| Falta | Por qué |
|-------|---------|
| Plano de emplazamiento, terreno, disposición de aguas lluvias | terreno excluido de v5 por el usuario |
| Proyecto de cálculo firmado, estudio de mecánica de suelos | requiere ingeniero civil y laboratorio |
| Instalaciones | `installations-reviewer` no se ha corrido |
| Precios | no hay precios con fecha y fuente |
| Veredictos normativos | umbrales sin transcribir |
