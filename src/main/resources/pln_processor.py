# -----------------------------------------------------------------
# ARQUIVO: pln_processor.py (VERSÃO FINAL E CORRIGIDA)
# -----------------------------------------------------------------
import sys
import json
import os
import re
from datetime import datetime
from unidecode import unidecode

# Função para normalizar texto: remove acentos e converte para minúsculas
def normalize_text(text):
    return unidecode(text).lower()

# Função para sair com uma mensagem de erro formatada em JSON
def exit_with_error(message):
    print(json.dumps({"erro": message}, ensure_ascii=False))
    sys.exit(0)

# Função para carregar recursos (mapas JSON e TXT)
def carregar_recurso(caminho_arquivo, tipo='json'):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            if tipo == 'json':
                # Normaliza as chaves do JSON para busca
                return {normalize_text(k): v for k, v in json.load(f).items()}
            elif tipo == 'mapa_simples':
                mapa = {}
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(';', 1)
                        if len(parts) == 2:
                            # Normaliza a chave (pergunta) para busca
                            mapa[normalize_text(parts[0].strip())] = parts[1].strip()
                return mapa
    except Exception as e:
        exit_with_error(f"Erro ao carregar recurso de {caminho_arquivo}: {e}")

# --- CARREGAMENTO DOS RECURSOS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PERGUNTAS_INTERESSE = carregar_recurso(os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt"), 'mapa_simples')
SINONIMOS_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "sinonimos_map.txt"), 'mapa_simples')
EMPRESA_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "empresa_nome_map.json"), 'json')
SETOR_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "setor_map.json"), 'json')

# Seleciona o template usando Spacy para similaridade (mais robusto)
import spacy
nlp = spacy.load("pt_core_news_lg")

def selecionar_template(pergunta_usuario):
    pergunta_proc = nlp(pergunta_usuario.lower())
    melhor_score = -1.0
    template_selecionado = None

    for pergunta_modelo, template_id in PERGUNTAS_INTERESSE.items():
        modelo_proc = nlp(pergunta_modelo)
        similaridade = pergunta_proc.similarity(modelo_proc)
        if similaridade > melhor_score:
            melhor_score = similaridade
            template_selecionado = template_id
            
    # Define um limiar mínimo de similaridade para considerar uma correspondência válida
    return template_selecionado if melhor_score > 0.75 else None

def extrair_placeholders(pergunta_usuario):
    mapeamentos = {}
    texto_norm = normalize_text(pergunta_usuario)

    # Extração de Data
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', texto_norm)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            mapeamentos["#DATA#"] = datetime.strptime(data_str, dt_format).strftime('%Y-%m-%d')
        except ValueError:
            pass

    # Extração de Empresa/Ticker (ordena por tamanho da chave para pegar a mais específica primeiro)
    for chave_norm, valor_final in sorted(EMPRESA_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave_norm in texto_norm:
            mapeamentos["#ENTIDADE_NOME#"] = valor_final
            break
            
    # Extração de Setor
    for chave_norm, valor_final in sorted(SETOR_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave_norm in texto_norm:
            mapeamentos["#SETOR#"] = valor_final
            break
            
    # Extração de Valor/Métrica Desejada
    for chave_norm, valor_final in sorted(SINONIMOS_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave_norm in texto_norm:
            mapeamentos["#VALOR_DESEJADO#"] = valor_final
            break

    return mapeamentos

def main(pergunta_usuario):
    template_id = selecionar_template(pergunta_usuario)
    if not template_id:
        exit_with_error("Não foi possível entender a intenção da sua pergunta. Tente ser mais específico.")
    
    placeholders = extrair_placeholders(pergunta_usuario)

    # Validação de placeholders essenciais
    if template_id in ["Template_1A", "Template_1B", "Template_2A"] and not placeholders.get("#ENTIDADE_NOME#"):
        exit_with_error("Não foi possível identificar a empresa ou o ticker na sua pergunta.")
    if template_id in ["Template_1A", "Template_1B", "Template_4A"] and not placeholders.get("#DATA#"):
        exit_with_error("Não foi possível identificar a data. Por favor, use o formato DD/MM/AAAA.")
    if template_id in ["Template_3A", "Template_4A"] and not placeholders.get("#SETOR#"):
        exit_with_error("Para esta pergunta, por favor, especifique um setor.")

    resposta = {"template_nome": template_id, "mapeamentos": placeholders}
    print(json.dumps(resposta, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(" ".join(sys.argv[1:]))
    else:
        exit_with_error("Nenhuma pergunta foi fornecida ao script Python.")