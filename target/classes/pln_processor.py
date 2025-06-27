# Arquivo: pln_processor.py
import sys, json, os, logging, re
from difflib import get_close_matches
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='PLN_PY - %(levelname)s - %(message)s', stream=sys.stderr)

def exit_with_error(message):
    print(json.dumps({"erro": message}))
    sys.exit(0)

def carregar_recurso(caminho_arquivo, nome_recurso, tipo='json'):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            if tipo == 'json':
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PERGUNTAS_INTERESSE = carregar_recurso(os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt"), "Perguntas", 'mapa_simples')
SINONIMOS_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "sinonimos_map.txt"), "Sinônimos", 'mapa_simples')
EMPRESA_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "empresa_nome_map.json"), "Empresas", 'json')
SETOR_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "setor_map.json"), "Setores", 'json')

def selecionar_template(pergunta_usuario):
    textos_perguntas_modelo = list(PERGUNTAS_INTERESSE.keys())
    matches = get_close_matches(pergunta_usuario.lower(), textos_perguntas_modelo, n=1, cutoff=0.5)
    return PERGUNTAS_INTERESSE.get(matches[0]) if matches else None

def extrair_placeholders(pergunta_usuario):
    mapeamentos = {}
    texto_lower = pergunta_usuario.lower()

    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', texto_lower)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            mapeamentos["#DATA#"] = datetime.strptime(data_str, dt_format).strftime('%Y-%m-%d')
        except ValueError: pass

    for chave, valor_final in sorted(EMPRESA_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave.lower() in texto_lower:
            mapeamentos["#ENTIDADE_NOME#"] = valor_final
            break

    for chave, valor_final in sorted(SETOR_MAP.items(), key=lambda item: len(item[0]), reverse=True):
         if chave.lower() in texto_lower:
            mapeamentos["#SETOR#"] = valor_final
            break
            
    for chave, valor_final in sorted(SINONIMOS_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave.lower() in texto_lower:
            mapeamentos["#VALOR_DESEJADO#"] = valor_final
            break
            
    return mapeamentos

def main(pergunta_usuario):
    logging.info(f"Processando a pergunta: '{pergunta_usuario}'")
    template_id = selecionar_template(pergunta_usuario)
    if not template_id:
        exit_with_error("Não foi possível entender a intenção da sua pergunta.")
    
    logging.info(f"Template selecionado: {template_id}")
    placeholders = extrair_placeholders(pergunta_usuario)
    logging.info(f"Placeholders extraídos: {placeholders}")

    if template_id not in ["Template_3A"] and not placeholders.get("#ENTIDADE_NOME#") and not placeholders.get("#SETOR#"):
         exit_with_error("Não foi possível identificar a empresa, ticker ou setor na sua pergunta.")

    if template_id in ["Template_1A", "Template_1B", "Template_4A"] and not placeholders.get("#DATA#"):
        exit_with_error("Não foi possível identificar a data na sua pergunta. Por favor, use o formato DD/MM/AAAA.")
        
    if template_id == "Template_4A" and not placeholders.get("#SETOR#"):
        exit_with_error("Para esta pergunta, por favor especifique um setor.")

    resposta = { "template_nome": template_id, "mapeamentos": placeholders }
    print(json.dumps(resposta, ensure_ascii=False))
    logging.info(f"Processamento PLN concluído. Enviando para o Java: {resposta}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(" ".join(sys.argv[1:]))
    else:
        exit_with_error("Nenhuma pergunta foi fornecida ao script Python.")