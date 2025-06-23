import sys
import json
import os
import logging
import re
from difflib import get_close_matches
from datetime import datetime

# --- 1. CONFIGURAÇÃO E FUNÇÕES AUXILIARES ---
logging.basicConfig(level=logging.INFO, format='PLN_PY - %(levelname)s - %(message)s', stream=sys.stderr)

def exit_with_error(message):
    print(json.dumps({"erro": message}))
    sys.exit(0)

def carregar_recurso(caminho_arquivo, nome_recurso, tipo='json'):
    try:
        if not os.path.exists(caminho_arquivo):
            raise FileNotFoundError(f"Arquivo '{nome_recurso}' não encontrado em: {caminho_arquivo}")
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            if tipo == 'json':
                return json.load(f)
            elif tipo == 'mapa_simples':
                mapa = {}
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        parts = line.strip().split(';', 1)
                        if len(parts) == 2:
                            mapa[parts[0].strip().lower()] = parts[1].strip()
                return mapa
    except Exception as e:
        exit_with_error(f"Erro crítico ao carregar {nome_recurso}: {str(e)}")

# --- 2. CARREGAMENTO DE TODOS OS RECURSOS ---
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PERGUNTAS_INTERESSE = carregar_recurso(os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt"), "Perguntas de Interesse", 'mapa_simples')
    SINONIMOS_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "resultado_similaridade.txt"), "Sinônimos", 'mapa_simples')
    EMPRESA_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "empresa_nome_map.json"), "Mapa de Empresas", 'json')
    SETOR_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "setor_map.json"), "Mapa de Setores", 'json')
    logging.info("Recursos carregados com sucesso.")
except SystemExit:
    sys.exit(1)

# --- 3. LÓGICA PRINCIPAL DE PROCESSAMENTO ---

def selecionar_template(pergunta_usuario):
    textos_perguntas_modelo = [p.lower().replace('<valor>', 'valor').replace('<empresa>', 'empresa').replace('<ticker>', 'ticker').replace('<data>', 'data').replace('<setor>', 'setor') for p in PERGUNTAS_INTERESSE.keys()]
    matches = get_close_matches(pergunta_usuario.lower(), textos_perguntas_modelo, n=1, cutoff=0.6)
    if matches:
        for original, template_id in PERGUNTAS_INTERESSE.items():
            if original.lower().replace('<valor>', 'valor').replace('<empresa>', 'empresa').replace('<ticker>', 'ticker').replace('<data>', 'data').replace('<setor>', 'setor') == matches[0]:
                return template_id
    return None

def extrair_placeholders(pergunta_usuario):
    mapeamentos = {}
    texto_lower = pergunta_usuario.lower()

    # Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', texto_lower)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            mapeamentos["#DATA#"] = datetime.strptime(data_str, dt_format).strftime('%Y-%m-%d')
        except ValueError:
            logging.warning(f"Data encontrada ('{match_data.group(1)}') mas não pode ser parseada.")

    # Entidade (Empresa/Ticker)
    for chave, valor in sorted(EMPRESA_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave.lower() in texto_lower:
            mapeamentos["#ENTIDADE_NOME#"] = valor
            break

    # Setor
    for chave, valor in sorted(SETOR_MAP.items(), key=lambda item: len(item[0]), reverse=True):
         if chave.lower() in texto_lower:
            mapeamentos["#SETOR#"] = valor
            break
            
    # Valor Desejado
    for chave, valor in sorted(SINONIMOS_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave.lower() in texto_lower:
            mapeamentos["#VALOR_DESEJADO#"] = valor
            break
            
    return mapeamentos

def main(pergunta_usuario):
    template_id = selecionar_template(pergunta_usuario)
    if not template_id:
        exit_with_error("Não foi possível entender a intenção da sua pergunta.")

    placeholders = extrair_placeholders(pergunta_usuario)
    
    resposta = {"template_nome": template_id, "mapeamentos": placeholders}
    print(json.dumps(resposta, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(" ".join(sys.argv[1:]))
    else:
        exit_with_error("Nenhuma pergunta foi fornecida ao script.")