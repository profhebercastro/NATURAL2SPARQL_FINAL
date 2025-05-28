# Usar uma imagem base Python oficial.
FROM python:3.9-slim

# Definir o diretório de trabalho na imagem.
WORKDIR /app

# Instalar dependências do sistema necessárias para compilação
# (como gcc para a biblioteca 'blis', uma dependência do spacy)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

# Copiar o arquivo de requisitos primeiro para aproveitar o cache do Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação Flask (web_app.py) para o diretório de trabalho.
COPY web_app.py .

# Copiar o arquivo de ontologia CORRETO (com inferência) para o diretório /app.
# Certifique-se que este arquivo está na raiz do seu projeto ou ajuste o caminho de origem.
COPY ontologiaB3_com_inferencia.ttl /app/ontologiaB3_com_inferencia.ttl

# Copiar toda a pasta de resources para dentro da estrutura /app/src/main/resources no container.
# Isso garante que pln_processor.py, setor_map.json, perguntas_de_interesse.txt,
# resultado_similaridade.txt, empresa_nome_map.json e a pasta Templates sejam acessíveis.
COPY src/main/resources /app/src/main/resources

# Informar ao Docker que a aplicação escuta na porta 5000 (ou a porta que Gunicorn usa).
# O Render define a porta através da variável de ambiente PORT, então essa linha é mais informativa.
# O Gunicorn será configurado para usar a porta do Render.
EXPOSE 5000 # Você pode deixar esta porta ou a porta que o Gunicorn usaria sem $PORT, ex: 8000 ou 8080

# Comando para executar a aplicação usando Gunicorn.
# 'web_app:app' refere-se ao arquivo web_app.py e à instância 'app' do Flask nele.
# Ajuste o número de workers (-w) conforme necessário para seu plano no Render.
# O Render define a variável de ambiente $PORT, que deve ser usada aqui.
# Alterado para a forma "shell" para garantir a expansão de $PORT.
CMD gunicorn --bind 0.0.0.0:$PORT -w 2 --timeout 120 web_app:app