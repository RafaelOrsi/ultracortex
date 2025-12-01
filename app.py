import os
import datetime
import hashlib
from typing import Tuple, Optional, Union, Dict, Any, List
from pymongo.errors import ServerSelectionTimeoutError

import streamlit as st
from pymongo import MongoClient
import smtplib
from email.message import EmailMessage

# ============================================================
# Configuração geral da página
# ============================================================

st.set_page_config(
    page_title="AI & Data Consulting",
    page_icon="💻",
    layout="wide"
)

# ============================================================
# Estilos customizados (CSS) estilo Dracula
# ============================================================

custom_css = """
<style>
/* Fundo inspirado no tema Dracula */
.main {
    background: #282a36;
    color: #f8f8f2;
}

/* Títulos */
h1, h2, h3, h4, h5 {
    color: #f8f8f2;
}

/* Caixa de destaque (hero) */
.hero-box {
    padding: 2.5rem 2rem;
    border-radius: 1.5rem;
    background: linear-gradient(135deg, rgba(189,147,249,0.25), rgba(80,250,123,0.12));
    border: 1px solid #6272a4;
    box-shadow: 0 24px 60px rgba(0,0,0,0.6);
}

/* Cards de serviços e cursos */
.service-card, .course-card {
    padding: 1.3rem 1.4rem;
    border-radius: 1.2rem;
    background: #44475a;
    border: 1px solid #6272a4;
    box-shadow: 0 18px 40px rgba(0,0,0,0.7);
    margin-bottom: 1.2rem;
}

/* Subtítulos */
.subtitle {
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #bd93f9;
}

/* Destaque de texto pequeno */
.badge {
    display: inline-block;
    padding: 0.15rem 0.65rem;
    border-radius: 999px;
    border: 1px solid #ff79c6;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: #ff79c6;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #1e1f29;
    color: #f8f8f2;
}

/* Botões padrão */
.stButton>button {
    background-color: #bd93f9;
    color: #282a36;
    border-radius: 999px;
    border: none;
}

.stButton>button:hover {
    background-color: #ff79c6;
    color: #282a36;
}

/* Entradas de texto e selects */
.stTextInput input,
.stTextArea textarea {
    background-color: #1e1f29;
    color: #f8f8f2;
    border: 1px solid #6272a4;
}

.stSelectbox div[data-baseweb="select"] {
    background-color: #1e1f29;
    color: #f8f8f2;
}

/* Mensagens de info/sucesso/erro ajustadas ao tema */
div.stAlert {
    border-radius: 0.8rem;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ============================================================
# Configurações de admins e e-mail
# ============================================================

ADMIN_EMAILS: List[str] = [
    e.strip().lower()
    for e in st.secrets.get("ADMIN_EMAILS", os.getenv("ADMIN_EMAILS", "")).split(",")
    if e.strip()
]

DEFAULT_FROM_EMAIL = st.secrets.get("FROM_EMAIL", os.getenv("FROM_EMAIL", ""))


def is_admin(email: str) -> bool:
    if not email:
        return False
    return email.lower() in ADMIN_EMAILS


# ============================================================
# Conexão com MongoDB
# ============================================================

def get_db():
    """
    Retorna uma instância do banco de dados MongoDB.
    Faz um ping ao servidor para validar a conexão.
    """
    uri = st.secrets.get("MONGODB_URI", os.getenv("MONGODB_URI", ""))
    db_name = st.secrets.get("MONGODB_DB", os.getenv("MONGODB_DB", "aieduc_site"))

    if not uri:
        st.error("Configuração do MongoDB ausente. Defina MONGODB_URI e MONGODB_DB em st.secrets ou nas variáveis de ambiente.")
        st.stop()

    # Timeout menor para falhar mais rápido em caso de problema
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    try:
        # Teste simples de conectividade
        client.admin.command("ping")
    except ServerSelectionTimeoutError as e:
        st.error(
            "Não foi possível conectar ao MongoDB.\n\n"
            "Verifique se:\n"
            "1) A connection string (MONGODB_URI) está correta.\n"
            "2) O cluster no Atlas está ativo.\n"
            "3) O IP do Streamlit Cloud está autorizado em Network Access "
            "(por exemplo, 0.0.0.0/0 para testes).\n"
        )
        # Opcional: mostrar um pedaço da mensagem original em ambiente de debug
        # st.text(str(e))
        st.stop()

    return client[db_name]


db = get_db()

# ============================================================
# Funções de e-mail
# ============================================================

def send_email(to: Union[str, List[str]], subject: str, body: str) -> None:
    """
    Envia e-mail via SMTP com parâmetros definidos em st.secrets ou variáveis de ambiente.
    Se não estiver configurado, a função não quebra a aplicação.
    """
    smtp_host = st.secrets.get("SMTP_HOST", os.getenv("SMTP_HOST", ""))
    if not smtp_host:
        # Integração de e-mail ainda não configurada.
        return

    smtp_port = int(st.secrets.get("SMTP_PORT", os.getenv("SMTP_PORT", "587")))
    smtp_user = st.secrets.get("SMTP_USER", os.getenv("SMTP_USER", ""))
    smtp_password = st.secrets.get("SMTP_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
    use_tls = str(st.secrets.get("SMTP_USE_TLS", os.getenv("SMTP_USE_TLS", "true"))).lower() == "true"
    from_email = DEFAULT_FROM_EMAIL or smtp_user or "no-reply@example.com"

    if isinstance(to, list):
        recipients = [t for t in to if t]
    else:
        recipients = [to] if to else []

    if not recipients:
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except Exception:
        # Em produção, você pode registrar o erro em log.
        pass


# ============================================================
# Funções de autenticação
# ============================================================

def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    Hash simples com SHA256 e salt.
    Para produção, considere usar bibliotecas específicas de segurança.
    """
    if salt is None:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split("$")
    except ValueError:
        return False
    check = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return check == hashed


