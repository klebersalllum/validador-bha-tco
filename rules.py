import pandas as pd
from normalize import normalize_tool_name # Importando seu script de normalização

def apply_validation_rules(df_bha, df_tco):
    """
    Aplica as regras de validação BHA x TCO.
    Retorna dois DataFrames: 
    1. Resultados da Validação (por item do BHA)
    2. Itens Extras (presentes na TCO mas não no BHA)
    """
    results = []
    
    # Normalizar nomes no BHA para comparação
    df_bha['norm_name'] = df_bha['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
    
    # Agrupar TCO por nome normalizado para contagem total
    # (Assumindo que você já rodou a normalização no df_tco antes de passar pra cá)
    tco_summary = df_tco.groupby('norm_name').agg({
        'qty': 'sum',
        'uh_connection': 'first', # Pega a primeira ocorrência para comparar
        'dh_connection': 'first'
    }).to_dict('index')

    matched_tco_names = set()

    for idx, row in df_bha.iterrows():
        bha_name = row['norm_name']
        status = "OK"
        obs = []
        
        # Buscar no TCO
        tco_match = tco_summary.get(bha_name)
        
        if not tco_match:
            # REGRA 1: Item não existe no TCO -> ERROR
            status = "ERROR"
            obs.append("Item não encontrado na TCO")
            tco_qty = 0
            tco_uh = "-"
            tco_dh = "-"
        else:
            matched_tco_names.add(bha_name)
            tco_qty = tco_match['qty']
            tco_uh = tco_match['uh_connection']
            tco_dh = tco_match['dh_connection']
            
            # REGRA 1: Validação de Quantidade
            if tco_qty == 1:
                status = "WARNING" if status != "ERROR" else "ERROR"
                obs.append("Sem backup (Qtd=1)")
            elif tco_qty == 0:
                status = "ERROR"
                obs.append("Qtd=0 na TCO")
            
            # REGRA 2: Validação de Conexões
            # Simplificação: comparando string exata. Ideal é normalizar espaços/maiúsculas
            if row['uh_connection'].upper() != str(tco_uh).upper():
                status = "ERROR"
                obs.append(f"UH Divergente (TCO: {tco_uh})")
                
            if row['dh_connection'].upper() != str(tco_dh).upper():
                status = "ERROR"
                obs.append(f"DH Divergente (TCO: {tco_dh})")

        results.append({
            'BHA Item': row['raw_name'],
            'Norm Name': bha_name,
            'BHA UH': row['uh_connection'],
            'BHA DH': row['dh_connection'],
            'TCO Qty': tco_qty,
            'Status': status,
            'Observações': "; ".join(obs)
        })

    # REGRA 3: Itens Extras na TCO
    extras = []
    all_tco_names = set(df_tco['norm_name'].unique())
    extra_names = all_tco_names - set(df_bha['norm_name'].unique())
    
    for name in extra_names:
        row = df_tco[df_tco['norm_name'] == name].iloc[0]
        extras.append({
            'TCO Item': row['raw_name'],
            'Norm Name': name,
            'Qty': df_tco[df_tco['norm_name'] == name]['qty'].sum(),
            'Status': 'INFO (Extra)'
        })

    return pd.DataFrame(results), pd.DataFrame(extras)