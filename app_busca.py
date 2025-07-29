# app_busca.py (Versão 5.1 - Tela de Login Profissional com OAuth)

import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import unicodedata
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 0. CONFIGURAÇÃO INICIAL DA PÁGINA ---

st.set_page_config(
    layout="wide",
    page_title="eXatos ITBI - Análise Imobiliária",
    page_icon="assets/icon.png" 
)

# --- 1. FUNÇÕES DE AUTENTICAÇÃO E DADOS ---

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
        st.error("ERRO: Credenciais do Supabase não configuradas. Verifique seus secrets ou o arquivo .env")
        st.stop()
        
    return create_client(supabase_url, supabase_key)

supabase = init_supabase_connection()

def get_user_profile():
    """Busca o perfil do usuário logado no banco de dados."""
    user_id = st.session_state.user.get('id')
    if user_id:
        response = supabase.table('profiles').select('*').eq('id', user_id).execute()
        if response.data:
            return response.data[0]
    return None

def check_search_limit(profile):
    """Verifica se o usuário pode realizar uma nova busca."""
    if not profile: return False, "Não foi possível carregar seu perfil. Tente relogar."
    if profile.get('plano') == 'profissional': return True, "Buscas ilimitadas para o plano Profissional."
    limite_gratuito = 5
    buscas_realizadas = profile.get('buscas_realizadas', 0)
    if profile.get('ultimo_reset'):
        ultimo_reset = datetime.fromisoformat(profile['ultimo_reset']).date()
    else:
        ultimo_reset = datetime.today().date()
    hoje = datetime.today().date()
    if hoje >= (ultimo_reset + relativedelta(months=1)):
        supabase.table('profiles').update({'buscas_realizadas': 0, 'ultimo_reset': str(hoje)}).eq('id', profile['id']).execute()
        buscas_realizadas = 0
    if buscas_realizadas < limite_gratuito:
        return True, f"Você usou {buscas_realizadas} de {limite_gratuito} buscas gratuitas este mês."
    else:
        return False, f"Você atingiu o limite de {limite_gratuito} buscas gratuitas. Considere fazer o upgrade."

def increment_search_count(profile):
    """Incrementa o contador de buscas para o usuário."""
    if profile and profile.get('plano') == 'gratuito':
        novo_total = profile.get('buscas_realizadas', 0) + 1
        supabase.table('profiles').update({'buscas_realizadas': novo_total}).eq('id', profile['id']).execute()

def normalizar_busca(texto_busca: str) -> str:
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
    if not _supabase_client: return []
    try:
        response = _supabase_client.rpc('get_distinct_anos', {}).execute()
        if response.data: return [item['ano'] for item in response.data]
        return []
    except Exception as e:
        st.error(f"Erro ao buscar lista de anos: {e}")
        return []

@st.cache_data(ttl=600)
def buscar_dados(_supabase_client, nome_rua: str = None, cep: str = None, numero: str = None, anos_selecionados: list = []):
    if not _supabase_client: return pd.DataFrame()
    query = _supabase_client.table('transacoes_imobiliarias').select('*')
    if anos_selecionados: query = query.in_('ano_transacao', anos_selecionados)
    if cep:
        cep_limpo = re.sub(r'\D', '', cep)
        if cep_limpo: query = query.eq('cep', int(cep_limpo))
    if nome_rua:
        rua_normalizada = normalizar_busca(nome_rua)
        query = query.ilike('nome_do_logradouro', f'%{rua_normalizada}%')
    if numero: query = query.eq('numero', numero.strip())
    try:
        response = query.limit(1000).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Ocorreu um erro durante a busca: {e}")
        return pd.DataFrame()

# --- 3. LAYOUT E LÓGICA DA APLICAÇÃO ---

# Inicializa o session_state
if 'user' not in st.session_state:
    st.session_state.user = None

