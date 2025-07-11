package com.example.Programa_heber.model;

/**
 * DTO (Data Transfer Object) que representa o corpo da requisição POST vinda do frontend.
 * O Jackson deserializará o JSON { "pergunta": "..." } para um objeto desta classe.
 */
public class PerguntaRequest {
    
    private String pergunta;



    // Getter para 'pergunta'
    public String getPergunta() {
        return pergunta;
    }

    // Setter para 'pergunta'
    public void setPergunta(String pergunta) {
        this.pergunta = pergunta;
    }
}