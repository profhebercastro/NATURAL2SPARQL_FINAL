import sys, json, os, logging, re
from datetime import datetime

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='NLP_PY - %(levelname)s - %(message)s', stream=sys.stderr)

def exit_with_error(message):
    print(json.dumps({"erro": message}))
    sys.exit(0)

def carregar_mapas_conhecimento(caminho_arquivo):
    """ Carrega o arquivo JSON unificado com todos os mapas. """
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Normaliza todas as chaves para minúsculas
            sinonimos = {k.lower(): v for k, v in data.get('sinonimos', {}).items()}
            empresas = {k.lower(): v for k, v in data.get('empresas', {}).items()}
            setores = {k.lower(): v for k, v in data.get('setores', {}).items()}
            return sinonimos, empresas, setores
    except Exception as e:
        exit_with_error(f"Erro ao carregar mapas de conhecimento de {caminho_arquivo}: {str(e)}")

# Carregamento dos recursos
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_MAP_PATH = os.path.join(SCRIPT_DIR, "knowledge_maps.json")
SINONIMOS_MAP, EMPRESA_MAP, SETOR_MAP = carregar_mapas_conhecimento(KNOWLEDGE_MAP_PATH)

# Ordenar mapas por tamanho da chave (do maior para o menor)
SORTED_SINONIMOS_KEYS = sorted(SINONIMOS_MAP.keys(), key=len, reverse=True)
SORTED_EMPRESA_KEYS = sorted(EMPRESA_MAP.keys(), key=len, reverse=True)
SORTED_SETOR_KEYS = sorted(SETOR_MAP.keys(), key=len, reverse=True)


def processar_pergunta(pergunta_usuario):
    """ Analisa a pergunta, extrai conceitos e seleciona o template apropriado. """
    texto_lower = pergunta_usuario.lower()
    placeholders = {}
    conceitos_encontrados = set()

    # ETAPA 1: Extração de Entidades e Conceitos
    # 1.1 Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', texto_lower)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            placeholders["#DATA#"] = datetime.strptime(data_str, dt_format).strftime('%Y-%m-%d')
            conceitos_encontrados.add('DATA')
        except ValueError:
            pass

    # 1.2 Empresa/Ticker
    for chave in SORTED_EMPRESA_KEYS:
        if re.search(r'\b' + re.escape(chave) + r'\b', texto_lower):
            placeholders["#ENTIDADE_NOME#"] = EMPRESA_MAP[chave]
            conceitos_encontrados.add('ENTIDADE')
            break

    # 1.3 Setor
    for chave in SORTED_SETOR_KEYS:
        if re.search(r'\b' + re.escape(chave) + r'\b', texto_lower):
            placeholders["#SETOR#"] = SETOR_MAP[chave]
            conceitos_encontrados.add('SETOR')
            break

    # 1.4 Métricas e outros conceitos do mapa de sinônimos
    for chave in SORTED_SINONIMOS_KEYS:
        if re.search(r'\b' + re.escape(chave) + r'\b', texto_lower):
            valor_mapeado = SINONIMOS_MAP[chave]
            if valor_mapeado.startswith('conceito_'):
                conceitos_encontrados.add(valor_mapeado.upper())
            else:
                placeholders["#VALOR_DESEJADO#"] = valor_mapeado
                conceitos_encontrados.add('VALOR_DESEJADO')

    logging.info(f"Placeholders extraídos: {placeholders}")
    logging.info(f"Conceitos encontrados: {conceitos_encontrados}")

    # ETAPA 2: Lógica de Seleção de Template
    template_id = None
    if all(c in conceitos_encontrados for c in ['VALOR_DESEJADO', 'ENTIDADE', 'DATA']):
        template_id = "Template_1A"
    elif all(c in conceitos_encontrados for c in ['CONCEITO_TICKER', 'ENTIDADE']):
        template_id = "Template_2A"
    elif all(c in conceitos_encontrados for c in ['CONCEITO_ACAO', 'SETOR']) and 'DATA' not in conceitos_encontrados:
        template_id = "Template_3A"
    elif all(c in conceitos_encontrados for c in ['VALOR_DESEJADO', 'SETOR', 'DATA']):
        template_id = "Template_4A"
    
    if not template_id:
        exit_with_error("Não consegui entender a sua pergunta. Tente ser mais específico.")

    logging.info(f"Template selecionado: {template_id}")
    return {"template_nome": template_id, "mapeamentos": placeholders}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pergunta = " ".join(sys.argv[1:])
        resultado = processar_pergunta(pergunta)
        print(json.dumps(resultado, ensure_ascii=False))
        logging.info(f"Processamento NLP concluído. Enviando para o Java: {resultado}")
    else:
        exit_with_error("Nenhuma pergunta foi fornecida ao script Python.")