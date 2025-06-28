# -----------------------------------------------------------------
# ARQUIVO: Dockerfile (VERSÃO FINAL E CORRIGIDA)
# -----------------------------------------------------------------

# Estágio 1: Build da Aplicação Java com Maven
# Usamos uma imagem oficial do Maven com JDK 17 para compilar o projeto.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho para o build
WORKDIR /build

# Copia primeiro o pom.xml e o .mvn para aproveitar o cache de dependências do Docker
COPY pom.xml .
COPY .mvn/ .mvn/

# Baixa as dependências do Maven (acelera builds futuros)
RUN mvn dependency:go-offline

# Copia o resto do código fonte para o contêiner
COPY src ./src

# Compila e empacota a aplicação em um JAR, pulando os testes para um build mais rápido.
RUN mvn clean package -DskipTests

# ---

# Estágio 2: Criação da Imagem Final de Produção
# Usamos uma imagem JRE (Java Runtime Environment) que é menor que a JDK,
# e baseada no Ubuntu 'focal' para termos o gerenciador de pacotes 'apt'.
FROM eclipse-temurin:17-jre-focal

# Define o diretório de trabalho da aplicação
WORKDIR /app

# Instala Python, pip e outras ferramentas básicas.
# '&& \' encadeia comandos, e 'rm -rf' limpa o cache para manter a imagem pequena.
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Copia o arquivo de requisitos do Python.
# Ele deve estar na raiz do seu projeto.
COPY requirements.txt .

# Instala as dependências Python listadas no requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# --- PASSO CRÍTICO ---
# Baixa o modelo de linguagem do spaCy durante a construção da imagem.
# Isso evita que o download aconteça em tempo de execução, o que é mais lento e pode falhar.
# Usamos 'pt_core_news_lg' (grande) por ser mais preciso, mas 'sm' (pequeno) também funciona.
RUN python3 -m spacy download pt_core_news_lg

# Copia o JAR da aplicação que foi construído no Estágio 1 para a imagem final
COPY --from=build /build/target/*.jar app.jar

# Expõe a porta que o Render espera que a aplicação escute (padrão do Spring Boot).
EXPOSE 8080

# Comando para iniciar a aplicação.
# O Render fará o mapeamento externo da porta 80/443 para a porta 8080 do contêiner.
CMD ["java", "-jar", "app.jar"]