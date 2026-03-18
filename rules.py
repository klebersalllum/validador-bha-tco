import pandas as pd
from normalize import normalize_tool_name, normalizar_conexao

def check_crossover_in_tco(conn_a, conn_b, df_tco):
    """
    Procura no TCO se existe um Crossover que adapte Conn_A para Conn_B.
    """
    if not conn_a or not conn_b: return False, None
    
    keywords_a = conn_a.split()
    keywords_b = conn_b.split()
    
    xos = df_tco[df_tco['norm_name'] == 'CROSSOVER']
    
    for _, row in xos.iterrows():
        xo_desc = str(row['raw_name']).upper() + " " + str(row['dh_connection']).upper() + " " + str(row['uh_connection']).upper()
        
        types_a = [k for k in keywords_a if k in ["REG", "H90", "XT57", "FH", "IF", "VX", "GPDS", "PAC", "NC50"]]
        types_b = [k for k in keywords_b if k in ["REG", "H90", "XT57", "FH", "IF", "VX", "GPDS", "PAC", "NC50"]]
        
        match_a = any(t in xo_desc for t in types_a) if types_a else True
        match_b = any(t in xo_desc for t in types_b) if types_b else True
        
        if match_a and match_b:
            return True, row['raw_name']
            
    return False, None

def validate_contingency_bha(df_cont, df_prim, df_tco):
    """
    Valida Contingência com rigor total:
    1. Estoque (Mínimo 2).
    2. Compatibilidade Física com TCO (A conexão TEM que bater com o que está no inventário).
    3. Engenharia (Mudança Primário -> Contingência exige XO).
    """
    results = []
    
    # Mapas do Primário
    prim_usage = df_prim.groupby('norm_name')['qty'].sum().to_dict()
    prim_conn_map = {}
    for _, row in df_prim.iterrows():
        prim_conn_map[row['norm_name']] = {
            'dh': normalizar_conexao(row.get('dh_connection', '')),
            'uh': normalizar_conexao(row.get('uh_connection', ''))
        }
        
    # Inventário TCO (Agora guardando as conexões do TCO também!)
    tco_inventory = df_tco.groupby('norm_name').agg({
        'qty': 'sum',
        'raw_name': 'first',
        'dh_connection': 'first', # Importante: Saber qual a conexão real no TCO
        'uh_connection': 'first'
    }).to_dict('index')

    for _, row in df_cont.iterrows():
        cont_name = row['norm_name']
        cont_qty = row.get('qty', 1)
        cont_dh = normalizar_conexao(row.get('dh_connection', ''))
        cont_uh = normalizar_conexao(row.get('uh_connection', ''))
        
        status = "OK"
        obs = []
        
        # Dados do TCO
        tco_data = tco_inventory.get(cont_name)
        
        # --- 1. VALIDAÇÃO DE ESTOQUE ---
        if not tco_data:
            status = "ERROR"
            obs.append("❌ Item não encontrado no TCO (Qtd=0)")
            total_in_tco = 0
            tco_dh_real = ""
            tco_uh_real = ""
        else:
            total_in_tco = tco_data['qty']
            tco_dh_real = normalizar_conexao(tco_data.get('dh_connection', ''))
            tco_uh_real = normalizar_conexao(tco_data.get('uh_connection', ''))
            
            used_in_prim = prim_usage.get(cont_name, 0)
            ideal_stock = used_in_prim + cont_qty
            
            if total_in_tco < ideal_stock:
                status = "WARNING"
                obs.append(f"⚠️ Quantidade Insuficiente/Reuso (TCO: {total_in_tco}, Necessário: {ideal_stock})")
            elif total_in_tco < 2:
                status = "WARNING"
                obs.append(f"⚠️ Sem Backup (TCO: {total_in_tco} - Mínimo exigido: 2)")
            else:
                obs.append(f"✅ Backup OK (TCO: {total_in_tco})")

        # --- 2. VALIDAÇÃO FÍSICA (CONTINGÊNCIA vs TCO) - A CORREÇÃO ---
        # Independente do primário, a ferramenta da contingência tem que ser igual a do TCO
        if tco_data:
            # Checa DH
            if cont_dh and tco_dh_real and cont_dh != tco_dh_real:
                status = "ERROR" # Erro grave: A ferramenta planejada não bate com o físico
                obs.append(f"❌ Conexão DH Incompatível com TCO (Plan: {cont_dh} vs TCO: {tco_dh_real})")
            
            # Checa UH
            if cont_uh and tco_uh_real and cont_uh != tco_uh_real:
                status = "ERROR"
                obs.append(f"❌ Conexão UH Incompatível com TCO (Plan: {cont_uh} vs TCO: {tco_uh_real})")

        # --- 3. VALIDAÇÃO DE ENGENHARIA (MUDANÇA EM RELAÇÃO AO PRIMÁRIO) ---
        # Se passou na validação física, checamos se precisa de XO pela mudança de plano
        if cont_name in prim_conn_map:
            prim_data = prim_conn_map[cont_name]
            conn_changed = False
            
            # Só faz sentido checar XO se o status ainda não for ERRO de incompatibilidade
            if status != "ERROR":
                # Checa DH
                if cont_dh and cont_dh != prim_data['dh']:
                    conn_changed = True
                    has_xo, xo_name = check_crossover_in_tco(prim_data['dh'], cont_dh, df_tco)
                    if has_xo:
                        obs.append(f"✅ Mudança DH ({prim_data['dh']}->{cont_dh}): XO OK ({xo_name})")
                    else:
                        status = "WARNING"
                        obs.append(f"⚠️ Mudança DH ({prim_data['dh']}->{cont_dh}) SEM XO")
                
                # Checa UH
                if cont_uh and cont_uh != prim_data['uh']:
                    conn_changed = True
                    has_xo, xo_name = check_crossover_in_tco(prim_data['uh'], cont_uh, df_tco)
                    if has_xo:
                        obs.append(f"✅ Mudança UH ({prim_data['uh']}->{cont_uh}): XO OK ({xo_name})")
                    else:
                        status = "WARNING"
                        obs.append(f"⚠️ Mudança UH ({prim_data['uh']}->{cont_uh}) SEM XO")
            
            if not conn_changed and status == "OK" and not any("❌" in o for o in obs):
                pass
                
        results.append({
            'Ferramenta (Cont)': row['raw_name'],
            'Norm Name': cont_name,
            'Conexão DH': cont_dh,
            'Conexão UH': cont_uh,
            'Status': status,
            'Análise': "; ".join(obs)
        })
        
    return pd.DataFrame(results)

