import pandas as pd
import numpy as np

def get_excel_sheet_names(file):
    """Returns the list of sheet names from an Excel file."""
    try:
        excel = pd.ExcelFile(file)
        return excel.sheet_names
    except:
        return []

def extract_bha_data(file_path, sheet_name=None):
    """
    Reads the BHA file. If it's an Excel file, reads the specified sheet.
    """
    df = None
    
    # 1. File Reading (Supports Specific Sheet)
    try:
        if sheet_name:
            # Reads specifically the selected sheet
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        else:
            # Tries CSV or default Excel
            try:
                df = pd.read_csv(file_path, header=None, sep=None, engine='python')
            except:
                df = pd.read_excel(file_path, header=None)
    except Exception as e:
        # Returns empty if an error occurs, to avoid breaking the entire app
        return pd.DataFrame()

    # 2. Locate the header row
    header_row = -1
    desc_col = -1
    
    possible_anchors = ['Desc.', 'Desc', 'Description', 'DESCRIPTION', 'DESC.']
    
    # Scans the first 50 rows
    for r in range(min(50, len(df))):
        row_values = [str(val).strip() for val in df.iloc[r, :].values]
        
        for col_idx, cell_val in enumerate(row_values):
            if cell_val in possible_anchors:
                header_row = r
                desc_col = col_idx
                break
            elif cell_val == 'Joint Count':
                header_row = r
                desc_col = col_idx + 1
                break
        
        if header_row != -1:
            break
            
    if header_row == -1 or desc_col == -1:
        return pd.DataFrame()

    # 3. Offsets
    OFF_MANU = 1      
    OFF_BOT_TYPE = 5  
    OFF_BOT_GEN = 6   

    def get_val(row_idx, col_idx):
        if col_idx < len(df.columns):
            return df.iloc[row_idx, col_idx]
        return np.nan

    items = []
    i = header_row + 2
    
    while i < len(df):
        raw_name = get_val(i, desc_col)
        
        if pd.isna(raw_name) or str(raw_name).strip() == '':
            if i + 2 < len(df) and not pd.isna(get_val(i + 2, desc_col)):
                i += 1
                continue
            else:
                break
            
        name = str(raw_name).strip()
        
        # SLB FILTER
        manu_val = str(get_val(i, desc_col + OFF_MANU)).strip().upper()
        if "SLB" not in manu_val:
            i += 2
            continue

        dh_type = str(get_val(i, desc_col + OFF_BOT_TYPE)).strip()
        dh_gender = str(get_val(i, desc_col + OFF_BOT_GEN)).strip()
        
        if i + 1 < len(df):
            uh_type = str(get_val(i+1, desc_col + OFF_BOT_TYPE)).strip()
            uh_gender = str(get_val(i+1, desc_col + OFF_BOT_GEN)).strip()
        else:
            uh_type = ""
            uh_gender = ""

        def clean(val):
            if val.lower() == 'nan': return ""
            return val

        # Identifies the source for the report
        source = sheet_name if sheet_name else getattr(file_path, 'name', 'BHA')

        items.append({
            'source_file': source,
            'qty': 1,
            'raw_name': name,
            'uh_connection': f"{clean(uh_type)} {clean(uh_gender)}".strip(),
            'dh_connection': f"{clean(dh_type)} {clean(dh_gender)}".strip()
        })
        
        i += 2 

    return pd.DataFrame(items)