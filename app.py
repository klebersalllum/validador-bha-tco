import streamlit as st
import pandas as pd
from extract_bha import extract_bha_data, get_excel_sheet_names
from extract_tco_pdf import build_tco_from_pdf
from normalize import normalize_tool_name
from rules import apply_validation_rules, validate_contingency_bha

st.set_page_config(page_title="Validador BHA x TCO Pro", layout="wide")
st.title("🔧 Validador: Primário  vs Contingências")

# --- SIDEBAR DE UPLOAD ---
with st.sidebar:
    st.header("📂 Upload")
    
    st.info("Passo 1: Suba o Excel com todas as abas")
    bha_master_file = st.file_uploader("Excel BHA Completo", type=['xlsx', 'xls', 'csv'])
    
    st.info("Passo 2: Suba o TCO em PDF")
    tco_file = st.file_uploader("TCO Assinado", type=['pdf'])

# --- ÁREA PRINCIPAL ---
if bha_master_file and tco_file:
    
    # 1. DETECÇÃO DE ABAS
    sheet_names = []
    is_excel = False
    
    if bha_master_file.name.endswith(('.xlsx', '.xls')):
        sheet_names = get_excel_sheet_names(bha_master_file)
        is_excel = True
    
    # 2. SELETORES INTELIGENTES
    if is_excel and len(sheet_names) > 0:
        st.markdown("### 🎯 Seleção de Abas")
        col1, col2 = st.columns(2)
        
        with col1:
            # Aqui você seleciona a "Amarelinha" (Ex: BHA#05_8.5in)
            st.markdown("**1️⃣ Selecione o BHA PRIMÁRIO **")
            prim_sheet = st.selectbox("Aba Principal:", sheet_names, index=0)
            
        with col2:
            # Aqui você seleciona as letras (Ex: BHA#05a, BHA#05b...)
            # O BHA 4 você simplesmente NÃO seleciona aqui, e ele será ignorado.
            st.markdown("**2️⃣ Selecione as CONTINGÊNCIAS**")
            avail_sheets = [s for s in sheet_names if s != prim_sheet]
            cont_sheets = st.multiselect("Abas de Backup:", avail_sheets)
            
    else:
        # Fallback para CSV
        prim_sheet = None
        cont_sheets = []
        st.info("Arquivo único (CSV) detectado.")

    # 3. BOTÃO DE AÇÃO
    if st.button("🚀 Validar Seleção", type="primary"):
        with st.spinner('Analisando abas selecionadas...'):
            try:
                # --- A. PROCESSAMENTO DO BHA PRIMÁRIO ---
                if is_excel:
                    df_bha = extract_bha_data(bha_master_file, sheet_name=prim_sheet)
                else:
                    bha_master_file.seek(0)
                    df_bha = extract_bha_data(bha_master_file)
                
                # --- B. PROCESSAMENTO DO TCO (COM FILTRO DE STATUS) ---
                tco_file.seek(0)
                with open("temp_tco.pdf", "wb") as f:
                    f.write(tco_file.getbuffer())
                df_tco = build_tco_from_pdf("temp_tco.pdf")

                # Limpeza e Normalização TCO
                df_tco.columns = [c.strip().lower().replace(" ", "_") for c in df_tco.columns]
                df_tco = df_tco.rename(columns={'quantity': 'qty', 'tool_raw': 'raw_name'})
                
                # Limpa conexões
                def clean_conn(text):
                    if not isinstance(text, str): return str(text)
                    return " ".join(text.upper().replace("SIZE", "").replace("TYPE", "").replace("CONNECTION", "").split())

                for col in ['dh_connection', 'uh_connection']:
                    if col in df_tco.columns: df_tco[col] = df_tco[col].apply(clean_conn)
                
                # Normaliza Nomes
                if 'norm_name' not in df_tco.columns:
                    df_tco['norm_name'] = df_tco['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
                if 'norm_name' not in df_bha.columns:
                    df_bha['norm_name'] = df_bha['raw_name'].apply(lambda x: normalize_tool_name(x)[1])

                # --- C. VALIDAÇÃO PRIMÁRIA (REGRA MÍNIMO 2) ---
                df_results_prim, df_extras = apply_validation_rules(df_bha, df_tco)

                st.divider()
                st.subheader(f"📊 Primário: {prim_sheet if prim_sheet else 'Arquivo'}")
                
                def color_status(val):
                    if val == 'OK': return 'background-color: #d4edda; color: #155724'
                    if val == 'WARNING': return 'background-color: #fff3cd; color: #856404'
                    return 'background-color: #f8d7da; color: #721c24'

                st.dataframe(df_results_prim.style.applymap(color_status, subset=['Status']), use_container_width=True)

                # --- D. VALIDAÇÃO CONTINGÊNCIAS (LOOP NAS LETRAS) ---
                if cont_sheets:
                    st.divider()
                    st.subheader(f"🔄 Contingências ({len(cont_sheets)} abas)")
                    
                    for sheet in cont_sheets:
                        with st.expander(f"Aba: {sheet}", expanded=True):
                            # Lê a aba de contingência
                            df_cont = extract_bha_data(bha_master_file, sheet_name=sheet)
                            
                            if not df_cont.empty:
                                if 'norm_name' not in df_cont.columns:
                                    df_cont['norm_name'] = df_cont['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
                                
                                # Valida contra o Primário selecionado
                                df_res_cont = validate_contingency_bha(df_cont, df_bha, df_tco)
                                st.dataframe(df_res_cont.style.applymap(color_status, subset=['Status']), use_container_width=True)
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
                         st.dataframe(df_tco[['raw_name', 'norm_name', 'qty', 'status']])

            except Exception as e:
                st.error(f"Erro: {e}")

else:
    st.info("Aguardando arquivos...")