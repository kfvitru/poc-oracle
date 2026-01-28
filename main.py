import asyncio
import os
import json

os.environ["OPENAI_API_TYPE"] = "chat_completions"
os.environ["OPENAI_USE_RESPONSES"] = "false"

import httpx
from agents import (
    Agent,
    Runner,
    ModelSettings,
    set_default_openai_client,
    set_tracing_disabled,
    function_tool,
)
try:
    from agents import set_default_openai_api
    HAS_SET_API = True
except ImportError:
    HAS_SET_API = False
    set_default_openai_api = None
from dotenv import load_dotenv
from oci_openai import AsyncOciOpenAI, OciUserPrincipalAuth

load_dotenv()

# Configurações do OCI OpenAI
OCI_SERVICE_ENDPOINT = os.getenv("OCI_SERVICE_ENDPOINT")
OCI_CONFIG_FILE_ENV = os.getenv("OCI_CONFIG_FILE")

docker_config_path = "/root/.oci/config"
if os.path.exists(docker_config_path):
    OCI_CONFIG_FILE = docker_config_path
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read(OCI_CONFIG_FILE)
        if 'DEFAULT' in config and 'key_file' in config['DEFAULT']:
            key_file = config['DEFAULT']['key_file']
            if key_file.startswith('/home/') or key_file.startswith('/Users/'):
                key_filename = os.path.basename(key_file)
                new_key_path = f"/root/.oci/{key_filename}"
                if os.path.exists(new_key_path):
                    import tempfile
                    temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.config')
                    config['DEFAULT']['key_file'] = new_key_path
                    config.write(temp_config)
                    temp_config.close()
                    OCI_CONFIG_FILE = temp_config.name
                    print(f"Configuração OCI ajustada para Docker")
                else:
                    print(f"Arquivo de chave não encontrado em {new_key_path}")
    except Exception as e:
        print(f"Aviso: Não foi possível ajustar o arquivo de config OCI: {e}")
        import traceback
        traceback.print_exc()
elif OCI_CONFIG_FILE_ENV:
    OCI_CONFIG_FILE = OCI_CONFIG_FILE_ENV
    if not os.path.isabs(OCI_CONFIG_FILE):
        OCI_CONFIG_FILE = os.path.abspath(OCI_CONFIG_FILE)
    print(f"Ambiente local: usando {OCI_CONFIG_FILE}")
else:
    OCI_CONFIG_FILE = None
    print("OCI_CONFIG_FILE não configurado!")
COMPARTMENT_ID = os.getenv("OCI_COMPARTMENT_ID")
OCI_MODEL_ID = os.getenv("OCI_MODEL_ID")

# Configurações da API de Atendimento
API_ATENDIMENTO_BASE_URL = os.getenv(
    "API_ATENDIMENTO_BASE_URL",
    "https://api-menuatendimento.uniasselvi.com.br"
)
API_ATENDIMENTO_TOKEN = os.getenv("API_ATENDIMENTO_TOKEN")

set_default_openai_client(
    AsyncOciOpenAI(
        service_endpoint=OCI_SERVICE_ENDPOINT,
        auth=OciUserPrincipalAuth(config_file=OCI_CONFIG_FILE),
        compartment_id=COMPARTMENT_ID,
    )
)
if HAS_SET_API and set_default_openai_api:
    try:
        set_default_openai_api("chat_completions")
        print("API configurada para usar chat_completions")
    except Exception as e:
        print(f"Não foi possível configurar API: {e}")
set_tracing_disabled(True)


