# Estágio 1: Builder (Compilação do Java)
FROM maven:3.8-openjdk-17 AS builder
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
RUN mvn package -DskipTests

# Estágio 2: Final (Imagem de Execução)
FROM eclipse-temurin:17-jre-focal

# Instala Python e pip
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copia o JAR compilado do estágio builder
COPY --from=builder /app/target/*.jar app.jar

# 2. Copia os recursos para o classpath do Java (onde ele espera)
COPY src/main/resources /app/resources

# 3. Copia os scripts e arquivos de configuração para a raiz do app
COPY requirements.txt start.sh nlp_controller.py ./
COPY *.json ./
COPY *.txt ./

# 4. Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# 5. Torna o script de inicialização executável
RUN chmod +x start.sh

EXPOSE 10000 5000

CMD ["./start.sh"]# ESTÁGIO 1: Build da Aplicação Java com Maven
FROM maven:3.8-openjdk-17 AS builder

WORKDIR /app

# Otimiza o cache copiando apenas os arquivos de dependência primeiro
COPY pom.xml .
RUN mvn dependency:go-offline

# Copia todo o código-fonte (incluindo a pasta src/main/resources/nlp)
COPY src ./src

# Constrói o projeto Java. O Maven irá empacotar a pasta 'resources' dentro do JAR.
RUN mvn clean package -DskipTests


# ====================================================================


# ESTÁGIO 2: Imagem Final de Produção
FROM eclipse-temurin:17-jre-focal

# Instala Python, pip e Gunicorn
RUN apt-get update && apt-get install -y python3 python3-pip gunicorn && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copia o JAR compilado do estágio builder. Ele já contém os recursos do Java.
COPY --from=builder /app/target/*.jar app.jar

# 2. Copia a pasta de NLP SEPARADAMENTE para o Python usar.
# Isso garante que nlp_controller.py e os dicionários existam no sistema de arquivos.
COPY src/main/resources/nlp /app/nlp/

# 3. Copia e instala as dependências Python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia e torna o script de inicialização executável
COPY start.sh .
RUN chmod +x start.sh

# Expõe as portas necessárias
EXPOSE 10000 5000

# Define o comando que será executado quando o container iniciar
CMD ["./start.sh"]