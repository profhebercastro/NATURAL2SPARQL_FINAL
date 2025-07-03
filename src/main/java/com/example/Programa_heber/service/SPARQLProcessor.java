package com.example.Programa_heber.service;

import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import org.springframework.util.StreamUtils;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class SPARQLProcessor {

    private static final Logger logger = LoggerFactory.getLogger(SPARQLProcessor.class);
    private static final String PYTHON_SCRIPT_NAME = "nlp_controller.py";

    // A lista de recursos agora aponta para os novos arquivos
    private static final String[] PYTHON_RESOURCES = {
        PYTHON_SCRIPT_NAME, "Thesaurus.json"
    };

    @Autowired
    private Ontology ontology;
    
    @Autowired
    private OntologyProfile ontologyProfile;

    private Path pythonScriptPath;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private static final Pattern TICKER_PATTERN = Pattern.compile("^[A-Z]{4}\\d{1,2}$");

    @PostConstruct
    public void initialize() throws IOException {
        logger.info("Iniciando SPARQLProcessor: Configurando ambiente Python...");
        try {
            Path tempDir = Files.createTempDirectory("pyscripts_temp_");
            tempDir.toFile().deleteOnExit();

            for (String fileName : PYTHON_RESOURCES) {
                Resource resource = new ClassPathResource(fileName);
                if (!resource.exists()) {
                    throw new FileNotFoundException("Recurso Python essencial não encontrado: " + fileName);
                }
                Path destination = tempDir.resolve(fileName);
                try (InputStream inputStream = resource.getInputStream()) {
                    Files.copy(inputStream, destination);
                }
                if (fileName.equals(PYTHON_SCRIPT_NAME)) {
                    this.pythonScriptPath = destination;
                    this.pythonScriptPath.toFile().setExecutable(true, false);
                }
            }
            logger.info("SPARQLProcessor inicializado com sucesso. Ambiente Python pronto em: {}", tempDir);
        } catch (IOException e) {
            logger.error("FALHA CRÍTICA AO CONFIGURAR AMBIENTE PYTHON.", e);
            throw e;
        }
    }

    public ProcessamentoDetalhadoResposta generateSparqlQuery(String question) {
        logger.info("Serviço SPARQLProcessor: Iniciando GERAÇÃO de query para: '{}'", question);
        ProcessamentoDetalhadoResposta respostaDetalhada = new ProcessamentoDetalhadoResposta();
        try {
            Map<String, Object> resultadoPython = executePythonScript(question);
            if (resultadoPython.containsKey("erro")) {
                respostaDetalhada.setErro("Falha na análise da pergunta: " + resultadoPython.get("erro"));
                return respostaDetalhada;
            }

            String templateId = (String) resultadoPython.get("template_nome");
            @SuppressWarnings("unchecked")
            Map<String, String> placeholders = (Map<String, String>) resultadoPython.get("mapeamentos");

            if (templateId == null || placeholders == null) {
                respostaDetalhada.setErro("Não foi possível determinar o tipo da pergunta ou extrair detalhes.");
                return respostaDetalhada;
            }

            String conteudoTemplate = readTemplateContent(templateId);
            String sparqlQueryGerada = buildSparqlQuery(conteudoTemplate, placeholders);
            respostaDetalhada.setSparqlQuery(sparqlQueryGerada);
            respostaDetalhada.setTemplateId(templateId);

        } catch (Exception e) {
            logger.error("Erro ao GERAR query para '{}': {}", question, e.getMessage(), e);
            respostaDetalhada.setErro("Ocorreu um erro interno ao gerar a consulta.");
        }
        return respostaDetalhada;
    }

    public String executeAndFormat(String sparqlQuery, String templateId) {
        logger.info("Serviço SPARQLProcessor: Iniciando EXECUÇÃO de query com template {}.", templateId);
        try {
            List<Map<String, String>> resultados = ontology.executeQuery(sparqlQuery);
            return formatarResultados(resultados, templateId);
        } catch (Exception e) {
            logger.error("Erro ao EXECUTAR query: {}", e.getMessage(), e);
            return "Erro ao executar a consulta na base de conhecimento.";
        }
    }

    private String buildSparqlQuery(String templateContent, Map<String, String> placeholders) {
        String query = templateContent;

        // ETAPA 1: Substituir placeholders dinâmicos vindos do Python
        if (placeholders.containsKey("#DATA#")) {
            query = query.replace("#O2#", "\"" + placeholders.get("#DATA#") + "\"^^xsd:date");
        }
        if (placeholders.containsKey("#ENTIDADE_NOME#")) {
            String entidade = placeholders.get("#ENTIDADE_NOME#");
            String valorFormatado = formatarEntidade(entidade);
            query = query.replace("#ENTIDADE_NOME#", valorFormatado);
        }
        if (placeholders.containsKey("#SETOR#")) {
            query = query.replace("#SETOR#", "\"" + placeholders.get("#SETOR#").replace("\"", "\\\"") + "\"@pt");
        }

        // ETAPA 2: Resolver o placeholder semântico #VALOR_DESEJADO#
        if (placeholders.containsKey("#VALOR_DESEJADO#")) {
            String valorDesejadoKey = "resposta." + placeholders.get("#VALOR_DESEJADO#");
            String predicadoGenerico = ontologyProfile.get(valorDesejadoKey); 
            query = query.replace("#VALOR_DESEJADO#", predicadoGenerico);
        }
        
        // ETAPA 3: Substituir todos os placeholders de MAPEAMENTO DE ONTOLOGIA
        query = substituirPlaceholdersDePerfil(query, "[?]*C\\d+");
        query = substituirPlaceholdersDePerfil(query, "[?]*P\\d+");
        query = substituirPlaceholdersDePerfil(query, "\\?S\\d+");
        query = substituirPlaceholdersDePerfil(query, "\\?O\\d+");
        query = substituirPlaceholdersDePerfil(query, "\\?ANS");

        // ETAPA 4: Adicionar prefixos
        String prefixes = "PREFIX b3: <" + ontologyProfile.get("prefix.b3") + ">\n" +
                          "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n" +
                          "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n" +
                          "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n\n";
        
        String finalQuery = prefixes + query;
        logger.info("Query SPARQL Final Gerada:\n{}", finalQuery);
        return finalQuery;
    }

    private String substituirPlaceholdersDePerfil(String query, String regex) {
        Pattern pattern = Pattern.compile(regex);
        Matcher matcher = pattern.matcher(query);
        StringBuffer sb = new StringBuffer();
        while (matcher.find()) {
            String placeholder = matcher.group(0).replace("?", "");
            String valorDoPerfil = ontologyProfile.get(placeholder);
            String valorFinal = valorDoPerfil.startsWith("?") ? valorDoPerfil : Matcher.quoteReplacement(valorDoPerfil);
            matcher.appendReplacement(sb, valorFinal);
        }
        matcher.appendTail(sb);
        return sb.toString();
    }

    private String formatarEntidade(String entidade) {
        String entidadeEscapada = entidade.replace("\"", "\\\"");
        return TICKER_PATTERN.matcher(entidade).matches()
            ? "\"" + entidadeEscapada + "\""
            : "\"" + entidadeEscapada + "\"@pt";
    }

    private Map<String, Object> executePythonScript(String question) throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder("python3", this.pythonScriptPath.toString(), question);
        logger.info("Executando comando Python: {}", String.join(" ", pb.command()));
        Process process = pb.start();
        String stdoutResult = StreamUtils.copyToString(process.getInputStream(), StandardCharsets.UTF_8);
        String stderrResult = StreamUtils.copyToString(process.getErrorStream(), StandardCharsets.UTF_8);
        int exitCode = process.waitFor();
        if (!stderrResult.isEmpty()) {
            logger.warn("Script Python emitiu mensagens no stderr: {}", stderrResult);
        }
        if (exitCode != 0) {
            throw new RuntimeException("Script Python falhou com código de saída " + exitCode + ". Erro: " + stderrResult);
        }
        if (stdoutResult.isEmpty()) {
            throw new RuntimeException("Script Python não retornou nenhuma saída (stdout). Erro: " + stderrResult);
        }
        return objectMapper.readValue(stdoutResult, new TypeReference<>() {});
    }

    private String readTemplateContent(String templateId) throws IOException {
        String templateFileName = templateId + ".txt";
        String templateResourcePath = "templates/" + templateFileName;
        Resource resource = new ClassPathResource(templateResourcePath);
        if (!resource.exists()) {
            throw new FileNotFoundException("Template SPARQL não encontrado: " + templateResourcePath);
        }
        try (InputStream inputStream = resource.getInputStream()) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private String formatarResultados(List<Map<String, String>> resultados, String templateId) {
        if (resultados == null || resultados.isEmpty()) {
            return "Não foram encontrados resultados para a sua pergunta.";
        }
        if ("Template_4A".equals(templateId)) {
            StringJoiner joiner = new StringJoiner("\n");
            joiner.add(String.format("%-10s | %s", "Ticker", "Volume Negociado"));
            joiner.add("------------------------------------");
            for (Map<String, String> row : resultados) {
                String ticker = limparValor(row.getOrDefault(ontologyProfile.get("O1").substring(1), "N/A"));
                try {
                    double volumeValue = Double.parseDouble(row.getOrDefault("volume", "0"));
                    String volumeFormatado = String.format("%,.2f", volumeValue);
                    joiner.add(String.format("%-10s | %s", ticker, volumeFormatado));
                } catch (NumberFormatException e) {
                     joiner.add(String.format("%-10s | %s", ticker, row.getOrDefault("volume", "N/A")));
                }
            }
            return joiner.toString();
        }
        StringJoiner joiner = new StringJoiner(", ");
        if (!resultados.get(0).isEmpty()) {
            String varName = resultados.get(0).keySet().stream().findFirst().orElse("valor");
            for (Map<String, String> row : resultados) {
                String valor = row.getOrDefault(varName, "");
                if (valor != null && !valor.isEmpty()) {
                    joiner.add(limparValor(valor));
                }
            }
        }
        String resultadoFinal = joiner.toString();
        return resultadoFinal.isEmpty() ? "Não foram encontrados resultados para a sua pergunta." : resultadoFinal;
    }

    private String limparValor(String item) {
        if (item == null) return "";
        String limpo = item.replaceAll("\\^\\^<http://www.w3.org/2001/XMLSchema#.*?>", "");
        String baseUri = ontologyProfile.get("prefix.b3");
        if (limpo.startsWith(baseUri)) {
            limpo = limpo.substring(baseUri.length());
        }
        return limpo.trim();
    }
}