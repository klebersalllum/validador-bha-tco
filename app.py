import streamlit as st
import pandas as pd
from extract_bha import extract_bha_data
from build_tco_from_pdf import build_tco_from_pdf # Seu script de PDF
from normalize import normalize_tool_name
from rules import apply_validation_rules

st.set_page_config(page_title="Validador BHA x TCO", layout="wide")

st.title("🔧 Validação Automática BHA vs TCO")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Upload BHA (Excel/CSV)")
    bha_file = st.file_uploader("Carregar arquivo BHA", type=['xlsx', 'csv'])

with col2:
    st.subheader("2. Upload TCO (PDF)")
    tco_file = st.file_uploader("Carregar arquivo TCO", type=['pdf'])

if bha_file and tco_file:
    with st.spinner('Processando arquivos...'):
        try:
            # 1. Extração
            df_bha = extract_bha_data(bha_file)
            
            # Salvar PDF temporariamente pq o pdfplumber lê do caminho
            with open("temp_tco.pdf", "wb") as f:
                f.write(tco_file.getbuffer())
            
            # Usando sua função de extração (ela deve retornar um DF ou lista)
            # Adaptar conforme o retorno exato do seu script build_tco_from_pdf
            # Assumindo que retorna lista de dicts
            raw_tco_data = build_tco_from_pdf("temp_tco.pdf")
            df_tco = pd.DataFrame(raw_tco_data)
            
            # 2. Normalização (Essencial para o match)
            # Normaliza TCO
            # Atenção: O build_tco_from_pdf já deve extrair tool_raw, quantity, etc.
            if 'norm_name' not in df_tco.columns:
                 df_tco['norm_name'] = df_tco['tool_raw'].apply(lambda x: normalize_tool_name(x)[1])

            # 3. Validação
            df_results, df_extras = apply_validation_rules(df_bha, df_tco)
            
            # 4. Exibição
            st.divider()
            st.subheader("📊 Resultado da Validação")
            
            # Função de estilo para colorir linhas
            def color_status(val):
                color = 'green' if val == 'OK' else 'orange' if val == 'WARNING' else 'red'
                return f'color: {color}; font-weight: bold'

            st.dataframe(df_results.style.map(color_status, subset=['Status']), use_container_width=True)
            
            # Métricas
            erro_count = len(df_results[df_results['Status'] == 'ERROR'])
            warn_count = len(df_results[df_results['Status'] == 'WARNING'])
            
            if erro_count > 0:
                st.error(f"Foram encontrados {erro_count} ERROS Críticos!")
            elif warn_count > 0:
                st.warning(f"Validação OK, mas com {warn_count} alertas.")
            else:
                st.success("Tudo certo! BHA e TCO compatíveis.")

            with st.expander("Ver Itens Extras na TCO"):
                st.dataframe(df_extras)

        except Exception as e:
            st.error(f"Erro durante o processamento: {e}")
            st.exception(e)