import streamlit as st
import pandas as pd
from extract_bha import extract_bha_data
from extract_tco_pdf import build_tco_from_pdf # Atualizado para importar do script PDF correto
from normalize import normalize_tool_name
from rules import apply_validation_rules

# Configuração da Página
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
            # ==========================================
            # 1. EXTRAÇÃO DE DADOS
            # ==========================================
            
            # 1.1 Processar BHA
            df_bha = extract_bha_data(bha_file)
            
            # 1.2 Processar TCO (PDF)
            # Salvar PDF temporariamente pq o pdfplumber lê do caminho
            with open("temp_tco.pdf", "wb") as f:
                f.write(tco_file.getbuffer())
            
            # Chama o extrator robusto que criamos
            raw_tco_data = build_tco_from_pdf("temp_tco.pdf")
            df_tco = pd.DataFrame(raw_tco_data)
            # [NOVO] VERIFICAÇÃO VISUAL DOS CAMPOS 6.2
            st.divider()
            st.markdown("### 🕵️ Auditoria de Extração (Requisito 6.2)")
            st.info("Verificação detalhada dos campos obrigatórios extraídos do PDF.")
            
            # Seleciona as colunas exatas pedidas no requisito 6.2
            audit_cols = [
                "tool_raw", 
                "tool_norm",          # Novo
                "quantity",
                "status",
                "DH Connection",      # (Modelo + Tipo unidos, ou Modelo cru dependendo da lógica visual)
                "DH Connection Type", # Novo
                "UH Connection",
                "UH Connection Type", # Novo
                "Size"
            ]
            
            # Filtra colunas que existem no DF
            existing_cols = [c for c in audit_cols if c in df_tco.columns]
            
            if len(df_tco) > 0:
                with st.expander("Ver Tabela de Conferência Completa", expanded=True):
                    st.dataframe(df_tco[existing_cols])
            else:
                st.error("Nenhuma ferramenta extraída.")
            

            # ==========================================
            # 2. PADRONIZAÇÃO E LIMPEZA
            # ==========================================

            # 2.1 Padronizar nomes das colunas (snake_case)
            # Ex: "DH Connection" -> "dh_connection"
            df_tco.columns = [c.strip().lower().replace(" ", "_") for c in df_tco.columns]

            # 2.2 Renomear para alinhar com o rules.py
            rename_map = {
                'quantity': 'qty',      # rules.py exige 'qty'
                'tool_raw': 'raw_name'  # rules.py exige 'raw_name'
            }
            df_tco = df_tco.rename(columns=rename_map)


            # 2.4 Função de Limpeza Agressiva (O "Triturador")
            def clean_conn(text):
                if not isinstance(text, str): return str(text)
                
                # Joga tudo pra maiúsculo
                text = text.upper()
                
                # Remove palavras "lixo" que atrapalham a comparação (MANTENDO PIN e BOX)
                garbage_words = ["SIZE", "TYPE", "CONNECTION", "CONN"] 
                for word in garbage_words:
                    text = text.replace(word, "")
                
                # --- PROTEÇÃO DO PIN ---
                # Remove " IN " (polegadas) apenas se estiver solto, para não estragar "PIN"
                text = text.replace(" IN ", " ").replace(" INCH", " ")
                
                # Padroniza traços e underscores por espaços
                text = text.replace('-', ' ').replace('_', ' ')
                
                # Remove espaços duplos e trim
                text = " ".join(text.split())
                
                return text

            # Aplica a limpeza nas colunas de conexão (BHA e TCO)
            cols_to_clean = ['uh_connection', 'dh_connection']
            for col in cols_to_clean:
                if col in df_bha.columns:
                    df_bha[col] = df_bha[col].apply(clean_conn)
                if col in df_tco.columns:
                    df_tco[col] = df_tco[col].apply(clean_conn)
                    
            # 2.5 Normalização de Nomes das Ferramentas
            if 'norm_name' not in df_tco.columns:
                 df_tco['norm_name'] = df_tco['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
            
            # Garante que o BHA também tenha norm_name (caso o extrator não tenha criado)
            if 'norm_name' not in df_bha.columns:
                 df_bha['norm_name'] = df_bha['raw_name'].apply(lambda x: normalize_tool_name(x)[1])

            # ==========================================
            # 3. VALIDAÇÃO E DEBUG
            # ==========================================

            st.divider()
            col_debug1, col_debug2 = st.columns(2)
            col_debug1.info(f"Itens lidos do BHA: {len(df_bha)}")
            col_debug2.info(f"Itens lidos da TCO: {len(df_tco)}")
            
            if len(df_tco) > 0:
                with st.expander("🕵️ Espionar dados brutos da TCO processada (Debug)"):
                    st.dataframe(df_tco.head())
            else:
                st.error("⚠️ Atenção: Nenhuma ferramenta foi encontrada no PDF da TCO! Verifique a extração.")

            # Chama as Regras
            df_results, df_extras = apply_validation_rules(df_bha, df_tco)
            
            # ==========================================
            # 4. EXIBIÇÃO DOS RESULTADOS
            # ==========================================
            st.divider()
            st.subheader("📊 Resultado da Validação")
            
            # Estilização
            def color_status(val):
                if val == 'OK': return 'color: green; font-weight: bold'
                if val == 'WARNING': return 'color: orange; font-weight: bold'
                return 'color: red; font-weight: bold'

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

            # ==========================================
            # 5. TIRA-TEIMA (DEBUG NORMALIZAÇÃO)
            # ==========================================
            st.divider()
            st.subheader("🕵️ Tira-Teima da Normalização")
            st.write("Se houver erro de 'Item não encontrado', compare os nomes abaixo:")

            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**BHA (Nomes Normalizados):**")
                st.dataframe(df_bha[['raw_name', 'norm_name']].drop_duplicates())

            with col_b:
                st.markdown("**TCO (Nomes Normalizados):**")
                if len(df_tco) > 0:
                    st.dataframe(df_tco[['raw_name', 'norm_name']].drop_duplicates())
                else:
                    st.error("Tabela TCO vazia.")

        except Exception as e:
            st.error(f"Erro durante o processamento: {e}")
            st.exception(e)