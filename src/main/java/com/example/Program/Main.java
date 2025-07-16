package com.example.Programa_heber;

import com.example.Programa_heber.model.ExecuteQueryRequest;
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.example.Programa_heber.service.SPARQLProcessor;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@SpringBootApplication
@RestController
@RequestMapping("/api") // Define o prefixo base /api para os endpoints
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    @Autowired
    private SPARQLProcessor sparqlProcessor;
    
    @Autowired
    private Ontology ontology;

    @Autowired
    private ObjectMapper objectMapper; // Injeta o ObjectMapper para serialização

    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
    }
    
    @PostMapping("/processar") // URL CORRIGIDA
    public ResponseEntity<ProcessamentoDetalhadoResposta> gerarConsulta(@RequestBody PerguntaRequest request) {
        String pergunta = request.getPergunta();
        
        if (pergunta == null || pergunta.trim().isEmpty()) {
            ProcessamentoDetalhadoResposta erro = new ProcessamentoDetalhadoResposta();
            erro.setErro("A pergunta não pode estar vazia.");
            return ResponseEntity.badRequest().body(erro);
        }

        logger.info("Recebida requisição para GERAR consulta para: '{}'", pergunta);
        try {
            ProcessamentoDetalhadoResposta resposta = sparqlProcessor.generateSparqlQuery(pergunta);
            if (resposta.getErro() != null) {
                return ResponseEntity.status(500).body(resposta);
            }
            return ResponseEntity.ok(resposta);
        } catch (Exception e) {
            logger.error("Erro no endpoint /processar: {}", e.getMessage(), e);
            ProcessamentoDetalhadoResposta erro = new ProcessamentoDetalhadoResposta();
            erro.setErro("Erro interno ao gerar a consulta: " + e.getMessage());
            return ResponseEntity.status(500).body(erro);
        }
    }

    @PostMapping("/executar") // URL CORRIGIDA
    public ResponseEntity<String> executarQuery(@RequestBody ExecuteQueryRequest request) {
        // Usa o método getter CORRIGIDO: getQuery()
        String sparqlQuery = request.getQuery();
        
        if (sparqlQuery == null || sparqlQuery.trim().isEmpty()) {
            return ResponseEntity.badRequest().body("{\"error\": \"A consulta SPARQL não pode estar vazia.\"}");
        }

        logger.info("Recebida requisição para EXECUTAR a consulta.");
        try {
            // Executa a consulta e obtém a estrutura de dados (ex: List<Map<String, String>>)
            Object resultObject = ontology.executeQuery(sparqlQuery);

            // Usa o ObjectMapper para converter o objeto de resultado em uma String JSON
            String resultadoJson = objectMapper.writeValueAsString(resultObject);
            
            return ResponseEntity.ok(resultadoJson);

        } catch (JsonProcessingException e) {
             logger.error("Erro ao serializar resultado para JSON: {}", e.getMessage(), e);
            return ResponseEntity.status(500).body("{\"error\": \"Erro ao formatar o resultado da consulta.\"}");
        } 
        catch (Exception e) {
            logger.error("Erro no endpoint /executar: {}", e.getMessage(), e);
            return ResponseEntity.status(500).body("{\"error\": \"Erro interno ao executar a consulta: " + e.getMessage() + "\"}");
        }
    }
}