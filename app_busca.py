# app_busca.py (Versão 9.1 - Correção Final com Redirecionamento JS)

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

# ... (Todas as outras funções como get_user_profile, buscar_dados, etc. continuam aqui, sem alterações)
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

def handle_session():
    """Gerencia a sessão do usuário, lidando com o callback do fluxo PKCE."""
    if 'user' in st.session_state and st.session_state.user is not None:
        return
    if st.query_params.get("code"):
        code = st.query_params.get("code")
        try:
            session = supabase.auth.exchange_code_for_session({"auth_code": code})
            if session and session.user:
                st.session_state.user = session.user.dict()
                st.query_params.clear()
                st.rerun()
        except Exception as e:
            st.error(f"Erro ao validar sessão: {e}")
            st.query_params.clear()
        return
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            st.session_state.user = session.user.dict()
        else:
            st.session_state.user = None
    except Exception:
        st.session_state.user = None

handle_session()

# --- TELA DE LOGIN ---
if not st.session_state.get('user'):
    st.title("Bem-vindo à eXatas ITBI")
    st.markdown("A plataforma de inteligência para o mercado imobiliário.")
    
    tab_login, tab_signup = st.tabs(["Entrar", "Cadastrar"])

    with tab_login:
        st.subheader("Acesse sua conta")
        
        # --- INÍCIO DA ATUALIZAÇÃO ---
        # Usamos st.markdown com HTML/JS para forçar o redirecionamento no navegador
        #if st.button("Entrar com o Google", use_container_width=True):
        # Substitua o st.link_button("Entrar com o Google", ...) por esta linha:
         if st.markdown(f'<a href="{google_auth_url}" target="_top" class="button">Entrar com o Google</a>', unsafe_allow_html=True)

# Para estilizar o link como um botão, você pode adicionar CSS
            st.markdown("""
            <style>
            .button {
                background-color: #FF4B4B; /* Cor do botão primário do Streamlit */
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 0.5rem;
                text-decoration: none;
                display: inline-block;
                text-align: center;
                width: 100%;
                border: none;
                cursor: pointer;
            }
            .button:hover {
                background-color: #FF6B6B;
                color: white;
            }
            </style>
            """, unsafe_allow_html=True)
                    
            res = supabase.auth.sign_in_with_oauth({
                "provider": "google",
                "options": { "redirect_to": st.secrets["SITE_URL"] }
            })
            # Injeta JavaScript para redirecionar a página
            st.markdown(f'<meta http-equiv="refresh" content="0; url={res.url}">', unsafe_allow_html=True)
        # --- FIM DA ATUALIZAÇÃO ---

        st.markdown("<h3 style='text-align: center; color: grey;'>ou</h3>", unsafe_allow_html=True)
        with st.form("login_form", border=False):
            email = st.text_input("Email")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar com Email", use_container_width=True):
                try:
                    user_session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = user_session.user.dict()
                    st.rerun()
                except Exception:
                    st.error("Erro no login: Credenciais inválidas.")
    with tab_signup:
        st.subheader("Crie sua conta")
        with st.form("signup_form", border=False):
            new_email = st.text_input("Seu Email", key="signup_email")
            new_password = st.text_input("Crie uma Senha", type="password", key="signup_password")
            if st.form_submit_button("Cadastrar", use_container_width=True):
                try:
                    supabase.auth.sign_up({"email": new_email, "password": new_password})
                    st.success("Cadastro realizado! Verifique seu e-mail para confirmar a conta.")
                except Exception as e:
                    st.error(f"Erro no cadastro: {e}")

# --- APLICAÇÃO PRINCIPAL ---
else:
    # ... (o código da aplicação principal continua aqui, sem alterações)
    user_profile = get_user_profile()
    col_user1, col_user2 = st.columns([4, 1])
    with col_user1:
        st.title("eXatas ITBI")
        st.markdown("##### Ferramenta de Análise do Mercado Imobiliário")
    with col_user2:
        if user_profile:
            st.write(f"Plano: **{user_profile.get('plano', 'N/A').capitalize()}**")
        if st.button("Sair", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()
    pode_buscar, msg_limite = check_search_limit(user_profile)
    st.info(msg_limite)
    with st.expander("🔍 Filtros de Busca", expanded=True):
        anos = get_anos_disponiveis(supabase)
        rua = st.text_input("Nome do Logradouro", placeholder="Ex: Av Paulista")
        num = st.text_input("Número", placeholder="(Opcional)")
        cep = st.text_input("CEP", placeholder="Ex: 01311-000")
        anos_sel = st.multiselect("Filtrar por Ano(s)", options=anos, placeholder="Todos os anos")
        buscar_btn = st.button("Buscar", type="primary", use_container_width=True, disabled=not pode_buscar)
    st.divider()
    if buscar_btn:
        if rua or cep:
            with st.spinner("Buscando dados..."):
                increment_search_count(user_profile)
                st.session_state.resultados_busca = buscar_dados(supabase, nome_rua=rua, cep=cep, numero=num, anos_selecionados=anos_sel)
                st.session_state.last_search_executed = True
        else:
            st.warning("Preencha o 'Nome do Logradouro' ou o 'CEP'.")
    if 'resultados_busca' in st.session_state:
        res_iniciais = st.session_state.get('resultados_busca')
        if res_iniciais is not None and not res_iniciais.empty:
            st.header("📊 Resultados da Busca")
            st.info(f"Busca encontrou **{len(res_iniciais)}** resultados (limitado a 1000).")
            st.markdown("###### Refine sua busca:")
            cols = sorted(res_iniciais.columns)
            col_filtro = st.selectbox("Filtrar por coluna:", options=cols)
            val_filtro = st.text_input("Contendo o valor:", placeholder="Digite para filtrar...")
            res_filtrados = res_iniciais
            if val_filtro:
                try:
                    res_filtrados = res_iniciais[res_iniciais[col_filtro].astype(str).str.contains(val_filtro, case=False, na=False)]
                except Exception as e:
                    st.error(f"Erro ao filtrar: {e}")
            df_exibir = res_filtrados.copy()
            col_valor = 'valor_de_transacao_declarado_pelo_contribuinte'
            if col_valor in df_exibir.columns:
                df_exibir[col_valor] = pd.to_numeric(df_exibir[col_valor], errors='coerce')
                df_exibir[col_valor] = df_exibir[col_valor].apply(
                    lambda x: f'R$ {x:,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".") if pd.notnull(x) else "N/A"
                )
            st.dataframe(df_exibir, use_container_width=True)
        elif st.session_state.get('last_search_executed', False):
            st.info("Nenhum resultado encontrado.")
    else:
        st.info("Utilize os filtros acima para iniciar sua análise.")
