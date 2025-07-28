# app_busca.py (Versão 3.0 - UI/UX Profissional)

import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import unicodedata

# --- 0. CONFIGURAÇÃO INICIAL DA PÁGINA ---

# Configura o layout da página, o título na aba do navegador e o ícone
st.set_page_config(
    layout="wide",
    page_title="eXatas ITBI - Análise Imobiliária",
    page_icon="assets/icon.png" # Caminho para o seu ícone
)

# --- 1. FUNÇÕES DE CONEXÃO E BUSCA ---

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

def normalizar_busca(texto_busca: str) -> str:
    """Prepara o texto de busca do usuário para ser compatível com o banco de dados."""
    if not texto_busca: return ""
    texto_sem_acento = ''.join(c for c in unicodedata.normalize('NFD', texto_busca) if unicodedata.category(c) != 'Mn')
    texto_lower = texto_sem_acento.lower()
    substituicoes = {'rua ': 'r ', 'avenida ': 'av ', 'estrada ': 'est ', 'travessa ': 'tv ', 'praca ': 'pca ', 'largo ': 'lgo '}
    for chave, valor in substituicoes.items():
        if texto_lower.startswith(chave):
            texto_lower = texto_lower.replace(chave, valor, 1)
            break
    return texto_lower.strip()

@st.cache_data(ttl=3600)
def get_anos_disponiveis(_supabase_client) -> list:
    """Busca os anos distintos chamando a função RPC no Supabase."""
    if not _supabase_client: return []
    try:
        response = _supabase_client.rpc('get_distinct_anos', {}).execute()
        if response.data:
            anos = [item['ano'] for item in response.data]
            return anos
        return []
    except Exception as e:
        st.error(f"Erro ao buscar lista de anos: {e}")
        return []

@st.cache_data(ttl=600)
def buscar_dados(_supabase_client, nome_rua: str, numero: str = None, anos_selecionados: list = []):
    """Executa a busca no banco de dados do Supabase."""
    if not _supabase_client:
        st.error("Conexão com o banco de dados falhou.")
        return pd.DataFrame()

    rua_normalizada = normalizar_busca(nome_rua)
    query = _supabase_client.table('transacoes_imobiliarias').select('*')
    if anos_selecionados:
        query = query.in_('ano_transacao', anos_selecionados)
    if numero:
        query = query.eq('numero', numero.strip())
    query = query.ilike('nome_do_logradouro', f'%{rua_normalizada}%')
        
    try:
        response = query.limit(1000).execute()
        df = pd.DataFrame(response.data)
        return df
    except Exception as e:
        st.error(f"Ocorreu um erro durante a busca: {e}")
        return pd.DataFrame()

# --- 2. LAYOUT DA INTERFACE (SIDEBAR E PÁGINA PRINCIPAL) ---

# --- BARRA LATERAL (SIDEBAR) PARA FILTROS ---
with st.sidebar:
    # Adicione seu logo aqui, se tiver um. Ex: st.image("assets/logo.png")
    st.header("🔍 Filtros de Busca")

    anos_disponiveis = get_anos_disponiveis(supabase)

    nome_rua_input = st.text_input(
        "Nome do Logradouro",
        placeholder="Ex: Av Paulista",
        help="Digite o nome da rua, avenida, etc. A busca corrige abreviações e acentos."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        numero_input = st.text_input("Número", placeholder="(Opcional)")
    with col2:
        anos_selecionados = st.multiselect(
            "Ano(s)",
            options=anos_disponiveis,
            placeholder="Todos"
        )
    
    buscar_btn = st.button("Buscar Endereço", type="primary", use_container_width=True)

# --- PÁGINA PRINCIPAL ---
st.title("eXatas ITBI")
st.markdown("##### Ferramenta de Análise do Mercado Imobiliário")
st.divider()

# Lógica para executar a busca quando o botão for clicado
if buscar_btn:
    if nome_rua_input:
        with st.spinner("Buscando dados no banco..."):
            st.session_state['resultados_busca'] = buscar_dados(supabase, nome_rua_input, numero_input, anos_selecionados)
            st.session_state['last_search_executed'] = True
    else:
        st.warning("Por favor, preencha o campo 'Nome do Logradouro' para iniciar a busca.")
        st.session_state['last_search_executed'] = False

# Seção de Resultados
if 'resultados_busca' in st.session_state:
    resultados_iniciais = st.session_state['resultados_busca']
    
    if not resultados_iniciais.empty:
        st.header("📊 Resultados da Busca")
        st.info(f"Busca encontrou **{len(resultados_iniciais)}** resultados (limitado aos 1000 mais recentes).")
        
        # Filtro Adicional
        st.markdown("###### Refine sua busca:")
        col_filtro1, col_filtro2 = st.columns(2)
        with col_filtro1:
            colunas_disponiveis = sorted(resultados_iniciais.columns)
            coluna_para_filtrar = st.selectbox("Filtrar por coluna:", options=colunas_disponiveis)
        with col_filtro2:
            valor_para_filtrar = st.text_input("Contendo o valor:", placeholder="Digite para filtrar...")

        # Lógica para aplicar o filtro dinâmico
        resultados_filtrados = resultados_iniciais
        if valor_para_filtrar:
            try:
                resultados_filtrados = resultados_iniciais[
                    resultados_iniciais[coluna_para_filtrar].astype(str).str.contains(valor_para_filtrar, case=False, na=False)
                ]
            except Exception as e:
                st.error(f"Erro ao aplicar filtro: {e}")

        # --- Formatação para Exibição ---
        df_para_exibir = resultados_filtrados.copy()
        
        coluna_valor = 'valor_de_transacao_declarado_pelo_contribuinte'
        if coluna_valor in df_para_exibir.columns:
            df_para_exibir[coluna_valor] = pd.to_numeric(df_para_exibir[coluna_valor], errors='coerce')
            df_para_exibir[coluna_valor] = df_para_exibir[coluna_valor].apply(
                lambda x: f'R$ {x:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) else "N/A"
            )

        st.dataframe(df_para_exibir, use_container_width=True)

    # Mensagem de "nenhum resultado"
    elif st.session_state.get('last_search_executed', False):
        st.info("Nenhum resultado encontrado para os filtros informados.")

else:
    # Mensagem inicial da página
    st.info("Utilize os filtros na barra lateral à esquerda para iniciar sua análise.")
