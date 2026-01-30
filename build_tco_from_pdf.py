import pdfplumber
import pandas as pd
import re

# ==============================================================================
# 6. Extração Padronizada - TCO (PDF)
# ==============================================================================

def clean_text_block(text):
    """Limpa caracteres invisíveis para facilitar a regex."""
    if not text: return ""
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)

def get_field_value(block_text, label, stop_words):
    """
    6.3 - Varredura de Conteúdo Interno:
    Busca um valor específico dentro do bloco de texto da ferramenta.
    """
    # Regex de parada (Stop Words)
    stops_regex = "|".join([re.escape(s) for s in stop_words])
    
    # Procura pela Label (ex: "DH Connection")
    # Ignora pontuação [:\-\s]*
    # Captura o conteúdo (.*?)
    # Para ao encontrar: 2 espaços, quebra de linha ou uma Stop Word
    pattern = rf"{label}[^\w]*?(.*?)(?=\s{2,}|\n|{stops_regex}|$)"
    
    match = re.search(pattern, block_text, re.IGNORECASE)
    
    if match:
        val = match.group(1).strip()
        # Filtro de segurança para não pegar lixo
        if len(val) < 50 and "ADDITIONAL" not in val.upper():
            return val
    return ""

def parse_tco_pdf(pdf_path):
    """
    Implementa a lógica 6.1: Extração por Blocos
    """
    full_text = ""
    
    # 1. Extração Brutal (Layout=True para detectar colunas visuais)
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                full_text += "\n" + text

    # 2. Divisão por Blocos usando "Quantity :"
    # O split gera uma lista. Como "Quantity" é o separador, reconstruímos o bloco.
    raw_blocks = re.split(r"(Quantity\s*:\s*)", full_text)
    
    extracted_tools = []
    
    # Stop Words (Campos que indicam o fim da leitura do campo anterior)
    stop_words = [
        "Size", "Type", "Additional Tool", "Specific Instructions", 
        "FMP Comment", "Redirected", "Ship To", "Comments", 
        "BRMEA", "Quantity", "Serial", "Part Number", 
        "DH Connection", "UH Connection", "Length", "Max OD"
    ]

    # Itera pulando de 2 em 2 (Header + Conteúdo)
    for i in range(1, len(raw_blocks), 2):
        header = raw_blocks[i]      # "Quantity :"
        content = raw_blocks[i+1]   # "1 (Tool Name)... restante do texto"
        block = header + content
        
        # --- 6.1 Cabeçalho do Bloco ---
        # Quantity : X (Tool Name)
        head_match = re.search(r"Quantity\s*:\s*(\d+)\s*\((.*?)\)", block, re.IGNORECASE)
        if not head_match: continue
            
        qty = int(head_match.group(1))
        tool_raw = head_match.group(2).strip()
        
        # Status (procura nos primeiros 300 caracteres do bloco)
        status = "Unknown"
        header_sample = content[:300].upper()
        if "ACCEPTED" in header_sample: status = "Accepted"
        elif "REDIRECTED" in header_sample: status = "Redirected"
        elif "CANCELLED" in header_sample: status = "Cancelled"

        # --- 6.2 Campos Obrigatórios (Varredura Interna) ---
        
        # DH Connection (Modelo)
        dh_conn = get_field_value(content, "DH Connection", stop_words + ["Type"])
        
        # DH Type (Pin/Box)
        # Note: A label no PDF muitas vezes aparece solta como "Type" abaixo de DH Connection
        # Aqui tentamos buscar "DH Connection Type" especificamente ou inferir pela proximidade
        # Mas seguindo a regra estrita, buscamos a label composta se existir, ou "Type" próximo.
        # Para simplificar e ser robusto, buscaremos "Type" logo após DH Connection na lógica de fusão futura,
        # mas aqui extraímos o campo se ele estiver explícito como "DH Connection Type" ou apenas "Type" na coluna certa.
        # Dado o layout de colunas, "Type" costuma ser uma label repetida. 
        # Vamos usar uma busca específica para "Type" que esteja perto de conexões.
        
        # Ajuste estratégico: O PDF separa em colunas.
        # Coluna 1: DH Connection: 7 5/8 REG
        # Coluna 2: DH Connection Type: PIN (ou as vezes só Type)
        
        # Vamos buscar explicitamente variações
        dh_type = get_field_value(content, "DH Connection Type", stop_words)
        if not dh_type:
             # Tenta pegar um "Type" genérico que apareça logo após a conexão se não achou o especifico
             pass 

        uh_conn = get_field_value(content, "UH Connection", stop_words + ["Type"])
        uh_type = get_field_value(content, "UH Connection Type", stop_words)
        
        size = get_field_value(content, "Size", stop_words)

        # Normalização simples para tool_norm (pode usar seu normalize.py aqui se quiser)
        tool_norm = tool_raw.upper().replace("-", " ").strip()

        extracted_tools.append({
            "tool_raw": tool_raw,
            "tool_norm": tool_norm,
            "quantity": qty,
            "status": status,
            "DH Connection": dh_conn,
            "DH Connection Type": dh_type,
            "UH Connection": uh_conn,
            "UH Connection Type": uh_type,
            "Size": size
        })

    return pd.DataFrame(extracted_tools)

# Função de compatibilidade para chamar no app.py
def build_tco_from_pdf(pdf_path):
    df = parse_tco_pdf(pdf_path)
    
    # 6.4 (Extra) - Pós-processamento para Validação
    # Como as regras de validação geralmente esperam "7 5/8 REG PIN" junto,
    # nós criamos colunas de "Full Connection" aqui para facilitar o rules.py
    
    df['dh_full'] = df.apply(lambda row: f"{row['DH Connection']} {row['DH Connection Type']}".strip(), axis=1)
    df['uh_full'] = df.apply(lambda row: f"{row['UH Connection']} {row['UH Connection Type']}".strip(), axis=1)
    
    # Renomeia para bater com o que o rules.py espera (opcional, depende do seu rules.py)
    # Mas seguindo a estrutura pedida, retornamos o DF com os campos separados E os juntos
    return df