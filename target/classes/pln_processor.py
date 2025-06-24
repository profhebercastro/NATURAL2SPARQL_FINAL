# Arquivo: pln_processor.py
# Versão Final: Robusta, com carregamento dinâmico de recursos e saída JSON padronizada.

import sys
import json
import os
import logging
import re
from difflib import get_close_matches
from datetime import datetime

# --- 1. CONFIGURAÇÃO E FUNÇÕES AUXILIARES ---

# Configura o logging para ir para o stderr, para que não polua a saída JSON (stdout).
# O Java pode capturar isso para depuração.
logging.basicConfig(level=logging.INFO, format='PLN_PY - %(levelname)s - %(message)s', stream=sys.stderr)

def exit_with_error(message):
    """Encerra o script e imprime um erro formatado em JSON para o stdout."""
    # Imprime para stdout para que o Java sempre tenha uma resposta JSON para parsear.
    print(json.dumps({"erro": message}))
    # Sai com código 0, pois o erro é lógico, não do sistema.
    sys.exit(0)

def carregar_recurso(caminho_arquivo, nome_recurso, tipo='json'):
    """Função genérica para carregar arquivos de recurso de forma segura."""
    try:
        if not os.path.exists(caminho_arquivo):
            # Erro fatal se um recurso essencial não for encontrado.
            raise FileNotFoundError(f"Arquivo de recurso '{nome_recurso}' não encontrado em: {caminho_arquivo}")
        
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            if tipo == 'json':
                # Garante que as chaves do JSON sejam minúsculas para correspondência insensível.
                return {str(k).lower(): v for k, v in json.load(f).items()}
            elif tipo == 'mapa_simples':
                mapa = {}
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(';', 1)
                        if len(parts) == 2:
                            # Chave minúscula para correspondência, valor preservado.
                            mapa[parts[0].strip().lower()] = parts[1].strip()
                return mapa
    except Exception as e:
        exit_with_error(f"Erro crítico ao carregar o recurso '{nome_recurso}': {str(e)}")


# --- 2. CARREGAMENTO DE TODOS OS RECURSOS ---

try:
    # O script espera que os arquivos de recurso estejam no mesmo diretório que ele.
    # O Java garante que isso aconteça ao copiar tudo para um diretório temporário.
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    
    PERGUNTAS_INTERESSE = carregar_recurso(os.path.join(SCRIPT_DIR, "perguntas_de_interesse.txt"), "Perguntas de Interesse", 'mapa_simples')
    SINONIMOS_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "sinonimos_map.txt"), "Mapa de Sinônimos", 'mapa_simples')
    EMPRESA_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "empresa_nome_map.json"), "Mapa de Empresas", 'json')
    SETOR_MAP = carregar_recurso(os.path.join(SCRIPT_DIR, "setor_map.json"), "Mapa de Setores", 'json')
    
    logging.info("Recursos de PLN carregados com sucesso.")
except SystemExit:
    # Propaga o erro fatal de carregamento, mas o exit_with_error já imprimiu o JSON.
    sys.exit(1)

# --- 3. LÓGICA PRINCIPAL DE PROCESSAMENTO ---

def selecionar_template(pergunta_usuario):
    """Encontra o template mais provável usando a similaridade de string com perguntas modelo."""
    textos_perguntas_modelo = list(PERGUNTAS_INTERESSE.keys())
    # O cutoff=0.6 é um bom ponto de partida, pode ser ajustado se necessário.
    matches = get_close_matches(pergunta_usuario.lower(), textos_perguntas_modelo, n=1, cutoff=0.5)
    
    if matches:
        # O valor no mapa de perguntas é o ID do template.
        return PERGUNTAS_INTERESSE.get(matches[0])
    return None

def extrair_placeholders(pergunta_usuario):
    """Extrai todas as entidades da pergunta e as mapeia para os placeholders do Java."""
    mapeamentos = {}
    texto_lower = pergunta_usuario.lower()

    # 1. Extrai Data e formata para o padrão YYYY-MM-DD, que o SPARQL espera.
    match_data = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', texto_lower)
    if match_data:
        try:
            data_str = match_data.group(1).replace('-', '/')
            dt_format = '%d/%m/%Y' if len(data_str.split('/')[-1]) == 4 else '%d/%m/%y'
            mapeamentos["#DATA#"] = datetime.strptime(data_str, dt_format).strftime('%Y-%m-%d')
        except ValueError:
            logging.warning(f"Data encontrada ('{match_data.group(1)}') mas não pôde ser parseada. Ignorando.")

    # 2. Extrai Entidade (Empresa/Ticker)
    # Itera pelas chaves do mapa da mais longa para a mais curta para evitar matches parciais.
    for chave, valor_final in sorted(EMPRESA_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave.lower() in texto_lower:
            mapeamentos["#ENTIDADE_NOME#"] = valor_final
            break # Pega a primeira (e mais longa) correspondência.

    # 3. Extrai Setor
    for chave, valor_final in sorted(SETOR_MAP.items(), key=lambda item: len(item[0]), reverse=True):
         if chave.lower() in texto_lower:
            mapeamentos["#SETOR#"] = valor_final
            break
            
    # 4. Extrai Valor Desejado (a propriedade da ontologia, ex: precoFechamento)
    for chave, valor_final in sorted(SINONIMOS_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if chave.lower() in texto_lower:
            mapeamentos["#VALOR_DESEJADO#"] = valor_final
            break
            
    return mapeamentos

def main(pergunta_usuario):
    """Função principal que orquestra o processamento."""
    logging.info(f"Processando a pergunta: '{pergunta_usuario}'")
    
    template_id = selecionar_template(pergunta_usuario)
    if not template_id:
        exit_with_error("Não foi possível entender a intenção da sua pergunta. Tente reformulá-la.")

    logging.info(f"Template selecionado: {template_id}")

    placeholders = extrair_placeholders(pergunta_usuario)
    logging.info(f"Placeholders extraídos: {placeholders}")
    
    # Validação Mínima:
    # Se o template não for o de listar setores (3A), ele provavelmente precisa de uma empresa/ticker.
    if template_id not in ["Template_3A"] and not placeholders.get("#ENTIDADE_NOME#"):
         exit_with_error("Não foi possível identificar a empresa ou o ticker na sua pergunta.")

    # Se o template precisa de uma data (1A, 1B, 4A) e não foi encontrada.
    if template_id in ["Template_1A", "Template_1B", "Template_4A"] and not placeholders.get("#DATA#"):
        exit_with_error("Não foi possível identificar a data na sua pergunta. Por favor, use o formato DD/MM/AAAA.")

    # Monta a resposta final em JSON
    resposta = {
        "template_nome": template_id,
        "mapeamentos": placeholders
    }
    
    # Imprime o resultado final para stdout, que será capturado pelo Java.
    print(json.dumps(resposta, ensure_ascii=False))
    logging.info(f"Processamento PLN concluído. Enviando para o Java: {resposta}")

# --- PONTO DE ENTRADA DO SCRIPT ---
if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Junta todos os argumentos para formar a pergunta completa, caso ela contenha espaços.
        main(" ".join(sys.argv[1:]))
    else:
        exit_with_error("Nenhuma pergunta foi fornecida ao script Python.")