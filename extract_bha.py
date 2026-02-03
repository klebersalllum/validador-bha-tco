import pandas as pd
import numpy as np

def extract_bha_data(file_path):
    """
    Lê o arquivo BHA (Excel/CSV) de forma robusta, suportando layouts diferentes.
    - Procura por 'Desc.' ou 'Joint Count' para se localizar.
    - Filtra itens que não são SLB (coluna Manu.).
    """
    
    # 1. Leitura Inteligente (Tenta CSV, depois Excel)
    df = None
    try:
        # Tenta ler como CSV primeiro (com separador inteligente)
        try:
            df = pd.read_csv(file_path, header=None, sep=None, engine='python')
        except:
            # Fallback para separador comum se o engine python falhar
            df = pd.read_csv(file_path, header=None)
    except:
        try:
            df = pd.read_excel(file_path, header=None)
        except Exception as e:
            raise ValueError(f"Não foi possível ler o arquivo. Verifique o formato. Erro: {e}")

    # 2. Localizar a linha de cabeçalho e a coluna âncora ("Desc." ou "Description")
    header_row = -1
    desc_col = -1
    
    # Lista de possíveis nomes para a coluna de descrição (Âncora)
    possible_anchors = ['Desc.', 'Desc', 'Description', 'DESCRIPTION', 'DESC.']
    
    # Varre as primeiras 30 linhas
    for r in range(min(30, len(df))):
        row_values = [str(val).strip() for val in df.iloc[r, :].values]
        
        # Tenta achar uma das âncoras
        for col_idx, cell_val in enumerate(row_values):
            if cell_val in possible_anchors:
                header_row = r
                desc_col = col_idx
                break
            # Fallback: Se achar "Joint Count", assume que Desc é a próxima (Joint Count + 1)
            elif cell_val == 'Joint Count':
                header_row = r
                desc_col = col_idx + 1
                break
        
        if header_row != -1:
            break
            
    if header_row == -1 or desc_col == -1:
        raise ValueError("Não foi possível localizar o cabeçalho 'Desc.' ou 'Joint Count' no arquivo BHA.")

    # 3. Definição dos Offsets Relativos à coluna "Desc."
    # Baseado na estrutura: [JointCount] [Desc] [Manu] ... [Bot Type] [Bot Gender]
    # Desc é o indice 0 relativo.
    OFF_MANU = 1      # Coluna Manu é logo a direita de Desc
    OFF_BOT_TYPE = 5  # DH Connection Type
    OFF_BOT_GEN = 6   # DH Connection Gender
    # Top Type (UH) geralmente está nas mesmas colunas, mas na linha de baixo

    # Função auxiliar para pegar valor com segurança
    def get_val(row_idx, col_idx):
        if col_idx < len(df.columns):
            return df.iloc[row_idx, col_idx]
        return np.nan

    items = []
    # Dados começam 2 linhas após o cabeçalho (Linha Header + Linha Unidades/Sub-header + DADOS)
    i = header_row + 2
    
    while i < len(df):
        # O nome da ferramenta (Desc) é o guia principal
        raw_name = get_val(i, desc_col)
        
        # Se não tem nome, acabou a lista ou é linha vazia
        if pd.isna(raw_name) or str(raw_name).strip() == '':
            # Tenta verificar se não é apenas uma quebra de página (checa próxima linha)
            if i + 2 < len(df) and not pd.isna(get_val(i + 2, desc_col)):
                i += 1
                continue
            else:
                break
            
        name = str(raw_name).strip()
        
        # ====================================================================
        # FILTRO POR FABRICANTE (MANU.)
        # ====================================================================
        manu_val = str(get_val(i, desc_col + OFF_MANU)).strip().upper()
        
        # Se não for SLB, ignora e pula o bloco do item (2 linhas)
        if "SLB" not in manu_val:
            i += 2
            continue
        # ====================================================================

        # Leitura das conexões
        # DH (Down Hole) -> Linha atual (Bot Type/Gender)
        dh_type = str(get_val(i, desc_col + OFF_BOT_TYPE)).strip()
        dh_gender = str(get_val(i, desc_col + OFF_BOT_GEN)).strip()
        
        # UH (Up Hole) -> Próxima linha (Top Type/Gender)
        if i + 1 < len(df):
            uh_type = str(get_val(i+1, desc_col + OFF_BOT_TYPE)).strip()
            uh_gender = str(get_val(i+1, desc_col + OFF_BOT_GEN)).strip()
        else:
            uh_type = ""
            uh_gender = ""

        # Limpeza de "nan" e formatação
        def clean(val):
            if val.lower() == 'nan': return ""
            return val

        items.append({
            'source_file': getattr(file_path, 'name', 'BHA'),
            'qty': 1,
            'raw_name': name,
            'uh_connection': f"{clean(uh_type)} {clean(uh_gender)}".strip(),
            'dh_connection': f"{clean(dh_type)} {clean(dh_gender)}".strip()
        })
        
        i += 2 

    return pd.DataFrame(items)