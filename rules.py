import pandas as pd
import streamlit as st # <--- IMPORTANTE: Adicione isso
from normalize import normalize_tool_name, normalizar_conexao 

def apply_validation_rules(df_bha, df_tco):
    results = []
    
    # ---------------------------------------------------------
    # 1. PREPARAÇÃO
    # ---------------------------------------------------------
    df_bha['norm_name'] = df_bha['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
    
    # Normalizar TCO
    df_tco['uh_norm'] = df_tco['uh_connection'].apply(normalizar_conexao)
    df_tco['dh_norm'] = df_tco['dh_connection'].apply(normalizar_conexao)

    tco_summary = df_tco.groupby('norm_name').agg({
        'qty': 'sum',
        'uh_norm': 'first',
        'dh_norm': 'first'
    }).to_dict('index')

    matched_tco_names = set()

    # ---------------------------------------------------------
    # 2. VALIDAÇÃO COM "ESPIÃO VISUAL"
    # ---------------------------------------------------------
    for idx, row in df_bha.iterrows():
        bha_name = row['norm_name']
        
        # Normaliza conexões do BHA
        bha_uh_clean = normalizar_conexao(row['uh_connection'])
        bha_dh_clean = normalizar_conexao(row['dh_connection'])

        status = "OK"
        obs = []
        
        tco_match = tco_summary.get(bha_name)
        
        if not tco_match:
            status = "ERROR"
            obs.append("Item não encontrado na TCO")
            tco_qty = 0
            tco_uh_clean = "-"
            tco_dh_clean = "-"
        else:
            matched_tco_names.add(bha_name)
            tco_qty = tco_match['qty']
            tco_uh_clean = tco_match['uh_norm']
            tco_dh_clean = tco_match['dh_norm']
            
            # Validação Qtd
            if tco_qty == 1:
                status = "WARNING" if status != "ERROR" else "ERROR"
                obs.append("Sem backup (Qtd=1)")
            elif tco_qty == 0:
                status = "ERROR"
                obs.append("Qtd=0 na TCO")
            
            # --- ÁREA DO ESPIÃO (Debug na Tela) ---
            
            # Checa UH
            if bha_uh_clean != tco_uh_clean:
                status = "ERROR"
                obs.append(f"UH Divergente (TCO: {tco_uh_clean})")
                
                # MOSTRA O ERRO NA TELA DO STREAMLIT
                with st.expander(f"🚨 ERRO REAL DETECTADO (Linha {idx+2}): {row['raw_name']}", expanded=True):
                    st.error(f"Divergência de Conexão Superior (UH)")
                    col1, col2 = st.columns(2)
                    col1.metric("BHA (Limpo)", repr(bha_uh_clean))
                    col2.metric("TCO (Limpo)", repr(tco_uh_clean))
                    st.code(f"Original BHA: '{row['uh_connection']}'\nOriginal TCO: '{tco_match.get('uh_norm')}'")

            # Checa DH
            if bha_dh_clean != tco_dh_clean:
                status = "ERROR"
                obs.append(f"DH Divergente (TCO: {tco_dh_clean})")
                
                # MOSTRA O ERRO NA TELA DO STREAMLIT
                with st.expander(f"🚨 ERRO REAL DETECTADO (Linha {idx+2}): {row['raw_name']}", expanded=True):
                    st.error(f"Divergência de Conexão Inferior (DH)")
                    col1, col2 = st.columns(2)
                    col1.metric("BHA (Limpo)", repr(bha_dh_clean))
                    col2.metric("TCO (Limpo)", repr(tco_dh_clean))
                    st.text("Verifique espaços invisíveis ou hífens diferentes acima.")

        results.append({
            'BHA Item': row['raw_name'],
            'Norm Name': bha_name,
            'BHA UH': row['uh_connection'],
            'BHA DH': row['dh_connection'],
            'TCO Qty': tco_qty,
            'Status': status,
            'Observações': "; ".join(obs)
        })

    # ... (Resto do código dos Itens Extras permanece igual)
    extras = []
    # (Copie o bloco de extras do código anterior se necessário, ou mantenha o seu)
    # Se precisar que eu reescreva o final, me avise.
    
    return pd.DataFrame(results), pd.DataFrame(extras)