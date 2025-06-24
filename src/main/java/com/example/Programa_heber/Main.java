package com.example.Programa_heber;

// 1. ADICIONAR O IMPORT PARA A NOVA CLASSE
import com.example.Programa_heber.model.PerguntaRequest;
import com.example.Programa_heber.model.ProcessamentoDetalhadoResposta;
import com.example.Programa_heber.service.QuestionProcessor;
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

/**
 * Ponto de entrada principal da aplicação Natural2SPARQL.
 * Esta classe inicia o servidor web Spring Boot e expõe os endpoints da API.
 */
@SpringBootApplication(exclude = {DataSourceAutoConfiguration.class}) // Essencial para evitar a configuração de um banco de dados SQL.
@RestController
public class Main {

    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    private final QuestionProcessor questionProcessor;

    /**
     * Construtor para injeção de dependência.
     * O Spring injetará uma instância do serviço QuestionProcessor.
     * @param questionProcessor O serviço responsável por processar as perguntas.
     */
    @Autowired
    public Main(QuestionProcessor questionProcessor) {
        this.questionProcessor = questionProcessor;
        logger.info("Controlador principal (Main) inicializado e injetado com QuestionProcessor.");
    }

    /**
     * Método main padrão que inicia a aplicação Spring Boot.
     */
    public static void main(String[] args) {
        SpringApplication.run(Main.class, args);
        logger.info(">>> Aplicação Natural2SPARQL iniciada com sucesso. <<<");
    }

    /**
     * Endpoint da API para processar uma pergunta em linguagem natural.
     * Espera uma requisição POST com um corpo JSON contendo uma chave "pergunta".
     * Exemplo de corpo da requisição: { "pergunta": "Qual o preço da PETR4?" }
     *
     * @param request O corpo da requisição JSON deserializado para um objeto PerguntaRequest.
     * @return Um ResponseEntity contendo o objeto ProcessamentoDetalhadoResposta com os resultados.
     */
    @PostMapping("/processar_pergunta")
    // 2. ALTERAR A ASSINATURA DO MÉTODO DE Map PARA PerguntaRequest
    public ResponseEntity<ProcessamentoDetalhadoResposta> processarPergunta(@RequestBody PerguntaRequest request) {
        
        // 3. OBTER A PERGUNTA DO OBJETO DTO EM VEZ DO MAP
        String question = request.getPergunta();

        // A lógica de validação permanece a mesma e é crucial.
        if (question == null || question.trim().isEmpty()) {
            logger.warn("Requisição recebida em /processar_pergunta com corpo inválido ou pergunta vazia.");
            ProcessamentoDetalhadoResposta errorReply = new ProcessamentoDetalhadoResposta();
            errorReply.setErro("A chave 'pergunta' não pode ser nula ou vazia no corpo da requisição.");
            return ResponseEntity.badRequest().body(errorReply);
        }

        logger.info("Recebida requisição para processar a pergunta: '{}'", question);
        
        // Delega o trabalho pesado para o serviço de processamento.
        ProcessamentoDetalhadoResposta respostaDetalhada = questionProcessor.processQuestion(question);
        
        // Verifica se houve um erro durante o processamento para retornar o status HTTP apropriado.
        if (respostaDetalhada.getErro() != null) {
            logger.error("Erro retornado pelo serviço de processamento: {}", respostaDetalhada.getErro());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(respostaDetalhada);
        }

        logger.info("Pergunta processada com sucesso. Retornando resposta para o cliente.");
        return ResponseEntity.ok(respostaDetalhada);
    }
}