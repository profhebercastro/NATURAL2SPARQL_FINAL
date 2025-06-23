# Usa uma imagem oficial do Python como base
FROM python:3.9-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Instala o Java (JDK 17) - necessário para rodar o seu JAR
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jdk maven && \
    rm -rf /var/lib/apt/lists/*

# Copia os arquivos de requisitos do Python e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download pt_core_news_sm

# Copia o código-fonte do projeto Java
COPY src ./src
# Copia o pom.xml
COPY pom.xml .

# Executa o build do Maven dentro do contêiner para criar o JAR
# Isso garante que a compilação aconteça no ambiente de produção
RUN mvn clean install -DskipTests

# Agora, copia os arquivos da aplicação Python e os arquivos de dados necessários para a raiz do /app
COPY web_app.py .
COPY ontologiaB3_com_inferencia.ttl .

# Expõe a porta que o Gunicorn vai usar
EXPOSE 10000

# Comando final para iniciar a aplicação
# Ele executa o JAR Java em background e o web_app.py em primeiro plano
# O JAR estará em /app/target/Programa_heber-1.0-SNAPSHOT.jar (ajuste se o nome for diferente)
CMD java -jar target/Programa_heber-1.0-SNAPSHOT.jar & gunicorn --bind 0.0.0.0:$PORT --workers 2 web_app:app