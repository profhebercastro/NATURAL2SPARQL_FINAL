# Arquivo: Dockerfile - Versão 5 (Final e Resiliente)

# ----------------- ESTÁGIO 1: BUILD -----------------
# Usa uma imagem base que JÁ CONTÉM Maven, JDK 17 e Python 3.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho.
WORKDIR /build

# Copia o requirements.txt para instalar as dependências Python.
COPY requirements.txt .

# CORREÇÃO: Usa 'python3' em vez de 'python' para garantir a compatibilidade
# com a imagem base que não possui o alias 'python'.
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m spacy download pt_core_news_sm

# Copia o resto do código fonte do projeto.
COPY . .

# Executa o build do Maven para criar o JAR.
RUN mvn clean package -DskipTests
# Arquivo: Dockerfile - Versão 6 (Corrigida e Robusta)

# ----------------- ESTÁGIO 1: BUILD -----------------
# Usa uma imagem base que contém Maven e JDK 17.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho.
WORKDIR /build

# --- CORREÇÃO 1: Instalar Python e Pip no estágio de build ---
# Garante que o python3 e o pip estejam disponíveis, independentemente da imagem base.
RUN apt-get update && apt-get install -y python3 python3-pip

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
# Usa uma imagem JRE mínima.
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# --- CORREÇÃO 2: Instalar o interpretador Python no estágio final ---
# A aplicação Java precisa chamar o 'python3' em tempo de execução.
RUN apt-get update && apt-get install -y python3

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# Copia as bibliotecas Python já instaladas e os modelos do spaCy do estágio de build.
# Isso evita ter que baixar tudo de novo.
COPY --from=build /usr/local/lib/python3.8/dist-packages/ /usr/local/lib/python3.8/dist-packages/

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará (Render definirá a variável $PORT).
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]

# ----------------- ESTÁGIO 2: EXECUÇÃO -----------------
# Usa uma imagem JRE mínima que também já inclui Python 3.
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# Copia as bibliotecas Python já instaladas do estágio de build.
COPY --from=build /usr/local/lib/python3.8/dist-packages/ /usr/local/lib/python3.8/dist-packages/

# Copia os modelos do spaCy já baixados.
COPY --from=build /usr/local/lib/python3.8/dist-packages/pt_core_news_sm-3.7.0/ /usr/local/lib/python3.8/dist-packages/pt_core_news_sm-3.7.0/

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará.
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]