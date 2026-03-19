import pandas as pd
from normalize import normalize_tool_name, normalizar_conexao

def check_crossover_in_tco(conn_needed, conn_actual, df_tco):
    if not conn_needed or not conn_actual or conn_needed == conn_actual: 
        return False, None
    
    conn_needed = normalizar_conexao(conn_needed)
    conn_actual = normalizar_conexao(conn_actual)
    
    xos = df_tco[df_tco['norm_name'] == 'CROSSOVER']
    
    for _, row in xos.iterrows():
        xo_dh = normalizar_conexao(row.get('dh_connection', ''))
        xo_uh = normalizar_conexao(row.get('uh_connection', ''))
        
        conns_do_xo = [xo_dh, xo_uh]
        
        if conn_needed in conns_do_xo and conn_actual in conns_do_xo:
            return True, row['raw_name']
            
    return False, None

def agrupar_ferramentas(df):
    """
    Agrupa ferramentas com o mesmo Nome Normalizado, Conexão DH e Conexão UH,
    somando suas quantidades em uma única linha.
    """
    if df is None or df.empty:
        return df
        
    df_temp = df.copy()
    if 'qty' not in df_temp.columns:
        df_temp['qty'] = 1
        
    if 'norm_name' not in df_temp.columns:
        df_temp['norm_name'] = df_temp['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
        
    df_temp['dh_connection'] = df_temp.get('dh_connection', '').apply(normalizar_conexao)
    df_temp['uh_connection'] = df_temp.get('uh_connection', '').apply(normalizar_conexao)
    
    # Agrupa somando a quantidade e mantendo o nome original
    df_agg = df_temp.groupby(
        ['norm_name', 'dh_connection', 'uh_connection'], 
        dropna=False, 
        as_index=False
    ).agg({
        'raw_name': 'first',
        'qty': 'sum'
    })
    
    return df_agg

def validate_contingency_bha(df_cont, df_prim, df_tco):
    results = []
    
    # Agrupa os DataFrames para consolidar ferramentas iguais
    df_cont_agg = agrupar_ferramentas(df_cont)
    df_prim_agg = agrupar_ferramentas(df_prim)
    df_tco_agg = agrupar_ferramentas(df_tco)
    
    prim_conn_map = {}
    for _, row in df_prim_agg.iterrows():
        prim_conn_map[row['norm_name']] = {
            'dh': row['dh_connection'],
            'uh': row['uh_connection']
        }
        
    tco_inventory = df_tco_agg.groupby('norm_name').agg({
        'qty': 'sum',
        'raw_name': 'first',
        'dh_connection': 'first',
        'uh_connection': 'first'
    }).to_dict('index')

    for _, row in df_cont_agg.iterrows():
        cont_name = row['norm_name']
        cont_qty = row['qty']
        cont_dh = row['dh_connection']
        cont_uh = row['uh_connection']
        
        status = "OK"
        obs = []
        tco_data = tco_inventory.get(cont_name)
        
        if not tco_data:
            status = "ERROR"
            obs.append("❌ Item não encontrado no TCO")
        else:
            total_in_tco = tco_data['qty']
            tco_dh_real = tco_data['dh_connection']
            tco_uh_real = tco_data['uh_connection']
            
            if total_in_tco == 0:
                status = "ERROR"
                obs.append("❌ Qtd=0 na TCO")
            elif total_in_tco < cont_qty:
                status = "ERROR"
                obs.append(f"❌ Qtd Insuficiente (Plan: {cont_qty} / TCO: {total_in_tco})")
            elif total_in_tco == cont_qty:
                status = "WARNING"
                obs.append(f"⚠️ Apenas {total_in_tco} peça(s) (Sem Backup)")
            else:
                obs.append(f"✅ Estoque OK ({total_in_tco})")

            # VALIDAÇÃO CONTINGÊNCIA: Aqui sim procuramos Crossover
            if cont_dh and tco_dh_real and cont_dh != tco_dh_real:
                has_xo, xo_name = check_crossover_in_tco(cont_dh, tco_dh_real, df_tco_agg)
                if has_xo:
                    obs.append(f"✅ Divergência DH com TCO resolvida com XO ({xo_name})")
                else:
                    status = "ERROR"
                    obs.append(f"❌ Conexão DH Inválida (Plan: {cont_dh} / TCO: {tco_dh_real}) SEM XO")
            
            if cont_uh and tco_uh_real and cont_uh != tco_uh_real:
                has_xo, xo_name = check_crossover_in_tco(cont_uh, tco_uh_real, df_tco_agg)
                if has_xo:
                    obs.append(f"✅ Divergência UH com TCO resolvida com XO ({xo_name})")
                else:
                    status = "ERROR"
                    obs.append(f"❌ Conexão UH Inválida (Plan: {cont_uh} / TCO: {tco_uh_real}) SEM XO")

            if cont_name in prim_conn_map and status != "ERROR":
                prim_data = prim_conn_map[cont_name]
                
                if cont_dh and cont_dh != prim_data['dh']:
                    has_xo, xo_name = check_crossover_in_tco(prim_data['dh'], cont_dh, df_tco_agg)
                    if has_xo:
                        obs.append(f"✅ Mudança de Plano DH suportada por XO ({xo_name})")
                    else:
                        status = "ERROR"
                        obs.append(f"❌ Mudança de Plano DH ({prim_data['dh']} -> {cont_dh}) SEM XO")
                
                if cont_uh and cont_uh != prim_data['uh']:
                    has_xo, xo_name = check_crossover_in_tco(prim_data['uh'], cont_uh, df_tco_agg)
                    if has_xo:
                        obs.append(f"✅ Mudança de Plano UH suportada por XO ({xo_name})")
                    else:
                        status = "ERROR"
                        obs.append(f"❌ Mudança de Plano UH ({prim_data['uh']} -> {cont_uh}) SEM XO")

        results.append({
            'Qtd': cont_qty,
            'Ferramenta (Cont)': row['raw_name'],
            'Norm Name': cont_name,
            'Conexão DH': cont_dh,
            'Conexão UH': cont_uh,
            'Status': status,
            'Análise': " ".join(obs)
        })
        
    return pd.DataFrame(results)

def apply_validation_rules(df_bha, df_tco):
    results = []
    
    df_bha_agg = agrupar_ferramentas(df_bha)
    df_tco_agg = agrupar_ferramentas(df_tco)

    bha_tools_set = set(df_bha_agg['norm_name'].dropna().unique())
    
    tco_summary = df_tco_agg.groupby('norm_name').agg({
        'qty': 'sum',
        'dh_connection': 'first',
        'uh_connection': 'first'
    }).to_dict('index')

    for _, row in df_bha_agg.iterrows():
        bha_name = row['norm_name']
        bha_qty = row['qty']
        bha_dh = row['dh_connection']
        bha_uh = row['uh_connection']
        
        status = "OK"
        obs = []
        tco_match = tco_summary.get(bha_name)
        
        if not tco_match:
            status = "ERROR"
            obs.append("❌ Item não encontrado na TCO")
            tco_dh = "-"
            tco_uh = "-"
        else:
            tco_qty = tco_match['qty']
            tco_dh = tco_match['dh_connection']
            tco_uh = tco_match['uh_connection']
            
            if tco_qty == 0:
                status = "ERROR"
                obs.append("❌ Qtd=0 na TCO")
            elif tco_qty < bha_qty:
                status = "ERROR"
                obs.append(f"❌ Qtd Insuficiente (Plan: {bha_qty} / TCO: {tco_qty})")
            elif tco_qty == bha_qty:
                status = "WARNING"
                obs.append(f"⚠️ Apenas {tco_qty} peça(s) (Sem Backup)")
            else:
                obs.append(f"✅ Estoque OK ({tco_qty})")
            
            # VALIDAÇÃO PRIMÁRIA: Sem verificação de Crossover. O Físico tem que bater com o Plan.
            if bha_dh != tco_dh and bha_dh != "":
                status = "ERROR"
                obs.append(f"❌ Conexão DH Divergente (BHA: {bha_dh} vs TCO: {tco_dh})")

            if bha_uh != tco_uh and bha_uh != "":
                status = "ERROR"
                obs.append(f"❌ Conexão UH Divergente (BHA: {bha_uh} vs TCO: {tco_uh})")

        results.append({
            'Qtd': bha_qty,
            'Ferramenta': row['raw_name'],
            'Normalizado': bha_name,
            'Conexão DH': bha_dh,
            'Conexão UH': bha_uh,
            'Conexão TCO DH': tco_dh,
            'Conexão TCO UH': tco_uh,
            'Status': status,
            'Observações': " ".join(obs)
        })

    mask_extras = ~df_tco_agg['norm_name'].isin(bha_tools_set)
    df_extras = df_tco_agg[mask_extras].copy()

    return pd.DataFrame(results), df_extras