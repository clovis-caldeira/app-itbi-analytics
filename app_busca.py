# app_busca.py (Versão para Produção - Conectada ao Supabase)

import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env (APENAS PARA TESTE LOCAL)
load_dotenv()

# --- 1. CONFIGURAÇÃO E CONEXÃO COM O SUPABASE ---

# Configura o layout da página
st.set_page_config(layout="wide")

# Função para inicializar a conexão com o Supabase, usando o cache do Streamlit
@st.cache_resource
def init_supabase_connection() -> Client:
    """Conecta ao Supabase usando as credenciais do Streamlit Secrets."""
    try:
        # Tenta pegar as credenciais do Streamlit Secrets (quando estiver online)
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
    except KeyError:
        # Se não encontrar, pega do arquivo .env (para rodar localmente)
        logger.info("Credenciais de secrets não encontradas, usando .env local.")
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        st.error("ERRO: Credenciais do Supabase não configuradas. Verifique seus secrets ou o arquivo .env")
        return None
        
    return create_client(supabase_url, supabase_key)

# Estabelece a conexão
supabase = init_supabase_connection()

# --- 2. FUNÇÃO DE BUSCA NO BANCO DE DADOS ---

def buscar_dados(nome_rua: str, numero: str = None):
    """Executa a busca no banco de dados do Supabase."""
    if not supabase:
        st.error("Conexão com o banco de dados falhou. Não é possível realizar a busca.")
        return pd.DataFrame()

    query = supabase.table('transacoes_imobiliarias').select('*')
    
    # Filtro obrigatório por nome da rua (case-insensitive)
    query = query.ilike('nome_do_logradouro', f'%{nome_rua.strip()}%')
    
    # Filtro opcional por número
    if numero:
        query = query.eq('numero', numero.strip())
        
    try:
        response = query.limit(1000).execute() # Limita a 1000 resultados para não sobrecarregar
        df = pd.DataFrame(response.data)
        return df
    except Exception as e:
        st.error(f"Ocorreu um erro durante a busca: {e}")
        return pd.DataFrame()

# --- 3. INTERFACE GRÁFICA (UI) DA APLICAÇÃO ---

st.title("🚀 Plataforma de Análise de Transações Imobiliárias (ITBI)")

st.header("1. Realize a busca no banco de dados")
col1, col2 = st.columns(2)
with col1:
    nome_rua_input = st.text_input("Nome da Rua (Obrigatório)", placeholder="Ex: R Celso Ramos")
with col2:
    numero_input = st.text_input("Número (Opcional)", placeholder="Deixe em branco para ver todos")

if st.button("Buscar Endereço", type="primary"):
    if nome_rua_input:
        with st.spinner("Buscando dados no banco..."):
            st.session_state['resultados_busca'] = buscar_dados(nome_rua_input, numero_input)
    else:
        st.warning("Por favor, preencha o campo 'Nome da Rua'.")

# --- Seção de Resultados e Filtro Adicional ---
if 'resultados_busca' in st.session_state and not st.session_state['resultados_busca'].empty:
    st.divider()
    st.header("2. Resultados da Busca")
    
    resultados_iniciais = st.session_state['resultados_busca']
    st.info(f"Busca inicial encontrou **{len(resultados_iniciais)}** resultados (limitado a 1000).")

    # Filtro Adicional
    st.markdown("#### Refine sua busca:")
    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        colunas_disponiveis = sorted(resultados_iniciais.columns)
        coluna_para_filtrar = st.selectbox("Filtrar por coluna:", options=colunas_disponiveis)
    with col_filtro2:
        valor_para_filtrar = st.text_input("Contendo o valor:", placeholder="Digite para filtrar...")

    resultados_filtrados = resultados_iniciais
    if valor_para_filtrar:
        try:
            resultados_filtrados = resultados_iniciais[
                resultados_iniciais[coluna_para_filtrar].astype(str).str.contains(valor_para_filtrar, case=False, na=False)
            ]
        except Exception as e:
            st.error(f"Erro ao aplicar filtro: {e}")

    st.success(f"Exibindo **{len(resultados_filtrados)}** resultados após o filtro adicional.")
    
    st.dataframe(resultados_filtrados, use_container_width=True)
else:
    st.info("Aguardando busca. Os resultados aparecerão aqui.")
