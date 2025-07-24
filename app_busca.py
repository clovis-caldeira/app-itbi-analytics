# app_busca.py (Versão 2.1 - Otimizada com RPC para Filtro de Ano)

import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env (APENAS PARA TESTE LOCAL)
load_dotenv()

# --- 1. CONFIGURAÇÃO E CONEXÃO COM O SUPABASE ---

st.set_page_config(layout="wide")

@st.cache_resource
def init_supabase_connection() -> Client:
    """Conecta ao Supabase usando as credenciais."""
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
    except KeyError:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        st.error("ERRO: Credenciais do Supabase não configuradas.")
        return None
        
    return create_client(supabase_url, supabase_key)

supabase = init_supabase_connection()

# --- 2. FUNÇÕES DE BUSCA NO BANCO DE DADOS ---

@st.cache_data(ttl=3600) # Cache de 1 hora
def get_anos_disponiveis() -> list:
    """Busca os anos distintos chamando a função RPC no Supabase."""
    if not supabase: return []
    try:
        # --- INÍCIO DA ATUALIZAÇÃO ---
        # Chama a função 'get_distinct_anos' que criamos no banco de dados.
        # É muito mais rápido e eficiente.
        response = supabase.rpc('get_distinct_anos', {}).execute()
        # --- FIM DA ATUALIZAÇÃO ---
        
        if response.data:
            anos = [item['ano'] for item in response.data]
            return anos
        return []
    except Exception as e:
        st.error(f"Erro ao buscar lista de anos: {e}")
        return []

def buscar_dados(nome_rua: str, numero: str = None, anos_selecionados: list = []):
    """Executa a busca no banco de dados do Supabase, com filtro de ano otimizado."""
    if not supabase:
        st.error("Conexão com o banco de dados falhou.")
        return pd.DataFrame()

    query = supabase.table('transacoes_imobiliarias').select('*')
    
    if anos_selecionados:
        query = query.in_('ano_transacao', anos_selecionados)

    query = query.ilike('nome_do_logradouro', f'%{nome_rua.strip()}%')
    
    if numero:
        query = query.eq('numero', numero.strip())
        
    try:
        response = query.limit(1000).execute()
        df = pd.DataFrame(response.data)
        return df
    except Exception as e:
        st.error(f"Ocorreu um erro durante a busca: {e}")
        return pd.DataFrame()

# --- 3. INTERFACE GRÁFICA (UI) DA APLICAÇÃO ---

st.title("eXatos - Ferramentade Análise de Transações Imobiliárias (ITBI)")
st.header("1. Filtros de Busca")

# Busca a lista de anos para o filtro
anos_disponiveis = get_anos_disponiveis()

col1, col2, col3 = st.columns([2, 1, 2])
with col1:
    nome_rua_input = st.text_input("Nome da Rua (Obrigatório)", placeholder="Ex: R Celso Ramos")
with col2:
    numero_input = st.text_input("Número (Opcional)")
with col3:
    anos_selecionados = st.multiselect(
        "Selecione o(s) Ano(s) (Opcional)",
        options=anos_disponiveis,
        help="Deixe em branco para buscar em todos os anos."
    )

if st.button("Buscar Endereço", type="primary"):
    if nome_rua_input:
        with st.spinner("Buscando dados no banco..."):
            st.session_state['resultados_busca'] = buscar_dados(nome_rua_input, numero_input, anos_selecionados)
            st.session_state['last_button_press'] = True # Controla a mensagem de "nenhum resultado"
    else:
        st.warning("Por favor, preencha o campo 'Nome da Rua'.")
        st.session_state['last_button_press'] = False

# Seção de Resultados
if 'resultados_busca' in st.session_state:
    resultados = st.session_state['resultados_busca']
    if not resultados.empty:
        st.divider()
        st.header("2. Resultados da Busca")
        
        st.info(f"Busca encontrou **{len(resultados)}** resultados (limitado a 1000).")
        
        # Filtro Adicional (Opcional)
        # st.dataframe(resultados, use_container_width=True) # Descomente se quiser um filtro adicional
        st.dataframe(resultados, use_container_width=True)

    elif st.session_state.get('last_button_press', False):
        st.info("Nenhum resultado encontrado para os filtros informados.")
