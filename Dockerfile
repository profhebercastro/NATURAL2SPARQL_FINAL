# Usar uma imagem base Python oficial.
FROM python:3.9-slim

# Definir o diretório de trabalho na imagem.
WORKDIR /app

# Instalar dependências do sistema necessárias para compilação
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

# Copiar o arquivo de requisitos primeiro para aproveitar o cache do Docker.
COPY requirements.txt .

# Instalar as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Baixar o modelo de linguagem spaCy para português
RUN python -m spacy download pt_core_news_sm

# Copiar o restante da aplicação
COPY web_app.py .
COPY ontologiaB3_com_inferencia.ttl .
COPY src/main/resources /app/src/main/resources

# Documenta a porta que o serviço expõe (o Render usará $PORT)
EXPOSE 10000

# ✅ Comando para executar a aplicação usando a forma "shell" do CMD
# Isso garante que a variável de ambiente $PORT seja substituída corretamente.
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 web_app:app