#!/usr/bin/env python3
"""Convert PDF invoices to text files."""
import subprocess
import os

fakturaer_dir = "Fakturaer"
pdf_files = [f for f in os.listdir(fakturaer_dir) if f.endswith('.pdf')]

for pdf in pdf_files:
    pdf_path = os.path.join(fakturaer_dir, pdf)
    txt_path = os.path.join(fakturaer_dir, pdf.replace('.pdf', '.txt'))
    print(f"Converting {pdf} -> {txt_path}")
    subprocess.run(['pdftotext', '-layout', pdf_path, txt_path])
    print(f"Done: {txt_path}")

print("\nAll PDFs converted!")