def register_user(name: str, email: str, password: str) -> Tuple[bool, str]:
    users_col = db["users"]
    if users_col.find_one({"email": email.lower().strip()}):
        return False, "E-mail já cadastrado."
    pwd_hash = hash_password(password)
    normalized_email = email.lower().strip()
    users_col.insert_one(
        {
            "name": name,
            "email": normalized_email,
            "password_hash": pwd_hash,
            "created_at": datetime.datetime.utcnow(),
            "active": True
        }
    )

    # E-mail para o usuário
    try:
        body_user = (
            f"Olá, {name}.\n\n"
            "Seu cadastro na plataforma AI & Data Consulting foi concluído com sucesso.\n"
            "Em breve você receberá novidades sobre cursos, trilhas e conteúdos exclusivos.\n\n"
            "Atenciosamente,\n"
            "Equipe AI & Data Consulting"
        )
        send_email(
            to=normalized_email,
            subject="Bem-vindo(a) à plataforma AI & Data Consulting",
            body=body_user
        )
    except Exception:
        pass

    # E-mail de notificação para admins
    if ADMIN_EMAILS:
        try:
            body_admin = (
                "Novo cadastro de usuário no site AI & Data Consulting.\n\n"
                f"Nome: {name}\n"
                f"E-mail: {normalized_email}\n"
                f"Data: {datetime.datetime.utcnow().isoformat()} (UTC)\n"
            )
            send_email(
                to=ADMIN_EMAILS,
                subject="Novo cadastro de usuário no site",
                body=body_admin
            )
        except Exception:
            pass

    return True, "Cadastro realizado com sucesso. Você já pode fazer login."


def login_user(email: str, password: str) -> Tuple[bool, Union[str, Dict[str, Any]]]:
    users_col = db["users"]
    user = users_col.find_one({"email": email.lower().strip(), "active": True})
    if not user:
        return False, "Usuário não encontrado ou inativo."
    if not verify_password(password, user.get("password_hash", "")):
        return False, "Senha incorreta."
    return True, user


if "user" not in st.session_state:
    st.session_state["user"] = None

# ============================================================
# Cursos no MongoDB (com fallback local)
# ============================================================

