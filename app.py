import streamlit as st
import pandas as pd
import re
from extract_bha import extract_bha_data, get_excel_sheet_names
from extract_tco_pdf import build_tco_from_pdf
from normalize import normalize_tool_name
from rules import apply_validation_rules, validate_contingency_bha

st.set_page_config(page_title="Validador BHA x TCO Pro", layout="wide")
st.title("🔧 Validador: Primário  vs Contingências")

with st.sidebar:
    st.header("📂 Upload")
    st.info("Passo 1: Suba o Excel com todas as abas")
    bha_master_file = st.file_uploader("Excel BHA Completo", type=['xlsx', 'xls', 'csv'])
    st.info("Passo 2: Suba o TCO em PDF")
    tco_file = st.file_uploader("TCO Assinado", type=['pdf'])

if bha_master_file and tco_file:
    sheet_names = []
    is_excel = False
    
    if bha_master_file.name.endswith(('.xlsx', '.xls')):
        sheet_names = get_excel_sheet_names(bha_master_file)
        is_excel = True
    
    if is_excel and len(sheet_names) > 0:
        st.markdown("### 🎯 Seleção de Abas")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**1️⃣ Selecione o BHA PRIMÁRIO**")
            prim_sheet = st.selectbox("Aba Principal:", sheet_names, index=0)
        with col2:
            st.markdown("**2️⃣ Selecione as CONTINGÊNCIAS**")
            avail_sheets = [s for s in sheet_names if s != prim_sheet]
            cont_sheets = st.multiselect("Abas de Backup:", avail_sheets)
    else:
        prim_sheet = None
        cont_sheets = []
        st.info("Arquivo único (CSV) detectado.")

    if st.button("🚀 Validar Seleção", type="primary"):
        with st.spinner('Analisando abas selecionadas...'):
            try:
                # --- A. BHA PRIMÁRIO ---
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
                # LÓGICA REFINADA DE ADIÇÃO DE TAMANHO
                # ==========================================
                extra_cols = [c for c in df_tco.columns if 'additional' in c or 'specific' in c]
                
                def process_tco_name(row):
                    raw_name = str(row.get('raw_name', ''))
                    # 1. Pega o nome puramente normalizado pelo raw name
                    base_norm = normalize_tool_name(raw_name)[1]
                    
                    # 2. Ignora as ferramentas que não devem ter tamanho
                    if base_norm == "UNKNOWN" or base_norm in ["JAR", "CROSSOVER", "FLOAT SUB"]:
                        return base_norm
                        
                    # 3. Se o nome base já possuir o tamanho (ex: TELESCOPE 675), não faz nada.
                    if re.search(r"\b(950|900|825|800|675|650|625|475|312)\b", base_norm):
                        return base_norm

                    # 4. Procura o texto nas colunas de instrução adicional
                    extra_text = ""
                    for col in extra_cols:
                        val = str(row.get(col, ''))
                        if val.lower() not in ['nan', 'none', 'n/a', '']:
                            extra_text += " " + val
                            
                    if not extra_text.strip():
                        return base_norm

                    # 5. Mapeia estritamente os tamanhos e cruza com a caixa adicional
                    size_map = {
                        "9 1/2": "950", "9.50": "950", "9.5": "950", "9,5": "950",
                        "8 1/4": "825", "8.25": "825", "8,25": "825",
                        "6 3/4": "675", "6.75": "675", "6,75": "675",
                        "6 1/2": "650", "6.50": "650", "6.5": "650", "6,5": "650",
                        "6 1/4": "625", "6.25": "625", "6,25": "625",
                        "4 3/4": "475", "4.75": "475", "4,75": "475",
                        "3 1/8": "312", "3.125": "312", "3,125": "312"
                    }

                    # 6. Se achar a string exata na observação (ex: "6.75"), junta no nome. Senão, não faz nada.
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

                # --- C. VALIDAÇÃO ---
                df_results_prim, df_extras = apply_validation_rules(df_bha, df_tco)

                st.divider()
                st.subheader(f"📊 Primário: {prim_sheet if prim_sheet else 'Arquivo'}")
                
                def color_status(val):
                    if val == 'OK': return 'background-color: #d4edda; color: #155724'
                    if val == 'WARNING': return 'background-color: #fff3cd; color: #856404'
                    return 'background-color: #f8d7da; color: #721c24'

                st.dataframe(df_results_prim.style.map(color_status, subset=['Status']), use_container_width=True)

                if cont_sheets:
                    st.divider()
                    st.subheader(f"🔄 Contingências ({len(cont_sheets)} abas)")
                    
                    for sheet in cont_sheets:
                        with st.expander(f"Aba: {sheet}", expanded=True):
                            df_cont = extract_bha_data(bha_master_file, sheet_name=sheet)
                            if not df_cont.empty:
                                if 'norm_name' not in df_cont.columns:
                                    df_cont['norm_name'] = df_cont['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
                                df_res_cont = validate_contingency_bha(df_cont, df_bha, df_tco)
                                st.dataframe(df_res_cont.style.map(color_status, subset=['Status']), use_container_width=True)
                            else:
                                st.warning(f"Aba {sheet} parece vazia ou sem itens SLB.")
                
                # --- E. EXTRAS E ESPIÃO ---
                st.divider()
                c1, c2 = st.columns(2)
                with c1:
                    with st.expander("📦 Sobras no TCO (Extras)"):
                        st.dataframe(df_extras)
                with c2:
                    with st.expander("🕵️ Espião TCO (Ver nomes lidos)"):
                         cols_to_show = ['raw_name', 'norm_name', 'qty']
                         if 'status' in df_tco.columns: cols_to_show.append('status')
                         if extra_cols: cols_to_show.extend(extra_cols)
                         st.dataframe(df_tco[cols_to_show])

            except Exception as e:
                st.error(f"Erro: {e}")

else:
    st.info("Aguardando arquivos...")