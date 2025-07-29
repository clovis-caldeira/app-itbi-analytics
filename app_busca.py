# app_busca.py (Versão 5.8 - Solução Definitiva com get_session())

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

# --- INÍCIO DA ATUALIZAÇÃO: Gerenciador de Sessão Definitivo ---
# Função alternativa para processar callback do Google
def processar_callback_google():
    """Função alternativa para processar o callback do Google OAuth"""
    query_params = dict(st.query_params)
    
    if not query_params:
        return False
    
    st.write("🔍 **Debug - Parâmetros da URL:**")
    st.json(query_params)
    
    # Processa diferentes formatos de callback
    if "access_token" in query_params:
        try:
            access_token = query_params["access_token"]
            
            # Método 1: Tentar com set_session
            if "refresh_token" in query_params:
                refresh_token = query_params["refresh_token"]
                st.write("🔄 **Tentativa 1:** Usando set_session com access + refresh token")
                
                try:
                    response = supabase.auth.set_session(access_token, refresh_token)
                    if response and response.user:
                        st.session_state.user = response.user.dict()
                        st.success("✅ Login realizado com set_session!")
                        st.query_params.clear()
                        return True
                except Exception as e:
                    st.write(f"❌ Erro no set_session: {e}")
            
            # Método 2: Tentar obter usuário diretamente com token
            st.write("🔄 **Tentativa 2:** Usando get_user com access token")
            try:
                user_response = supabase.auth.get_user(access_token)
                if user_response and user_response.user:
                    st.session_state.user = user_response.user.dict()
                    
                    # Também tenta salvar o token para futuras requisições
                    supabase.auth.set_session(access_token, query_params.get("refresh_token", ""))
                    
                    st.success("✅ Login realizado com get_user!")
                    st.query_params.clear()
                    return True
            except Exception as e:
                st.write(f"❌ Erro no get_user: {e}")
            
            # Método 3: Processamento manual dos dados
            if "token_type" in query_params:
                st.write("🔄 **Tentativa 3:** Processamento manual do token")
                token_type = query_params.get("token_type", "bearer")
                
                # Cria um header de autorização e faz uma requisição manual
                headers = {"Authorization": f"{token_type} {access_token}"}
                st.write(f"Headers criados: {headers}")
                
        except Exception as e:
            st.error(f"❌ Erro geral no processamento: {e}")
    
    return False

def check_user_session():
    """Verifica a sessão usando o método oficial da biblioteca Supabase."""
    
    # Primeiro, verifica se há parâmetros de callback do Google OAuth na URL
    query_params = dict(st.query_params)
    
    # Debug: mostra os parâmetros recebidos
    if query_params:
        st.sidebar.write("🔍 **Parâmetros recebidos:**", dict(query_params))
    
    # CORREÇÃO: Processar diferentes tipos de callback do Supabase
    # O Supabase pode retornar: access_token, refresh_token, type=recovery, etc.
    
    if "access_token" in query_params:
        access_token = query_params["access_token"]
        refresh_token = query_params.get("refresh_token", "")
        
        try:
            st.info("🔄 Processando login do Google...")
            
            # MÉTODO CORRETO: Usar o token para obter a sessão
            if refresh_token:
                # Tem refresh token - usar set_session
                session_response = supabase.auth.set_session(access_token, refresh_token)
            else:
                # Só access token - usar get_user
                session_response = supabase.auth.get_user(access_token)
            
            if session_response and session_response.user:
                st.session_state.user = session_response.user.dict()
                st.success("✅ Login realizado com sucesso!")
                
                # IMPORTANTE: Limpar parâmetros da URL
                st.query_params.clear()
                st.rerun()
                return True
            else:
                st.error("❌ Erro: Não foi possível obter dados do usuário")
                
        except Exception as e:
            st.error(f"❌ Erro ao processar login do Google: {e}")
            st.write("**Detalhes do erro:**", str(e))
            
            # Tentar método alternativo
            try:
                st.info("🔄 Tentando método alternativo...")
                # Força a sessão manualmente
                supabase.auth._client.auth.set_session(access_token, refresh_token)
                user = supabase.auth.get_user(access_token)
                if user and user.user:
                    st.session_state.user = user.user.dict()
                    st.success("✅ Login realizado com método alternativo!")
                    st.query_params.clear()
                    st.rerun()
                    return True
            except Exception as e2:
                st.error(f"❌ Método alternativo também falhou: {e2}")
    
    # Verificação normal da sessão existente
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            if 'user' not in st.session_state or not st.session_state.user:
                st.session_state.user = session.user.dict()
        elif 'user' not in st.session_state:
            st.session_state.user = None
    except Exception as e:
        st.sidebar.write("**Erro ao verificar sessão:**", str(e))
        st.session_state.user = None
    
    return False

