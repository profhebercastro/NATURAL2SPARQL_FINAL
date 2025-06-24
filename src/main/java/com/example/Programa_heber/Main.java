package com.example.Programa_heber;

import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.service.QuestionProcessor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration; // <-- IMPORT NECESSÁRIO
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map; // Import para o novo método

@SpringBootApplication(exclude = {DataSourceAutoConfiguration.class}) // <-- CORREÇÃO PRINCIPAL
@RestController
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    private final QuestionProcessor questionProcessor;

    // Injeção de dependência pelo construtor (ótima prática!)
    @Autowired
    public Main(QuestionProcessor questionProcessor) {
        this.questionProcessor = questionProcessor;
        logger.info("Main Controller inicializado com QuestionProcessor.");
    }

    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
        logger.info("Aplicação Natural2SPARQL iniciada com sucesso.");
    }

    /*
     * A rota para a página inicial (/) foi removida.
     * O Spring Boot serve automaticamente qualquer arquivo `index.html` ou `index2.html`
     * que esteja na pasta `src/main/resources/static/`.
     * Isso simplifica o código e evita a lógica manual de leitura de arquivo.
     */

    // Endpoint para receber a pergunta. Usa um Map genérico para mais flexibilidade.
    @PostMapping("/processar_pergunta")
    public ResponseEntity<ProcessamentoDetalhadoResposta> processarPergunta(@RequestBody Map<String, String> payload) {
        String question = payload.get("pergunta"); // A chave deve ser "pergunta"

        if (question == null || question.trim().isEmpty()) {
            logger.warn("Requisição POST recebida sem a chave 'pergunta' ou com valor vazio.");
            ProcessamentoDetalhadoResposta errorReply = new ProcessamentoDetalhadoResposta();
            errorReply.setErro("Nenhuma pergunta fornecida no corpo da requisição.");
            return ResponseEntity.badRequest().body(errorReply);
        }

        if (questionProcessor == null) {
            logger.error("CRÍTICO: QuestionProcessor é nulo no momento da requisição!");
            ProcessamentoDetalhadoResposta errorReply = new ProcessamentoDetalhadoResposta();
            errorReply.setErro("Erro interno crítico: Serviço de processamento indisponível.");
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorReply);
        }

        logger.info("Processando pergunta: '{}'", question);
        
        ProcessamentoDetalhadoResposta respostaDetalhada = questionProcessor.processQuestion(question);
        
        // Determina o status HTTP com base na presença de um erro
        if (respostaDetalhada.getErro() != null) {
            logger.error("Erro durante o processamento da pergunta: {}", respostaDetalhada.getErro());
            // Retorna 500 para qualquer erro interno, simplificando a lógica.
            // O frontend pode exibir a mensagem de erro específica.
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(respostaDetalhada);
        }

        logger.info("Pergunta processada com sucesso.");
        return ResponseEntity.ok(respostaDetalhada);
    }
}