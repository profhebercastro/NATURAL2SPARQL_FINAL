# Arquivo: Dockerfile - Versão 9 (Usa imagem base com Python pré-instalado)

# ----------------- ESTÁGIO 1: BUILD -----------------
# MELHORIA: Usa uma imagem base mais recente (Debian 12 Bookworm)
# que JÁ INCLUI Python 3, pip, e ferramentas de build essenciais.
# Isso evita a necessidade de 'apt-get' e torna o build mais rápido e confiável.
FROM maven:3.9-eclipse-temurin-17-bookworm AS build

# Define o diretório de trabalho.
WORKDIR /build

# A imagem já tem python3 e pip. Apenas atualizamos o pip.
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
# Usa uma imagem JRE mínima correspondente (Bookworm).
FROM eclipse-temurin:17-jre-bookworm

WORKDIR /app

# --- Instala APENAS o interpretador Python no estágio final ---
# A imagem base JRE não tem Python, então ainda precisamos instalá-lo aqui.
# Usamos a mesma tática de antes para garantir robustez.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 && \
    rm -rf /var/lib/apt/lists/*

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# Copia as bibliotecas Python já instaladas e os modelos do spaCy do estágio de build.
# NOTA: O caminho do Python no Debian Bookworm é python3.11.
# O Docker lida com isso automaticamente ao copiar, mas é bom saber.
COPY --from=build /usr/local/lib/python3.11/dist-packages/ /usr/local/lib/python3.11/dist-packages/

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará (Render definirá a variável $PORT).
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]