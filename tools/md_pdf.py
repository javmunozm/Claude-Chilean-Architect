"""Markdown -> HTML -> PDF (A4) para memorias y EETT.

Convierte el subconjunto de Markdown que escriben las herramientas de este repo
(títulos, párrafos, listas, tablas, citas, **negrita**, `código`) a HTML y lo pasa a
PDF imprimiéndolo con un navegador Chromium en modo headless (Chrome, Edge o
Chromium); si no hay ninguno, con LibreOffice Writer. Sin dependencias fuera de la
biblioteca estándar: corre con el Python del sistema.

    python tools/md_pdf.py memoria.md [-o memoria.pdf] [--browser RUTA]

Si no encuentra con qué imprimir, deja el HTML y lo dice (exit 2): el .md sigue
siendo el documento fuente.

Medido en el contenedor de desarrollo (2026-10-04): LibreOffice instalado solo con
libreoffice-core no tiene Writer y falla con "source file could not be loaded";
Chromium headless imprime bien.
"""
import os
import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9.5pt; line-height: 1.35; color: #111; }
h1 { font-size: 15pt; border-bottom: 1.5pt solid #333; padding-bottom: 3pt; }
h2 { font-size: 12pt; margin-top: 14pt; border-bottom: 0.5pt solid #999; }
h3 { font-size: 10.5pt; margin-top: 10pt; }
table { border-collapse: collapse; margin: 6pt 0; width: 100%; }
th, td { border: 0.5pt solid #888; padding: 2pt 4pt; vertical-align: top; }
th { background: #e8e8e8; }
td.r, th.r { text-align: right; }
blockquote { border-left: 3pt solid #999; margin: 6pt 0; padding: 2pt 8pt; background: #f4f4f4; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.5pt; }
"""


def _inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\*)", r"<i>\1</i>", t)
    return t


def _celdas(linea):
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def md_a_html(md, titulo="documento"):
    out, lineas, i = [], md.splitlines(), 0
    while i < len(lineas):
        ln = lineas[i]
        if not ln.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        if m:
            n = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (n, _inline(m.group(2)), n))
            i += 1
            continue
        if ln.lstrip().startswith("|") and i + 1 < len(lineas) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lineas[i + 1]):
            cab = _celdas(ln)
            alin = ["r" if c.strip().endswith(":") else "" for c in _celdas(lineas[i + 1])]
            fila = lambda cs, tag: "<tr>" + "".join(  # noqa: E731
                '<%s class="%s">%s</%s>' % (tag, alin[k] if k < len(alin) else "", _inline(c), tag)
                for k, c in enumerate(cs)) + "</tr>"
            out.append("<table>" + fila(cab, "th"))
            i += 2
            while i < len(lineas) and lineas[i].lstrip().startswith("|"):
                out.append(fila(_celdas(lineas[i]), "td"))
                i += 1
            out.append("</table>")
            continue
        if ln.startswith(">"):
            bloque = []
            while i < len(lineas) and lineas[i].startswith(">"):
                bloque.append(lineas[i].lstrip(">").strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % _inline(" ".join(bloque)))
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            tag = "ol" if re.match(r"^\s*\d+\.", ln) else "ul"
            out.append("<%s>" % tag)
            while i < len(lineas) and re.match(r"^\s*([-*]|\d+\.)\s+", lineas[i]):
                out.append("<li>%s</li>" % _inline(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lineas[i])))
                i += 1
            out.append("</%s>" % tag)
            continue
        par = []
        while i < len(lineas) and lineas[i].strip() and not re.match(r"^(#|\||>|\s*([-*]|\d+\.)\s)", lineas[i]):
            par.append(lineas[i].strip())
            i += 1
        out.append("<p>%s</p>" % _inline(" ".join(par)))
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>%s</title><style>%s</style></head><body>\n%s\n</body></html>'
            % (html.escape(titulo), CSS, "\n".join(out)))


NAVEGADORES = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
]


def _navegador(explicito=None):
    if explicito:
        return explicito
    for n in ("chromium", "chromium-browser", "google-chrome", "chrome", "msedge"):
        if shutil.which(n):
            return shutil.which(n)
    return next((n for n in NAVEGADORES if os.path.isfile(n)), None)


def convertir(md_path, pdf_path=None, browser=None):
    md_path = Path(md_path)
    pdf_path = Path(pdf_path) if pdf_path else md_path.with_suffix(".pdf")
    doc = md_a_html(md_path.read_text(encoding="utf-8"), md_path.stem)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / (pdf_path.stem + ".html")
        h.write_text(doc, encoding="utf-8")
        nav = _navegador(browser)
        if nav:
            r = subprocess.run([nav, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                                "--print-to-pdf=%s" % pdf_path.resolve(), h.resolve().as_uri()],
                               capture_output=True, text=True, timeout=180)
            if r.returncode == 0 and pdf_path.exists():
                print("escrito", pdf_path)
                return 0
            print(r.stderr[-800:], file=sys.stderr)
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice:
            r = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", td, str(h)],
                               capture_output=True, text=True, timeout=180)
            gen = Path(td) / (pdf_path.stem + ".pdf")
            if gen.exists():
                shutil.copyfile(gen, pdf_path)
                print("escrito", pdf_path)
                return 0
            print(r.stdout, r.stderr, file=sys.stderr)
    h = pdf_path.with_suffix(".html")
    h.write_text(doc, encoding="utf-8")
    print("sin navegador ni LibreOffice Writer que imprima: queda %s (abrirlo e imprimir a PDF)" % h)
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md")
    ap.add_argument("-o", "--out")
    ap.add_argument("--browser", help="ruta a Chrome/Edge/Chromium")
    a = ap.parse_args(argv)
    return convertir(a.md, a.out, a.browser)


if __name__ == "__main__":
    sys.exit(main())
