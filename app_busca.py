# app_busca.py (Versão Final - Correção Definitiva do X-Frame-Options)

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
st.set_page_config(layout="wide", page_title="eXatas ITBI - Análise Imobiliária", page_icon="assets/icon.png")

# --- 1. FUNÇÕES DE AUTENTICAÇÃO E DADOS ---

@st.cache_resource
def init_supabase_connection() -> Client:
    try:
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
    except KeyError:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        st.error("ERRO: Credenciais do Supabase não configuradas.")
        st.stop()
    return create_client(supabase_url, supabase_key)

supabase = init_supabase_connection()

def get_user_profile():
    user_id = st.session_state.get('user', {}).get('id')
    if user_id:
        response = supabase.table('profiles').select('*').eq('id', user_id).execute()
        if response.data:
            return response.data[0]
    return None

def check_search_limit(profile):
    if not profile: return False, "Não foi possível carregar seu perfil."
    if profile.get('plano') == 'profissional': return True, "Buscas ilimitadas."
    limite = 5
    usadas = profile.get('buscas_realizadas', 0)
    if profile.get('ultimo_reset'):
        ultimo_reset = datetime.fromisoformat(profile['ultimo_reset']).date()
    else:
        ultimo_reset = datetime.today().date()
    hoje = datetime.today().date()
    if hoje >= (ultimo_reset + relativedelta(months=1)):
        supabase.table('profiles').update({'buscas_realizadas': 0, 'ultimo_reset': str(hoje)}).eq('id', profile['id']).execute()
        usadas = 0
    if usadas < limite:
        return True, f"Buscas gratuitas: {usadas} de {limite} usadas."
    else:
        return False, f"Limite de buscas gratuitas atingido."

def increment_search_count(profile):
    if profile and profile.get('plano') == 'gratuito':
        novo_total = profile.get('buscas_realizadas', 0) + 1
        supabase.table('profiles').update({'buscas_realizadas': novo_total}).eq('id', profile['id']).execute()

def normalizar_busca(texto: str) -> str:
    if not texto: return ""
    s = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    s = s.lower()
    subs = {'rua ': 'r ', 'avenida ': 'av ', 'estrada ': 'est ', 'travessa ': 'tv ', 'praca ': 'pca ', 'largo ': 'lgo '}
    for k, v in subs.items():
        if s.startswith(k):
            s = s.replace(k, v, 1)
            break
    return s.strip()

@st.cache_data(ttl=3600)
def get_anos_disponiveis(_db: Client) -> list:
    if not _db: return []
    try:
        res = _db.rpc('get_distinct_anos', {}).execute()
        return [item['ano'] for item in res.data] if res.data else []
    except Exception as e:
        st.error(f"Erro ao buscar anos: {e}")
        return []

@st.cache_data(ttl=600)
def buscar_dados(_db: Client, **kwargs):
    if not _db: return pd.DataFrame()
    query = _db.table('transacoes_imobiliarias').select('*')
    if kwargs.get('anos_selecionados'): query = query.in_('ano_transacao', kwargs['anos_selecionados'])
    if kwargs.get('cep'):
        cep = re.sub(r'\D', '', kwargs['cep'])
        if cep: query = query.eq('cep', int(cep))
    if kwargs.get('nome_rua'):
        rua = normalizar_busca(kwargs['nome_rua'])
        query = query.ilike('nome_do_logradouro', f'%{rua}%')
    if kwargs.get('numero'): query = query.eq('numero', kwargs['numero'].strip())
    try:
        res = query.limit(1000).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Erro na busca: {e}")
        return pd.DataFrame()

# --- 3. LAYOUT E LÓGICA DA APLICAÇÃO ---

def set_user_session():
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            st.session_state.user = session.user.dict()
    except Exception:
        st.session_state.user = None

if 'user' not in st.session_state:
    set_user_session()

# --- TELA DE LOGIN ---
if not st.session_state.get('user'):
    st.title("Bem-vindo à eXatas ITBI")
    st.markdown("A plataforma de inteligência para o mercado imobiliário.")

    tab_login, tab_signup = st.tabs(["Entrar", "Cadastrar"])

    with tab_login:
        st.subheader("Acesse sua conta")

        supabase_url = st.secrets["SUPABASE_URL"]
        redirect_url = st.secrets["SITE_URL"]
        google_auth_url = f"{supabase_url}/auth/v1/authorize?provider=google&redirect_to={redirect_url}"

        # --- INÍCIO DA CORREÇÃO ---
        # Estilo CSS para o botão-link
        st.markdown("""
        <style>
        .google-button-container {
            width: 100%;
            display: flex;
            justify-content: center;
        }
        .google-button {
            background-color: #FFFFFF;
            color: #444444;
            border: 1px solid #DDDDDD;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            text-decoration: none;
            display: inline-block;
            text-align: center;
            width: 100%;
            cursor: pointer;
            font-weight: bold;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 1rem;
        }
        .google-button:hover {
            background-color: #F8F8F8;
            color: #333333;
        }
        </style>
        """, unsafe_allow_html=True)

        # O botão-link que força o redirecionamento para a janela principal (target="_top")
        st.markdown(f'<div class="google-button-container"><a href="{google_auth_url}" target="_top" class="google-button">Entrar com o Google</a></div>', unsafe_allow_html=True)
        # --- FIM DA CORREÇÃO ---

        st.markdown("<h3 style='text-align: center; color: grey;'>ou</h3>", unsafe_allow_html=True)
        with st.form("login_form", border=False):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar com Email", use_container_width=True):
                try:
                    user_session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state