def _fazer_requisicao_api(endpoint: str, codigo_aluno: int) -> dict:
    """Função auxiliar para fazer requisições à API de atendimento.
    
    Args:
        endpoint: Nome do endpoint (ex: 'sofia_dados_aluno')
        codigo_aluno: Código do aluno (matrícula)
    
    Returns:
        dict: Resposta da API ou None em caso de erro
    """
    url = f"{API_ATENDIMENTO_BASE_URL}/v1/repositories/{endpoint}"
    token = API_ATENDIMENTO_TOKEN.strip()
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": token,
    }
    payload = {"codigo_aluno": codigo_aluno}
    
    print(f"Consulta API: POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"Resposta API ({response.status_code}): {json.dumps(data, indent=2)}")
        return data
    except httpx.HTTPStatusError as exc:
        error_msg = exc.response.text if exc.response.text else str(exc)
        print(f"Erro HTTP ({exc.response.status_code}): {error_msg}")
        if exc.response.status_code == 401:
            return {"erro": "Token de autenticação inválido ou ausente"}
        elif exc.response.status_code == 404:
            return {"erro": f"Aluno com código {codigo_aluno} não encontrado"}
        elif exc.response.status_code == 400:
            return {"erro": f"Erro na requisição: {error_msg}"}
        return {"erro": f"Erro HTTP {exc.response.status_code}: {error_msg}"}
    except httpx.RequestError as exc:
        error_msg = f"Erro de conexão com a API: {exc}"
        print(error_msg)
        return {"erro": error_msg}


@function_tool
def buscar_dados_aluno(codigo_aluno: int) -> str:
    """Consulta os dados completos do aluno incluindo informações acadêmicas, contatos, mensagens e avisos não lidos, e participação no Sofia.

    Parâmetros:
        codigo_aluno: Código do aluno (matrícula) - número inteiro
    """
    resultado = _fazer_requisicao_api("sofia_dados_aluno", codigo_aluno)
    
    if "erro" in resultado:
        return resultado["erro"]
    
    if "data" not in resultado or not resultado["data"]:
        return f"Nenhum dado encontrado para o aluno {codigo_aluno}."
    
    aluno = resultado["data"][0]
    resposta = f"Dados do aluno {codigo_aluno}:\n"
    resposta += f"- Nome: {aluno.get('nome_aluno', 'N/A')}\n"
    resposta += f"- CPF: {aluno.get('cpf', 'N/A')}\n"
    resposta += f"- Matrícula: {aluno.get('matricula', 'N/A')}\n"
    resposta += f"- Curso: {aluno.get('nome_curso', 'N/A')} ({aluno.get('tipo_curso', 'N/A')})\n"
    resposta += f"- Tipo de Ensino: {aluno.get('tipo_ensino', 'N/A')}\n"
    resposta += f"- Semestre de Ingresso: {aluno.get('semestre_ingresso', 'N/A')}\n"
    resposta += f"- Semestre Atual: {aluno.get('semestre_atual', 'N/A')}\n"
    resposta += f"- Início do Curso: {aluno.get('inicio_curso', 'N/A')}\n"
    resposta += f"- Carga Horária: {aluno.get('carga_horaria', 'N/A')} horas\n"
    resposta += f"- Forma de Ingresso: {aluno.get('forma_ingresso', 'N/A')}\n"
    resposta += f"- Primeiro Acesso: {aluno.get('primeiro_acesso', 'N/A')}\n"
    resposta += f"- Mensagens não lidas: {aluno.get('mensagens_nao_lidas', '0')}\n"
    resposta += f"- Avisos não lidos: {aluno.get('avisos_nao_lidos', '0')}\n"
    resposta += f"- Participa ativamente do Sofia: {aluno.get('participa_ativamente_sofia', 'N/A')}\n"
    resposta += f"- É aluno ingressante: {aluno.get('is_aluno_ingressante', 'N/A')}"
    
    return resposta


@function_tool
def buscar_proximo_evento_presencial(codigo_aluno: int) -> str:
    """Consulta o próximo evento presencial do aluno (data, dia da semana e hora).

    Parâmetros:
        codigo_aluno: Código do aluno (matrícula) - número inteiro
    """
    resultado = _fazer_requisicao_api("sofia_proximo_evento_presencial", codigo_aluno)
    
    if "erro" in resultado:
        return resultado["erro"]
    
    if "data" not in resultado or not resultado["data"]:
        return f"Nenhum evento presencial encontrado para o aluno {codigo_aluno}."
    
    evento = resultado["data"][0]
    resposta = f"Próximo evento presencial do aluno {codigo_aluno}:\n"
    resposta += f"- Data e Hora: {evento.get('proximo_evento_presencial', 'N/A')}\n"
    resposta += f"- Descrição: {evento.get('descricao', 'N/A')}"
    
    return resposta


@function_tool
def buscar_acessos_aluno(codigo_aluno: int) -> str:
    """Consulta os dados de acesso do aluno ao Ambiente Virtual de Aprendizagem (AVA), incluindo disciplinas, turmas, telas acessadas e estatísticas de acesso.

    Parâmetros:
        codigo_aluno: Código do aluno (matrícula) - número inteiro
    """
    resultado = _fazer_requisicao_api("sofia_acessos_aluno", codigo_aluno)
    
    if "erro" in resultado:
        return resultado["erro"]
    
    if "data" not in resultado or not resultado["data"]:
        return f"Nenhum acesso encontrado para o aluno {codigo_aluno}."
    
    acessos = resultado["data"]
    resposta = f"Acessos ao AVA do aluno {codigo_aluno}:\n\n"
    
    for acesso in acessos:
        resposta += f"Disciplina: {acesso.get('nome_disciplina', 'N/A')} ({acesso.get('disciplina', 'N/A')})\n"
        resposta += f"  - Turma: {acesso.get('turma', 'N/A')}\n"
        resposta += f"  - Tela: {acesso.get('tela', 'N/A')}\n"
        resposta += f"  - Total de acessos: {acesso.get('total_acessos', 0)}\n"
        resposta += f"  - Primeiro acesso: {acesso.get('primeiro_acesso', 'N/A')}\n"
        resposta += f"  - Último acesso: {acesso.get('ultimo_acesso', 'N/A')}\n\n"
    
    return resposta


@function_tool
def buscar_calendario_academico(codigo_aluno: int) -> str:
    """Consulta o calendário acadêmico do aluno com os próximos eventos presenciais (próximos 15 dias).

    Parâmetros:
        codigo_aluno: Código do aluno (matrícula) - número inteiro
    """
    resultado = _fazer_requisicao_api("sofia_calendario_academico", codigo_aluno)
    
    if "erro" in resultado:
        return resultado["erro"]
    
    if "data" not in resultado or not resultado["data"]:
        return f"Nenhum evento encontrado no calendário acadêmico para o aluno {codigo_aluno}."
    
    eventos = resultado["data"]
    resposta = f"Calendário acadêmico do aluno {codigo_aluno} (próximos eventos):\n\n"
    
    for i, evento in enumerate(eventos, 1):
        resposta += f"{i}. {evento.get('descricao', 'N/A')}\n"
        resposta += f"   Data/Hora: {evento.get('proximo_evento_presencial', 'N/A')}\n\n"
    
    return resposta


@function_tool
def buscar_dados_curso(codigo_aluno: int) -> str:
    """Consulta informações detalhadas sobre o curso do aluno, incluindo disciplinas, turmas, médias, situação da matrícula e materiais.

    Parâmetros:
        codigo_aluno: Código do aluno (matrícula) - número inteiro
    """
    resultado = _fazer_requisicao_api("sofia_dados_curso", codigo_aluno)
    
    if "erro" in resultado:
        return resultado["erro"]
    
    if "data" not in resultado or not resultado["data"]:
        return f"Nenhum dado de curso encontrado para o aluno {codigo_aluno}."
    
    dados = resultado["data"]
    resposta = f"Dados do curso do aluno {codigo_aluno}:\n\n"
    
    if dados:
        primeiro_item = dados[0]
        resposta += f"Curso: {primeiro_item.get('nome_curso', 'N/A')}\n"
        resposta += f"Tipo: {primeiro_item.get('tipo_curso', 'N/A')} - {primeiro_item.get('tipo_ensino', 'N/A')}\n"
        resposta += f"Semestre: {primeiro_item.get('semestre', 'N/A')}\n\n"
        resposta += "Disciplinas:\n\n"
        
        for disciplina in dados:
            resposta += f"- {disciplina.get('nome_disciplina', 'N/A')} ({disciplina.get('codigo_disciplina', 'N/A')})\n"
            resposta += f"  Turma: {disciplina.get('turma', 'N/A')}\n"
            resposta += f"  Média do semestre: {disciplina.get('media_semestre', 'N/A')}\n"
            resposta += f"  Situação: {disciplina.get('situacao_matricula', 'N/A')}\n"
            resposta += f"  Início: {disciplina.get('data_inicio_disciplina', 'N/A')}\n"
            if disciplina.get('livro'):
                resposta += f"  Livro: {disciplina.get('livro')}\n"
            resposta += "\n"
    
    return resposta


async def main():
    agent = Agent(
        name="Assistente de Atendimento Acadêmico",
        instructions=(
            "Você é um assistente que consulta dados acadêmicos de alunos através da API de atendimento. "
            "Sempre que o usuário mencionar um código de aluno (matrícula) ou pedir informações acadêmicas, "
            "extraia o código do aluno e use as ferramentas apropriadas:\n"
            "- buscar_dados_aluno: para dados gerais do aluno\n"
            "- buscar_proximo_evento_presencial: para o próximo evento presencial\n"
            "- buscar_acessos_aluno: para acessos ao AVA\n"
            "- buscar_calendario_academico: para o calendário acadêmico completo\n"
            "- buscar_dados_curso: para detalhes do curso e disciplinas\n\n"
            "Se a ferramenta retornar um erro, informe isso diretamente ao usuário. "
            "Seja claro e objetivo nas respostas, organizando as informações de forma legível."
        ),
        model=OCI_MODEL_ID,
        model_settings=ModelSettings(store=False),
        tools=[
            buscar_dados_aluno,
            buscar_proximo_evento_presencial,
            buscar_acessos_aluno,
            buscar_calendario_academico,
            buscar_dados_curso,
        ],
    )
    try:
        while True:
            pergunta = input("Pergunte sobre um aluno (ESC + Enter para sair): ").strip()
            if not pergunta:
                print("Entrada vazia. Tente novamente.")
                continue
            if pergunta == "\x1b" or pergunta.lower() in {"esc", "sair", "exit"}:
                print("Saindo...")
                break
            result = await Runner.run(agent, pergunta)
            print("Resultado: ", result.final_output)
    except (EOFError, KeyboardInterrupt):
        print("\nSaindo...")


if __name__ == "__main__":
    asyncio.run(main())
