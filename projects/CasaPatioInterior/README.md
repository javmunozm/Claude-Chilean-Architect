# Casa con patio interior

Vivienda unifamiliar de dos pisos con patio interior, envolvente 13,00 × 14,00 m,
cumbrera a +7,10 m. Entorno de Concepción (comuna por definir). Origen: archivos de
`sources/Test/` (rev. G).

Este archivo es el **índice del proyecto**. Cada versión vive en `versions/vN/` con su
propio README, sus scripts, sus cálculos y sus exportaciones (`docs/versioning.md`).
`site.json` es uno solo, en esta carpeta, y lo leen todas las versiones.

## Versiones

| Versión | Carpeta | Desciende de | Qué cambió y por qué | Estado |
|---------|---------|--------------|----------------------|--------|
| v0 | `versions/v0/` | — | rev. H: modelo JSON (corrige la escalera de rev. G a 17 contrahuellas; bandas de cubierta corregidas el 2026-10-01). Planos desde el JSON, 3D en Blender | `review` |
| v2 | `versions/v2/` | v0 | Reconstrucción con objetos Arch en FreeCAD, 29 recintos medidos, DXF/PDF desde el modelo medido, OBJ con normales; cubierta compartida (`tools/cubierta.py`) y puertas (`tools/puertas.py`). Detecta 2 problemas de escalera | `review` |
| v3 | `versions/v3/` | v2 | Rehecha el 2026-10-02 desde `sources/Test` con el sistema actualizado. Geometría y puertas idénticas a v2 (medido); cadena completa re-ejecutada y verificada en 3D | `review` |
| v4 | `versions/v4/` | v3 | Juego de planos completo: 5 láminas A2 a escala real (plantas, cubierta, 4 elevaciones, 2 cortes), viñeta con datos del proyecto, fecha y numeración. Geometría idéntica a v3 (medido) | `review` |
| v5 | `versions/v5/` | v4 | Canales y bajadas (en el modelo y la cubierta), terminaciones de fachada (propuesta), lámina 6 de detalles constructivos, memoria de predimensionamiento estructural y EETT con cubicación medida; 4 agentes nuevos en el flujo. Geometría idéntica a v4 (medido) | `review` |

Para comparar cómo cambió el método entre versiones:
`diff -r versions/v4/scripts versions/v5/scripts`.

**Documentos vigentes:** `versions/v5/exports/planos_v5.pdf` (6 láminas),
`eett_v5.pdf`, `memoria_calculo_v5.pdf` y `cubicacion_v5.csv`. Los PDF de v2 y v3 no están a
escala (defecto corregido en v4, ver su README).

## Estructura de cada versión

```
versions/vN/
├── README.md     qué cambia, por qué y de qué versión desciende
├── source/       entradas propias (solo v0: casa_rev_g.json, casa_rev_h.json, recintos.json)
├── scripts/      macros de generación de esa versión
├── calcs/        medido y derivado
└── exports/      planos_vN.pdf + model/ + drawings/ + renders/
```

## Pendientes del proyecto (afectan a todas las versiones)

- Comuna, zona térmica y zona sísmica sin definir (`site.json` en null).
- Umbrales OGUC sin transcribir: `norm_check` da INCONCLUSO.
- Orientación norte por decidir: v0 usa la convención del repo (+Y sur); v2 y v3, la del
  documento (+Y norte).
- Holgura de escalera (1,259 m) y escalera que termina 0,30 m antes de la losa: decisión
  de diseño abierta (ver `versions/v2/README.md`).
