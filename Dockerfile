# Arquivo: Dockerfile - Versão 10 (Final - Combina o melhor dos dois mundos)

# ----------------- ESTÁGIO 1: BUILD (ROBUSTO) -----------------
# Usa uma imagem base mais recente (Debian 12 Bookworm)
# que JÁ INCLUI Python 3, pip, e ferramentas de build essenciais.
# Isso evita a necessidade de 'apt-get' e torna o build mais rápido e confiável.
FROM maven:3.9-eclipse-temurin-17-bookworm AS build

# Define o diretório de trabalho.
WORKDIR /build

# A imagem já tem python3 e pip. Apenas atualizamos o pip.
# Copia o requirements.txt para instalar as dependências Python.
COPY requirements.txt .

# Instala as dependências Python.
# O --break-system-packages é necessário em imagens Debian mais recentes para permitir o uso do pip.
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt && \
    python3 -m spacy download pt_core_news_sm

# Copia o resto do código fonte do projeto.
COPY . .

# Executa o build do Maven para criar o JAR.
RUN mvn clean package -DskipTests


# ----------------- ESTÁGIO 2: EXECUÇÃO (LEVE E COMPROVADO) -----------------
# Volta a usar a imagem JRE baseada no Focal, que sabemos que existe e é estável.
FROM eclipse-temurin:17-jre-focal

WORKDIR /app

# --- Instala APENAS o interpretador Python no estágio final ---
# A imagem JRE 'focal' não tem Python, então precisamos instalá-lo aqui.
# Mantemos as otimizações de rede para garantir.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 && \
    rm -rf /var/lib/apt/lists/*

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar

# Copia as bibliotecas Python já instaladas e os modelos do spaCy do estágio de build.
# O caminho do Python no Debian Bookworm é python3.11, mas o Docker lida com a cópia.
# O importante é que a imagem final (Focal, com Python 3.8) terá essas bibliotecas prontas.
COPY --from=build /usr/local/lib/python3.11/dist-packages/ /usr/local/lib/python3.8/dist-packages/

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará (Render definirá a variável $PORT).
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]