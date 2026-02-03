import re
import unicodedata

# ======================================================
# 1. NORMALIZAÇÃO DE CONEXÕES (Padrão)
# ======================================================
def normalizar_conexao(texto):
    if not texto: return ""
    s = str(texto).upper()
    s = unicodedata.normalize('NFKD', s).replace('\xa0', ' ')
    s = re.sub(r'\bPIN\b', '', s)
    s = re.sub(r'\bBOX\b', '', s)
    s = re.sub(r'\bIN\b', '', s)
    s = re.sub(r'(?<=\d)-(?=\d)', ' ', s)
    s = re.sub(r'[^\w\s/]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ======================================================
# 2. TOOL FAMILIES (Famílias de Ferramentas)
# ======================================================
TOOL_FAMILIES = {
    # --- LWD / MWD Avançados ---
    "ARC": ["ARC", "ARC6", "ARC8", "ARC9", "ARCVISION", "ARRAY RESISTIVITY"],
    "TELESCOPE": ["TELESCOPE", "TELE"],
    "SONICSCOPE": ["SONICSCOPE", "SONIC SCOPE"],
    "SONIC": ["SONIC", "SONICVISION"], 
    "ECOSCOPE": ["ECOSCOPE"],
    "PROVISION": ["PROVISION"],
    "MICROSCOPE": ["MICROSCOPE"],
    "TERRASPHERE": ["TERRASPHERE", "TERRA SPHERE"],
    "STETHOSCOPE": ["STETHOSCOPE"],
    "GVR": ["GVR", "GEOVISION"],
    "GEOSPHERE": ["GEOSPHERE", "GSHD"],
    "ADN": ["ADN", "AZIMUTHAL DENSITY"],
    "GWD": ["GWD", "GYRO"],
    
    # --- RSS / Motores ---
    # PowerDrive: PD e X6 são chaves comuns, mas a lógica específica resolve a ambiguidade
    "POWERDRIVE": ["POWERDRIVE", "PD", "XCEL", "XCEED", "VORTEX", "PDX", "X6"],
    "RHOSSILI": ["RHOSSILI"],
    # Motores: Inclui DynaForce, Slider, PowerPak e o modelo A962
    "MOTOR": ["MOTOR", "MUD MOTOR", "DRILLING MOTOR", "DYNAFORCE", "SLIDER", "POWERPAK", "A962"],
    
    # --- Estabilizadores e Alargadores ---
    "STABILIZER": ["STABILIZER", "STAB", "ILS"], 
    "REAMER": ["REAMER", "ANDERREAMER", "XR", "GUNDRILL", "GUN DRILL", "RHINO", "ROLLER REAMER", "HOLE OPENER"],
    
    # --- Componentes Básicos (BHA) ---
    "BIT": ["BROCA", "BIT", "PDC", "ROCK BIT"],
    "DRILL COLLAR": ["DRILL COLLAR", "DC"],
    "HWDP": ["HWDP", "HEAVY WEIGHT", "HW"],
    "DRILL PIPE": ["DRILL PIPE", "DPV", "DP", "DPS"],
    
    # --- Acessórios ---
    "CROSSOVER": ["XO", "CROSSOVER", "SUB"],
    "JAR": ["JAR", "HYDRA"],
    "FLOAT SUB": ["FLOAT", "FLOATSUB"],
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
# 3. NORMALIZAÇÃO DE NOMES DE FERRAMENTAS
# ======================================================
def normalize_tool_name(text: str):
    
    if not text or not isinstance(text, str):
        return text, None

    original = text
    text_clean = text.upper().replace("-", " ").replace("_", " ")
    
    text_clean = re.sub(r"#A\d+", "", text_clean)
    text_clean = re.sub(r"\(.*?\)", "", text_clean)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()

    # -------------------------
    # 1. REGRAS DE PRIORIDADE
    # -------------------------
    if "ILS" in text_clean:
        return original, "STRING STABILIZER"
    if text_clean.startswith("XO ") or " XO " in f" {text_clean} ":
        return original, "CROSSOVER"
    if "FLOAT" in text_clean:
        return original, "FLOAT SUB"
    if "BROCA" in text_clean or "BIT" in text_clean:
        return original, "BIT"

    # -------------------------
    # 2. BUSCA POR FAMÍLIA
    # -------------------------
    base = None
    
    for family, keys in TOOL_FAMILIES.items():
        if any(k in text_clean for k in keys):
            
            # --- Lógica Específica para POWERDRIVE ---
            if family == "POWERDRIVE":
                # 1. Identifica Receiver separado para não confundir com a ferramenta
                if "RECEIVER" in text_clean:
                    base = "POWERDRIVE RECEIVER"
                # 2. PowerDrive X6 (PDX6)
                elif "PDX6" in text_clean or "X6" in text_clean:
                    base = "POWERDRIVE X6"
                # 3. PowerDrive Xcel
                elif "XCEL" in text_clean:
                    base = "POWERDRIVE XCEL"
                # 4. PowerDrive Xceed
                elif "XCEED" in text_clean:
                    base = "POWERDRIVE XCEED"
                # 5. Vortex
                elif "VORTEX" in text_clean:
                    base = "POWERDRIVE VORTEX"
                else:
                    base = "POWERDRIVE"
            
            # --- Lógica para Estabilizadores ---
            elif family == "STABILIZER":
                if "NEAR BIT" in text_clean or "NB" in text_clean.split():
                    base = "NB STABILIZER"
                else:
                    base = "STRING STABILIZER"
            
            else:
                base = family
            break

    # -------------------------
    # 3. CAPTURA DE TAMANHO E GERAÇÃO
    # -------------------------
    if base:
        GEN_MAP = {
            '9': '900',
            '8': '825',
            '6': '675',
            '4': '475'
        }

        # Busca tamanho explícito
        size_match = re.search(r"\b(950|900|825|800|675|650|475|312)\b", text_clean)
        
        # Busca geração (1 dígito) para famílias relevantes
        gen_match = None
        if not size_match and base in ["ARC", "SONIC", "ADK", "ADN", "POWERDRIVE", "TELESCOPE", "POWERDRIVE X6", "POWERDRIVE XCEL", "POWERDRIVE XCEED"]:
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