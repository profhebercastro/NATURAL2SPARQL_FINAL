# Arquivo: pln_processor.py
import sys, json, os, logging, re
from difflib import get_close_matches
from datetime import datetime

# Configuração de logging para depuração no Render
logging.basicConfig(level=logging.INFO, format='PLN_PY - %(levelname)s - %(message)s', stream=sys.stderr)

def exit_with_error(message):
    """ Encerra o script retornando um JSON de erro. """
    print(json.dumps({"erro": message}))
    # Usar sys.exit(0) para não ser interpretado como um erro de execução pelo Java,
    # permitindo que o Java trate o erro de negócio contido no JSON.
    sys.exit(0)

def carregar_recurso(caminho_arquivo, nome_recurso, tipo='json'):
    """ Carrega um arquivo de recurso (JSON, TXT, etc.) do disco. """
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            if tipo == 'json':
                # Garante que as chaves sejam strings minúsculas para correspondência sem case-sensitive.
                return {str(k).lower(): v for k, v in json.load(f).items()}
            elif tipo == 'mapa_simples':
                mapa = {}
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(';', 1)
                        if len(parts) == 2:
                            mapa[parts[0].strip().lower()] = parts[1].strip()
                return mapa
    except Exception as e:
        exit_with_error(f"Erro ao carregar {nome_recurso} de {caminho_arquivo}: {str(e)}")

# Carregamento dos recursos necessários
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PERGUNTAS_INTERESSE = carregar_recurso(os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt"), "Perguntas", 'mapa_simples')
SINONIMOS_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "sinonimos_map.txt"), "Sinônimos", 'mapa_simples')
EMPRESA_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "empresa_nome_map.json"), "Empresas", 'json')
SETOR_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "setor_map.json"), "Setores", 'json')

def selecionar_template(pergunta_usuario):
    """ Seleciona o template mais apropriado com base na similaridade da pergunta. """
    textos_perguntas_modelo = list(PERGUNTAS_INTERESSE.keys())
    # Usa um cutoff de 0.6 para ser um pouco mais estrito na correspondência.
    matches = get_close_matches(pergunta_usuario.lower(), textos_perguntas_modelo, n=1, cutoff=0.6)
    return PERGUNTAS_INTERESSE.get(matches[0]) if matches else None

def extrair_placeholders(pergunta_usuario):
    """ Extrai as entidades (placeholders) da pergunta do usuário. """
    mapeamentos = {}
    texto_lower = pergunta_usuario.lower()

    # 1. Extrair Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', texto_lower)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            # Tenta analisar com ano de 4 dígitos primeiro, depois com 2
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            mapeamentos["#DATA#"] = datetime.strptime(data_str, dt_format).strftime('%Y-%m-%d')
        except ValueError:
             # Se a data for inválida, o Java não receberá o placeholder e o template falhará (comportamento desejado).
             pass

    # 2. Extrair Entidade (Empresa/Ticker)
    # **IMPORTANTE**: Ordenar pelas chaves mais longas primeiro.
    # Isso garante que "CSN MINERACAO" seja encontrado antes de "CSN", resolvendo a ambiguidade.
    for chave in sorted(EMPRESA_MAP.keys(), key=len, reverse=True):
        # Usar \b (word boundary) para evitar correspondências parciais (ex: "light" em "enlightenment")
        if re.search(r'\b' + re.escape(chave.lower()) + r'\b', texto_lower):
            mapeamentos["#ENTIDADE_NOME#"] = EMPRESA_MAP[chave]
            break # Pára no primeiro e mais longo match

    # 3. Extrair Setor
    for chave in sorted(SETOR_MAP.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(chave.lower()) + r'\b', texto_lower):
            mapeamentos["#SETOR#"] = SETOR_MAP[chave]
            break

    # 4. Extrair Valor Desejado (Métrica)
    for chave in sorted(SINONIMOS_MAP.keys(), key=len, reverse=True):
        if chave.lower() in texto_lower:
            mapeamentos["#VALOR_DESEJADO#"] = SINONIMOS_MAP[chave]
            break
            
    return mapeamentos

def main(pergunta_usuario):
    logging.info(f"Processando a pergunta: '{pergunta_usuario}'")
    
    # Etapa 1: Classificar a intenção da pergunta para selecionar o template
    template_id = selecionar_template(pergunta_usuario)
    if not template_id:
        exit_with_error("Não foi possível entender a intenção da sua pergunta. Tente reformular usando um dos exemplos.")
    
    logging.info(f"Template selecionado: {template_id}")
    
    # Etapa 2: Extrair as entidades (placeholders)
    placeholders = extrair_placeholders(pergunta_usuario)
    logging.info(f"Placeholders extraídos: {placeholders}")

    # Etapa 3: Validação dos placeholders necessários para cada template
    if template_id == "Template_1A":
        if not placeholders.get("#ENTIDADE_NOME#"):
             exit_with_error("Não foi possível identificar a empresa ou ticker na sua pergunta.")
        if not placeholders.get("#DATA#"):
            exit_with_error("Não foi possível identificar a data na sua pergunta. Use o formato DD/MM/AAAA.")
        if not placeholders.get("#VALOR_DESEJADO#"):
            exit_with_error("Não foi possível identificar o que você deseja saber (ex: preço de fechamento, volume).")

    if template_id == "Template_2A" and not placeholders.get("#ENTIDADE_NOME#"):
        exit_with_error("Não foi possível identificar a empresa ou ticker na sua pergunta.")

    if template_id == "Template_3A" and not placeholders.get("#SETOR#"):
        exit_with_error("Para esta pergunta, por favor especifique um setor (ex: setor elétrico, bancário).")
        
    if template_id == "Template_4A":
        if not placeholders.get("#SETOR#"):
            exit_with_error("Para esta pergunta, por favor especifique um setor.")
        if not placeholders.get("#DATA#"):
            exit_with_error("Não foi possível identificar a data na sua pergunta. Use o formato DD/MM/AAAA.")

    # Etapa 4: Retornar o resultado em JSON para o Java
    resposta = { "template_nome": template_id, "mapeamentos": placeholders }
    print(json.dumps(resposta, ensure_ascii=False))
    logging.info(f"Processamento PLN concluído. Enviando para o Java: {resposta}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(" ".join(sys.argv[1:]))
    else:
        exit_with_error("Nenhuma pergunta foi fornecida ao script Python.")