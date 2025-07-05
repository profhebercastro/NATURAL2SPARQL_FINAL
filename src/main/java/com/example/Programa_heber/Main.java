package com.example.Programa_heber;

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

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@SpringBootApplication
@RestController
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    
    private final SPARQLProcessor sparqlProcessor;
    private final Ontology ontology;

    @Autowired
    public Main(SPARQLProcessor sparqlProcessor, Ontology ontology) {
        this.sparqlProcessor = sparqlProcessor;
        this.ontology = ontology;
    }

    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
    }

    /**
     * Endpoint unificado para processar uma pergunta do início ao fim.
     * Recebe: {"pergunta": "Qual o preço..."}
     * Retorna: {"sparqlQuery": "SELECT...", "resultado": [{...}]}
     */
    @PostMapping("/api/process-question")
    public ResponseEntity<Map<String, Object>> processarPerguntaCompleta(@RequestBody Map<String, String> request) {
        String pergunta = request.get("pergunta");
        if (pergunta == null || pergunta.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "A pergunta não pode estar vazia."));
        }

        Map<String, Object> response = new HashMap<>();

        try {
            // Passo 1: Gerar a consulta SPARQL
            logger.info("Gerando consulta para: '{}'", pergunta);
            String sparqlQuery = sparqlProcessor.generateSparqlQuery(pergunta);
            response.put("sparqlQuery", sparqlQuery);

            if (sparqlQuery.startsWith("Erro")) {
                response.put("error", sparqlQuery);
                return ResponseEntity.internalServerError().body(response);
            }

            // Passo 2: Executar a consulta gerada
            logger.info("Executando a consulta gerada...");
            List<Map<String, String>> result = ontology.executeQuery(sparqlQuery);
            response.put("resultado", result);

            return ResponseEntity.ok(response);

        } catch (Exception e) {
            logger.error("Erro no fluxo completo de processamento para a pergunta '{}': {}", pergunta, e.getMessage(), e);
            response.put("error", "Erro interno grave durante o processamento.");
            return ResponseEntity.internalServerError().body(response);
        }
    }
}