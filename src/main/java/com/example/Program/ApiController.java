package com.example.Programa_heber;

import com.example.Programa_heber.model.ExecuteQueryRequest;
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.ontology.Ontology;
import com.example.Programa_heber.service.SPARQLProcessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class ApiController {

    private static final Logger logger = LoggerFactory.getLogger(ApiController.class);

    @Autowired
    private SPARQLProcessor sparqlProcessor;

    @Autowired
    private Ontology ontology;

    @PostMapping("/processar")
    public ResponseEntity<ProcessamentoDetalhadoResposta> gerarConsulta(@RequestBody PerguntaRequest request) {
        logger.info("API: Recebida requisição para GERAR consulta para: '{}'", request.getPergunta());
        try {
            ProcessamentoDetalhadoResposta resposta = sparqlProcessor.generateSparqlQuery(request.getPergunta());
            return ResponseEntity.ok(resposta);
        } catch (Exception e) {
            logger.error("Erro no endpoint /api/processar: ", e);
            ProcessamentoDetalhadoResposta erroResposta = new ProcessamentoDetalhadoResposta();
            erroResposta.setErro("Falha interna do servidor ao processar a pergunta.");
            return ResponseEntity.status(500).body(erroResposta);
        }
    }

    @PostMapping("/executar")
    public ResponseEntity<String> executarQuery(@RequestBody ExecuteQueryRequest request) {
        logger.info("API: Recebida requisição para EXECUTAR a consulta.");
        try {
            // Usa o getter corrigido: getQuery()
            String resultadoJson = ontology.executeQuery(request.getQuery());
            return ResponseEntity.ok(resultadoJson);
        } catch (Exception e) {
            logger.error("Erro no endpoint /api/executar: ", e);
            String erroJson = "{\"error\": \"Falha interna do servidor ao executar a consulta.\"}";
            return ResponseEntity.status(500).body(erroJson);
        }
    }
}