def apply_validation_rules(df_bha, df_tco):
    """
    Validação Padrão (BHA Primário vs TCO).
    """
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
        bha_qty = row.get('qty', 1)
        bha_dh = normalizar_conexao(row.get('dh_connection', ''))
        bha_uh = normalizar_conexao(row.get('uh_connection', ''))
        
        status = "OK"
        obs = []
        
        tco_match = tco_summary.get(bha_name)
        
        if not tco_match:
            status = "ERROR"
            obs.append("❌ Item não encontrado na TCO")
            tco_qty = 0
            tco_dh = "-"
            tco_uh = "-"
        else:
            tco_qty = tco_match['qty']
            tco_dh = normalizar_conexao(tco_match.get('dh_connection', ''))
            tco_uh = normalizar_conexao(tco_match.get('uh_connection', ''))
            
            if tco_qty == 0:
                status = "ERROR"
                obs.append("❌ Qtd=0 na TCO")
            elif tco_qty < bha_qty:
                status = "ERROR"
                obs.append(f"❌ Qtd Insuficiente (Plan: {bha_qty}, TCO: {tco_qty})")
            elif tco_qty < 2:
                status = "WARNING"
                obs.append(f"⚠️ Sem Backup (TCO: {tco_qty} - Mínimo exigido: 2)")
            else:
                obs.append(f"✅ Backup OK (TCO: {tco_qty})")
            
            if bha_dh != tco_dh and bha_dh != "":
                status = "ERROR"
                obs.append(f"❌ Conexão DH Divergente (BHA: {bha_dh} vs TCO: {tco_dh})")

            if bha_uh != tco_uh and bha_uh != "":
                status = "ERROR"
                obs.append(f"❌ Conexão UH Divergente (BHA: {bha_uh} vs TCO: {tco_uh})")

        results.append({
            'Ferramenta': row['raw_name'],
            'Normalizado': bha_name,
            'Conexão DH': bha_dh,
            'Conexão UH': bha_uh,
            'Conexão TCO DH': tco_dh,
            'Conexão TCO UH': tco_uh,
            'Status': status,
            'Observações': "; ".join(obs)
        })

    mask_extras = ~df_tco['norm_name'].isin(bha_tools_set)
    df_extras = df_tco[mask_extras].copy()

    return pd.DataFrame(results), df_extras