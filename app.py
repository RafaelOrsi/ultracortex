import os
import datetime
import hashlib
from typing import Tuple, Optional, Union, Dict, Any, List

import streamlit as st
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import smtplib
from email.message import EmailMessage

# ============================================================
# Configuração geral da página
# ============================================================

st.set_page_config(
    page_title="ULTRACORTEX",
    #page_icon="",
    layout="wide"
)

# ============================================================
# Estilos customizados - tema escuro, topo fixo, logo central
# ============================================================

custom_css = """
<style>

/* Escurecer toda a aplicação */
html, body {
    background-color: #020617;
}

.stApp {
    background: radial-gradient(circle at top, #020617 0, #020617 40%, #020617 100%);
    color: #e5e7eb;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* Container principal */
.block-container {
    padding-top: 5.0rem;
}

/* Títulos */
h1, h2, h3, h4, h5 {
    color: #e5e7eb;
}

/* Barra de navegação superior fixa */
.nav-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 999;
    padding: 0.6rem 1.0rem;
    background: rgba(15,23,42,0.98);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(148,163,184,0.4);
}

/* Container para centralizar a navegação */
.nav-inner {
    max-width: 1100px;
    margin: 0 auto;
}

/* Rádio da navegação (ocultar label padrão) */
.nav-inner label {
    display: none;
}

/* Ajustar grupo de botões da navegação */
.nav-inner div[role="radiogroup"] {
    display: flex;
    justify-content: center;
    gap: 1.6rem;
}

/* Logo central no topo da página */
.center-logo {
    text-align: center;
    margin: 1.2rem 0 1.8rem 0;
}

/* Limitar largura do logo */
.center-logo img {
    max-width: 260px;
}

/* Cards de serviços e cursos */
.service-card, .course-card {
    padding: 1.3rem 1.4rem;
    border-radius: 1.2rem;
    background: #020617;
    border: 1px solid rgba(148,163,184,0.55);
    box-shadow: 0 18px 40px rgba(0,0,0,0.8);
    margin-bottom: 1.2rem;
}

/* Imagem de curso no card */
.course-image {
    border-radius: 1rem;
    margin-bottom: 0.8rem;
}

/* Subtítulos */
.subtitle {
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: #9ca3af;
}

/* Badge padrão */
.badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    border: 1px solid #38bdf8;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: #38bdf8;
}

/* Badge de curso destaque */
.badge-destaque {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    background: rgba(251,191,36,0.14);
    color: #facc15;
    border: 1px solid rgba(250,204,21,0.7);
}

/* Preço do curso */
.course-price {
    font-size: 1.2rem;
    font-weight: 700;
    color: #4ade80;
}

/* Próxima turma */
.course-next {
    font-size: 0.9rem;
    color: #e5e7eb;
}

/* Sidebar (login / cadastro) */
section[data-testid="stSidebar"] {
    background-color: #020617;
    color: #e5e7eb;
}

/* Botões padrão */
.stButton>button {
    background-color: #2563eb;
    color: #ffffff;
    border-radius: 999px;
    border: none;
    font-weight: 600;
}

.stButton>button:hover {
    background-color: #1d4ed8;
    color: #ffffff;
}

/* Inputs de texto e área de texto no corpo */
.stTextInput input,
.stTextArea textarea {
    background-color: #020617;
    color: #e5e7eb;
    border: 1px solid #4b5563;
}

/* Inputs na sidebar podem herdar o mesmo estilo */
section[data-testid="stSidebar"] .stTextInput input,
section[data-testid="stSidebar"] .stTextArea textarea {
    background-color: #020617;
    color: #e5e7eb;
    border: 1px solid #4b5563;
}

/* Mensagens */
div.stAlert {
    border-radius: 0.8rem;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ============================================================
# Configurações de admins e e mail
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

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

def get_db():
    uri = st.secrets.get("MONGODB_URI", os.getenv("MONGODB_URI", ""))
    db_name = st.secrets.get("MONGODB_DB", os.getenv("MONGODB_DB", "aieduc_site"))

    if not uri:
        st.error("Configuração do MongoDB ausente. Defina MONGODB_URI e MONGODB_DB em st.secrets ou nas variáveis de ambiente.")
        st.stop()

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    try:
        client.admin.command("ping")
    except ServerSelectionTimeoutError:
        st.error(
            "Não foi possível conectar ao MongoDB.\n\n"
            "Verifique se a string de conexão está correta, se o cluster está ativo "
            "e se o IP do Streamlit está autorizado no MongoDB Atlas."
        )
        st.stop()

    return client[db_name]


db = get_db()

# ============================================================
# Funções de e mail
# ============================================================

def send_email(to: Union[str, List[str]], subject: str, body: str) -> None:
    smtp_host = st.secrets.get("SMTP_HOST", os.getenv("SMTP_HOST", ""))
    if not smtp_host:
        return

    smtp_port = int(st.secrets.get("SMTP_PORT", os.getenv("SMTP_PORT", "587")))
    smtp_user = st.secrets.get("SMTP_USER", os.getenv("SMTP_USER", ""))
    smtp_password = st.secrets.get("SMTP_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
    use_tls = str(st.secrets.get("SMTP_USE_TLS", os.getenv("SMTP_USE_TLS", "true"))).lower() == "true"
    from_email = DEFAULT_FROM_EMAIL or smtp_user or "no-reply@example.com"

    if isinstance(to, List):
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
        pass

# ============================================================
# Funções de autenticação
# ============================================================

def hash_password(password: str, salt: Optional[str] = None) -> str:
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
        return False, "E mail já cadastrado."
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
            subject="Bem vindo(a) à plataforma AI & Data Consulting",
            body=body_user
        )
    except Exception:
        pass

    if ADMIN_EMAILS:
        try:
            body_admin = (
                "Novo cadastro de usuário no site AI & Data Consulting.\n\n"
                f"Nome: {name}\n"
                f"E mail: {normalized_email}\n"
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

if "auth_tab" not in st.session_state:
    st.session_state["auth_tab"] = "Entrar"

# ============================================================
# Utilitário para imagens
# ============================================================

def resolve_image_path(path_or_url: str) -> Optional[str]:
    if not path_or_url:
        return None
    path_or_url = path_or_url.strip()
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    if os.path.exists(path_or_url):
        return path_or_url
    candidate = os.path.join("images", path_or_url)
    if os.path.exists(candidate):
        return candidate
    return None

# ============================================================
# Cursos no MongoDB - vitrine
# ============================================================

def get_courses():
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
                "tag": c.get("tag", ""),
                "imagem_url": c.get("imagem_url", ""),
                "preco": c.get("preco", ""),
                "destaque": c.get("destaque", False),
                "proxima_turma": c.get("proxima_turma", "")
            }
            for c in cursos_db
        ]

    return [
        {
            "nome": "Formação em Python para Programação",
            "categoria": "Programação",
            "nivel": "Iniciante a Intermediário",
            "descricao": "Curso focado em problemas reais e boas práticas modernas em Python.",
            "carga_horaria": "24h",
            "tag": "Python",
            "imagem_url": "",
            "preco": "997,00",
            "destaque": True,
            "proxima_turma": "Próxima turma: Setembro 2025"
        },
        {
            "nome": "Ciência de Dados Aplicada a Negócios",
            "categoria": "Ciência de Dados",
            "nivel": "Intermediário",
            "descricao": "Da coleta à visualização com foco em métricas de negócio e tomada de decisão.",
            "carga_horaria": "32h",
            "tag": "Data Science",
            "imagem_url": "",
            "preco": "1.297,00",
            "destaque": True,
            "proxima_turma": "Próxima turma: Outubro 2025"
        },
        {
            "nome": "Inteligência Artificial e Machine Learning",
            "categoria": "IA e ML",
            "nivel": "Intermediário a Avançado",
            "descricao": "Modelos preditivos, pipelines e implantação em ambiente produtivo.",
            "carga_horaria": "36h",
            "tag": "Machine Learning",
            "imagem_url": "",
            "preco": "1.497,00",
            "destaque": True,
            "proxima_turma": "Próxima turma: Novembro 2025"
        },
    ]

# ============================================================
# Autenticação na Sidebar, com redirecionamento
# ============================================================

def sidebar_auth():
    st.sidebar.markdown("### Área do aluno")

    aba = st.sidebar.radio(
        "Acesso",
        ["Entrar", "Cadastrar"],
        key="auth_tab"
    )

    st.sidebar.markdown(
        "_No futuro, poderá haver um botão de Entrar com Google integrado ao OAuth._"
    )

    if st.session_state["user"] is None:

        if aba == "Entrar":
            with st.sidebar.form("login_form"):
                email = st.text_input("E mail")
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
                        st.sidebar.success("Login realizado com sucesso. Redirecionando...")
                        st.sidebar.markdown(
                            "<script>setTimeout(function(){window.location.reload();},1500);</script>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.sidebar.error(result)

        if aba == "Cadastrar":
            with st.sidebar.form("register_form"):
                name = st.text_input("Nome completo")
                email = st.text_input("E mail corporativo ou pessoal")
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
                            st.sidebar.success(msg + " Redirecionando para o login...")
                            st.session_state["auth_tab"] = "Entrar"
                            st.sidebar.markdown(
                                "<script>setTimeout(function(){window.location.reload();},1500);</script>",
                                unsafe_allow_html=True
                            )
                        else:
                            st.sidebar.error(msg)
    else:
        user = st.session_state["user"]
        st.sidebar.success(f"Conectado como {user['name']}")
        if st.sidebar.button("Sair"):
            st.session_state["user"] = None
            st.experimental_rerun()

# ============================================================
# Navegação superior fixa e logo central
# ============================================================

def top_navigation() -> str:
    st.markdown('<div class="nav-bar"><div class="nav-inner">', unsafe_allow_html=True)

    pages = ["Início", "Serviços", "Cursos", "Contato", "Área do aluno"]
    if st.session_state["user"] is not None and is_admin(st.session_state["user"].get("email", "")):
        pages.append("Admin")

    page = st.radio(
        "",
        pages,
        horizontal=True,
        label_visibility="collapsed",
        key="nav_page"
    )

    st.markdown('</div></div>', unsafe_allow_html=True)
    return page


def show_center_logo():
    hero_image_config = st.secrets.get("HERO_IMAGE", os.getenv("HERO_IMAGE", "images/hero_empresa.png"))
    img_path = resolve_image_path(hero_image_config)
    cols = st.columns([1, 2, 1])
    with cols[1]:
        st.markdown('<div class="center-logo">', unsafe_allow_html=True)
        if img_path:
            st.image(img_path, use_container_width=False)
        else:
            st.markdown(
                "_Adicione a imagem hero_empresa.png na pasta images/ ou defina a variável HERO_IMAGE em Secrets._"
            )
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# Páginas
# ============================================================

def page_home():
    show_center_logo()
    st.markdown("### Inteligência Artificial e Ciência de Dados aplicados ao seu negócio")
    st.markdown(
        """
        Estruturamos projetos de IA, Ciência de Dados e Visão Computacional, e oferecemos trilhas completas de cursos em tecnologia
        para formar e fortalecer o seu time técnico e de gestão.
        """
    )

def page_services():
    show_center_logo()
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

    with col2:
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

    st.markdown("")
    col3, col4 = st.columns(2)
    with col3:
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
    with col4:
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
    show_center_logo()
    st.markdown("### Vitrine de cursos e turmas")
    st.markdown(
        '<p class="subtitle">Cursos práticos em Python, Ciência de Dados, IA, Visualização e Bancos de Dados</p>',
        unsafe_allow_html=True
    )

    cursos = get_courses()
    tags = sorted(list({c["tag"] for c in cursos if c.get("tag")}))
    filtro_tag = st.multiselect("Filtrar por trilha ou foco", options=tags, default=[])

    col_a, col_b, col_c = st.columns(3)
    cols = [col_a, col_b, col_c]
    idx_col = 0

    inscricoes_col = db["inscricoes"]

    for idx, curso in enumerate(cursos):
        if filtro_tag and curso.get("tag") not in filtro_tag:
            continue

        with cols[idx_col]:
            st.markdown('<div class="course-card">', unsafe_allow_html=True)

            img_path = resolve_image_path(curso.get("imagem_url", ""))
            if img_path:
                st.image(img_path, use_column_width=True)

            topo = ""
            if curso.get("destaque"):
                topo = '<span class="badge-destaque">Curso carro chefe</span>'
            elif curso.get("tag"):
                topo = f'<span class="badge">{curso["tag"]}</span>'

            if topo:
                st.markdown(topo, unsafe_allow_html=True)

            st.markdown(f"#### {curso['nome']}")
            st.markdown(
                f"**Categoria:** {curso['categoria']}  \n"
                f"**Nível:** {curso['nivel']}  \n"
                f"**Carga horária:** {curso['carga_horaria']}"
            )

            preco = curso.get("preco", "")
            if preco:
                st.markdown(f'<div class="course-price">R$ {preco}</div>', unsafe_allow_html=True)

            proxima = curso.get("proxima_turma", "")
            if proxima:
                st.markdown(f'<div class="course-next">{proxima}</div>', unsafe_allow_html=True)

            st.markdown("")
            st.markdown(curso["descricao"])

            st.markdown("")
            btn_key = f"inscricao_{idx}"
            if st.button("Inscrever me", key=btn_key):
                if st.session_state["user"] is None:
                    st.warning("Faça login na barra lateral para concluir a pré inscrição neste curso.")
                else:
                    user = st.session_state["user"]
                    inscricoes_col.insert_one(
                        {
                            "user_id": user["_id"],
                            "user_name": user["name"],
                            "user_email": user["email"],
                            "curso_nome": curso["nome"],
                            "curso_tag": curso.get("tag", ""),
                            "curso_preco": preco,
                            "curso_proxima_turma": proxima,
                            "created_at": datetime.datetime.utcnow()
                        }
                    )
                    st.success("Pré inscrição registrada. Entraremos em contato com você para próximos passos.")

            st.markdown("</div>", unsafe_allow_html=True)

        idx_col = (idx_col + 1) % 3

    st.markdown("---")
    if st.session_state["user"] is None:
        st.info("Faça login ou cadastro na barra lateral para gerenciar suas pré inscrições.")
    else:
        st.success("Você está logado. Em versões futuras, esta área exibirá suas inscrições e acesso às aulas.")


def page_contact():
    show_center_logo()
    st.markdown("### Fale conosco para projetos, consultorias e programas de cursos")

    col1, col2 = st.columns([1.2, 1])

    with col1:
        with st.form("contact_form"):
            nome = st.text_input("Nome")
            email = st.text_input("E mail")
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
    show_center_logo()
    st.markdown("### Área do aluno - versão inicial")

    if st.session_state["user"] is None:
        st.info("Faça login pela barra lateral para acessar a área do aluno.")
        return

    user = st.session_state["user"]
    st.success(f"Bem vindo, {user['name']}!")
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
# Painel administrativo
# ============================================================

def page_admin():
    show_center_logo()
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

    with aba_cadastro:
        st.markdown("#### Novo curso")

        with st.form("new_course_form"):
            nome = st.text_input("Nome do curso")
            categoria = st.text_input("Categoria")
            nivel = st.text_input("Nível")
            carga_horaria = st.text_input("Carga horária")
            tag = st.text_input("Tag principal")
            imagem_url = st.text_input("URL ou caminho da imagem do curso (opcional)")
            preco = st.text_input("Preço (ex.: 997,00)")
            proxima_turma = st.text_input("Próxima turma (ex.: Setembro 2025)")
            destaque = st.checkbox("Curso carro chefe (destaque)", value=False)
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
                        "imagem_url": imagem_url,
                        "preco": preco,
                        "proxima_turma": proxima_turma,
                        "destaque": bool(destaque),
                        "descricao": descricao,
                        "ordem": int(ordem),
                        "ativo": bool(ativo),
                        "created_at": datetime.datetime.utcnow()
                    }
                    courses_col.insert_one(doc)
                    st.success("Curso cadastrado com sucesso.")
                    st.experimental_rerun()

    with aba_gerenciar:
        st.markdown("#### Cursos cadastrados")

        cursos_db = list(courses_col.find().sort("ordem", 1))
        if not cursos_db:
            st.info("Nenhum curso cadastrado ainda.")
            return

        data_view = [
            {
                "Nome": c.get("nome", ""),
                "Categoria": c.get("categoria", ""),
                "Nível": c.get("nivel", ""),
                "Carga horária": c.get("carga_horaria", ""),
                "Tag": c.get("tag", ""),
                "Preço": c.get("preco", ""),
                "Próx turma": c.get("proxima_turma", ""),
                "Destaque": c.get("destaque", False),
                "Ordem": c.get("ordem", 0),
                "Ativo": c.get("ativo", False),
            }
            for c in cursos_db
        ]
        st.dataframe(data_view, use_container_width=True)

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
    page = top_navigation()

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
