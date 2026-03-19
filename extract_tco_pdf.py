import pdfplumber
import pandas as pd
import re

# ==============================================================================
# 6. Extração Padronizada - TCO (PDF) - STATUS UPDATE & FILTRO
# ==============================================================================

def normalize_tool_name(tool_raw):
    if not tool_raw: return ""
    s = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(tool_raw).upper())
    return re.sub(r'\s+', ' ', s).strip()

def smart_distribute_values(candidates_dict):
    """
    Decide qual valor é o Modelo e qual é o Tipo, com base na origem.
    """
    model_found = ""
    type_found = ""
    
    # 1. Varredura por TIPO (PIN/BOX)
    for item in candidates_dict:
        val = item['value'].upper()
        if val in ["PIN", "BOX", "PIN/BOX", "BOX/PIN"]:
            type_found = val
        elif " PIN " in f" {val} " or val.endswith(" PIN"):
            type_found = "PIN"
        elif " BOX " in f" {val} " or val.endswith(" BOX"):
            type_found = "BOX"

    # 2. Varredura por MODELO
    potential_models = []
    for item in candidates_dict:
        val = item['value']
        # Pula se for só o tipo, lixo ou estabilizador invadindo
        if val.upper() in ["PIN", "BOX", "PIN/BOX", "BOX/PIN"]: continue
        if len(val) < 2 or not any(char.isdigit() for char in val): continue
        if "STABILIZER" in val.upper() or " OD" in val.upper(): continue
        
        potential_models.append(item)
    
    # Seleção do Melhor Modelo
    best_model = ""
    conn_sources = [x['value'] for x in potential_models if 'CONN' in x['source']]
    
    if conn_sources:
        best_model = max(conn_sources, key=len)
    else:
        size_sources = [x['value'] for x in potential_models if 'SIZE' in x['source']]
        if size_sources:
            best_model = max(size_sources, key=len)
            
    return best_model, type_found

def parse_block_smart(block_text):
    """
    Explosão por Marcadores com Stop Words Agressivas.
    """
    stop_markers = [
        "QUANTITY", "STATUS", "COMMENTS", 
        "SERIAL", "PART NUMBER", "FMP COMMENT", 
        "REDIRECTED", "SHIP TO", "BRMEA", "LENGTH", "MAX OD", "ID",
        "STABILIZER OD", "STABILIZER", "BLADE OD", "IMP OD", 
        "BALL CATCHER", "CAPACITY", "TRAPPER", "BALL BYPASS", "REQUIRED"
    ]
    
    interest_markers = [
        "DH CONNECTION TYPE", "DH CONNECTION", "DH CONN",
        "UH CONNECTION TYPE", "UH CONNECTION", "UH CONN",
        "SIZE", "TYPE", "ADDITIONAL TOOL"
    ]
    
    all_markers = interest_markers + stop_markers
    all_markers.sort(key=len, reverse=True)
    
    pattern = r"(" + "|".join([re.escape(m) for m in all_markers]) + r")"
    tokens = re.split(pattern, block_text, flags=re.IGNORECASE)
    
    dh_candidates = []
    uh_candidates = []
    current_context = None 
    add_text = ""
    
    for i in range(1, len(tokens)-1, 2):
        marker = tokens[i].upper().strip()
        value = tokens[i+1].strip()
        
        value = re.sub(r"^[:\-\s]+", "", value).strip()
        value = re.sub(r"\s+", " ", value)
        
        if marker in stop_markers:
            current_context = None
            continue
            
        if "DH" in marker:
            current_context = "DH"
            if value: dh_candidates.append({'value': value, 'source': marker})
        elif "UH" in marker:
            current_context = "UH"
            if value: uh_candidates.append({'value': value, 'source': marker})
        elif "ADDITIONAL TOOL" in marker:
            current_context = "ADDITIONAL"
            if value: add_text = value
        elif marker == "SIZE":
            if current_context == "DH" and value: dh_candidates.append({'value': value, 'source': 'SIZE'})
            elif current_context == "UH" and value: uh_candidates.append({'value': value, 'source': 'SIZE'})
        elif marker == "TYPE":
            if current_context == "DH" and value: dh_candidates.append({'value': value, 'source': 'TYPE'})
            elif current_context == "UH" and value: uh_candidates.append({'value': value, 'source': 'TYPE'})
        elif current_context == "ADDITIONAL":
            if value: add_text += " " + value

    dh_model, dh_type = smart_distribute_values(dh_candidates)
    uh_model, uh_type = smart_distribute_values(uh_candidates)
    
    dh_final = f"{dh_model} {dh_type}".strip()
    uh_final = f"{uh_model} {uh_type}".strip()
    
    # Limpeza dos textos espúrios da estrutura do PDF
    add_text = re.sub(r'(?i)specific\s+instructions.*?(?:please read|\))', '', add_text, flags=re.DOTALL)
    add_text = re.sub(r'(?i)specific\s+instructions', '', add_text)
    add_text = re.sub(r'\(\s*PLEASE\s+READ\s*\)', '', add_text, flags=re.IGNORECASE)
    add_text = re.sub(r'\s+', ' ', add_text).strip()
    
    return dh_final, uh_final, dh_model, dh_type, add_text

def parse_tco_pdf(pdf_path):
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text: full_text += "\n" + text

    raw_blocks = re.split(r"(Quantity\s*:\s*)", full_text)
    extracted_tools = []

    for i in range(1, len(raw_blocks), 2):
        header = raw_blocks[i]
        content = raw_blocks[i+1]
        
        head_match = re.search(r"Quantity\s*:\s*(\d+)\s*\((.*?)\)", header + content, re.IGNORECASE)
        if not head_match: continue
        
        qty = int(head_match.group(1))
        tool_raw = head_match.group(2).strip()
        tool_norm = normalize_tool_name(tool_raw)
        
        # --- LÓGICA DE STATUS ---
        status = "Unknown"
        header_sample = content[:400].upper()
        
        if "ACCEPTED" in header_sample: status = "Accepted"
        elif "RELEASED" in header_sample: status = "Released"
        elif "REDIRECTED" in header_sample: status = "Redirected"
        elif "CANCELLED" in header_sample: status = "Cancelled"
        elif "SUBMITTED" in header_sample: status = "Submitted"

        # --- FILTRO DE STATUS ---
        valid_statuses = ["Accepted", "Redirected", "Released", "Submitted"]
        if status not in valid_statuses:
            continue
            
        # --- PARSING ---
        dh_full, uh_full, dh_m, dh_t, add_spec = parse_block_smart(content)

        extracted_tools.append({
            "tool_raw": tool_raw,
            "tool_norm": tool_norm,
            "quantity": qty,
            "status": status,
            "DH Connection": dh_full,
            "UH Connection": uh_full,
            "DH Model": dh_m,
            "DH Type": dh_t,
            "Additional Tool Specific": add_spec
        })

    return pd.DataFrame(extracted_tools)

def build_tco_from_pdf(pdf_path):
    return parse_tco_pdf(pdf_path)