# --- NOVA TELA DE LOGIN ---
if st.session_state.user is None:
    # Adicione seu logo aqui, se tiver um, na pasta assets
    # st.image("assets/logo.png", width=200) 
    st.title("Bem-vindo à eXatos ITBI")
    st.markdown("A plataforma de inteligência para o mercado imobiliário.")

    # Sistema de Abas
    tab_login, tab_signup = st.tabs(["Entrar", "Cadastrar"])

    with tab_login:
        st.subheader("Acesse sua conta")
        # Botão de Login com Google (exemplo, requer configuração no Supabase)
        if st.button("Entrar com o Google", use_container_width=True):
             # A biblioteca Supabase cuidará do redirecionamento
            supabase.auth.sign_in_with_oauth({"provider": "google"})

        st.markdown("<h3 style='text-align: center; color: grey;'>ou</h3>", unsafe_allow_html=True)

        with st.form("login_form", border=False):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            st.form_submit_button("Entrar com Email", use_container_width=True, on_click=lambda: setattr(st.session_state, 'login_attempt', {'email': email, 'password': password}))
    
    if 'login_attempt' in st.session_state and st.session_state.login_attempt:
        try:
            user_session = supabase.auth.sign_in_with_password(st.session_state.login_attempt)
            st.session_state.user = user_session.user.dict()
            del st.session_state.login_attempt
            st.rerun()
        except Exception:
            st.error("Erro no login: Credenciais inválidas.")
            del st.session_state.login_attempt

    with tab_signup:
        st.subheader("Crie sua conta")
        with st.form("signup_form", border=False):
            new_email = st.text_input("Seu Email", key="signup_email")
            new_password = st.text_input("Crie uma Senha", type="password", key="signup_password")
            st.form_submit_button("Cadastrar", use_container_width=True, on_click=lambda: setattr(st.session_state, 'signup_attempt', {'email': new_email, 'password': new_password}))

    if 'signup_attempt' in st.session_state and st.session_state.signup_attempt:
        try:
            supabase.auth.sign_up(st.session_state.signup_attempt)
            st.success("Cadastro realizado! Por favor, verifique seu e-mail para confirmar a conta.")
        except Exception as e:
            st.error(f"Erro no cadastro: {e}")
        del st.session_state.signup_attempt


# --- APLICAÇÃO PRINCIPAL (SÓ APARECE SE ESTIVER LOGADO) ---
else:
    user_profile = get_user_profile()

    col_user1, col_user2 = st.columns([4, 1])
    with col_user1:
        st.title("eXatas ITBI")
        st.markdown("##### Ferramenta de Análise do Mercado Imobiliário")
    with col_user2:
        st.write(f"Plano: **{user_profile.get('plano', 'N/A').capitalize()}**")
        if st.button("Sair", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    pode_buscar, mensagem_limite = check_search_limit(user_profile)
    st.info(mensagem_limite)
    
    with st.expander("🔍 Filtros de Busca", expanded=True):
        anos_disponiveis = get_anos_disponiveis(supabase)
        st.markdown("**Buscar por Endereço**")
        col_f1, col_f2 = st.columns(2)
        with col_f1: nome_rua_input = st.text_input("Nome do Logradouro", placeholder="Ex: Av Paulista")
        with col_f2: numero_input = st.text_input("Número", placeholder="(Opcional)")
        st.markdown("**ou Buscar por CEP**")
        cep_input = st.text_input("CEP", placeholder="Ex: 01311-000")
        st.markdown("---")
        anos_selecionados = st.multiselect("Filtrar por Ano(s)", options=anos_disponiveis, placeholder="Todos os anos")
        buscar_btn = st.button("Buscar", type="primary", use_container_width=True, disabled=not pode_buscar)

    st.divider()

    # Lógica para executar e exibir a busca
    if buscar_btn:
        if nome_rua_input or cep_input:
            with st.spinner("Buscando dados..."):
                increment_search_count(user_profile)
                st.session_state['resultados_busca'] = buscar_dados(supabase, nome_rua_input, cep_input, numero_input, anos_selecionados)
                st.session_state['last_search_executed'] = True
        else:
            st.warning("Preencha o 'Nome do Logradouro' ou o 'CEP'.")
            st.session_state['last_search_executed'] = False
    
    if 'resultados_busca' in st.session_state:
        resultados_iniciais = st.session_state.get('resultados_busca')
        if resultados_iniciais is not None and not resultados_iniciais.empty:
            st.header("📊 Resultados da Busca")
            st.info(f"Busca encontrou **{len(resultados_iniciais)}** resultados (limitado aos 1000 mais recentes).")
            st.markdown("###### Refine sua busca:")
            colunas_disponiveis = sorted(resultados_iniciais.columns)
            coluna_para_filtrar = st.selectbox("Filtrar por coluna:", options=colunas_disponiveis)
            valor_para_filtrar = st.text_input("Contendo o valor:", placeholder="Digite para filtrar...")
            resultados_filtrados = resultados_iniciais
            if valor_para_filtrar:
                try:
                    resultados_filtrados = resultados_iniciais[resultados_iniciais[coluna_para_filtrar].astype(str).str.contains(valor_para_filtrar, case=False, na=False)]
                except Exception as e:
                    st.error(f"Erro ao aplicar filtro: {e}")
            
            df_para_exibir = resultados_filtrados.copy()
            coluna_valor = 'valor_de_transacao_declarado_pelo_contribuinte'
            if coluna_valor in df_para_exibir.columns:
                df_para_exibir[coluna_valor] = pd.to_numeric(df_para_exibir[coluna_valor], errors='coerce')
                df_para_exibir[coluna_valor] = df_para_exibir[coluna_valor].apply(
                    lambda x: f'R$ {x:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) else "N/A"
                )
            st.dataframe(df_para_exibir, use_container_width=True)
        elif st.session_state.get('last_search_executed', False):
            st.info("Nenhum resultado encontrado para os filtros informados.")
    else:
        st.info("Utilize os filtros acima para iniciar sua análise.")
