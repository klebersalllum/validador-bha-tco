import pandas as pd
from normalize import normalize_tool_name, normalizar_conexao 

def apply_validation_rules(df_bha, df_tco):
    """
    Compara BHA vs TCO e gera:
    1. df_results: Validação item a item do BHA.
    2. df_extras: Itens que existem no TCO mas NÃO existem no BHA.
    """
    results = []
    
    # ---------------------------------------------------------
    # 1. PREPARAÇÃO
    # ---------------------------------------------------------

    # Garante que temos os nomes normalizados
    if 'norm_name' not in df_bha.columns:
        df_bha['norm_name'] = df_bha['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
    
    if 'norm_name' not in df_tco.columns:
        df_tco['norm_name'] = df_tco['raw_name'].apply(lambda x: normalize_tool_name(x)[1])

    # Cria listas de nomes presentes
    bha_tools_set = set(df_bha['norm_name'].dropna().unique())

    # Agrupar TCO para validação de quantidade (Item a Item do BHA)
    tco_summary = df_tco.groupby('norm_name').agg({
        'qty': 'sum',
        'dh_connection': 'first', # Pega a primeira ocorrência para comparar conexões
        'uh_connection': 'first'
    }).to_dict('index')

    # ---------------------------------------------------------
    # 2. VALIDAÇÃO PRINCIPAL (O que está no BHA vs TCO)
    # ---------------------------------------------------------
    for idx, row in df_bha.iterrows():
        bha_name = row['norm_name']
        
        # Normaliza conexões do BHA para comparação limpa
        bha_uh_clean = normalizar_conexao(row.get('uh_connection', ''))
        bha_dh_clean = normalizar_conexao(row.get('dh_connection', ''))

        status = "OK"
        obs = []
        
        tco_match = tco_summary.get(bha_name)
        
        if not tco_match:
            # ERRO CRÍTICO: Planejado mas não encontrado no PDF
            status = "ERROR"
            obs.append("Item não encontrado na TCO")
            tco_qty = 0
            tco_uh_clean = "-"
            tco_dh_clean = "-"
        else:
            tco_qty = tco_match['qty']
            # Normaliza conexões do TCO
            tco_uh_clean = normalizar_conexao(tco_match.get('uh_connection', ''))
            tco_dh_clean = normalizar_conexao(tco_match.get('dh_connection', ''))
            
            # Validação Qtd (BHA pede X, TCO tem Y)
            # Regra simples: Se TCO tiver 0, é erro. Se tiver 1, é warning (sem backup).
            if tco_qty == 0:
                status = "ERROR"
                obs.append("Qtd=0 na TCO")
            elif tco_qty < row.get('qty', 1): # Se veio menos que o planejado
                status = "ERROR"
                obs.append(f"Qtd Insuficiente (Plan: {row.get('qty', 1)}, TCO: {tco_qty})")
            elif tco_qty == 1 and row.get('qty', 1) == 1:
                status = "WARNING" if status != "ERROR" else "ERROR"
                obs.append("Sem backup (Qtd=1)")
            
            # Validação Conexões
            if bha_uh_clean != tco_uh_clean:
                status = "ERROR"
                obs.append(f"UH Divergente (TCO: {tco_match.get('uh_connection')})")
            
            if bha_dh_clean != tco_dh_clean:
                status = "ERROR"
                obs.append(f"DH Divergente (TCO: {tco_match.get('dh_connection')})")

        results.append({
            'BHA Item': row['raw_name'],
            'Norm Name': bha_name,
            'BHA UH': row.get('uh_connection', ''),
            'BHA DH': row.get('dh_connection', ''),
            'TCO Qty': tco_qty,
            'Status': status,
            'Observações': "; ".join(obs)
        })

    # ---------------------------------------------------------
    # 3. IDENTIFICAR ITENS EXTRAS (Sobrando na TCO)
    # ---------------------------------------------------------
    # Lógica: Filtra linhas do TCO cujo 'norm_name' NÃO está na lista do BHA
    
    # Mascara booleana: True se o nome NÃO estiver no BHA
    mask_extras = ~df_tco['norm_name'].isin(bha_tools_set)
    
    # Filtra o DataFrame
    df_extras_raw = df_tco[mask_extras].copy()
    
    # Seleciona e renomeia colunas para ficar bonito no relatório
    cols_to_show = {
        'raw_name': 'Nome no PDF (TCO)',
        'norm_name': 'Nome Normalizado',
        'qty': 'Qtd',
        'dh_connection': 'Conexão DH',
        'uh_connection': 'Conexão UH',
        'status': 'Status PDF'
    }
    
    # Garante que as colunas existem antes de selecionar
    available_cols = [c for c in cols_to_show.keys() if c in df_extras_raw.columns]
    df_extras = df_extras_raw[available_cols].rename(columns=cols_to_show)

    return pd.DataFrame(results), df_extras