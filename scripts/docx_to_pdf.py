"""
Convert a .docx to PDF with LibreOffice, updating the table of contents first.

A plain `soffice --convert-to pdf` leaves the TOC field showing its placeholder
text ("Right-click and choose 'Update Field' …"), so this drives LibreOffice
over UNO: open the document, update every index, then export to PDF.

Must run under the *system* python (/usr/bin/python3), which is the one that
has the `uno` bindings (apt: libreoffice-writer python3-uno).

    /usr/bin/python3 scripts/docx_to_pdf.py report.docx report.pdf
"""

import os
import subprocess
import sys
import tempfile
import time

import uno
from com.sun.star.beans import PropertyValue


def _prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def _insert_toc(doc, levels: int = 2) -> None:
    """LibreOffice doesn't pick up the TOC field that build_docx() writes, so add a
    native one in the same spot: the empty paragraph just above the blank line
    before "Recommended citation" (or after the title block if that isn't found)."""
    paragraphs = []
    enum = doc.Text.createEnumeration()
    while enum.hasMoreElements():
        p = enum.nextElement()
        if p.supportsService("com.sun.star.text.Paragraph"):
            paragraphs.append(p)
    anchor = None
    for i, p in enumerate(paragraphs):
        if p.String.startswith("Recommended citation") and i >= 2:
            anchor = paragraphs[i - 2]
            break
    if anchor is None:
        anchor = paragraphs[min(3, len(paragraphs) - 1)]

    toc = doc.createInstance("com.sun.star.text.ContentIndex")
    toc.Title = "Contents"
    toc.CreateFromOutline = True
    toc.Level = levels
    doc.Text.insertTextContent(anchor.getStart(), toc, False)

    # Tighten entry spacing so the cover page (title, TOC, citation) fits on one page.
    para_styles = doc.StyleFamilies.getByName("ParagraphStyles")
    for level in range(1, levels + 1):
        name = f"Contents {level}"
        if para_styles.hasByName(name):
            style = para_styles.getByName(name)
            style.ParaTopMargin = 0
            style.ParaBottomMargin = 60  # 0.6 mm


def convert(src: str, dst: str, port: int = 2002) -> None:
    profile = tempfile.mkdtemp(prefix="lo_profile_")
    proc = subprocess.Popen([
        "soffice", "--headless", "--invisible", "--nologo", "--norestore", "--nodefault",
        f"--accept=socket,host=127.0.0.1,port={port};urp;",
        f"-env:UserInstallation=file://{profile}",
    ])
    desktop = None
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        ctx = None
        for _ in range(60):
            try:
                ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(1)
        if ctx is None:
            raise RuntimeError("LibreOffice did not start within 60 s")

        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(os.path.abspath(src)), "_blank", 0, (_prop("Hidden", True),)
        )
        indexes = doc.getDocumentIndexes()
        if indexes.getCount() == 0:
            _insert_toc(doc)
            indexes = doc.getDocumentIndexes()
        for i in range(indexes.getCount()):
            indexes.getByIndex(i).update()
        # A second pass picks up page numbers that shifted after the TOC grew.
        for i in range(indexes.getCount()):
            indexes.getByIndex(i).update()
        doc.storeToURL(uno.systemPathToFileUrl(os.path.abspath(dst)),
                       (_prop("FilterName", "writer_pdf_Export"),))
        doc.close(True)
    finally:
        try:
            if desktop is not None:
                desktop.terminate()
        except Exception:
            pass  # terminate() drops the bridge, which raises on the way out
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: docx_to_pdf.py INPUT.docx OUTPUT.pdf")
    convert(sys.argv[1], sys.argv[2])
