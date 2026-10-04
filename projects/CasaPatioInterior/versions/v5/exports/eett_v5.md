# Especificaciones técnicas — Vivienda unifamiliar 2 pisos con patio interior, versión v5

> **Documento PROVISIONAL.** Las revisiones normativas están INCONCLUSAS (umbrales sin transcribir, comuna y zonas del sitio en null). Los materiales son **propuestas** de los agentes facade-designer y structural-calculator hasta que el usuario o el arquitecto los confirme. Las cantidades se midieron en el modelo; los precios no se escriben (no hay ninguno con fecha y fuente).

## A. Generalidades

- Proyecto: Vivienda unifamiliar 2 pisos con patio interior. Propietario: por definir. Arquitecto: por definir.
- Dirección: por definir. Comuna: por definir. Rol: por definir.
- Documentos que complementan estas EETT: `planos_v5.pdf` (6 láminas, incluye detalles D1–D5) y `memoria_calculo_v5.pdf` (predimensionamiento estructural).
- Cantidades: `calcs/model_extract.json` (FreeCAD), `calcs/aguas_lluvias.json`, `calcs/estructura_calc.json` y la geometría de origen; el detalle de cada una está en la columna *fuente* y en `cubicacion_v5.csv`.
- Normas citadas sin artículo: están por transcribir en `tools/norms/`. Una partida que cita una norma así no se declara conforme.

## B. Obra gruesa

### B.1 Fundaciones

Cimiento corrido de hormigón bajo todos los muros estructurales, con sobrecimiento. **No se cubica**: ancho y profundidad los fija el calculista con el estudio de mecánica de suelos (memoria §8 da anchos de cálculo de 0,14 a 0,28 m para σadm de 100 a 200 kPa, escenarios; rige el mínimo constructivo). Esquema en el detalle D3.

| Ítem | Descripción | Unidad | Cantidad | Fuente |
|---|---|---|---:|---|
| B.2 | Losa / radier del 1er piso, e = 0,35 m | m² | 155,64 | model_extract (losa p1) |
| B.2 | ídem, volumen de hormigón | m³ | 54,47 | model_extract (losa p1) |
| B.3 | Muros de albañilería confinada 0,20 m, 1er piso (19 muros, 89,88 m) | m² | 244,87 | model_extract, largo x alto |
| B.3 | Muros de albañilería confinada 0,20 m, 2º piso (10 muros, 51,74 m) | m² | 129,35 | model_extract, largo x alto |
| B.3 | Hastiales y cierres bajo cubierta (9 piezas), volumen | m³ | 4,84 | model_extract (sin largo ni espesor medidos) |
| B.3 | Muros de 0,20 m, volumen total | m³ | 54,64 | model_extract (vanos descontados) |
| B.4 | Losa de hormigón armado del 2º piso, e = 0,25 m | m² | 105,65 | model_extract (losa p2) |
| B.4 | ídem, volumen de hormigón | m³ | 26,41 | model_extract (losa p2) |
| B.5 | Viga del eje B, 0,20 x 0,50 x 6,00 m (predimensión) | m³ | 0,60 | estructura_calc (predimensionamiento) |
| B.6 | Escalera de hormigón armado, 17 contrahuellas de 0,1676 m, huella 0,280 m | gl | 1 | model_extract (escalera) |
| B.7 | Estructura de cubierta: Cubierta dos aguas, pendiente 35,7 % | m² | 139,44 | planta 131,31 m² x √(1+p²) |
| B.7 | Estructura de cubierta: Cubierta ala oriente (una agua), pendiente 19,0 % | m² | 69,30 | planta 68,08 m² x √(1+p²) |

- **B.2–B.6 Hormigones y armaduras.** Hormigón y acero según el proyecto de cálculo (NCh 430, NCh 204: sin transcribir). Grado de hormigón, recubrimientos y armaduras: **los fija el calculista**; esta EETT no los inventa.
- **B.3 Albañilería confinada.** Muros de albañilería confinada (ladrillo hecho a máquina) de 20 cm con pilares y cadenas de hormigón armado. Diseño y ejecución según NCh 2123 (sin transcribir), con pilares y cadenas de hormigón armado según el proyecto de cálculo. Densidad de muros y corte: memoria §4 (predimensionamiento).
- **B.4 Losa del 2º piso.** Vuela 1,50 m sobre el patio (memoria §6). Espesor 0,25 m (estructura.json, propuesta).
- **B.7 Cubierta.** Estructura de madera (estructura.json, propuesta); escuadrías por el calculista. Superficie inclinada = planta x √(1+p²) (139,44 + 69,30 m²). Referencia, no control: volumen del sólido modelado / espesor = 131,31 + 66,24 m² (el modelo extruye el espesor de cubierta en vertical, así que esa cifra se acerca a la planta, no a la inclinada).

## C. Tabiquería

| Ítem | Descripción | Unidad | Cantidad | Fuente |
|---|---|---|---:|---|
| C.1 | Tabique liviano 0,12 m, 1er piso (8 tabiques, 28,76 m) | m² | 74,78 | model_extract, largo x alto |
| C.1 | Tabique liviano 0,12 m, 2º piso (8 tabiques, 37,78 m) | m² | 94,45 | model_extract, largo x alto |

Tabiques interiores no estructurales (estructura.json, propuesta). Composición y aislación acústica: por definir.

