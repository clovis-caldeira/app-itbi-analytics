import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAÇÃO ESSENCIAL ---

# 1. AJUSTE OS NOMES DAS COLUNAS AQUI, SE NECESSÁRIO
COLUNA_LOGRADOURO = 'Nome do Logradouro'
COLUNA_NUMERO = 'Número'
COLUNA_COMPLEMENTO = 'Complemento'
COLUNA_VALOR = 'Valor de Transação (declarado pelo contribuinte)'
COLUNA_DATA = 'Data de Transação'

# 2. GERA AUTOMATICAMENTE A LISTA DE TODAS AS ABAS DE 2020 A 2026
meses_pt = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ']
ABAS_PARA_LER = [f"{mes}-{ano}" for ano in range(2020, 2027) for mes in meses_pt]

# --- Função de Busca (Robusta e Flexível) ---
@st.cache_data # Usa o cache do Streamlit para acelerar buscas repetidas com os mesmos arquivos
def buscar_em_planilhas(lista_arquivos_bytes, nome_rua, numero=None):
    """
    Função principal que lê os arquivos, limpa os dados e faz a busca inicial.
    """
    lista_dfs = []
    for arquivo_bytes in lista_arquivos_bytes:
        try:
            # Lê apenas as abas que existem no arquivo e estão na nossa lista gigante
            planilha = pd.ExcelFile(arquivo_bytes)
            abas_existentes_no_arquivo = [aba for aba in ABAS_PARA_LER if aba in planilha.sheet_names]
            
            if abas_existentes_no_arquivo:
                 df_arquivo = pd.concat(
                    [planilha.parse(sheet_name=aba) for aba in abas_existentes_no_arquivo],
                    ignore_index=True
                )
                 lista_dfs.append(df_arquivo)
        except Exception as e:
            st.error(f"Erro ao processar um dos arquivos: {e}.")
            return pd.DataFrame()

    if not lista_dfs:
        st.warning("Nenhuma aba com dados (Ex: JAN-2025) foi encontrada nos arquivos carregados.")
        return pd.DataFrame()

    df_consolidado = pd.concat(lista_dfs, ignore_index=True)

    # --- Limpeza e Preparação dos Dados ---
    df_consolidado['busca_logradouro'] = df_consolidado[COLUNA_LOGRADOURO].astype(str).str.strip()
    df_consolidado['busca_numero'] = pd.to_numeric(df_consolidado[COLUNA_NUMERO], errors='coerce').fillna(0).astype(np.int64).astype(str)

    # --- Filtro da Busca (Lógica Modificada) ---
    resultados = df_consolidado[df_consolidado['busca_logradouro'].str.contains(nome_rua.strip(), case=False, na=False)].copy()
    if numero:
        resultados = resultados[resultados['busca_numero'] == str(numero).strip()]

    # Remove colunas de busca auxiliares
    resultados = resultados.drop(columns=['busca_logradouro', 'busca_numero'])
    
    return resultados


# --- Interface Gráfica com Streamlit ---

st.set_page_config(layout="wide")
st.title("🚀 PrimeX - Ferramenta Avançada de Avaliação")

# Inicializa o session_state para guardar os resultados
if 'resultados_busca' not in st.session_state:
    st.session_state['resultados_busca'] = pd.DataFrame()

st.header("1. Carregue as planilhas")
uploaded_files = st.file_uploader(
    "Selecione uma ou mais planilhas Excel (.xlsx)",
    type="xlsx",
    accept_multiple_files=True
)

st.divider()

st.header("2. Realize a busca inicial")
col1, col2 = st.columns(2)
with col1:
    nome_rua_input = st.text_input("Nome da Rua (Obrigatório)", placeholder="Ex: R Celso Ramos")
with col2:
    numero_input = st.text_input("Número (Opcional)", placeholder="Deixe em branco para ver todos")

if st.button("Buscar Endereço", type="primary"):
    if nome_rua_input and uploaded_files:
        # Converte os arquivos para bytes para que a função em cache funcione
        lista_bytes = [file.getvalue() for file in uploaded_files]
        st.session_state['resultados_busca'] = buscar_em_planilhas(tuple(lista_bytes), nome_rua_input, numero_input)
    else:
        st.warning("Por favor, carregue ao menos uma planilha e preencha o campo 'Nome da Rua'.")
        st.session_state['resultados_busca'] = pd.DataFrame() # Limpa resultados antigos

# --- Seção de Resultados e Filtro Adicional ---
if not st.session_state['resultados_busca'].empty:
    st.divider()
    st.header("3. Resultados e Filtro Adicional")
    
    resultados_iniciais = st.session_state['resultados_busca']
    st.info(f"Busca inicial encontrou **{len(resultados_iniciais)}** resultados.")

    # --- Filtro Adicional ---
    st.markdown("#### Refine sua busca:")
    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        # Oferece todas as colunas do resultado como opção de filtro
        coluna_para_filtrar = st.selectbox(
            "Filtrar por coluna:",
            options=resultados_iniciais.columns
        )
    with col_filtro2:
        valor_para_filtrar = st.text_input("Contendo o valor:", placeholder="Digite para filtrar...")

    # Aplica o filtro adicional
    resultados_filtrados = resultados_iniciais
    if valor_para_filtrar:
        resultados_filtrados = resultados_iniciais[
            resultados_iniciais[coluna_para_filtrar].astype(str).str.contains(valor_para_filtrar, case=False, na=False)
        ]

    st.success(f"Exibindo **{len(resultados_filtrados)}** resultados após o filtro adicional.")

    # --- Formatação para Exibição ---
    resultados_para_exibir = resultados_filtrados.copy()
    if COLUNA_VALOR in resultados_para_exibir.columns:
        resultados_para_exibir[COLUNA_VALOR] = pd.to_numeric(resultados_para_exibir[COLUNA_VALOR], errors='coerce').apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if pd.notna(x) else "N/A"
        )
    if COLUNA_DATA in resultados_para_exibir.columns:
        resultados_para_exibir[COLUNA_DATA] = pd.to_datetime(resultados_para_exibir[COLUNA_DATA], errors='coerce').dt.strftime('%d/%m/%Y')
    
    st.dataframe(resultados_para_exibir, use_container_width=True)
else:
    # Mensagem para quando não há busca ou a busca não retorna nada
    st.info("Aguardando busca. Os resultados aparecerão aqui.")