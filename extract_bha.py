import pandas as pd
import numpy as np

def extract_bha_data(file_path):
    """
    Lê o arquivo BHA (Excel/CSV) e retorna um DataFrame limpo com:
    [Quantity, Tool Name, UH Type, UH Gender, DH Type, DH Gender]
    """
    # Tenta ler ignorando cabeçalho inicialmente para achar a linha correta
    try:
        df = pd.read_csv(file_path, header=None)
    except:
        df = pd.read_excel(file_path, header=None)

    # Localizar a linha de cabeçalho "Joint Count"
    header_row = -1
    joint_col = -1
    
    for r in range(min(30, len(df))):
        for c in range(len(df.columns)):
            val = str(df.iloc[r, c]).strip()
            if val == 'Joint Count':
                header_row = r
                joint_col = c
                break
        if header_row != -1:
            break
            
    if header_row == -1:
        raise ValueError("Cabeçalho 'Joint Count' não encontrado no arquivo BHA.")

    # Mapear colunas baseadas na linha de cabeçalho encontrada
    # Assumindo estrutura fixa a partir da coluna Joint Count
    # Joint Count (0), Desc (1), ... Bot Type (6), Bot Gender (7) - offsets relativos
    
    # Função auxiliar para pegar valor com segurança
    def get_val(row_idx, col_offset):
        if joint_col + col_offset < len(df.columns):
            return df.iloc[row_idx, joint_col + col_offset]
        return np.nan

    # Dados começam 2 linhas após o cabeçalho
    items = []
    i = header_row + 2
    
    while i < len(df):
        # O nome da ferramenta (Desc) é o guia principal
        raw_name = get_val(i, 1) # Desc é offset +1
        if pd.isna(raw_name):
            break
            
        name = str(raw_name).strip()
        
        # Leitura das conexões (DH na linha 1, UH na linha 2)
        dh_type = str(get_val(i, 6)).strip()   # Bot Type
        dh_gender = str(get_val(i, 7)).strip() # Bot Gender
        
        # Verificar se existe linha seguinte para UH (Top Type)
        if i + 1 < len(df):
            uh_type = str(get_val(i+1, 6)).strip()
            uh_gender = str(get_val(i+1, 7)).strip()
        else:
            uh_type = ""
            uh_gender = ""

        # Limpeza de "nan"
        if dh_type.lower() == 'nan': dh_type = ""
        if dh_gender.lower() == 'nan': dh_gender = ""
        if uh_type.lower() == 'nan': uh_type = ""
        if uh_gender.lower() == 'nan': uh_gender = ""

        items.append({
            'source_file': file_path.name if hasattr(file_path, 'name') else 'BHA',
            'qty': 1, # BHA lista item a item, então qtd é sempre 1 por linha
            'raw_name': name,
            'uh_connection': f"{uh_type} {uh_gender}".strip(),
            'dh_connection': f"{dh_type} {dh_gender}".strip()
        })
        
        i += 2 # Pula de 2 em 2 linhas (item ocupa 2 linhas)

    return pd.DataFrame(items)