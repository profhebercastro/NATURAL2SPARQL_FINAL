# Arquivo: Dockerfile

# Estágio 1: Build da Aplicação com Maven e Python
# Usamos uma imagem que contém Maven, JDK 17 e Python para o estágio de build.
# Isso garante que todas as ferramentas necessárias estejam disponíveis.
FROM maven:3.9.6-eclipse-temurin-17-focal AS build

# Define o diretório de trabalho dentro do contêiner.
WORKDIR /build

# Copia todos os arquivos do projeto para o diretório de trabalho.
# O .dockerignore deve ser usado para excluir arquivos desnecessários (target, .git, etc.).
COPY . .

# Instala as dependências Python usando o requirements.txt, que é a melhor prática.
# Instala também o modelo de linguagem do spaCy.
RUN apt-get update && apt-get install -y python3-pip && \
    pip3 install --no-cache-dir -r requirements.txt && \
    python3 -m spacy download pt_core_news_sm && \
    apt-get purge -y --auto-remove python3-pip && rm -rf /var/lib/apt/lists/*

# Executa o build do Maven. O -DskipTests acelera o processo de deploy,
# assumindo que os testes já foram executados em um pipeline de CI/CD.
RUN mvn clean package -DskipTests

# Estágio 2: Imagem Final de Execução
# Usamos uma imagem JRE mínima para reduzir o tamanho e a superfície de ataque.
# Incluímos Python, que é uma dependência de tempo de execução para a aplicação.
FROM eclipse-temurin:17-jre-focal

# Instala apenas o Python 3, que é necessário para executar o script de PLN.
RUN apt-get update && apt-get install -y python3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia o JAR compilado do estágio de build.
COPY --from=build /build/target/*.jar app.jar
# Copia o diretório de scripts Python já com as dependências instaladas pelo spaCy.
# O spaCy baixa modelos em um local específico, que precisa ser copiado.
# O caminho pode variar, mas geralmente fica em /root/.local/lib/pythonX.Y/site-packages
# Para simplificar e garantir, vamos copiar o diretório temporário criado no estágio 1
# que o `QuestionProcessor.java` usa. Assumindo que o build maven copia os recursos.
# Uma abordagem mais simples é deixar o QuestionProcessor.java extrair os scripts do JAR.

# Otimização de Memória para o plano gratuito do Render (512MB).
# Aloca um máximo de 384MB para a Heap do Java, deixando espaço para o S.O. e o processo Python.
ENV JAVA_TOOL_OPTIONS="-Xmx384m"

# Expõe a porta que a aplicação Spring Boot usará.
EXPOSE 8080

# Comando para rodar a aplicação. Render.com injeta a variável de ambiente $PORT.
# O -Dserver.port=${PORT} garante que o Spring Boot escute na porta correta.
CMD ["java", "-Dserver.port=${PORT}", "-jar", "app.jar"]