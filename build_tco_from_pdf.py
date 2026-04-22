import pdfplumber
import pandas as pd
import re

# ==============================================================================
# 6. Standardized Extraction - TCO (PDF)
# ==============================================================================

def clean_text_block(text):
    """Cleans invisible characters to facilitate regex."""
    if not text: return ""
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)

def get_field_value(block_text, label, stop_words):
    """
    6.3 - Internal Content Scan:
    Searches for a specific value within the tool's text block.
    """
    # Stop regex (Stop Words)
    stops_regex = "|".join([re.escape(s) for s in stop_words])
    
    # Searches for the Label (e.g., "DH Connection")
    # Ignores punctuation [:\-\s]*
    # Captures the content (.*?)
    # Stops when finding: 2 spaces, line break, or a Stop Word
    pattern = rf"{label}[^\w]*?(.*?)(?=\s{2,}|\n|{stops_regex}|$)"
    
    match = re.search(pattern, block_text, re.IGNORECASE)
    
    if match:
        val = match.group(1).strip()
        # Security filter to avoid picking up garbage
        if len(val) < 50 and "ADDITIONAL" not in val.upper():
            return val
    return ""

def parse_tco_pdf(pdf_path):
    """
    Implements logic 6.1: Block Extraction
    """
    full_text = ""
    
    # 1. Brute Extraction (Layout=True to detect visual columns)
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                full_text += "\n" + text

    # 2. Division by Blocks using "Quantity :"
    # The split generates a list. Since "Quantity" is the separator, we reconstruct the block.
    raw_blocks = re.split(r"(Quantity\s*:\s*)", full_text)
    
    extracted_tools = []
    
    # Stop Words (Fields that indicate the end of reading the previous field)
    stop_words = [
        "Size", "Type", "Additional Tool", "Specific Instructions", 
        "FMP Comment", "Redirected", "Ship To", "Comments", 
        "BRMEA", "Quantity", "Serial", "Part Number", 
        "DH Connection", "UH Connection", "Length", "Max OD"
    ]

    # Iterates skipping by 2 (Header + Content)
    for i in range(1, len(raw_blocks), 2):
        header = raw_blocks[i]      # "Quantity :"
        content = raw_blocks[i+1]   # "1 (Tool Name)... rest of the text"
        block = header + content
        
        # --- 6.1 Block Header ---
        # Quantity : X (Tool Name)
        head_match = re.search(r"Quantity\s*:\s*(\d+)\s*\((.*?)\)", block, re.IGNORECASE)
        if not head_match: continue
            
        qty = int(head_match.group(1))
        tool_raw = head_match.group(2).strip()
        
        # Status (searches in the first 300 characters of the block)
        status = "Unknown"
        header_sample = content[:300].upper()
        if "ACCEPTED" in header_sample: status = "Accepted"
        elif "REDIRECTED" in header_sample: status = "Redirected"
        elif "CANCELLED" in header_sample: status = "Cancelled"

        # --- 6.2 Mandatory Fields (Internal Scan) ---
        
        # DH Connection (Model)
        dh_conn = get_field_value(content, "DH Connection", stop_words + ["Type"])
        
        # DH Type (Pin/Box)
        # Note: The label in the PDF often appears loose as "Type" below DH Connection
        # Here we try to specifically search for "DH Connection Type" or infer by proximity
        # But following the strict rule, we search for the composite label if it exists, or "Type" nearby.
        # To simplify and be robust, we will search for "Type" right after DH Connection in the future fusion logic,
        # but here we extract the field if it is explicitly "DH Connection Type" or just "Type" in the right column.
        # Given the column layout, "Type" is usually a repeated label. 
        # We will use a specific search for "Type" that is close to connections.
        
        # Strategic adjustment: The PDF separates into columns.
        # Column 1: DH Connection: 7 5/8 REG
        # Column 2: DH Connection Type: PIN (or sometimes just Type)
        
        # Let's explicitly search for variations
        dh_type = get_field_value(content, "DH Connection Type", stop_words)
        if not dh_type:
             # Try to get a generic "Type" that appears right after the connection if the specific one wasn't found
             pass 

        uh_conn = get_field_value(content, "UH Connection", stop_words + ["Type"])
        uh_type = get_field_value(content, "UH Connection Type", stop_words)
        
        size = get_field_value(content, "Size", stop_words)

        # Simple normalization for tool_norm (you can use your normalize.py here if you want)
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

# Compatibility function to call in app.py
def build_tco_from_pdf(pdf_path):
    df = parse_tco_pdf(pdf_path)
    
    # 6.4 (Extra) - Post-processing for Validation
    # Since the validation rules usually expect "7 5/8 REG PIN" together,
    # we create "Full Connection" columns here to facilitate rules.py
    
    df['dh_full'] = df.apply(lambda row: f"{row['DH Connection']} {row['DH Connection Type']}".strip(), axis=1)
    df['uh_full'] = df.apply(lambda row: f"{row['UH Connection']} {row['UH Connection Type']}".strip(), axis=1)
    
    # Rename to match what rules.py expects (optional, depends on your rules.py)
    # But following the requested structure, we return the DF with the separated AND combined fields
    return df