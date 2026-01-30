import pdfplumber
import pandas as pd
import re

# ==============================================================================
# 6. Extração Padronizada - TCO (PDF) - VERSÃO FINAL (STOP WORDS REFINADAS)
# ==============================================================================

def normalize_tool_name(tool_raw):
    if not tool_raw: return ""
    s = re.sub(r'[^a-zA-Z0-9\s]', ' ', str(tool_raw).upper())
    return re.sub(r'\s+', ' ', s).strip()

def smart_distribute_values(candidates_dict):
    """
    Decide qual valor é o Modelo e qual é o Tipo, com base na origem (Source).
    candidates_dict = list of {'value': '...', 'source': 'DH_CONN'|'SIZE'|'TYPE'}
    """
    model_found = ""
    type_found = ""
    
    # 1. Varredura por TIPO (PIN/BOX) - Prioridade Absoluta
    for item in candidates_dict:
        val = item['value'].upper()
        if val in ["PIN", "BOX", "PIN/BOX", "BOX/PIN"]:
            type_found = val
        # Se achou "PIN" solto dentro de uma string maior
        elif " PIN " in f" {val} " or val.endswith(" PIN"):
            type_found = "PIN"
        elif " BOX " in f" {val} " or val.endswith(" BOX"):
            type_found = "BOX"

    # 2. Varredura por MODELO
    # Prioridade: Valor vindo de 'CONNECTION' > Valor vindo de 'SIZE'
    
    # Filtra candidatos a modelo (tem número e não é só PIN/BOX)
    potential_models = []
    for item in candidates_dict:
        val = item['value']
        # Pula se for só o tipo
        if val.upper() in ["PIN", "BOX", "PIN/BOX", "BOX/PIN"]: continue
        # Pula se for lixo conhecido ou muito curto sem numero
        if len(val) < 2 or not any(char.isdigit() for char in val): continue
        # PROTEÇÃO CONTRA O ERRO DO ILS (STABILIZER OD)
        if "STABILIZER" in val.upper() or " OD" in val.upper(): continue
        
        potential_models.append(item)
    
    # Seleção do Melhor Modelo
    best_model = ""
    
    # Tenta pegar direto da label "CONNECTION" primeiro
    conn_sources = [x['value'] for x in potential_models if 'CONN' in x['source']]
    if conn_sources:
        # Pega o mais longo (geralmente mais completo)
        best_model = max(conn_sources, key=len)
    else:
        # Se não tem, pega da label "SIZE" (Caso Well Defender)
        size_sources = [x['value'] for x in potential_models if 'SIZE' in x['source']]
        if size_sources:
            best_model = max(size_sources, key=len)
            
    return best_model, type_found

def parse_block_smart(block_text):
    """
    Explosão por Marcadores com Stop Words Agressivas (Anti-Ruído).
    """
    
    # 1. Stop Markers: Palavras que encerram a leitura.
    # ADICIONADO: STABILIZER OD, BALL CATCHER, ETC. para corrigir ILS e Well Defender
    stop_markers = [
        "QUANTITY", "STATUS", "ADDITIONAL TOOL", "ADDITIONAL", "COMMENTS", 
        "SERIAL", "PART NUMBER", "SPECIFIC INSTRUCTIONS", "FMP COMMENT", 
        "REDIRECTED", "SHIP TO", "BRMEA", "LENGTH", "MAX OD", "ID",
        # Correções Específicas:
        "STABILIZER OD", "STABILIZER", "BLADE OD", "IMP OD", 
        "BALL CATCHER", "CAPACITY", "TRAPPER", "BALL BYPASS", "REQUIRED"
    ]
    
    # 2. Interest Markers: Onde esperamos encontrar dados
    interest_markers = [
        "DH CONNECTION TYPE", "DH CONNECTION", "DH CONN",
        "UH CONNECTION TYPE", "UH CONNECTION", "UH CONN",
        "SIZE", "TYPE"
    ]
    
    all_markers = interest_markers + stop_markers
    all_markers.sort(key=len, reverse=True)
    
    pattern = r"(" + "|".join([re.escape(m) for m in all_markers]) + r")"
    
    # Explode o texto
    tokens = re.split(pattern, block_text, flags=re.IGNORECASE)
    
    dh_candidates = []
    uh_candidates = []
    
    current_context = None # DH ou UH
    
    # Itera tokens (1 = primeiro marcador)
    for i in range(1, len(tokens)-1, 2):
        marker = tokens[i].upper().strip()
        value = tokens[i+1].strip()
        
        # Limpeza
        value = re.sub(r"^[:\-\s]+", "", value).strip()
        value = re.sub(r"\s+", " ", value)
        
        # Reset de Contexto se for Stop Marker
        if marker in stop_markers:
            current_context = None
            continue
            
        # Define Contexto e Guarda Valor com a Origem (Source)
        if "DH" in marker:
            current_context = "DH"
            if value: dh_candidates.append({'value': value, 'source': marker})
            
        elif "UH" in marker:
            current_context = "UH"
            if value: uh_candidates.append({'value': value, 'source': marker})
            
        elif marker == "SIZE":
            # SIZE associa ao contexto atual
            if current_context == "DH" and value:
                dh_candidates.append({'value': value, 'source': 'SIZE'})
            elif current_context == "UH" and value:
                uh_candidates.append({'value': value, 'source': 'SIZE'})
                
        elif marker == "TYPE":
            # TYPE associa ao contexto atual
            if current_context == "DH" and value:
                dh_candidates.append({'value': value, 'source': 'TYPE'})
            elif current_context == "UH" and value:
                uh_candidates.append({'value': value, 'source': 'TYPE'})

    # Classificação
    dh_model, dh_type = smart_distribute_values(dh_candidates)
    uh_model, uh_type = smart_distribute_values(uh_candidates)
    
    # Fusão
    dh_final = f"{dh_model} {dh_type}".strip()
    uh_final = f"{uh_model} {uh_type}".strip()
    
    return dh_final, uh_final, dh_model, dh_type

def parse_tco_pdf(pdf_path):
    full_text = ""
    # Leitura layout=True para separar blocos corretamente
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
        
        status = "Unknown"
        header_sample = content[:300].upper()
        if "ACCEPTED" in header_sample: status = "Accepted"
        elif "REDIRECTED" in header_sample: status = "Redirected"
        elif "CANCELLED" in header_sample: status = "Cancelled"

        # --- PARSING ---
        dh_full, uh_full, dh_m, dh_t = parse_block_smart(content)

        extracted_tools.append({
            "tool_raw": tool_raw,
            "tool_norm": tool_norm,
            "quantity": qty,
            "status": status,
            "DH Connection": dh_full,
            "UH Connection": uh_full,
            # Debug
            "DH Model": dh_m,
            "DH Type": dh_t
        })

    return pd.DataFrame(extracted_tools)

def build_tco_from_pdf(pdf_path):
    return parse_tco_pdf(pdf_path)