# Executa a verificação no início de cada recarregamento da página
check_user_session()
# --- FIM DA ATUALIZAÇÃO ---

# --- TELA DE LOGIN ---
if not st.session_state.get('user'):
    st.title("Bem-vindo à eXatas ITBI")
    st.markdown("A plataforma de inteligência para o mercado imobiliário.")
    
    tab_login, tab_signup = st.tabs(["Entrar", "Cadastrar"])

    with tab_login:
        st.subheader("Acesse sua conta")
        
        try:
            supabase_url = st.secrets["SUPABASE_URL"]
            redirect_url = st.secrets["SITE_URL"]
        except KeyError:
            supabase_url = os.getenv("SUPABASE_URL")
            redirect_url = "http://localhost:8501"  # Fallback para desenvolvimento
        
        # URL corrigida para o Google OAuth
        google_auth_url = f"{supabase_url}/auth/v1/authorize?provider=google&redirect_to={redirect_url}"
        
        # Adiciona informação sobre o redirecionamento
        st.info("🔄 Após autorizar com o Google, você será redirecionado de volta para esta página.")
        
        # Verifica se há tokens na URL (indicando callback do Google)
        query_params = dict(st.query_params)
        if query_params:
            st.warning("🔍 Parâmetros detectados na URL - processando...")
            
            col_debug1, col_debug2 = st.columns([1, 1])
            
            with col_debug1:
                if st.button("🔄 Processar Automático", type="primary"):
                    check_user_session()
                    st.rerun()
            
            with col_debug2:
                if st.button("�️ Processar Manual", type="secondary"):
                    if processar_callback_google():
                        st.rerun()
            
            # Mostrar dados para debug
            with st.expander("🔍 Ver dados de debug"):
                st.json(query_params)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.link_button("🔐 Entrar com Google", url=google_auth_url, use_container_width=True)
        with col2:
            if st.button("🔄 Verificar Login", use_container_width=True):
                check_user_session()
                st.rerun()

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

# --- APLICAÇÃO PRINCIPAL (SÓ APARECE SE ESTIVER LOGADO) ---
else:
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
            st.info(f"Busca encontrou **{len(res_iniciais)}** resultados (limitado aos 1000 mais recentes).")
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

# --- DEBUG: Mostrar informações da sessão (remover em produção) ---
if st.sidebar.button("🔍 Debug Session"):
    st.sidebar.write("**Query Params:**", dict(st.query_params))
    st.sidebar.write("**Session State:**", st.session_state.get('user', 'Não logado'))
    
    # Verifica sessão atual
    try:
        session = supabase.auth.get_session()
        st.sidebar.write("**Supabase Session:**", "Ativa" if session and session.user else "Inativa")
    except Exception as e:
        st.sidebar.write("**Erro na sessão:**", str(e))

# Função alternativa para processar callback do Google
def processar_callback_google():
    """Função alternativa para processar o callback do Google OAuth"""
    query_params = dict(st.query_params)
    
    if not query_params:
        return False
    
    st.write("🔍 **Debug - Parâmetros da URL:**")
    st.json(query_params)
    
    # Processa diferentes formatos de callback
    if "access_token" in query_params:
        try:
            access_token = query_params["access_token"]
            
            # Método 1: Tentar com set_session
            if "refresh_token" in query_params:
                refresh_token = query_params["refresh_token"]
                st.write("🔄 **Tentativa 1:** Usando set_session com access + refresh token")
                
                try:
                    response = supabase.auth.set_session(access_token, refresh_token)
                    if response and response.user:
                        st.session_state.user = response.user.dict()
                        st.success("✅ Login realizado com set_session!")
                        st.query_params.clear()
                        return True
                except Exception as e:
                    st.write(f"❌ Erro no set_session: {e}")
            
            # Método 2: Tentar obter usuário diretamente com token
            st.write("🔄 **Tentativa 2:** Usando get_user com access token")
            try:
                user_response = supabase.auth.get_user(access_token)
                if user_response and user_response.user:
                    st.session_state.user = user_response.user.dict()
                    
                    # Também tenta salvar o token para futuras requisições
                    supabase.auth.set_session(access_token, query_params.get("refresh_token", ""))
                    
                    st.success("✅ Login realizado com get_user!")
                    st.query_params.clear()
                    return True
            except Exception as e:
                st.write(f"❌ Erro no get_user: {e}")
            
            # Método 3: Processamento manual dos dados
            if "token_type" in query_params:
                st.write("🔄 **Tentativa 3:** Processamento manual do token")
                token_type = query_params.get("token_type", "bearer")
                
                # Cria um header de autorização e faz uma requisição manual
                headers = {"Authorization": f"{token_type} {access_token}"}
                st.write(f"Headers criados: {headers}")
                
        except Exception as e:
            st.error(f"❌ Erro geral no processamento: {e}")
    
    return False