## D. Terminaciones exteriores (propuesta, terminaciones.json)

| Ítem | Descripción | Unidad | Cantidad | Fuente |
|---|---|---|---:|---|
| D.1 | Estuco de mortero de cemento afinado, pintura elastomérica exterior, blanco hueso | m² | 233,31 | fachada bruta 380,48 − vanos 90,31 − zócalo 56,85 |
| D.2 | Zócalo: Estuco de mortero con hidrófugo, pintura de alto tráfico, altura terreno a +0,60 | m² | 56,85 | 75,80 m de muro exterior del 1er piso x 0,75 m |
| D.3 | Cubierta: Plancha de acero prepintado ondulada o trapezoidal sobre fieltro asfáltico y costaneras, gris grafito | m² | 208,74 | superficie inclinada (B.7) |
| D.4 | Tapacán y forro de alero: Tapacán y forro de alero en fibrocemento pintado | m | 44,40 | largo de aleros con canal (aguas_lluvias) |
| D.5 | Pavimento exterior: Baldosa microvibrada antideslizante sobre radier | m² | 151,23 | rectángulos de pavimento de la geometría de origen |

- Fachada bruta: paños de muro de 0,20 m con un lado fuera de la huella de su nivel, más hastiales (20,08 m²); el 1er piso desde el terreno (-0,15) hasta +2,85, el 2º hasta el coronamiento. Vanos descontados: ancho x (dintel − alféizar) de los vanos de esos muros.
- Espesor de estuco 20 mm; ninguna transmitancia se declara aquí: la verifica thermal-reviewer (OGUC 4.1.10 / DS 15, sin transcribir).

## E. Ventanas y puertas

| Ítem | Descripción | Unidad | Cantidad | Fuente |
|---|---|---|---:|---|
| E.1 | Ventana 2,60 x 2,20 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 2 | model_extract (ventanas) |
| E.1 | Ventana 2,00 x 2,05 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 2,20 x 1,80 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 3,10 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 1,60 x 2,20 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 2,60 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 1,40 x 2,05 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 2,20 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 2,00 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 1,80 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 2 | model_extract (ventanas) |
| E.1 | Ventana 1,00 x 2,20 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 1,60 x 1,35 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 1,60 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 1,50 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 1,70 x 1,10 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 2 | model_extract (ventanas) |
| E.1 | Ventana 1,40 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 4 | model_extract (ventanas) |
| E.1 | Ventana 1,20 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 0,70 x 2,05 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 1,10 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.1 | Ventana 0,80 x 1,25 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 2 | model_extract (ventanas) |
| E.1 | Ventana 0,90 x 0,80 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 3 | model_extract (ventanas) |
| E.1 | Ventana 0,80 x 0,80 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 3 | model_extract (ventanas) |
| E.1 | Ventana 0,45 x 1,35 m — Perfil de PVC con doble vidriado hermético (termopanel) | u | 1 | model_extract (ventanas) |
| E.2 | Puerta 2,80 x 2,35 m | u | 1 | model_extract (puertas) |
| E.2 | Puerta 2,70 x 2,36 m | u | 1 | model_extract (puertas) |
| E.2 | Puerta 1,60 x 2,35 m | u | 1 | model_extract (puertas) |
| E.2 | Puerta 0,90 x 2,10 m | u | 6 | model_extract (puertas) |
| E.2 | Puerta 0,80 x 2,10 m | u | 8 | model_extract (puertas) |
| E.2 | Puerta 0,70 x 2,10 m | u | 1 | model_extract (puertas) |

Superficie total de ventanas medida: 72,74 m². Puerta de acceso (P01): Puerta de madera sólida con barniz exterior (terminaciones.json, partida 7). Puertas interiores: material por definir. Herrajes y sentido de apertura: planos de planta (tools/puertas.py).

## F. Aguas lluvias

| Ítem | Descripción | Unidad | Cantidad | Fuente |
|---|---|---|---:|---|
| F.1 | Canal de alero 0,15 x 0,10 m, Acero prepintado, uniones remachadas y selladas | m | 44,40 | aguas_lluvias (6 canales) |
| F.2 | Canal de encuentro con muro, con forro y babeta | m | 9,20 | aguas_lluvias (2 canales) |
| F.3 | Bajada 0,08 x 0,08 m, acero prepintado | m | 39,44 | aguas_lluvias (10 bajadas, z canal − z descarga) |

8 bajadas descargan a terreno y 2 sobre una cubierta más baja (cuadro en la lámina 3). Disposición final de las aguas lluvias en el terreno: fuera del alcance de v5 (terreno no incluido). Verificación hidráulica: INCONCLUSA mientras `rainfall_intensity_mm_h` esté en null en site.json.

## G. Instalaciones

No forman parte de v5: las revisa installations-reviewer (NCh Elec. 4/2003, NCh 2485). Sin partida.

## H. Pendientes que estas EETT no resuelven

- Confirmar las propuestas de terminaciones.json y estructura.json.
- Proyecto de cálculo firmado (fundaciones, armaduras, grado de hormigón, escuadrías de cubierta).
- Estudio de mecánica de suelos; comuna, zona sísmica y zona térmica del sitio.
- Precios unitarios con fecha y fuente (columna vacía en la cubicación).
- Terreno (fuera de alcance de v5): movimiento de tierras, drenaje y disposición de aguas lluvias.
