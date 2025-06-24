package com.example.Programa_heber;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * Controller responsável por servir as páginas web estáticas (frontend).
 * Separa a lógica de servir a interface do usuário da lógica da API.
 */
@Controller
public class WebController {

    /**
     * Mapeia a rota raiz ("/") para a página de entrada da aplicação.
     * O Spring Boot procurará por um arquivo chamado 'index2.html'
     * na pasta `src/main/resources/static/` e o retornará.
     *
     * @return O nome do template HTML a ser renderizado.
     */
    @GetMapping("/")
    public String index() {
        return "index2.html"; // O nome do seu arquivo HTML
    }
}