def get_courses():
    """
    Tenta carregar cursos da collection 'courses'.
    Se não houver dados, utiliza uma lista local de cursos exemplos.
    """
    courses_col = db["courses"]
    try:
        cursos_db = list(courses_col.find({"ativo": True}).sort("ordem", 1))
    except Exception:
        cursos_db = []

    if cursos_db:
        return [
            {
                "nome": c.get("nome"),
                "categoria": c.get("categoria", ""),
                "nivel": c.get("nivel", ""),
                "descricao": c.get("descricao", ""),
                "carga_horaria": c.get("carga_horaria", ""),
                "tag": c.get("tag", "")
            }
            for c in cursos_db
        ]

    # Fallback estático para versão inicial
    return [
        {
            "nome": "Formação em Python para Programação",
            "categoria": "Programação",
            "nivel": "Iniciante a Intermediário",
            "descricao": "Curso focado em resolução de problemas reais, boas práticas e uso de bibliotecas modernas.",
            "carga_horaria": "24h",
            "tag": "Python"
        },
        {
            "nome": "Ciência de Dados Aplicada a Negócios",
            "categoria": "Ciência de Dados",
            "nivel": "Intermediário",
            "descricao": "Da coleta à visualização, com foco em métricas de negócio, storytelling e impacto em decisões.",
            "carga_horaria": "32h",
            "tag": "Data Science"
        },
        {
            "nome": "Inteligência Artificial e Machine Learning",
            "categoria": "IA e ML",
            "nivel": "Intermediário a Avançado",
            "descricao": "Modelos preditivos, pipelines, explicabilidade e implantação em ambientes produtivos.",
            "carga_horaria": "36h",
            "tag": "Machine Learning"
        },
        {
            "nome": "Visualização de Dados e Storytelling",
            "categoria": "Visualização",
            "nivel": "Intermediário",
            "descricao": "Dashboards, gráficos eficientes e estratégias de comunicação orientadas a executivos.",
            "carga_horaria": "20h",
            "tag": "Data Viz"
        },
        {
            "nome": "Estrutura de Dados e Algoritmos",
            "categoria": "Fundamentos",
            "nivel": "Intermediário",
            "descricao": "Base sólida de estruturas de dados e algoritmos para desenvolvimento de soluções escaláveis.",
            "carga_horaria": "24h",
            "tag": "Algoritmos"
        },
        {
            "nome": "Banco de Dados Relacionais e NoSQL",
            "categoria": "Banco de Dados",
            "nivel": "Intermediário",
            "descricao": "Modelagem, SQL, MongoDB e conceitos de bancos híbridos para aplicações modernas.",
            "carga_horaria": "28h",
            "tag": "Databases"
        },
    ]

# ============================================================
# Componentes de interface
# ============================================================

def sidebar_auth():
    st.sidebar.markdown("### Área do aluno")

    if st.session_state["user"] is None:
        aba = st.sidebar.radio("Acesso", ["Entrar", "Cadastrar"])

        if aba == "Entrar":
            with st.sidebar.form("login_form"):
                email = st.text_input("E-mail")
                password = st.text_input("Senha", type="password")
                submitted = st.form_submit_button("Entrar")
                if submitted:
                    ok, result = login_user(email, password)
                    if ok:
                        st.session_state["user"] = {
                            "name": result["name"],
                            "email": result["email"],
                            "_id": str(result["_id"])
                        }
                        st.sidebar.success(f"Bem-vindo, {result['name']}!")
                    else:
                        st.sidebar.error(result)

        if aba == "Cadastrar":
            with st.sidebar.form("register_form"):
                name = st.text_input("Nome completo")
                email = st.text_input("E-mail corporativo ou pessoal")
                password = st.text_input("Senha", type="password")
                password2 = st.text_input("Confirmar senha", type="password")
                submitted = st.form_submit_button("Criar conta")

                if submitted:
                    if password != password2:
                        st.sidebar.error("As senhas não coincidem.")
                    elif not name or not email or not password:
                        st.sidebar.error("Preencha todos os campos.")
                    else:
                        ok, msg = register_user(name, email, password)
                        if ok:
                            st.sidebar.success(msg)
                        else:
                            st.sidebar.error(msg)
    else:
        user = st.session_state["user"]
        st.sidebar.success(f"Conectado como {user['name']}")
        if st.sidebar.button("Sair"):
            st.session_state["user"] = None
            st.experimental_rerun()


