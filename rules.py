import pandas as pd
from normalize import normalize_tool_name, normalize_connection

def check_crossover_in_tco(conn_needed, conn_actual, df_tco):
    if not conn_needed or not conn_actual or conn_needed == conn_actual: 
        return False, None
    
    conn_needed = normalize_connection(conn_needed)
    conn_actual = normalize_connection(conn_actual)
    
    xos = df_tco[df_tco['norm_name'] == 'CROSSOVER']
    
    for _, row in xos.iterrows():
        xo_dh = normalize_connection(row.get('dh_connection', ''))
        xo_uh = normalize_connection(row.get('uh_connection', ''))
        
        conns_do_xo = [xo_dh, xo_uh]
        
        if conn_needed in conns_do_xo and conn_actual in conns_do_xo:
            return True, row['raw_name']
            
    return False, None

def group_tools(df):
    """
    Groups tools with the same Normalized Name, DH Connection, and UH Connection,
    summing their quantities into a single row.
    """
    if df is None or df.empty:
        return df
        
    df_temp = df.copy()
    if 'qty' not in df_temp.columns:
        df_temp['qty'] = 1
        
    if 'norm_name' not in df_temp.columns:
        df_temp['norm_name'] = df_temp['raw_name'].apply(lambda x: normalize_tool_name(x)[1])
        
    df_temp['dh_connection'] = df_temp.get('dh_connection', '').apply(normalize_connection)
    df_temp['uh_connection'] = df_temp.get('uh_connection', '').apply(normalize_connection)
    
    # Groups by summing the quantity and keeping the original name
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
    
    # Groups the DataFrames to consolidate identical tools
    df_cont_agg = group_tools(df_cont)
    df_prim_agg = group_tools(df_prim)
    df_tco_agg = group_tools(df_tco)
    
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
            obs.append("❌ Item not found in TCO")
        else:
            total_in_tco = tco_data['qty']
            tco_dh_real = tco_data['dh_connection']
            tco_uh_real = tco_data['uh_connection']
            
            if total_in_tco == 0:
                status = "ERROR"
                obs.append("❌ Qty=0 in TCO")
            elif total_in_tco < cont_qty:
                status = "ERROR"
                obs.append(f"❌ Insufficient Qty (Plan: {cont_qty} / TCO: {total_in_tco})")
            elif total_in_tco == cont_qty:
                status = "WARNING"
                obs.append(f"⚠️ Only {total_in_tco} piece(s) (No Backup)")
            else:
                obs.append(f"✅ Stock OK ({total_in_tco})")

            # CONTINGENCY VALIDATION: Here we do look for a Crossover
            if cont_dh and tco_dh_real and cont_dh != tco_dh_real:
                has_xo, xo_name = check_crossover_in_tco(cont_dh, tco_dh_real, df_tco_agg)
                if has_xo:
                    obs.append(f"✅ DH Divergence with TCO resolved with XO ({xo_name})")
                else:
                    status = "ERROR"
                    obs.append(f"❌ Invalid DH Connection (Plan: {cont_dh} / TCO: {tco_dh_real}) NO XO")
            
            if cont_uh and tco_uh_real and cont_uh != tco_uh_real:
                has_xo, xo_name = check_crossover_in_tco(cont_uh, tco_uh_real, df_tco_agg)
                if has_xo:
                    obs.append(f"✅ UH Divergence with TCO resolved with XO ({xo_name})")
                else:
                    status = "ERROR"
                    obs.append(f"❌ Invalid UH Connection (Plan: {cont_uh} / TCO: {tco_uh_real}) NO XO")

            if cont_name in prim_conn_map and status != "ERROR":
                prim_data = prim_conn_map[cont_name]
                
                if cont_dh and cont_dh != prim_data['dh']:
                    has_xo, xo_name = check_crossover_in_tco(prim_data['dh'], cont_dh, df_tco_agg)
                    if has_xo:
                        obs.append(f"✅ DH Plan Change supported by XO ({xo_name})")
                    else:
                        status = "ERROR"
                        obs.append(f"❌ DH Plan Change ({prim_data['dh']} -> {cont_dh}) NO XO")
                
                if cont_uh and cont_uh != prim_data['uh']:
                    has_xo, xo_name = check_crossover_in_tco(prim_data['uh'], cont_uh, df_tco_agg)
                    if has_xo:
                        obs.append(f"✅ UH Plan Change supported by XO ({xo_name})")
                    else:
                        status = "ERROR"
                        obs.append(f"❌ UH Plan Change ({prim_data['uh']} -> {cont_uh}) NO XO")

        results.append({
            'Qty': cont_qty,
            'Tool (Cont)': row['raw_name'],
            'Norm Name': cont_name,
            'DH Connection': cont_dh,
            'UH Connection': cont_uh,
            'Status': status,
            'Analysis': " ".join(obs)
        })
        
    return pd.DataFrame(results)

def apply_validation_rules(df_bha, df_tco):
    results = []
    
    df_bha_agg = group_tools(df_bha)
    df_tco_agg = group_tools(df_tco)

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
            obs.append("❌ Item not found in TCO")
            tco_dh = "-"
            tco_uh = "-"
        else:
            tco_qty = tco_match['qty']
            tco_dh = tco_match['dh_connection']
            tco_uh = tco_match['uh_connection']
            
            if tco_qty == 0:
                status = "ERROR"
                obs.append("❌ Qty=0 in TCO")
            elif tco_qty < bha_qty:
                status = "ERROR"
                obs.append(f"❌ Insufficient Qty (Plan: {bha_qty} / TCO: {tco_qty})")
            elif tco_qty == bha_qty:
                status = "WARNING"
                obs.append(f"⚠️ Only {tco_qty} piece(s) (No Backup)")
            else:
                obs.append(f"✅ Stock OK ({tco_qty})")
            
            # PRIMARY VALIDATION: No Crossover check. Physical must match the Plan.
            if bha_dh != tco_dh and bha_dh != "":
                status = "ERROR"
                obs.append(f"❌ Divergent DH Connection (BHA: {bha_dh} vs TCO: {tco_dh})")

            if bha_uh != tco_uh and bha_uh != "":
                status = "ERROR"
                obs.append(f"❌ Divergent UH Connection (BHA: {bha_uh} vs TCO: {tco_uh})")

        results.append({
            'Qty': bha_qty,
            'Tool': row['raw_name'],
            'Normalized': bha_name,
            'DH Connection': bha_dh,
            'UH Connection': bha_uh,
            'TCO DH Connection': tco_dh,
            'TCO UH Connection': tco_uh,
            'Status': status,
            'Observations': " ".join(obs)
        })

    mask_extras = ~df_tco_agg['norm_name'].isin(bha_tools_set)
    df_extras = df_tco_agg[mask_extras].copy()

    return pd.DataFrame(results), df_extras