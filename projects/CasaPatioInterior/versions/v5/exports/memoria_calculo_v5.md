# Memoria de cálculo estructural — predimensionamiento

> **Predimensionamiento para anteproyecto.** No es el proyecto de cálculo estructural que exige el permiso de edificación: ese lo firma un ingeniero civil. Todos los números salen del modelo medido y de parámetros que están marcados según su fuente; **INCONCLUSO: zona sísmica y suelo del sitio en null (site.json); se muestran escenarios y el más desfavorable**.

## 1. Sistema estructural (propuesta, estado: propuesta)

Muros de albañilería confinada (ladrillo hecho a máquina) de 20 cm con pilares y cadenas de hormigón armado; losa del 2º piso de hormigón armado; estructura de cubierta de madera; tabiques interiores de 12 cm livianos, no estructurales.

Fundaciones: Cimiento corrido de hormigón bajo todos los muros estructurales, con sobrecimiento.

## 2. Cargas (kN)

| Peso propio | kN | | Sobrecarga | kN |
|---|---:|---|---|---:|
| muros p1 | 627,4 | | vivienda p2 | 211,3 |
| muros p2 | 356,2 | | cubierta | 199,4 |
| tabiques p1 | 37,4 | |  |  |
| tabiques p2 | 47,2 | |  |  |
| hastiales cierres | 87,1 | |  |  |
| losa p2 | 660,3 | |  |  |
| terminaciones p2 | 105,6 | |  |  |
| cubierta | 79,8 | |  |  |

Losa del 2º piso 105,65 m²; cubiertas en planta 199,39 m². Volúmenes de muros y losa: `model_extract.json` (medidos en el modelo FreeCAD).

## 3. Sismo — método estático (NCh 433)

Peso sísmico: nivel 2º piso (z = 2,85 m) 1352,8 kN; nivel techo (z = 5,35 m) 368,6 kN; total P = 1721,4 kN.

Zona sísmica del sitio: **sin dato**; suelo: **sin dato** (site.json). Sin estos datos se calcula cada escenario y se verifica el más desfavorable.

| Zona | Suelo | C | Q0 (kN) | Corte 2º piso (kN) |
|---|---|---:|---:|---:|
| 1 | A | 0,063 | 108,4 | 40,2 |
| 1 | B | 0,070 | 120,5 | 44,6 |
| 1 | C | 0,073 | 126,5 | 46,9 |
| 1 | D | 0,084 | 144,6 | 53,6 |
| 1 | E | 0,091 | 156,6 | 58,0 |
| 2 | A | 0,095 | 162,7 | 60,3 |
| 2 | B | 0,105 | 180,7 | 67,0 |
| 2 | C | 0,110 | 189,8 | 70,3 |
| 2 | D | 0,126 | 216,9 | 80,4 |
| 2 | E | 0,137 | 235,0 | 87,1 |
| 3 | A | 0,126 | 216,9 | 80,4 |
| 3 | B | 0,140 | 241,0 | 89,3 |
| 3 | C | 0,147 | 253,0 | 93,8 |
| 3 | D | 0,168 | 289,2 | 107,2 |
| 3 | E | 0,182 | 313,3 | 116,1 |

## 4. Muros: densidad y corte (caso zona 3, suelo E)

| Nivel | Dir. | Largo neto (m) | Área muros (m²) | Densidad (%) | σ0 (kPa) | Va (kN) | Q (kN) | Q/Va |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| p1 | X | 16,55 | 3,310 | 2,13 | 174,5 | 450,0 | 313,3 | 0,696 |
| p1 | Y | 32,78 | 6,556 | 4,21 | 174,5 | 891,2 | 313,3 | 0,352 |
| p2 | X | 13,40 | 2,680 | 2,54 | 63,2 | 328,5 | 116,1 | 0,353 |
| p2 | Y | 15,74 | 3,148 | 2,98 | 63,2 | 385,9 | 116,1 | 0,301 |

Muros estructurales: espesor ≥ 0,20 m, descontados los vanos. Va = (a·τm + b·σ0)·A (NCh 2123), con σ0 promedio del nivel. Q/Va < 1 indica capacidad suficiente **con parámetros sin transcribir**: no es veredicto.

## 5. Viga del eje B (luz 6,00 m)

Muro del 2º piso sobre la viga 5,67 kN/m; peso propio del descolgado 1,25 kN/m; ancho tributario de losa 2,55 m; D = 25,40 kN/m, L = 5,10 kN/m; wu = 38,64 kN/m. Mu = 173,9 kNm, Vu = 115,9 kN. Predimensión: 0,20 x 0,50 m (h = L/12, regla práctica); As ≈ 11,36 cm² de acero inferior (φ = 0,90). Muro del 2º piso sobre la viga (pesado como albañilería: envolvente, la propuesta lo declara tabique de 12 cm) + peso propio del descolgado + losa tributaria; la cubierta que pueda cargar ese muro no se incluyó.

## 6. Losa en voladizo sobre el patio (luz 1,50 m)

wu = 11,90 kN/m²; Mu = 13,39 kNm/m; As ≈ 1,97 cm²/m de acero superior. Espesor 0,25 m vs mínimo práctico L/10 = 0,150 m: suficiente.

## 7. Losa del 2º piso

Luz mayor (lado menor del recinto mayor bajo la losa: Dormitorio 1) 3,54 m; espesor 0,25 m vs L/30 = 0,118 m: suficiente.

## 8. Cimientos corridos

Largo de muros estructurales del 1er piso 89,88 m; carga de servicio media 19,2 kN/m, máxima 28,2 kN/m (muro con muro del 2º piso encima).

| σadm (kPa, escenario) | Ancho medio (m) | Ancho máximo (m) |
|---:|---:|---:|
| 100 | 0,19 | 0,28 |
| 150 | 0,13 | 0,19 |
| 200 | 0,10 | 0,14 |

Anchos calculados = carga / σadm. Donde resultan menores que el muro que reciben (0,20 m), rige el ancho mínimo constructivo del cimiento, que fija el calculista; este cálculo no lo fija. La tensión admisible real sale del estudio de mecánica de suelos (DS 61 exige además clasificar el suelo).

## 9. Parámetros sin transcribir

Cada uno está en `tools/norms/estructura.json` con la norma de donde debe transcribirse: `pesos.albanileria_kN_m3`, `pesos.hormigon_armado_kN_m3`, `pesos.tabique_liviano_kN_m2`, `pesos.cubierta_kN_m2`, `pesos.terminaciones_piso_kN_m2`, `sobrecargas.vivienda_kN_m2`, `sobrecargas.cubierta_kN_m2`, `sobrecargas.fraccion_sismica_vivienda`, `sismo.A0_g_por_zona`, `sismo.S_por_suelo`, `sismo.I_vivienda`, `sismo.R_albanileria_confinada`, `sismo.Cmax_factor_R4`, `sismo.Cmin_divisor`, `albanileria.tau_m_MPa`, `albanileria.corte_admisible`, `hormigon.fy_MPa`, `hormigon.phi_flexion`, `hormigon.combinacion_ultima`.

## 10. Lo que sigue

- Definir comuna (zona sísmica) y encargar el estudio de mecánica de suelos (suelo y σadm).
- Transcribir los parámetros desde NCh 433, NCh 1537, NCh 2123, NCh 3171 y NCh 204.
- Encargar el proyecto de cálculo a un ingeniero civil: este predimensionamiento es su punto de partida, no su reemplazo.
