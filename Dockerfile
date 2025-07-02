# Arquivo: Dockerfile - Versão 11 (Final, Robusto e Explícito)

# ----------------- ESTÁGIO 1: BUILD (ROBUSTO) -----------------
# Usa a imagem Focal, que sabemos que existe e é estável.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho.
WORKDIR /build

# --- Instala TODAS as dependências necessárias explicitamente ---
# Isso torna o build resiliente a mudanças na imagem base.
# 1. build-essential: Para compilar código C/C++ (dependências do spaCy).
# 2. python3-dev: Para os arquivos de cabeçalho do Python.
# 3. python3-pip: Para instalar pacotes Python.
# 4. git & ca-certificates: Ocasionalmente necessários pelo pip para pacotes complexos.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    python3-pip \
    git \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copia o requirements.txt para instalar as dependências Python.
COPY requirements.txt .

# Instala as dependências Python.
# Usar --no-cache-dir é uma boa prática para manter a imagem limpa.
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m spacy download pt_core_news_sm

# Copia o resto do código fonte do projeto.
COPY . .

# Executa o build do Maven para criar o JAR.
RUN mvn clean package -DskipTests


# ----------------- ESTÁGIO 2: EXECUÇÃO (LEVE E COMPROVADO) -----------------
# Usa a imagem JRE baseada no Focal, que é leve e sabemos que existe.
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
# O caminho do Python em ambas as imagens Focal é python3.8, então a cópia é direta.
COPY --from=build /usr/local/lib/python3.8/dist-packages/ /usr/local/lib/python3.8/dist-packages/

# Define as variáveis de ambiente.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará (Render definirá a variável $PORT).
EXPOSE 8080

# Comando para rodar a aplicação.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]