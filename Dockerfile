# Começamos com uma imagem base do Python
FROM python:3.9-slim

# Define o diretório de trabalho principal
WORKDIR /app

# --- 1. INSTALAÇÃO DE DEPENDÊNCIAS DO SISTEMA ---
# Primeiro, atualizamos os pacotes e instalamos TUDO que precisamos:
# - openjdk-17-jre: Para rodar o JAR Java.
# - maven: Para compilar o projeto Java.
# - build-essential: Para instalar 'gcc' e outras ferramentas de compilação para o Python.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless \
        maven \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- 2. INSTALAÇÃO DE DEPENDÊNCIAS PYTHON ---
# Com as ferramentas de build já instaladas, esta etapa agora funcionará.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download pt_core_news_sm

# --- 3. BUILD DO PROJETO JAVA ---
# Copia todo o código-fonte para o diretório de trabalho
COPY . .
# Executa o Maven para compilar o Java e criar o JAR
RUN mvn clean package -DskipTests

# --- 4. CONFIGURAÇÃO FINAL E EXECUÇÃO ---
# Expõe a porta que o Gunicorn/Flask usará
EXPOSE 10000

# Comando final para iniciar a aplicação.
# O Gunicorn (servidor Python) será o processo principal.
# Ele irá, por sua vez, chamar o serviço Java que foi compilado na etapa anterior.
# Nota: Esta CMD assume que o web_app.py chama o Main.java como um processo separado.
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "3", "--timeout", "120", "web_app:app"]