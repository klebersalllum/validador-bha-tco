import re
import unicodedata

# ======================================================
# 1. NORMALIZAÇÃO DE CONEXÕES
# ======================================================
def normalizar_conexao(texto):
    if not texto: return ""
    s = str(texto).upper()
    s = unicodedata.normalize('NFKD', s).replace('\xa0', ' ')
    
    # --- MAPA DE EQUIVALÊNCIA API (ROBUSTO COM REGEX) ---
    # Captura 4 1/2 IF, 4-1/2 IF, 4.1/2 IF, 4 1/2IF independentemente dos espaços
    s = re.sub(r'4[\s.\-]*1/2[\s]*IF', 'NC50', s)
    s = re.sub(r'3[\s.\-]*1/2[\s]*IF', 'NC38', s)
    s = re.sub(r'2[\s.\-]*7/8[\s]*IF', 'NC31', s)
    
    # Limpeza padrão
    s = re.sub(r'\bPIN\b', '', s)
    s = re.sub(r'\bBOX\b', '', s)
    s = re.sub(r'\bIN\b', '', s)
    
    s = re.sub(r'(?<=\d)-(?=\d)', ' ', s)
    
    s = re.sub(r'[^\w\s/.-]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ======================================================
# 2. TOOL FAMILIES (MAPA GERAL)
# ======================================================
TOOL_FAMILIES = {
    # --- LWD / MWD Avançados ---
    "ARC": ["ARC", "ARC6", "ARC8", "ARC9", "ARCVISION", "ARRAY RESISTIVITY"],
    "TELESCOPE": ["TELESCOPE", "TELE", "TSP"],
    "SONICSCOPE": ["SONICSCOPE", "SONIC SCOPE"],
    "SONIC": ["SONIC", "SONICVISION"], 
    "ECOSCOPE": ["ECOSCOPE", "ECO"],
    "PROVISION": ["PROVISION"],
    "MICROSCOPE": ["MICROSCOPE", "MCR"],
    "TERRASPHERE": ["TERRASPHERE", "TERRA SPHERE"],
    "STETHOSCOPE": ["STETHOSCOPE", "TST"],
    "GVR": ["GVR", "GEOVISION"],
    "GEOSPHERE": ["GEOSPHERE", "GSHD"],
    "ADN": ["ADN", "AZIMUTHAL DENSITY"],
    "GWD": ["GWD", "GYRO"],
    
    # --- RSS / Motores ---
    "POWERDRIVE": ["POWERDRIVE", "PD", "XCEL", "XCEED", "VORTEX", "PDX", "X6", "RSS"],
    "RHOSSILI": ["RHOSSILI"],
    "MOTOR": ["MOTOR", "MUD MOTOR", "DRILLING MOTOR", "DYNAFORCE", "SLIDER", "POWERPAK", "A962", "PDM", "S700", "S700M"],
    
    # --- Estabilizadores e Alargadores ---
    "STABILIZER": ["STABILIZER", "STAB", "ILS", "NB", "NEAR BIT"], 
    "REAMER": ["REAMER", "ANDERREAMER", "XR", "GUNDRILL", "GUN DRILL", "RHINO", "ROLLER REAMER", "HOLE OPENER", "HO"],
    
    # --- Componentes Básicos (BHA) ---
    "BIT": ["BROCA", "BIT", "PDC", "ROCK BIT", "TRICÔNICA", "TRICONICA"],
    "DRILL COLLAR": ["DRILL COLLAR", "DC"],
    "HWDP": ["HWDP", "HEAVY WEIGHT", "HW"],
    "DRILL PIPE": ["DRILL PIPE", "DPV", "DP", "DPS"],
    
    # --- Acessórios ---
    "CROSSOVER": ["XO", "CROSSOVER", "SUB", "ADAPTER"],
    "JAR": ["JAR", "HYDRA"],
    "FLOAT SUB": ["FLOAT", "FLOATSUB", "VALVE"],
    "LIFT SUB": ["LIFT SUB", "LIFTING"],
    "BASKET": ["BASKET", "TRANSPORTATION"],
    "PBL": ["PBL"],
    "MUDGARD": ["MUDGARD", "MUD GARD"],
    "BALL CATCHER": ["BALL CATCHER"],
    "WELL DEFENDER": ["WELL DEFENDER", "WELLDEFENDER"],
    "WELL COMMANDER": ["WELL COMMANDER", "WELLCOMMANDER"],
    "FIRBP": ["FIRBP"],
    
    # --- Diversos ---
    "NON MAG": ["NON MAG", "NMDC", "NMPC"],
}

# ======================================================
# 3. NORMALIZAÇÃO DE NOMES
# ======================================================
def normalize_tool_name(text: str):
    if not text or not isinstance(text, str):
        return text, None

    original = text
    text_clean = text.upper().replace("-", " ").replace("_", " ")
    text_clean = re.sub(r"#A\d+", "", text_clean)
    text_clean = re.sub(r"\(.*?\)", "", text_clean)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()

    # 1. REGRAS DE PRIORIDADE
    if "ILS" in text_clean:
        return original, "STRING STABILIZER"
    if text_clean.startswith("XO ") or " XO " in f" {text_clean} ":
        return original, "CROSSOVER"
    if "FLOAT" in text_clean:
        return original, "FLOAT SUB"
    
    if ("BROCA" in text_clean or "BIT" in text_clean) and "NEAR" not in text_clean:
        return original, "BIT"

    # 2. BUSCA POR FAMÍLIA
    base = None
    for family, keys in TOOL_FAMILIES.items():
        if any(k in text_clean for k in keys):
            if family == "POWERDRIVE":
                if "RECEIVER" in text_clean: base = "POWERDRIVE RECEIVER"
                elif "PDX6" in text_clean or "X6" in text_clean: base = "POWERDRIVE X6"
                elif "XCEL" in text_clean: base = "POWERDRIVE XCEL"
                elif "XCEED" in text_clean: base = "POWERDRIVE XCEED"
                elif "VORTEX" in text_clean: base = "POWERDRIVE VORTEX"
                else: base = "POWERDRIVE"
            elif family == "STABILIZER":
                if "NEAR BIT" in text_clean or " NB " in f" {text_clean} " or text_clean.startswith("NB"):
                    base = "NB STABILIZER"
                else:
                    base = "STRING STABILIZER"
            else:
                base = family
            break

    # --- REGRA DE MODIFICADORES ESPECIAIS (BATTERY / FNP) ---
    
    # 1. BATERIA
    if "BATTERY" in text_clean or " BATT " in f" {text_clean} ":
        if base:
            base = f"{base} BATTERY"
        else:
            base = "BATTERY"

    # 2. FNP (Novo para EcoScope)
    if "FNP" in text_clean:
        if base:
            if "FNP" not in base:
                base = f"{base} FNP"

    # 3. CAPTURA DE TAMANHO
    if base:
        GEN_MAP = {'9': '900', '8': '825', '6': '675', '4': '475'}
        size_match = re.search(r"\b(950|900|825|800|675|650|625|475|312)\b", text_clean)
        
        gen_match = None
        if "BATTERY" not in base:
            if not size_match and base in ["ARC", "SONIC", "ADK", "ADN", "POWERDRIVE", "TELESCOPE", "STETHOSCOPE"]:
                 gen_match = re.search(r"\b(4|5|6|8|9)\b", text_clean)

        suffix = ""
        if size_match:
            suffix = size_match.group(1)
        elif gen_match:
            raw_gen = gen_match.group(1)
            suffix = GEN_MAP.get(raw_gen, raw_gen)

        if suffix and suffix not in base:
            return original, f"{base} {suffix}"
        
        return original, base

    return original, "UNKNOWN"