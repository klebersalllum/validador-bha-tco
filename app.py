import streamlit as st
import pandas as pd
import re
from extract_bha import extract_bha_data, get_excel_sheet_names
from extract_tco_pdf import build_tco_from_pdf
from normalize import normalize_tool_name
from rules import apply_validation_rules, validate_contingency_bha

st.set_page_config(page_title="BHA vs TCO Validator Pro", layout="wide")
st.title("🔧 Validator: Primary vs Contingencies")

with st.sidebar:
    st.header("📂 Upload")
    st.info("Step 1: Upload the Excel file with all sheets")
    bha_master_file = st.file_uploader("Complete BHA Excel", type=['xlsx', 'xls', 'csv'])
    st.info("Step 2: Upload the signed TCO PDF")
    tco_file = st.file_uploader("Signed TCO", type=['pdf'])

if bha_master_file and tco_file:
    sheet_names = []
    is_excel = False
    
    if bha_master_file.name.endswith(('.xlsx', '.xls')):
        sheet_names = get_excel_sheet_names(bha_master_file)
        is_excel = True
    
    if is_excel and len(sheet_names) > 0:
        st.markdown("### 🎯 Sheet Selection")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**1️⃣ Select PRIMARY BHA**")
            prim_sheet = st.selectbox("Main Sheet:", sheet_names, index=0)
        with col2:
            st.markdown("**2️⃣ Select CONTINGENCIES**")
            avail_sheets = [s for s in sheet_names if s != prim_sheet]
            cont_sheets = st.multiselect("Backup Sheets:", avail_sheets)
    else:
        prim_sheet = None
        cont_sheets = []
        st.info("Single file (CSV) detected.")

    if st.button("🚀 Validate Selection", type="primary"):
        with st.spinner('Analyzing selected sheets...'):
            try:
                # --- A. PRIMARY BHA ---
                if is_excel:
                    df_bha = extract_bha_data(bha_master_file, sheet_name=prim_sheet)
                else:
                    bha_master_file.seek(0)
                    df_bha = extract_bha_data(bha_master_file)
                
                # --- B. TCO ---
                tco_file.seek(0)
                with open("temp_tco.pdf", "wb") as f:
                    f.write(tco_file.getbuffer())
                df_tco = build_tco_from_pdf("temp_tco.pdf")

                df_tco.columns = [c.strip().lower().replace(" ", "_") for c in df_tco.columns]
                df_tco = df_tco.rename(columns={'quantity': 'qty', 'tool_raw': 'raw_name'})
                
                if 'status' in df_tco.columns:
                    status_validos = ['ACCEPTED', 'REDIRECTED', 'RELEASED']
                    df_tco = df_tco[df_tco['status'].astype(str).str.upper().isin(status_validos)]

                # ==========================================
                # REFINED SIZE ADDITION LOGIC
                # ==========================================
                extra_cols = [c for c in df_tco.columns if 'additional' in c or 'specific' in c]
                
                def process_tco_name(row):
                    raw_name = str(row.get('raw_name', ''))
                    # 1. Gets the purely normalized name from raw name
                    base_norm = normalize_tool_name(raw_name)[1]
                    
                    # 2. Ignores tools that shouldn't have a size
                    if base_norm == "UNKNOWN" or base_norm in ["JAR", "CROSSOVER", "FLOAT SUB"]:
                        return base_norm
                        
                    # 3. If the base name already has the size (e.g., TELESCOPE 675), do nothing.
                    if re.search(r"\b(950|900|825|800|675|650|625|475|312)\b", base_norm):
                        return base_norm

                    # 4. Searches for text in the additional instruction columns
                    extra_text = ""
                    for col in extra_cols:
                        val = str(row.get(col, ''))
                        if val.lower() not in ['nan', 'none', 'n/a', '']:
                            extra_text += " " + val
                            
                    if not extra_text.strip():
                        return base_norm

                    # 5. Strictly maps sizes and cross-references with the additional box
                    size_map = {
                        "9 1/2": "950", "9.50": "950", "9.5": "950", "9,5": "950",
                        "8 1/4": "825", "8.25": "825", "8,25": "825",
                        "6 3/4": "675", "6.75": "675", "6,75": "675",
                        "6 1/2": "650", "6.50": "650", "6.5": "650", "6,5": "650",
                        "6 1/4": "625", "6.25": "625", "6,25": "625",
                        "4 3/4": "475", "4.75": "475", "4,75": "475",
                        "3 1/8": "312", "3.125": "312", "3,125": "312"
                    }

                    # 6. If it finds the exact string in the observation (e.g., "6.75"), appends to name. Otherwise, does nothing.
                    for key, code in size_map.items():
                        if key in extra_text:
                            return f"{base_norm} {code}"
                            
                    return base_norm

                df_tco['norm_name'] = df_tco.apply(process_tco_name, axis=1)
                # ==========================================
                
                def clean_conn(text):
                    if not isinstance(text, str): return str(text)
                    return " ".join(text.upper().replace("SIZE", "").replace("TYPE", "").replace("CONNECTION", "").split())

                for col in ['dh_connection', 'uh_connection']:
                    if col in df_tco.columns: df_tco[col] = df_tco[col].apply(clean_conn)
                
                if 'norm_name' not in df_bha.columns:
                    df_bha['norm_name'] = df_bha['raw_name'].apply(lambda x: normalize_tool_name(x)[1])

                # --- C. VALIDATION ---
                df_results_prim, df_extras = apply_validation_rules(df_bha, df_tco)

                st.divider()
                st.subheader(f"📊 Primary: {prim_sheet if prim_sheet else 'File'}")
                
                def color_status(val):
                    if val == 'OK': return 'background-color: #d4edda; color: #155724'
                    if val == 'WARNING': return 'background-color: #fff3cd; color: #856404'
                    return 'background-color: #f8d7da; color: #721c24'

                st.dataframe(df_results_prim.style.map(color_status, subset=['Status']), use_container_width=True)

                if cont_sheets:
                    st.divider()
                    st.subheader(f"🔄 Contingencies ({len(cont_sheets)} sheets)")
                    
                    for sheet in cont_sheets:
                        with st.expander(f"Sheet: {sheet}", expanded=True):
                            df_cont = extract_bha_data(bha_master_file, sheet_name=sheet)
                            if not df_cont.empty:
                                if 'norm_name' not in df_cont.columns:
                                    df_cont['norm_name'] = df_cont['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
                                df_res_cont = validate_contingency_bha(df_cont, df_bha, df_tco)
                                st.dataframe(df_res_cont.style.map(color_status, subset=['Status']), use_container_width=True)
                            else:
                                st.warning(f"Sheet {sheet} appears empty or without SLB items.")
                
                # --- E. EXTRAS AND SPY ---
                st.divider()
                c1, c2 = st.columns(2)
                with c1:
                    with st.expander("📦 Leftovers in TCO (Extras)"):
                        st.dataframe(df_extras)
                with c2:
                    with st.expander("🕵️ TCO Spy (View read names)"):
                         cols_to_show = ['raw_name', 'norm_name', 'qty']
                         if 'status' in df_tco.columns: cols_to_show.append('status')
                         if extra_cols: cols_to_show.extend(extra_cols)
                         st.dataframe(df_tco[cols_to_show])

            except Exception as e:
                st.error(f"Error: {e}")

else:
    st.info("Waiting for files...")