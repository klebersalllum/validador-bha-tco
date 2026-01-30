import re
import unicodedata

# ======================================================
# 1. NORMALIZAÇÃO DE CONEXÕES (Manteve-se igual)
# ======================================================
def normalizar_conexao(texto):
    """
    Padroniza conexões removendo PIN/BOX para garantir o match.
    """
    if not texto: return ""
    
    # 1. Normalização Unicode e Maiúsculas
    s = str(texto).upper()
    s = unicodedata.normalize('NFKD', s).replace('\xa0', ' ')
    
    # 2. Remover PIN e BOX
    s = re.sub(r'\bPIN\b', '', s)
    s = re.sub(r'\bBOX\b', '', s)
    
    # 3. Remover "IN" de polegadas
    s = re.sub(r'\bIN\b', '', s)
    
    # 4. Padronizar Hífens em Números (Ex: "7-5/8" -> "7 5/8")
    s = re.sub(r'(?<=\d)-(?=\d)', ' ', s)
    
    # 5. Limpeza Final
    s = re.sub(r'[^\w\s/]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    
    return s

# ======================================================
# 2. TOOL FAMILIES (BASE EXTENDIDA)
# ======================================================

TOOL_FAMILIES = {
    # --- LWD / MWD Avançados ---
    "ARC": ["ARC", "ARC6", "ARC8", "ARC9", "ARRAY RESISTIVITY"],
    "TELESCOPE": ["TELESCOPE", "TELE"],
    "SONICSCOPE": ["SONICSCOPE", "SONIC SCOPE"],
    "SONIC": ["SONIC", "SONICVISION"], # Pega Sonic 900
    "ECOSCOPE": ["ECOSCOPE"],
    "PROVISION": ["PROVISION"],
    "MICROSCOPE": ["MICROSCOPE"],
    "GVR": ["GVR", "GEOVISION"],
    "GEOSPHERE": ["GEOSPHERE", "GSHD"],
    "ADN": ["ADN", "AZIMUTHAL DENSITY"],
    
    # --- RSS / Motores ---
    "POWERDRIVE": ["POWERDRIVE", "PD", "XCEL", "XCEED", "VORTEX"],
    "RHOSSILI": ["RHOSSILI"], # Ferramenta específica
    "MOTOR": ["MOTOR", "MUD MOTOR", "DRILLING MOTOR", "DYNAFORCE", "SLIDER"], # Slider entra aqui ou separado
    
    # --- Estabilizadores e Alargadores ---
    "STABILIZER": ["STABILIZER", "STAB", "ILS"], # ILS entra aqui
    "REAMER": ["REAMER", "ANDERREAMER", "XR"],
    
    # --- Componentes Básicos (BHA) ---
    "BIT": ["BROCA", "BIT", "PDC", "ROCK BIT"],
    "DRILL COLLAR": ["DRILL COLLAR", "DC"],
    "HWDP": ["HWDP", "HEAVY WEIGHT", "HW"],
    "DRILL PIPE": ["DRILL PIPE", "DPV", "DP"],
    
    # --- Acessórios ---
    "CROSSOVER": ["XO", "CROSSOVER", "SUB"], # MWD Crossover Subs cai aqui
    "JAR": ["JAR", "HYDRA"],
    "FLOAT SUB": ["FLOAT", "FLOATSUB"],
    "LIFT SUB": ["LIFT SUB", "LIFTING"],
    "BASKET": ["BASKET", "TRANSPORTATION"],
    "PBL": ["PBL"],
    "MUDGARD": ["MUDGARD", "MUD GARD"],
    "BALL CATCHER": ["BALL CATCHER"],
    "WELL DEFENDER": ["WELL DEFENDER"],
    "WELL COMMANDER": ["WELL COMMANDER"],
    
    # --- Diversos ---
    "NON MAG": ["NON MAG", "NMDC", "NMPC"],
}

# ======================================================
# 3. NORMALIZAÇÃO DE NOMES DE FERRAMENTAS
# ======================================================

def normalize_tool_name(text: str):
    
    if not text or not isinstance(text, str):
        return text, None

    original = text
    text = text.upper()

    # -------------------------
    # LIMPEZA BÁSICA
    # -------------------------
    text = text.replace("-", " ")
    text = text.replace("_", " ")
    text = re.sub(r"#A\d+", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    # -------------------------
    # 1. REGRAS DE PRIORIDADE (Specific Overrides)
    # -------------------------
    
    # ILS (In-Line Stabilizer)
    if "ILS" in text:
        return original, "STRING STABILIZER" # Ou "ILS" se preferir separar
        
    # XO (Crossover) - Captura genérica para qualquer coisa começando com XO
    if text.startswith("XO ") or " XO " in f" {text} ":
        return original, "CROSSOVER"

    # Float Sub
    if "FLOAT" in text:
        return original, "FLOAT SUB"

    # Brocas
    if "BROCA" in text or "BIT" in text:
        return original, "BIT"

    # -------------------------
    # 2. BUSCA POR FAMÍLIA (Dicionário)
    # -------------------------
    base = None
    
    # Itera sobre as famílias
    for family, keys in TOOL_FAMILIES.items():
        # Verifica se alguma chave da família está no texto
        if any(k in text for k in keys):
            # Lógica especial para PowerDrive (manter variantes)
            if family == "POWERDRIVE":
                if "XCEL" in text: base = "POWERDRIVE XCEL"
                elif "XCEED" in text: base = "POWERDRIVE XCEED"
                elif "VORTEX" in text: base = "POWERDRIVE VORTEX"
                else: base = "POWERDRIVE"
            
            # Lógica especial para Estabilizadores
            elif family == "STABILIZER":
                if "NEAR BIT" in text or "NB" in text.split():
                    base = "NB STABILIZER"
                else:
                    base = "STRING STABILIZER"
            
            # Lógica padrão
            else:
                base = family
            break

    # -------------------------
    # 3. Captura de Tamanho (Opcional, para complementar)
    # -------------------------
    # Se encontrou família, tenta anexar tamanho relevante (900, 675, etc) se houver
    if base:
        size_match = re.search(r"\b(950|900|825|800|675|475|312)\b", text)
        if size_match:
            # Evita duplicar se o nome base já tiver o número
            if size_match.group(1) not in base:
                return original, f"{base} {size_match.group(1)}"
        return original, base

    # -------------------------
    # 4. Fallback (Se não achou nada)
    # -------------------------
    # Retorna o próprio texto limpo em vez de None, para não "sumir" na validação,
    # mas idealmente queremos categorizar tudo.
    return original, "UNKNOWN"