package com.example.Programa_heber;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * Controller simples, responsável apenas por servir as páginas web estáticas (frontend).
 * Separa a lógica de servir a interface da lógica da API.
 */
@Controller
public class WebController {

    /**
     * Mapeia a rota raiz ("/") do site para a página de entrada da aplicação.
     * Quando um usuário acessa "https://seu-site.com/", este método é chamado.
     * O Spring Boot então procura por um arquivo com o nome retornado ('index2.html')
     * na pasta `src/main/resources/static/` e o entrega ao navegador.
     *
     * @return O nome do arquivo HTML a ser renderizado.
     */
    @GetMapping("/")
    public String index() {
        return "index2.html";
    }
}