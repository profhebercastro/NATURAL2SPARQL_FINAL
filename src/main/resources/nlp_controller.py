import sys, json, os, logging, re
from datetime import datetime

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='NLP_PY - %(levelname)s - %(message)s', stream=sys.stderr)

def exit_with_error(message):
    print(json.dumps({"erro": message}))
    sys.exit(0)

def carregar_thesaurus(caminho_arquivo):
    """ Carrega o arquivo Thesaurus.json unificado. """
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            data = json.load(f)
            sinonimos = {k.lower(): v for k, v in data.get('sinonimos', {}).items()}
            empresas = {k.lower(): v for k, v in data.get('empresas', {}).items()}
            setores = {k.lower(): v for k, v in data.get('setores', {}).items()}
            return sinonimos, empresas, setores
    except Exception as e:
        exit_with_error(f"Erro ao carregar Thesaurus.json de {caminho_arquivo}: {str(e)}")

# Carregamento dos recursos
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# <<<<< CORREÇÃO APLICADA AQUI
THESAURUS_PATH = os.path.join(SCRIPT_DIR, "Thesaurus.json")
SINONIMOS_MAP, EMPRESA_MAP, SETOR_MAP = carregar_thesaurus(THESAURUS_PATH)

# ... (o resto do script nlp_controller.py permanece o mesmo da resposta anterior)
# Ordena os mapas pela chave de maior comprimento para evitar correspondências parciais
SORTED_SINONIMOS_KEYS = sorted(SINONIMOS_MAP.keys(), key=len, reverse=True)
SORTED_EMPRESA_KEYS = sorted(EMPRESA_MAP.keys(), key=len, reverse=True)
SORTED_SETOR_KEYS = sorted(SETOR_MAP.keys(), key=len, reverse=True)

def processar_pergunta(pergunta_usuario):
    """ Analisa a pergunta, extrai conceitos e placeholders, e seleciona o template apropriado. """
    texto_lower = pergunta_usuario.lower()
    placeholders = {}
    conceitos_encontrados = set()

    # --- ETAPA 1: Extração de Entidades e Conceitos ---
    # 1.1 Extrai a Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', texto_lower)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            placeholders["#DATA#"] = datetime.strptime(data_str, dt_format).strftime('%Y-%m-%d')
            conceitos_encontrados.add('DATA')
        except ValueError:
            pass # Ignora datas inválidas

    # 1.2 Extrai Entidades (Empresa, Setor, Sinônimos) usando uma função auxiliar robusta
    def extrair_entidade(texto, chaves_ordenadas, mapa, nome_conceito, ph_map):
        for chave in chaves_ordenadas:
            if re.search(r'\b' + re.escape(chave) + r'\b', texto):
                if nome_conceito == 'VALOR_DESEJADO':
                    valor = mapa[chave]
                    if valor.startswith('conceito_'):
                        conceitos_encontrados.add(valor.upper())
                    else:
                        ph_map["#VALOR_DESEJADO#"] = valor
                        conceitos_encontrados.add('VALOR_DESEJADO')
                else:
                    ph_map[f"#{nome_conceito}#"] = mapa[chave]
                    conceitos_encontrados.add(nome_conceito)
                return True 
        return False

    extrair_entidade(texto_lower, SORTED_EMPRESA_KEYS, EMPRESA_MAP, 'ENTIDADE', placeholders)
    extrair_entidade(texto_lower, SORTED_SETOR_KEYS, SETOR_MAP, 'SETOR', placeholders)
    extrair_entidade(texto_lower, SORTED_SINONIMOS_KEYS, SINONIMOS_MAP, 'VALOR_DESEJADO', placeholders)
    
    if re.search(r'\b(ações|acao)\b', texto_lower):
        conceitos_encontrados.add('CONCEITO_ACAO')

    logging.info(f"Placeholders extraídos: {placeholders}")
    logging.info(f"Conceitos encontrados: {conceitos_encontrados}")

    # --- ETAPA 2: Lógica de Seleção de Template ---
    template_id = None
    if all(c in conceitos_encontrados for c in ['VALOR_DESEJADO', 'ENTIDADE', 'DATA']):
        template_id = "Template_1A"
    elif all(c in conceitos_encontrados for c in ['CONCEITO_TICKER', 'ENTIDADE']):
        template_id = "Template_2A"
    elif 'CONCEITO_ACAO' in conceitos_encontrados and 'SETOR' in conceitos_encontrados and 'DATA' not in conceitos_encontrados:
        template_id = "Template_3A"
    elif 'VALOR_DESEJADO' in conceitos_encontrados and 'SETOR' in conceitos_encontrados and 'DATA' in conceitos_encontrados:
        template_id = "Template_4A"
    
    if not template_id:
        exit_with_error("Não consegui entender a sua pergunta. Verifique se forneceu todos os detalhes (empresa/setor, data, o que deseja saber).")

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