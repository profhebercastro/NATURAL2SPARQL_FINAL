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
# Copiando os arquivos da raiz do projeto para a raiz do WORKDIR (/app)
COPY web_app.py .
COPY ontologiaB3_com_inferencia.ttl .

# Copiando a estrutura de diretórios 'src'
COPY src/main/resources /app/src/main/resources

# A porta que o Gunicorn vai escutar será definida pela variável de ambiente $PORT
# que o Render.com fornece. EXPOSE é apenas uma documentação para o Docker.
EXPOSE 10000

# ✅ Comando de execução CORRIGIDO usando a forma "exec".
# Esta forma é mais robusta para lidar com variáveis de ambiente.
# O Render.com irá definir a variável $PORT.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--workers", "2", "--timeout", "120", "web_app:app"]