eXatas ITBI - Plataforma de Análise Imobiliária
Visão Geral
eXatas ITBI é uma plataforma web de Business Intelligence focada no mercado imobiliário. A aplicação coleta, processa e armazena dados públicos de transações de ITBI (Imposto sobre a Transmissão de Bens Imóveis), oferecendo uma interface de busca e filtragem para análise de valores reais de mercado.

O sistema é composto por dois componentes principais:

Robô Coletor (coletor_itbi.py): Um script automatizado que busca dados de fontes públicas, os limpa, padroniza e os insere em um banco de dados central.

Aplicação Web (app_busca.py): Uma interface interativa construída com Streamlit que permite aos usuários consultar o banco de dados de forma rápida e intuitiva, com múltiplos filtros para refinar as buscas.

✨ Principais Funcionalidades
Coleta de Dados Automatizada: Robô que busca e processa planilhas de ITBI de múltiplos anos.

Banco de Dados Centralizado: Armazena mais de 1 milhão de registros de transações em um banco de dados PostgreSQL na nuvem.

Busca Inteligente: Permite buscas por nome de rua com normalização de abreviações (ex: "Avenida" -> "Av") e remoção de acentos para uma melhor experiência do usuário.

Filtros Avançados: Filtro por ano(s) da transação e um filtro dinâmico adicional sobre qualquer coluna dos resultados da busca.

Visualização Profissional: Apresentação de valores monetários no formato de moeda brasileira (R$).

Arquitetura Escalável: Construído com tecnologias de nuvem que suportam o crescimento do volume de dados e de usuários com baixo custo.

🛠️ Tecnologias Utilizadas
Backend & Coleta: Python, Pandas

Banco de Dados: PostgreSQL (via Supabase)

Interface Web (Frontend): Streamlit

Hospedagem & Deploy: GitHub, Streamlit Community Cloud

📂 Estrutura do Projeto
/seu-projeto-raiz
│
├── .env                  # Arquivo para chaves de API locais (NÃO ENVIAR PARA O GITHUB)
├── .gitignore            # Para ignorar arquivos como .env
├── app_busca.py          # O código da aplicação web Streamlit
├── coletor_itbi.py       # O código do robô coletor de dados
├── requirements.txt      # As dependências do projeto Python
├── README.md             # Esta documentação
│
└── /planilhas/           # Pasta opcional para planilhas que o coletor pode usar
🚀 Configuração e Instalação
Siga os passos abaixo para configurar e executar o projeto em um ambiente de desenvolvimento local.

1. Pré-requisitos
Python 3.9+

Uma conta no Supabase

Uma conta no GitHub

2. Configuração do Banco de Dados (Supabase)
Antes de rodar os scripts, o banco de dados precisa ser preparado.

Crie a Tabela: Execute o script SQL de criação da tabela no SQL Editor do seu projeto Supabase. Ele irá criar a tabela transacoes_imobiliarias com todas as colunas e índices de otimização.

Crie a Função de Busca por Ano: Execute o script SQL para a função RPC no SQL Editor. Isso criará a função get_distinct_anos, que otimiza o filtro de anos na aplicação.

3. Configuração do Ambiente Local
Clone o Repositório:

Bash

git clone https://github.com/seu-usuario/seu-repositorio.git
cd seu-repositorio
Crie um Ambiente Virtual (Recomendado):

Bash

python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
Instale as Dependências:

Bash

pip install -r requirements.txt
Configure as Variáveis de Ambiente:

Crie um arquivo chamado .env na raiz do projeto.

Preencha com suas credenciais do Supabase, que você encontra em "Project Settings > API":

SUPABASE_URL="https://SEU_PROJETO_URL.supabase.co"
SUPABASE_KEY="SUA_CHAVE_API_ANON_PUBLIC"
⚙️ Executando o Projeto
Coletor de Dados (coletor_itbi.py)
O coletor é executado via terminal e possui diferentes modos de operação.

Carga Histórica Completa (Execute uma única vez):

Bash

python coletor_itbi.py --carga-total
Atualização Mensal (Para agendamento):

Bash

python coletor_itbi.py --atualizar
Carga de um Ano Específico:

Bash

python coletor_itbi.py --ano 2024
Aplicação Web (app_busca.py)
Para iniciar a interface web localmente:

Bash

streamlit run app_busca.py
A aplicação será aberta no seu navegador.

☁️ Deployment (Publicação)
A aplicação está configurada para ser implantada continuamente através do Streamlit Community Cloud.

Conecte o GitHub: Conecte sua conta do Streamlit Cloud ao seu repositório do GitHub.

Crie a Aplicação: Crie uma "New app" no Streamlit, selecionando o repositório e o arquivo app_busca.py.

Configure os "Secrets": Nas configurações avançadas ("Advanced settings..."), adicione suas credenciais do Supabase na seção "Secrets". O conteúdo deve ser o mesmo do seu arquivo .env:

Ini, TOML

SUPABASE_URL="https'://SEU_PROJETO_URL.supabase.co"
SUPABASE_KEY="SUA_CHAVE_API_ANON_PUBLIC"
Deploy: Clique em "Deploy!". A cada novo push para o seu repositório, a aplicação será atualizada automaticamente.
