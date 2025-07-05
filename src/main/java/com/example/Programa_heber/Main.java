package com.example.Programa_heber;

import com.example.Programa_heber.model.ExecuteQueryRequest;
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.example.Programa_heber.service.SPARQLProcessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

// A anotação @SpringBootApplication define esta como a única classe principal da aplicação.
// A anotação @RestController combina @Controller e @ResponseBody, indicando que esta
// classe lidará com requisições web e retornará dados (como JSON) diretamente.
@SpringBootApplication
@RestController
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    // Injeção de dependências dos serviços necessários via construtor.
    private final SPARQLProcessor sparqlProcessor;
    private final Ontology ontology;

    @Autowired
    public Main(SPARQLProcessor sparqlProcessor, Ontology ontology) {
        this.sparqlProcessor = sparqlProcessor;
        this.ontology = ontology;
    }

    // O método main que o Spring Boot procura para iniciar toda a aplicação.
    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
    }
    
    /**
     * Endpoint para GERAR a consulta SPARQL.
     * Mapeado para: POST /gerar_consulta
     * Recebe: JSON no formato {"pergunta": "..."} (mapeado para PerguntaRequest).
     * Retorna: JSON com a query e o ID do template (mapeado de ProcessamentoDetalhadoResposta).
     */
    @PostMapping("/gerar_consulta")
    public ResponseEntity<ProcessamentoDetalhadoResposta> gerarConsulta(@RequestBody PerguntaRequest request) {
        String pergunta = request.getPergunta();
        ProcessamentoDetalhadoResposta resposta = new ProcessamentoDetalhadoResposta();

        if (pergunta == null || pergunta.trim().isEmpty()) {
            resposta.setErro("A pergunta não pode estar vazia.");
            return ResponseEntity.badRequest().body(resposta);
        }

        logger.info("Recebida requisição para GERAR consulta para: '{}'", pergunta);
        try {
            // Delega a lógica de geração para o SPARQLProcessor
            resposta = sparqlProcessor.generateSparqlQuery(pergunta);

            if (resposta.getErro() != null) {
                return ResponseEntity.internalServerError().body(resposta);
            }
            return ResponseEntity.ok(resposta);
        } catch (Exception e) {
            logger.error("Erro no endpoint /gerar_consulta: {}", e.getMessage(), e);
            resposta.setErro("Erro interno ao gerar a consulta: " + e.getMessage());
            return ResponseEntity.internalServerError().body(resposta);
        }
    }

    /**
     * Endpoint para EXECUTAR uma consulta SPARQL.
     * Mapeado para: POST /executar_query
     * Recebe: JSON no formato {"sparqlQuery": "...", "templateId": "..."} (mapeado para ExecuteQueryRequest).
     * Retorna: JSON no formato {"resultado": "..."}.
     */
    @PostMapping("/executar_query")
    public ResponseEntity<Map<String, String>> executarQuery(@RequestBody ExecuteQueryRequest request) {
        String sparqlQuery = request.getSparqlQuery();
        
        if (sparqlQuery == null || sparqlQuery.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("erro", "A consulta SPARQL não pode estar vazia."));
        }

        logger.info("Recebida requisição para EXECUTAR a consulta.");
        try {
            // Delega a execução da consulta para a classe Ontology
            List<Map<String, String>> resultList = ontology.executeQuery(sparqlQuery);

            // Formata a lista de resultados em uma única string para a textarea do frontend
            String formattedResult = formatResultSet(resultList);
            
            return ResponseEntity.ok(Map.of("resultado", formattedResult));
        } catch (Exception e) {
            logger.error("Erro no endpoint /executar_query: {}", e.getMessage(), e);
            return ResponseEntity.internalServerError().body(Map.of("erro", "Erro interno ao executar a consulta."));
        }
    }

    /**
     * Método privado auxiliar para formatar o resultado da consulta em uma string de texto.
     * @param resultList A lista de resultados vinda do Jena.
     * @return Uma string formatada para ser exibida na textarea.
     */
    private String formatResultSet(List<Map<String, String>> resultList) {
        if (resultList == null || resultList.isEmpty()) {
            return "A consulta foi executada com sucesso, mas não retornou resultados.";
        }
        
        StringBuilder sb = new StringBuilder();
        // Constrói o cabeçalho
        sb.append(String.join("\t|\t", resultList.get(0).keySet())).append("\n");
        sb.append("=".repeat(sb.length() + (resultList.get(0).size() * 3))).append("\n");

        // Constrói as linhas de dados
        for (Map<String, String> row : resultList) {
            String line = row.values().stream().collect(Collectors.joining("\t|\t"));
            sb.append(line).append("\n");
        }
        
        return sb.toString();
    }
}