import re

# ======================================================
# TOOL FAMILIES (BASE OFICIAL)
# ======================================================

TOOL_FAMILIES = {
    "ARC": ["ARC"],
    "GEOSPHERE": ["GEOSPHERE", "GSHD"],
    "LIFTING SUB": ["LIFTING SUB", "LIFT SUB"],
    "TELESCOPE": ["TELESCOPE"],
    "SONICVISION": ["SONICVISION"],
    "SONICSCOPE": ["SONICSCOPE"],
    "SADN": ["SADN"],
    "ECOSCOPE": ["ECOSCOPE"],
    "PROVISION": ["PROVISION"],
    "TERRASPHERE": ["TERRASPHERE"],
    "MICROSCOPE": ["MICROSCOPE"],
    "GVR": ["GVR", "GEOVISION"],
    "WELL COMMANDER": ["WELL COMMANDER"],
    "WELL DEFENDER": ["WELL DEFENDER"],
    "PBL": ["PBL"],
    "JAR": ["DJR DRLG HYDRA", "DJR-DRLG-HYDRA", "HYDRA"],
    "PDX6": ["PDX6"],
    "POWERDRIVE XCEL": ["POWERDRIVE XCEL", "XCEL"],
    "POWERDRIVE XCEED": ["POWERDRIVE XCEED", "XCEED"],
    "FLOAT SUB": ["FLOAT SUB", "FLOATSUB"],
    "GWD": ["GWD"],
    "MUDGARD": ["MUDGARD", "MUD GARD", "MUD-GARD"],
    "BALL CATCHER": ["BALL CATCHER", "BALLCATCHER"],

    # Non-Mag
    "NMDC": ["NON MAG DRILL", "NONMAG DRILL", "NMDC"],
    "NMPC": ["NON MAG PONY", "NONMAG PONY", "NMPC"],

    # Motors
    "MOTOR": ["A962", "MOTOR", "MUD MOTOR", "DRILLING MOTOR", "DYNAFORCE"],
}

# ======================================================
# NORMALIZATION
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
    text = re.sub(r"#A\d+", "", text)
    text = re.sub(r"\(.*?\)", "", text)  # remove (NP), (XXX)
    text = re.sub(r"\bNP\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    # -------------------------
    # FLOAT SUB (PRIORIDADE ABSOLUTA)
    # -------------------------
    if "FLOAT" in text and "SUB" in text:
        return original, "FLOAT SUB"

    # -------------------------
    # RECEIVER
    # -------------------------
    if "RECEIVER" in text:
        return original, "RECEIVER"

    # -------------------------
    # POWERDRIVE
    # -------------------------
    size = re.search(r"(900|825|675)", text)

    if "XCEL" in text:
        return original, f"POWERDRIVE XCEL {size.group(1)}" if size else "POWERDRIVE XCEL"

    if "XCEED" in text:
        return original, f"POWERDRIVE XCEED {size.group(1)}" if size else "POWERDRIVE XCEED"

    if "PDX6" in text or re.search(r"\bX6\b", text):
        return original, f"PDX6 {size.group(1)}" if size else "PDX6"

    # -------------------------
    # BATTERY (se ainda usar)
    # -------------------------
    if "BATTERY" in text:
        if "ARC" in text:
            return original, "ARC BATTERY"
        if "STETHO" in text or "TST" in text:
            return original, "STETHOSCOPE BATTERY"

    # -------------------------
    # STABILIZER
    # -------------------------
    if "STABILIZER" in text:
        if "NEAR BIT" in text or re.search(r"\bNB\b", text):
            return original, "NB STABILIZER"
        return original, "STRING STABILIZER"

    # -------------------------
    # MUDGARD
    # -------------------------
    if "MUD" in text and "GARD" in text:
        return original, "MUDGARD"

    # -------------------------
    # MOTOR
    # -------------------------
    if "A962" in text:
        return original, "MOTOR"

    # -------------------------
    # FAMÍLIAS PADRÃO
    # -------------------------
    base = None
    for family, keys in TOOL_FAMILIES.items():
        if any(k in text for k in keys):
            base = family
            break

    if not base:
        return original, None

    # -------------------------
    # TAMANHO
    # -------------------------
    if size:
        return original, f"{base} {size.group(1)}"

    return original, base