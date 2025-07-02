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