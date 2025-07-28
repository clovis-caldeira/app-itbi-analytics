# app_busca.py (Versão 2.5 - com Título Atualizado e Formatação de Moeda)

import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import unicodedata

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

# --- 2. FUNÇÕES DE BUSCA E NORMALIZAÇÃO ---

def normalizar_busca(texto_busca: str) -> str:
    """Prepara o texto de busca do usuário para ser compatível com o banco de dados."""
    if not texto_busca:
        return ""
        
    texto_sem_acento = ''.join(c for c in unicodedata.normalize('NFD', texto_busca) if unicodedata.category(c) != 'Mn')
    texto_lower = texto_sem_acento.lower()
    
    substituicoes = {
        'rua ': 'r ', 'avenida ': 'av ', 'estrada ': 'est ',
        'travessa ': 'tv ', 'praca ': 'pca ', 'largo ': 'lgo '
    }
    
    for chave, valor in substituicoes.items():
        if texto_lower.startswith(chave):
            texto_lower = texto_lower.replace(chave, valor, 1)
            break
            
    return texto_lower.strip()


@st.cache_data(ttl=3600)
def get_anos_disponiveis() -> list:
    """Busca os anos distintos chamando a função RPC no Supabase."""
    if not supabase: return []
    try:
        response = supabase.rpc('get_distinct_anos', {}).execute()
        if response.data:
            anos = [item['ano'] for item in response.data]
            return anos
        return []
    except Exception as e:
        st.error(f"Erro ao buscar lista de anos: {e}")
        return []

def buscar_dados(nome_rua: str, numero: str = None, anos_selecionados: list = []):
    """Executa a busca no banco de dados, usando a busca normalizada."""
    if not supabase:
        st.error("Conexão com o banco de dados falhou.")
        return pd.DataFrame()

    rua_normalizada = normalizar_busca(nome_rua)

    query = supabase.table('transacoes_imobiliarias').select('*')
    
    if anos_selecionados:
        query = query.in_('ano_transacao', anos_selecionados)

    query = query.ilike('nome_do_logradouro', f'%{rua_normalizada}%')
    
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

# --- INÍCIO DA ATUALIZAÇÃO ---
st.title("eXatas ITBI - Ferramenta de Análise Imobiliária")
# --- FIM DA ATUALIZAÇÃO ---

st.header("1. Filtros de Busca")

anos_disponiveis = get_anos_disponiveis()

col1, col2, col3 = st.columns([2, 1, 2])
with col1:
    nome_rua_input = st.text_input("Nome da Rua (Obrigatório)", placeholder="Ex: Rua Celso Ramos ou Av Paulista")
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
            st.session_state['last_button_press'] = True
    else:
        st.warning("Por favor, preencha o campo 'Nome da Rua'.")
        st.session_state['last_button_press'] = False

# --- Seção de Resultados e Filtro Adicional ---
if 'resultados_busca' in st.session_state:
    resultados_iniciais = st.session_state['resultados_busca']
    
    if not resultados_iniciais.empty:
        st.divider()
        st.header("2. Resultados da Busca")
        
        st.info(f"Busca inicial encontrou **{len(resultados_iniciais)}** resultados (limitado a 1000).")
        
        st.markdown("#### Refine sua busca:")
        col_filtro1, col_filtro2 = st.columns(2)
        
        with col_filtro1:
            colunas_disponiveis = sorted(resultados_iniciais.columns)
            coluna_para_filtrar = st.selectbox("Filtrar por coluna:", options=colunas_disponiveis)
        
        with col_filtro2:
            valor_para_filtrar = st.text_input("Contendo o valor:", placeholder="Digite para filtrar os resultados abaixo...")

        resultados_filtrados = resultados_iniciais
        if valor_para_filtrar:
            try:
                resultados_filtrados = resultados_iniciais[
                    resultados_iniciais[coluna_para_filtrar].astype(str).str.contains(valor_para_filtrar, case=False, na=False)
                ]
            except Exception as e:
                st.error(f"Erro ao aplicar filtro: {e}")

        st.success(f"Exibindo **{len(resultados_filtrados)}** resultados após o filtro adicional.")
        
        df_para_exibir = resultados_filtrados.copy()
        coluna_valor = 'valor_de_transacao_declarado_pelo_contribuinte'
        
        if coluna_valor in df_para_exibir.columns:
            df_para_exibir[coluna_valor] = pd.to_numeric(df_para_exibir[coluna_valor], errors='coerce')
            df_para_exibir[coluna_valor] = df_para_exibir[coluna_valor].apply(
                lambda x: f'R$ {x:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) else "N/A"
            )
        
        st.dataframe(df_para_exibir, use_container_width=True)

    elif st.session_state.get('last_button_press', False):
        st.info("Nenhum resultado encontrado para os filtros informados.")
