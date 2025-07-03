package com.example.Programa_heber;

import com.example.Programa_heber.model.ExecuteQueryRequest;
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.service.SPARQLProcessor; // MUDANÇA AQUI
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@SpringBootApplication(exclude = {DataSourceAutoConfiguration.class})
@RestController
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);
    // MUDANÇA AQUI: Renomeando a dependência
    private final SPARQLProcessor sparqlProcessor;

    @Autowired
    // MUDANÇA AQUI: Atualizando o construtor
    public Main(SPARQLProcessor sparqlProcessor) {
        this.sparqlProcessor = sparqlProcessor;
    }

    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
    }

    @PostMapping("/gerar_consulta")
    public ResponseEntity<ProcessamentoDetalhadoResposta> gerarConsulta(@RequestBody PerguntaRequest request) {
        String question = request.getPergunta();
        if (question == null || question.trim().isEmpty()) {
            ProcessamentoDetalhadoResposta errorReply = new ProcessamentoDetalhadoResposta();
            errorReply.setErro("A pergunta não pode estar vazia.");
            return ResponseEntity.badRequest().body(errorReply);
        }

        logger.info("Recebida requisição para GERAR consulta para: '{}'", question);
        // MUDANÇA AQUI: Usando a nova variável
        ProcessamentoDetalhadoResposta resposta = sparqlProcessor.generateSparqlQuery(question);

        if (resposta.getErro() != null) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(resposta);
        }
        return ResponseEntity.ok(resposta);
    }

    @PostMapping("/executar_query")
    public ResponseEntity<Map<String, String>> executarQuery(@RequestBody ExecuteQueryRequest request) {
        String sparqlQuery = request.getSparqlQuery();
        String templateId = request.getTemplateId();

        if (sparqlQuery == null || sparqlQuery.trim().isEmpty() || templateId == null || templateId.trim().isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("resultado", "Erro: A consulta SPARQL e o ID do template são necessários."));
        }

        logger.info("Recebida requisição para EXECUTAR consulta com template ID: {}", templateId);
        // MUDANÇA AQUI: Usando a nova variável
        String resultado = sparqlProcessor.executeAndFormat(sparqlQuery, templateId);

        return ResponseEntity.ok(Map.of("resultado", resultado));
    }
}