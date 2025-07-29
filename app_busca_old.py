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

# --- 4. SISTEMA DE AUTENTICAÇÃO ---

def check_user_session():
    """Verifica e processa a sessão do usuário."""
    query_params = dict(st.query_params)
    
    # Processar callback do Google OAuth
    if "access_token" in query_params:
        access_token = query_params["access_token"]
        refresh_token = query_params.get("refresh_token", "")
        
        try:
            # Definir a sessão no Supabase
            if refresh_token:
                session_response = supabase.auth.set_session(access_token, refresh_token)
            else:
                session_response = supabase.auth.get_user(access_token)
            
            if session_response and session_response.user:
                st.session_state.user = session_response.user.dict()
                st.session_state.authenticated = True
                st.query_params.clear()
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
                return True
                
        except Exception as e:
            st.error(f"❌ Erro ao processar login: {e}")
    
    # Verificar sessão existente
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            if 'user' not in st.session_state:
                st.session_state.user = session.user.dict()
                st.session_state.authenticated = True
            return True
        else:
            st.session_state.user = None
            st.session_state.authenticated = False
            return False
    except Exception as e:
        st.session_state.user = None
        st.session_state.authenticated = False
        return False

def login_com_email_senha(email, password):
    """Faz login com email e senha."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            st.session_state.user = response.user.dict()
            st.session_state.authenticated = True
            st.success("✅ Login realizado com sucesso!")
            st.rerun()
            return True
        else:
            st.error("❌ Credenciais inválidas")
            return False
            
    except Exception as e:
        st.error(f"❌ Erro no login: {e}")
        return False

def cadastrar_usuario(email, password, nome):
    """Cadastra um novo usuário."""
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "nome": nome
                }
            }
        })
        
        if response.user:
            st.success("✅ Cadastro realizado! Verifique seu email para confirmar a conta.")
            return True
        else:
            st.error("❌ Erro no cadastro")
            return False
            
    except Exception as e:
        st.error(f"❌ Erro no cadastro: {e}")
        return False

def logout_usuario():
    """Faz logout do usuário."""
    try:
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.authenticated = False
        st.success("✅ Logout realizado com sucesso!")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Erro no logout: {e}")

def tela_autenticacao():
    """Exibe a tela de autenticação."""
    st.title("🔐 Acesso ao Sistema")
    st.markdown("Faça login ou cadastre-se para acessar a ferramenta de análise imobiliária.")
    
    # Verificar callback do Google
    query_params = dict(st.query_params)
    if query_params:
        st.info("🔄 Processando login do Google...")
        if check_user_session():
            return
    
    # Tabs para Login e Cadastro
    tab_login, tab_cadastro = st.tabs(["🔑 Login", "📝 Cadastro"])
    
    with tab_login:
        st.subheader("Entrar na sua conta")
        
        # CORREÇÃO: Usar st.secrets corretamente
        try:
            # Primeiro, tentar obter do secrets do Streamlit
            supabase_url = st.secrets["SUPABASE_URL"]
            site_url = st.secrets.get("SITE_URL", "https://pmivvwtqllcspjwnxzuc.supabase.co")
        except (KeyError, FileNotFoundError):
            # Fallback para variáveis de ambiente se secrets não estiver disponível
            supabase_url = os.getenv("SUPABASE_URL")
            site_url = os.getenv("SITE_URL", "https://pmivvwtqllcspjwnxzuc.supabase.co")
        
        # Verificar se conseguimos obter a URL
        if not supabase_url:
            st.error("❌ Erro: URL do Supabase não configurada nos secrets.")
            st.info("Configure SUPABASE_URL nos secrets do Streamlit.")
            return
        
        # Botão Google OAuth
        google_auth_url = f"{supabase_url}/auth/v1/authorize?provider=google&redirect_to={site_url}"
        
        # Debug: Mostrar URLs configuradas (remover em produção)
        with st.expander("🔍 Configurações (Debug)"):
            st.write(f"**Supabase URL:** {supabase_url}")
            st.write(f"**Site URL:** {site_url}")
            st.write(f"**Google Auth URL:** {google_auth_url}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.link_button("🔐 Entrar com Google", url=google_auth_url, use_container_width=True)
        with col2:
            if st.button("🔄 Verificar Sessão", use_container_width=True):
                check_user_session()
        
        st.divider()
        
        # Login com email/senha
        with st.form("form_login"):
            st.markdown("**Ou entre com email e senha:**")
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Senha", type="password")
            
            if st.form_submit_button("🔑 Entrar", use_container_width=True):
                if email and password:
                    login_com_email_senha(email, password)
                else:
                    st.warning("⚠️ Preencha todos os campos")
    
    with tab_cadastro:
        st.subheader("Criar nova conta")
        
        with st.form("form_cadastro"):
            nome = st.text_input("👤 Nome Completo")
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Senha", type="password")
            password_confirm = st.text_input("🔒 Confirmar Senha", type="password")
            
            if st.form_submit_button("📝 Criar Conta", use_container_width=True):
                if not all([nome, email, password, password_confirm]):
                    st.warning("⚠️ Preencha todos os campos")
                elif password != password_confirm:
                    st.error("❌ As senhas não coincidem")
                elif len(password) < 6:
                    st.error("❌ A senha deve ter pelo menos 6 caracteres")
                else:
                    cadastrar_usuario(email, password, nome)
    
    # Debug (apenas em desenvolvimento)
    with st.expander("🔍 Debug (Desenvolvimento)"):
        st.write("**Query Params:**", query_params)
        st.write("**Session State:**", {
            "authenticated": st.session_state.get("authenticated", False),
            "user": bool(st.session_state.get("user"))
        })
        
        # Debug: Verificar se secrets estão carregados
        st.write("**Secrets disponíveis:**", list(st.secrets.keys()) if hasattr(st, 'secrets') else "Nenhum")

def sidebar_usuario():
    """Exibe informações do usuário na sidebar."""
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        user = st.session_state.user
        
        st.sidebar.success(f"✅ Logado como: **{user.get('email', 'Usuário')}**")
        
        # Informações do usuário
        if user.get('user_metadata', {}).get('nome'):
            st.sidebar.write(f"👤 **Nome:** {user['user_metadata']['nome']}")
        
        if user.get('user_metadata', {}).get('full_name'):
            st.sidebar.write(f"👤 **Nome:** {user['user_metadata']['full_name']}")
        
        # Botão de logout
        if st.sidebar.button("🚪 Sair", use_container_width=True):
            logout_usuario()
    else:
        st.sidebar.info("🔒 Você não está logado")

# --- 5. CONTROLE PRINCIPAL DA APLICAÇÃO ---

# Verificar sessão no início
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Verificar se está logado
is_logged_in = check_user_session()

# Mostrar sidebar do usuário
sidebar_usuario()

# Controlar exibição de conteúdo
if not is_logged_in:
    # Esconder conteúdo principal e mostrar tela de login
    st.markdown("""
    <style>
    .main > div:first-child {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)
    
    tela_autenticacao()
else:
    # Usuário logado - conteúdo já exibido acima
    st.sidebar.success("🎉 Acesso liberado!")
