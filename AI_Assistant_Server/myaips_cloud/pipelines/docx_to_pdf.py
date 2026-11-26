# app/pipelines/docx_to_pdf.py

import os
import subprocess
import tempfile


def convert_docx_to_pdf(docx_path: str) -> str:
    """
    Convert a DOCX file to PDF using LibreOffice (headless).

    Returns:
        path to the generated PDF file

    Raises:
        RuntimeError if conversion fails
    """
    if not docx_path.lower().endswith((".docx", ".doc")):
        raise ValueError("Input file is not a .docx")

    out_dir = tempfile.mkdtemp(prefix="docx_pdf_")

    cmd = [
        "libreoffice",
        "--headless",
        "--convert-to",
        "pdf",
        docx_path,
        "--outdir",
        out_dir,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"DOCX → PDF conversion failed: {e.stderr.decode(errors='ignore')}"
        )

    # LibreOffice keeps the same filename, changes extension
    base = os.path.basename(docx_path)
    pdf_name = os.path.splitext(base)[0] + ".pdf"
    pdf_path = os.path.join(out_dir, pdf_name)

    if not os.path.exists(pdf_path):
        raise RuntimeError("PDF file was not created by LibreOffice")

    return pdf_path
