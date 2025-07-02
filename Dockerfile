# Arquivo: Dockerfile - Versão 8 (Final - Com Ferramentas de Build)

# ----------------- ESTÁGIO 1: BUILD -----------------
# Usa uma imagem base que contém Maven e JDK 17.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho.
WORKDIR /build

# --- MELHORIA FINAL: Instala ferramentas de build essenciais ---
# Adiciona build-essential (para g++, gcc) e python3-dev (para cabeçalhos Python).
# Isso é necessário para compilar as dependências C do spaCy (cymem, murmurhash, etc).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3 \
    python3-pip \
    python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copia o requirements.txt para instalar as dependências Python.
COPY requirements.txt .

# Instala as dependências Python.
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m spacy download pt_core_news_sm

# Copia o resto do código fonte do projeto.
COPY . .

# Executa o build do Maven para criar o JAR.
RUN mvn clean package -DskipTests


# ----------------- ESTÁGIO 2: EXECUÇÃO -----------------
# Usa uma imagem JRE mínima para a imagem final.
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# --- Instala APENAS o interpretador Python no estágio final ---
# Não precisamos das ferramentas de build aqui, apenas do python3 para executar o script.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 && \
    rm -rf /var/lib/apt/lists/*

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# Copia as bibliotecas Python já instaladas e os modelos do spaCy do estágio de build.
# Isso evita ter que baixar tudo de novo na imagem final e não requer compilação.
COPY --from=build /usr/local/lib/python3.8/dist-packages/ /usr/local/lib/python3.8/dist-packages/

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará (Render definirá a variável $PORT).
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]