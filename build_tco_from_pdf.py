import pdfplumber
import pandas as pd
import re


PDF_PATH = "report.pdf"
OUTPUT_XLSX = "tco_extracted_full.xlsx"


def extract_tool_blocks(pdf):
    """
    Retorna lista de dicionários com:
    tool_raw, quantity, status, page, raw_text
    """
    tools = []

    for page_number, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()
        if not text:
            continue

        lines = [l.strip() for l in text.splitlines() if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Exemplo:
            # Quantity : 1 (A962 XP 5/6 4.0)
            qty_match = re.search(r"Quantity\s*:\s*(\d+)\s*\((.*?)\)", line, re.IGNORECASE)
            if qty_match:
                quantity = int(qty_match.group(1))
                tool_raw = qty_match.group(2).strip()

                # Próxima linha normalmente tem status
                status = None
                if i + 1 < len(lines):
                    if "ACCEPTED" in lines[i + 1].upper():
                        status = "Accepted"
                    elif "REDIRECTED" in lines[i + 1].upper():
                        status = "Redirected"
                    elif "CANCELLED" in lines[i + 1].upper():
                        status = "Cancelled"

                # Captura bloco completo da ferramenta até a próxima Quantity
                block_lines = []
                j = i + 1
                while j < len(lines) and "Quantity" not in lines[j]:
                    block_lines.append(lines[j])
                    j += 1

                raw_block = "\n".join(block_lines)

                tools.append({
                    "tool_raw": tool_raw,
                    "quantity": quantity,
                    "status": status,
                    "page": page_number,
                    "raw_block": raw_block
                })

                i = j
                continue

            i += 1

    return tools


def extract_connections_from_block(block_text):
    """
    Extrai:
    - DH Connection
    - DH Connection Type
    - UH Connection
    - UH Connection Type
    """
    dh_conn = dh_type = uh_conn = uh_type = None

    # Normaliza texto
    text = block_text.upper()

    # DH
    m = re.search(r"DH CONNECTION\s+([^\n]+)", text)
    if m:
        dh_conn = m.group(1).strip()

    m = re.search(r"DH CONNECTION\s+TYPE\s+([^\n]+)", text)
    if m:
        dh_type = m.group(1).strip()

    # UH
    m = re.search(r"UH CONNECTION\s+([^\n]+)", text)
    if m:
        uh_conn = m.group(1).strip()

    m = re.search(r"UH CONNECTION\s+TYPE\s+([^\n]+)", text)
    if m:
        uh_type = m.group(1).strip()

    return dh_conn, dh_type, uh_conn, uh_type


def build_tco_from_pdf(pdf_path):
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        tools = extract_tool_blocks(pdf)

        for t in tools:
            if t["status"] != "Accepted":
                continue

            dh_conn, dh_type, uh_conn, uh_type = extract_connections_from_block(
                t["raw_block"]
            )

            rows.append({
                "Tool Raw": t["tool_raw"],
                "Quantity": t["quantity"],
                "Status": t["status"],
                "Page": t["page"],
                "DH Connection": dh_conn,
                "DH Connection Type": dh_type,
                "UH Connection": uh_conn,
                "UH Connection Type": uh_type
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build_tco_from_pdf(PDF_PATH)
    df.to_excel(OUTPUT_XLSX, index=False)
    print(f"Arquivo gerado: {OUTPUT_XLSX}")
