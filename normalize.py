import re
import unicodedata

# ======================================================
# 1. NORMALIZAÇÃO DE CONEXÕES
# ======================================================
def normalizar_conexao(texto):
    if not texto or str(texto).lower() == 'nan': return ""
    
    s = str(texto).upper()
    
    # 1. FORÇA BRUTA DE SUBSTITUIÇÃO (Garante o NC50)
    s = s.replace("4 1/2 IF", "NC50").replace("4-1/2 IF", "NC50").replace("4.1/2 IF", "NC50")
    s = s.replace("3 1/2 IF", "NC38").replace("3-1/2 IF", "NC38").replace("3.1/2 IF", "NC38")
    s = s.replace("2 7/8 IF", "NC31").replace("2-7/8 IF", "NC31").replace("2.7/8 IF", "NC31")
    
    # 2. Limpeza padrão
    s = unicodedata.normalize('NFKD', s).replace('\xa0', ' ')
    s = re.sub(r'\bPIN\b', '', s)
    s = re.sub(r'\bBOX\b', '', s)
    s = re.sub(r'\bIN\b', '', s)
    
    # 3. Limpeza de lixo residual de extração de colunas do PDF
    s = re.sub(r'\bSPECIFIC\b', '', s)
    s = re.sub(r'\bINSTRUCTIONS\b', '', s)
    s = re.sub(r'\bADDITIONAL\b', '', s)
    s = re.sub(r'\bTOOL\b', '', s)
    s = re.sub(r'\bPLEASE\b', '', s)
    s = re.sub(r'\bREAD\b', '', s)
    
    s = re.sub(r'(?<=\d)-(?=\d)', ' ', s)
    s = re.sub(r'[^\w\s/.-]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ======================================================
# 2. TOOL FAMILIES (MAPA GERAL)
# ======================================================
TOOL_FAMILIES = {
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
    "POWERDRIVE": ["POWERDRIVE", "PD", "XCEL", "XCEED", "VORTEX", "PDX", "X6", "RSS"],
    "RHOSSILI": ["RHOSSILI"],
    "MOTOR": ["MOTOR", "MUD MOTOR", "DRILLING MOTOR", "DYNAFORCE", "SLIDER", "POWERPAK", "A962", "PDM", "S700", "S700M"],
    "STABILIZER": ["STABILIZER", "STAB", "ILS", "NB", "NEAR BIT"], 
    "REAMER": ["REAMER", "ANDERREAMER", "XR", "GUNDRILL", "GUN DRILL", "RHINO", "ROLLER REAMER", "HOLE OPENER", "HO"],
    "BIT": ["BROCA", "BIT", "PDC", "ROCK BIT", "TRICÔNICA", "TRICONICA"],
    "DRILL COLLAR": ["DRILL COLLAR", "DC"],
    "HWDP": ["HWDP", "HEAVY WEIGHT", "HW"],
    "DRILL PIPE": ["DRILL PIPE", "DPV", "DP", "DPS"],
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
    "NON MAG": ["NON MAG", "NMDC", "NMPC"],
}

# ======================================================
# 3. NORMALIZAÇÃO DE NOMES
# ======================================================
def normalize_tool_name(text: str):
    if not text or not isinstance(text, str): return text, None

    original = text
    text_clean = text.upper().replace("-", " ").replace("_", " ")
    
    text_clean = text_clean.replace("9 1/2", "950").replace("9.50", "950").replace("9.5", "950").replace("9,5", "950")
    text_clean = text_clean.replace("8 1/4", "825").replace("8.25", "825").replace("8,25", "825")
    text_clean = text_clean.replace("6 3/4", "675").replace("6.75", "675").replace("6,75", "675")
    text_clean = text_clean.replace("6 1/2", "650").replace("6.50", "650").replace("6.5", "650").replace("6,5", "650")
    text_clean = text_clean.replace("6 1/4", "625").replace("6.25", "625").replace("6,25", "625")
    text_clean = text_clean.replace("4 3/4", "475").replace("4.75", "475").replace("4,75", "475")
    text_clean = text_clean.replace("3 1/8", "312").replace("3.125", "312").replace("3,125", "312")

    text_clean = re.sub(r"#A\d+", "", text_clean)
    text_clean = re.sub(r"\(.*?\)", "", text_clean)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()
    
    palavras = text_clean.split()

    if "ILS" in palavras: return original, "STRING STABILIZER"
    if text_clean.startswith("XO ") or " XO " in f" {text_clean} ": return original, "CROSSOVER"
    if "FLOAT" in text_clean: return original, "FLOAT SUB"
    
    if ("BROCA" in palavras or "BIT" in palavras or "BITS" in palavras) and "NEAR" not in text_clean: 
        return original, "BIT"

    base = None
    for family, keys in TOOL_FAMILIES.items():
        if any(re.search(rf"\b{k}[0-9]*S?\b", text_clean) for k in keys):
            if family == "POWERDRIVE":
                if "RECEIVER" in text_clean or " RX " in f" {text_clean} ": base = "POWERDRIVE RECEIVER"
                elif "PDX" in text_clean or "X6" in text_clean: base = "POWERDRIVE X6"
                elif "XCEL" in text_clean: base = "POWERDRIVE XCEL"
                elif "XCEED" in text_clean: base = "POWERDRIVE XCEED"
                elif "VORTEX" in text_clean: base = "POWERDRIVE VORTEX"
                else: base = "POWERDRIVE"
            elif family == "STABILIZER":
                if "NEAR BIT" in text_clean or "NB" in palavras: base = "NB STABILIZER"
                else: base = "STRING STABILIZER"
            else:
                base = family
            break

    if "BATTERY" in text_clean or "BATT" in palavras:
        base = f"{base} BATTERY" if base else "BATTERY"
    if "FNP" in palavras:
        if base and "FNP" not in base: base = f"{base} FNP"

    if base:
        if base in ["JAR", "CROSSOVER", "FLOAT SUB"]:
            return original, base

        GEN_MAP = {'9': '900', '8': '825', '6': '675', '4': '475'}
        size_match = re.search(r"\b(950|900|825|800|675|650|625|475|312)\b", text_clean)
        gen_match = None
        
        if "BATTERY" not in base:
            if not size_match and base in ["ARC", "SONIC", "ADK", "ADN", "POWERDRIVE", "TELESCOPE", "STETHOSCOPE"]:
                 gen_match = re.search(r"\b(4|5|6|8|9)\b", text_clean)

        suffix = size_match.group(1) if size_match else (GEN_MAP.get(gen_match.group(1), gen_match.group(1)) if gen_match else "")
        if suffix and suffix not in base: return original, f"{base} {suffix}"
        return original, base

    return original, "UNKNOWN"