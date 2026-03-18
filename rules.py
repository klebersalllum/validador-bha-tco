import pandas as pd
from normalize import normalize_tool_name, normalizar_conexao

def check_crossover_in_tco(conn_needed, conn_actual, df_tco):
    """
    Solução baseada em Física: Se precisamos ligar 'conn_needed' em 'conn_actual',
    o código busca qualquer XO no TCO que possua essas duas roscas nas extremidades.
    """
    if not conn_needed or not conn_actual or conn_needed == conn_actual: 
        return False, None
    
    xos = df_tco[df_tco['norm_name'] == 'CROSSOVER']
    
    for _, row in xos.iterrows():
        xo_dh = normalizar_conexao(row.get('dh_connection', ''))
        xo_uh = normalizar_conexao(row.get('uh_connection', ''))
        
        conns_do_xo = [xo_dh, xo_uh]
        
        # Se o XO possui as duas roscas necessárias, ele serve como ponte.
        if conn_needed in conns_do_xo and conn_actual in conns_do_xo:
            return True, row['raw_name']
            
    return False, None

def validate_contingency_bha(df_cont, df_prim, df_tco):
    results = []
    
    prim_conn_map = {}
    for _, row in df_prim.iterrows():
        prim_conn_map[row['norm_name']] = {
            'dh': normalizar_conexao(row.get('dh_connection', '')),
            'uh': normalizar_conexao(row.get('uh_connection', ''))
        }
        
    tco_inventory = df_tco.groupby('norm_name').agg({
        'qty': 'sum',
        'raw_name': 'first',
        'dh_connection': 'first',
        'uh_connection': 'first'
    }).to_dict('index')

    for _, row in df_cont.iterrows():
        cont_name = row['norm_name']
        cont_dh = normalizar_conexao(row.get('dh_connection', ''))
        cont_uh = normalizar_conexao(row.get('uh_connection', ''))
        
        status = "OK"
        obs = []
        tco_data = tco_inventory.get(cont_name)
        
        if not tco_data:
            status = "ERROR"
            obs.append("❌ Item não encontrado no TCO")
        else:
            total_in_tco = tco_data['qty']
            tco_dh_real = normalizar_conexao(tco_data.get('dh_connection', ''))
            tco_uh_real = normalizar_conexao(tco_data.get('uh_connection', ''))
            
            # --- 1. ESTOQUE ---
            if total_in_tco == 0:
                status = "ERROR"
                obs.append("❌ Qtd=0 na TCO")
            elif total_in_tco == 1:
                status = "WARNING"
                obs.append("⚠️ Apenas 1 peça (Sem Backup)")
            else:
                obs.append(f"✅ Estoque OK ({total_in_tco})")

            # --- 2. FÍSICA (A peça da contingência encaixa na peça física do TCO?) ---
            if cont_dh and tco_dh_real and cont_dh != tco_dh_real:
                has_xo, xo_name = check_crossover_in_tco(cont_dh, tco_dh_real, df_tco)
                if has_xo:
                    obs.append(f"✅ Divergência DH com TCO resolvida com XO ({xo_name})")
                else:
                    status = "ERROR"
                    obs.append(f"❌ Conexão DH Inválida (Plan: {cont_dh} / TCO: {tco_dh_real}) SEM XO")
            
            if cont_uh and tco_uh_real and cont_uh != tco_uh_real:
                has_xo, xo_name = check_crossover_in_tco(cont_uh, tco_uh_real, df_tco)
                if has_xo:
                    obs.append(f"✅ Divergência UH com TCO resolvida com XO ({xo_name})")
                else:
                    status = "ERROR"
                    obs.append(f"❌ Conexão UH Inválida (Plan: {cont_uh} / TCO: {tco_uh_real}) SEM XO")

            # --- 3. ENGENHARIA (Mudou a ferramenta em relação ao plano Primário?) ---
            if cont_name in prim_conn_map and status != "ERROR":
                prim_data = prim_conn_map[cont_name]
                
                if cont_dh and cont_dh != prim_data['dh']:
                    has_xo, xo_name = check_crossover_in_tco(prim_data['dh'], cont_dh, df_tco)
                    if has_xo:
                        obs.append(f"✅ Mudança de Plano DH suportada por XO ({xo_name})")
                    else:
                        status = "ERROR"
                        obs.append(f"❌ Mudança de Plano DH ({prim_data['dh']} -> {cont_dh}) SEM XO")
                
                if cont_uh and cont_uh != prim_data['uh']:
                    has_xo, xo_name = check_crossover_in_tco(prim_data['uh'], cont_uh, df_tco)
                    if has_xo:
                        obs.append(f"✅ Mudança de Plano UH suportada por XO ({xo_name})")
                    else:
                        status = "ERROR"
                        obs.append(f"❌ Mudança de Plano UH ({prim_data['uh']} -> {cont_uh}) SEM XO")

        results.append({
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
    
    if 'norm_name' not in df_bha.columns:
        df_bha['norm_name'] = df_bha['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
    if 'norm_name' not in df_tco.columns:
        df_tco['norm_name'] = df_tco['raw_name'].apply(lambda x: normalize_tool_name(x)[1])

    bha_tools_set = set(df_bha['norm_name'].dropna().unique())
    
    tco_summary = df_tco.groupby('norm_name').agg({
        'qty': 'sum',
        'dh_connection': 'first',
        'uh_connection': 'first'
    }).to_dict('index')

    for _, row in df_bha.iterrows():
        bha_name = row['norm_name']
        bha_dh = normalizar_conexao(row.get('dh_connection', ''))
        bha_uh = normalizar_conexao(row.get('uh_connection', ''))
        
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
            tco_dh = normalizar_conexao(tco_match.get('dh_connection', ''))
            tco_uh = normalizar_conexao(tco_match.get('uh_connection', ''))
            
            if tco_qty == 0:
                status = "ERROR"
                obs.append("❌ Qtd=0 na TCO")
            elif tco_qty == 1:
                status = "WARNING"
                obs.append("⚠️ Apenas 1 peça (Sem Backup)")
            else:
                obs.append(f"✅ Estoque OK ({tco_qty})")
            
            # Valida Conexões e procura Crossover em caso de divergência BHA vs Físico
            if bha_dh != tco_dh and bha_dh != "":
                has_xo, xo_name = check_crossover_in_tco(bha_dh, tco_dh, df_tco)
                if has_xo:
                    obs.append(f"✅ Divergência DH suportada por XO ({xo_name})")
                else:
                    status = "ERROR"
                    obs.append(f"❌ Conexão DH Divergente (BHA: {bha_dh} vs TCO: {tco_dh}) SEM XO")

            if bha_uh != tco_uh and bha_uh != "":
                has_xo, xo_name = check_crossover_in_tco(bha_uh, tco_uh, df_tco)
                if has_xo:
                    obs.append(f"✅ Divergência UH suportada por XO ({xo_name})")
                else:
                    status = "ERROR"
                    obs.append(f"❌ Conexão UH Divergente (BHA: {bha_uh} vs TCO: {tco_uh}) SEM XO")

        results.append({
            'Ferramenta': row['raw_name'],
            'Normalizado': bha_name,
            'Conexão DH': bha_dh,
            'Conexão UH': bha_uh,
            'Conexão TCO DH': tco_dh,
            'Conexão TCO UH': tco_uh,
            'Status': status,
            'Observações': " ".join(obs)
        })

    mask_extras = ~df_tco['norm_name'].isin(bha_tools_set)
    df_extras = df_tco[mask_extras].copy()

    return pd.DataFrame(results), df_extras