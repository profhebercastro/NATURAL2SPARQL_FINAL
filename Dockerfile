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

# Baixar o modelo de linguagem spaCy para português
# Certifique-se que 'spacy' está no requirements.txt
RUN python -m spacy download pt_core_news_sm

# Copiar o código da aplicação Flask (web_app.py) para o diretório de trabalho.
COPY web_app.py .

# Copiar o arquivo de ontologia CORRETO (com inferência) para o diretório /app.
COPY ontologiaB3_com_inferencia.ttl /app/ontologiaB3_com_inferencia.ttl

# Copiar toda a pasta de resources para dentro da estrutura /app/src/main/resources no container.
COPY src/main/resources /app/src/main/resources

# Informar ao Docker que a aplicação escuta na porta X.
EXPOSE 5000

# Comando para executar a aplicação usando Gunicorn.
CMD gunicorn --bind 0.0.0.0:$PORT -w 2 --timeout 120 web_app:app