def hero_section():
    st.markdown(
        """
        <div class="hero-box">
            <div class="badge">Consultoria em Inteligência Artificial e Educação em Tecnologia</div>
            <h1 style="margin-top: 0.8rem; margin-bottom: 0.3rem;">
                Inteligência Artificial aplicada à decisão de negócio e formação de times em tecnologia
            </h1>
            <p style="font-size:1.0rem; color:#f8f8f2; max-width: 820px; line-height: 1.6;">
                Consultorias, projetos e cursos de alta performance em Python, Ciência de Dados, 
                Machine Learning, Visão Computacional e Bancos de Dados. Do protótipo à implantação, 
                com foco em resultado mensurável e formação de equipes.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1.2, 1, 1])

    with col1:
        st.markdown("#### O que entregamos na prática")
        st.markdown(
            """
            - Estruturação de projetos de IA e Machine Learning
            - Modelos de Visão Computacional e Reconhecimento de Padrões
            - Projetos completos de coleta, curadoria e governança de dados
            - Criação de conjuntos de dados para P&D e inovação
            - Trilha de cursos para formação de times em tecnologia
            """
        )
    with col2:
        st.markdown("#### Para quem")
        st.markdown(
            """
            - Empresas que desejam aplicar IA de forma estratégica  
            - Instituições de ensino e pesquisa  
            - Indústrias e serviços com foco em produtividade  
            - Times que precisam acelerar a curva de aprendizado em tecnologia
            """
        )
    with col3:
        st.markdown("#### Carro-chefe")
        st.info(
            "Trilhas completas de **Cursos de Tecnologia**: Python, Ciência de Dados, "
            "Inteligência Artificial, Visualização de Dados, Estrutura de Dados, "
            "Banco de Dados e outros."
        )


def page_home():
    hero_section()
    st.markdown("")
    st.markdown("### Destaques em consultoria e serviços profissionais")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("##### Consultoria em IA e Machine Learning")
        st.markdown(
            """
            Projetos de ponta a ponta em:
            - Modelagem preditiva e prescritiva  
            - Otimização de processos produtivos  
            - Sistemas de apoio à decisão baseados em dados  
            """
        )

    with col2:
        st.markdown("##### Visão Computacional e Reconhecimento de Padrões")
        st.markdown(
            """
            Soluções em:
            - Inspeção automatizada de qualidade  
            - Detecção de anomalias em imagens  
            - Reconhecimento de padrões e classificação  
            """
        )

    with col3:
        st.markdown("##### Dados, P&D e Cursos")
        st.markdown(
            """
            - Coleta e curadoria de dados em campo  
            - Criação de datasets para pesquisa e inovação  
            - Trilha estruturada de cursos de tecnologia para equipes  
            """
        )


def page_services():
    st.markdown("### Serviços de consultoria e projetos profissionais")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="service-card">', unsafe_allow_html=True)
        st.markdown("#### Consultorias em Inteligência Artificial e Machine Learning")
        st.markdown(
            """
            - Diagnóstico de maturidade analítica  
            - Desenho de roadmap de IA para o negócio  
            - Modelos de Machine Learning orientados a indicadores de resultado  
            - Governança, explicabilidade e vieses em modelos de IA  
            """
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="service-card">', unsafe_allow_html=True)
        st.markdown("#### Projetos de Visão Computacional e Reconhecimento de Padrões")
        st.markdown(
            """
            - Classificação e segmentação de imagens  
            - Inspeção visual para manufatura e serviços  
            - Modelos de reconhecimento de padrões em sinais e imagens  
            """
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="service-card">', unsafe_allow_html=True)
        st.markdown("#### Conjuntos de Dados e Serviços de Coleta")
        st.markdown(
            """
            - Planejamento de coleta e protocolos de pesquisa  
            - Coleta de dados em campo e ambientes laboratoriais  
            - Padronização, anonimização e documentação de datasets  
            """
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="service-card">', unsafe_allow_html=True)
        st.markdown("#### Palestras, Workshops e Programas In Company")
        st.markdown(
            """
            - Palestras sobre IA, Ciência de Dados e Transformação Digital  
            - Workshops práticos para equipes técnicas e de negócio  
            - Programas de formação continuada em tecnologia  
            """
        )
        st.markdown("</div>", unsafe_allow_html=True)


def page_courses():
    st.markdown("### Cursos de Tecnologia - carro chefe da empresa")
    st.markdown(
        '<p class="subtitle">Formações em Python, Ciência de Dados, IA, Visualização, Estruturas de Dados e Bancos de Dados</p>',
        unsafe_allow_html=True
    )

    cursos = get_courses()

    tags = sorted(list({c["tag"] for c in cursos if c.get("tag")}))
    filtro_tag = st.multiselect("Filtrar por trilha ou foco", options=tags, default=[])

    col_a, col_b, col_c = st.columns(3)
    cols = [col_a, col_b, col_c]
    idx_col = 0

    for curso in cursos:
        if filtro_tag and curso.get("tag") not in filtro_tag:
            continue

        with cols[idx_col]:
            st.markdown('<div class="course-card">', unsafe_allow_html=True)
            st.markdown(f"#### {curso['nome']}")
            st.markdown(
                f"**Categoria:** {curso['categoria']}  \n"
                f"**Nível:** {curso['nivel']}  \n"
                f"**Carga horária:** {curso['carga_horaria']}"
            )
            st.markdown("")
            st.markdown(curso["descricao"])
            st.markdown("")
            st.markdown(
                f'<span class="badge">{curso["tag"]}</span>',
                unsafe_allow_html=True
            )
            st.markdown("</div>", unsafe_allow_html=True)

        idx_col = (idx_col + 1) % 3

    st.markdown("---")
    if st.session_state["user"] is None:
        st.info("Faça login ou cadastro na barra lateral para receber novidades sobre novos cursos e turmas.")
    else:
        st.success("Você está logado. Em versões futuras, esta área exibirá sua trilha personalizada de cursos e seu progresso.")


def page_contact():
    st.markdown("### Fale conosco para projetos, consultorias e programas de cursos")

    col1, col2 = st.columns([1.2, 1])

    with col1:
        with st.form("contact_form"):
            nome = st.text_input("Nome")
            email = st.text_input("E-mail")
            empresa = st.text_input("Empresa / Instituição")
            tipo_interesse = st.selectbox(
                "Tipo de interesse",
                [
                    "Consultoria em IA / ML",
                    "Projetos com Visão Computacional",
                    "Conjuntos de dados e coleta",
                    "Cursos e trilhas de formação",
                    "Palestras e workshops",
                    "Outro"
                ]
            )
            mensagem = st.text_area("Conte um pouco sobre a sua demanda")
            submitted = st.form_submit_button("Enviar mensagem")

            if submitted:
                leads_col = db["leads"]
                leads_col.insert_one(
                    {
                        "nome": nome,
                        "email": email,
                        "empresa": empresa,
                        "tipo_interesse": tipo_interesse,
                        "mensagem": mensagem,
                        "created_at": datetime.datetime.utcnow()
                    }
                )

                # E-mail para o lead
                try:
                    body_lead = (
                        f"Olá, {nome}.\n\n"
                        "Recebemos sua mensagem na AI & Data Consulting.\n"
                        "Nossa equipe analisará sua demanda e retornará em breve.\n\n"
                        "Resumo do contato:\n"
                        f"Tipo de interesse: {tipo_interesse}\n"
                        f"Empresa/Instituição: {empresa}\n\n"
                        "Atenciosamente,\n"
                        "Equipe AI & Data Consulting"
                    )
                    send_email(
                        to=email,
                        subject="Recebemos sua mensagem na AI & Data Consulting",
                        body=body_lead
                    )
                except Exception:
                    pass

                # E-mail para admins
                if ADMIN_EMAILS:
                    try:
                        body_admin = (
                            "Novo lead recebido pelo formulário de contato.\n\n"
                            f"Nome: {nome}\n"
                            f"E-mail: {email}\n"
                            f"Empresa: {empresa}\n"
                            f"Tipo de interesse: {tipo_interesse}\n"
                            f"Mensagem: {mensagem}\n"
                            f"Data: {datetime.datetime.utcnow().isoformat()} (UTC)\n"
                        )
                        send_email(
                            to=ADMIN_EMAILS,
                            subject="Novo lead no site AI & Data Consulting",
                            body=body_admin
                        )
                    except Exception:
                        pass

                st.success("Mensagem enviada com sucesso. Em breve entraremos em contato.")

    with col2:
        st.markdown("#### Como funcionam os projetos")
        st.markdown(
            """
            - Etapa 1: diagnóstico da demanda e definição de objetivos  
            - Etapa 2: desenho da solução técnica e plano de execução  
            - Etapa 3: desenvolvimento, validação e implantação  
            - Etapa 4: treinamento da equipe e transferência de conhecimento  
            """
        )
        st.markdown("#### Canais e formatos")
        st.markdown(
            """
            - Atuação remota e presencial, conforme a necessidade  
            - Atendimento a empresas, instituições de ensino e centros de pesquisa  
            - Projetos sob medida para a realidade do cliente  
            """
        )


def page_dashboard_user():
    st.markdown("### Área do aluno (versão inicial)")

    if st.session_state["user"] is None:
        st.info("Faça login pela barra lateral para acessar a área do aluno.")
        return

    user = st.session_state["user"]
    st.success(f"Bem-vindo, {user['name']}!")

    st.markdown(
        """
        Nesta versão inicial, a área do aluno exibe apenas informações básicas.
        Em versões futuras, você poderá:
        - Acompanhar sua trilha de cursos e progresso  
        - Acessar materiais, certificados e gravações  
        - Atualizar seus dados de perfil e preferências  
        """
    )


# ============================================================
# Painel administrativo de cursos
# ============================================================

def page_admin():
    st.markdown("### Painel administrativo de cursos")

    if st.session_state["user"] is None:
        st.warning("Acesso restrito. Faça login com um usuário administrador.")
        return

    email_user = st.session_state["user"].get("email", "")
    if not is_admin(email_user):
        st.warning("Acesso restrito a usuários administradores.")
        return

    courses_col = db["courses"]

    aba_cadastro, aba_gerenciar = st.tabs(["Cadastrar curso", "Gerenciar cursos"])

    # Aba de cadastro
    with aba_cadastro:
        st.markdown("#### Novo curso")

        with st.form("new_course_form"):
            nome = st.text_input("Nome do curso")
            categoria = st.text_input("Categoria (ex.: Programação, Ciência de Dados)")
            nivel = st.text_input("Nível (ex.: Iniciante, Intermediário, Avançado)")
            carga_horaria = st.text_input("Carga horária (ex.: 24h, 32h)")
            tag = st.text_input("Tag principal (ex.: Python, Data Science)")
            descricao = st.text_area("Descrição do curso")
            ordem = st.number_input("Ordem de exibição", min_value=0, max_value=999, value=0, step=1)
            ativo = st.checkbox("Curso ativo", value=True)

            submitted = st.form_submit_button("Salvar curso")

            if submitted:
                if not nome:
                    st.error("Informe pelo menos o nome do curso.")
                else:
                    doc = {
                        "nome": nome,
                        "categoria": categoria,
                        "nivel": nivel,
                        "carga_horaria": carga_horaria,
                        "tag": tag,
                        "descricao": descricao,
                        "ordem": int(ordem),
                        "ativo": bool(ativo),
                        "created_at": datetime.datetime.utcnow()
                    }
                    courses_col.insert_one(doc)
                    st.success("Curso cadastrado com sucesso.")
                    st.experimental_rerun()

    # Aba de gerenciamento
    with aba_gerenciar:
        st.markdown("#### Cursos cadastrados")

        cursos_db = list(courses_col.find().sort("ordem", 1))
        if not cursos_db:
            st.info("Nenhum curso cadastrado ainda.")
            return

        # Tabela resumida
        data_view = [
            {
                "Nome": c.get("nome", ""),
                "Categoria": c.get("categoria", ""),
                "Nível": c.get("nivel", ""),
                "Carga horária": c.get("carga_horaria", ""),
                "Tag": c.get("tag", ""),
                "Ordem": c.get("ordem", 0),
                "Ativo": c.get("ativo", False),
            }
            for c in cursos_db
        ]
        st.dataframe(data_view, use_container_width=True)

        # Ações em um curso específico
        st.markdown("#### Editar status ou remover curso")

        labels = [
            f"{c.get('nome','')} ({c.get('tag','')})"
            for c in cursos_db
        ]
        mapa_label_id = {label: c["_id"] for label, c in zip(labels, cursos_db)}

        escolha = st.selectbox("Selecione um curso", options=labels)
        curso_id = mapa_label_id.get(escolha)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("Ativar curso"):
                courses_col.update_one({"_id": curso_id}, {"$set": {"ativo": True}})
                st.success("Curso ativado.")
                st.experimental_rerun()
        with col_b:
            if st.button("Desativar curso"):
                courses_col.update_one({"_id": curso_id}, {"$set": {"ativo": False}})
                st.success("Curso desativado.")
                st.experimental_rerun()
        with col_c:
            if st.button("Excluir curso"):
                courses_col.delete_one({"_id": curso_id})
                st.success("Curso excluído.")
                st.experimental_rerun()


# ============================================================
# Layout principal
# ============================================================

def main():
    sidebar_auth()

    st.sidebar.markdown("---")

    pages = ["Início", "Serviços", "Cursos", "Contato", "Área do aluno"]

    # Exibe opção Admin somente para usuários administradores
    if st.session_state["user"] is not None and is_admin(st.session_state["user"].get("email", "")):
        pages.append("Admin")

    page = st.sidebar.radio("Navegação", pages)

    if page == "Início":
        page_home()
    elif page == "Serviços":
        page_services()
    elif page == "Cursos":
        page_courses()
    elif page == "Contato":
        page_contact()
    elif page == "Área do aluno":
        page_dashboard_user()
    elif page == "Admin":
        page_admin()


if __name__ == "__main__":
    main()
