package com.example.Programa_heber.ontology;

import jakarta.annotation.PostConstruct;
import org.apache.jena.query.*;
import org.apache.jena.rdf.model.*;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import org.apache.jena.shared.JenaException;
import org.apache.jena.vocabulary.OWL;
import org.apache.jena.vocabulary.RDF;
import org.apache.jena.vocabulary.RDFS;
import org.apache.jena.datatypes.xsd.XSDDatatype;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.text.Normalizer;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.regex.Pattern;

@Component
public class Ontology {

    private static final Logger logger = LoggerFactory.getLogger(Ontology.class);

    private InfModel infModel;
    private final ReadWriteLock lock = new ReentrantReadWriteLock();

    // --- CONSTANTES DE CONFIGURAÇÃO ---
    private static final String ONT_PREFIX = "https://dcm.ffclrp.usp.br/lssb/stock-market-ontology#";
    
    // Caminhos relativos ao classpath (src/main/resources)
    private static final String[] PREGAO_FILES = { "datasets/dados_novos_anterior.xlsx", "datasets/dados_novos_atual.xlsx" };
    private static final String SCHEMA_FILE = "stock_market.owl";
    private static final String BASE_DATA_FILE = "ontologiaB3.ttl";
    private static final String INFO_EMPRESAS_FILE = "templates/Informacoes_Empresas.xlsx";
    private static final String INFERENCE_OUTPUT_FILENAME = "ontologiaB3_com_inferencia.ttl";

    /**
     * Método de inicialização do Spring. Ele orquestra o carregamento da ontologia.
     * Utiliza uma lógica de cache para evitar a reconstrução do modelo a cada reinicialização.
     */
    @PostConstruct
    public void init() {
        logger.info(">>> INICIANDO Inicialização do Componente Ontology (@PostConstruct)...");
        lock.writeLock().lock();
        try {
            this.infModel = loadOrCreateInferredModel();

            if (this.infModel == null || this.infModel.isEmpty()) {
                throw new IllegalStateException("FALHA CRÍTICA: O modelo de inferência RDF não pôde ser carregado ou criado. A aplicação não pode funcionar.");
            }
            logger.info("<<< Ontology INICIALIZADA COM SUCESSO. Total de triplas no modelo: {} >>>", this.infModel.size());

        } catch (Exception e) {
            logger.error("!!!!!!!! FALHA GRAVE E IRRECUPERÁVEL NA INICIALIZAÇÃO DA ONTOLOGY !!!!!!!!", e);
            // Lançar uma exceção aqui impede que o Spring Boot continue a inicialização, o que é o comportamento correto.
            throw new RuntimeException("Falha crítica ao inicializar a camada de ontologia. Verifique os logs.", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * Tenta carregar um modelo pré-calculado. Se não encontrar, constrói um novo a partir das fontes.
     * @return O modelo de inferência pronto para uso.
     */
    private InfModel loadOrCreateInferredModel() throws IOException {
        ClassPathResource inferredResource = new ClassPathResource(INFERENCE_OUTPUT_FILENAME);
        
        if (inferredResource.exists()) {
            logger.info("--- Encontrado modelo inferido pré-calculado '{}'. Carregando diretamente... ---", INFERENCE_OUTPUT_FILENAME);
            Model dataModel = ModelFactory.createDefaultModel();
            try (InputStream in = inferredResource.getInputStream()) {
                RDFDataMgr.read(dataModel, in, Lang.TURTLE);
            }
            // Quando o modelo já está inferido, um raciocinador RDFS simples é suficiente e rápido.
            return ModelFactory.createRDFSModel(dataModel);
        } else {
            logger.warn("--- Modelo inferido '{}' não encontrado no classpath. Construindo do zero (este é um processo lento)... ---", INFERENCE_OUTPUT_FILENAME);
            Model baseModel = buildBaseModelFromSources();
            
            long baseSize = baseModel.size();
            validateBaseModelLoad(baseSize);

            Reasoner reasoner = ReasonerRegistry.getRDFSReasoner();
            InfModel constructedInfModel = ModelFactory.createInfModel(reasoner, baseModel);
            
            long infSize = constructedInfModel.size();
            long inferredCount = infSize - baseSize;
            logger.info("--- Modelo de inferência criado. Triplas Base: {}, Triplas Inferidas: {}, Total: {} ---", baseSize, Math.max(0, inferredCount), infSize);
            
            // Tenta salvar o modelo inferido no sistema de arquivos para depuração e para uso futuro.
            saveInferredModelToFileSystem(constructedInfModel);
            
            return constructedInfModel;
        }
    }

    /**
     * Orquestra a leitura de todos os arquivos fonte (OWL, TTL, XLSX) para construir o modelo base.
     * @return O modelo RDF base, antes da inferência.
     */
    private Model buildBaseModelFromSources() throws IOException {
        Model model = ModelFactory.createDefaultModel();
        model.setNsPrefix("b3", ONT_PREFIX); // Usando 'b3' como prefixo para ser mais curto nas queries
        model.setNsPrefix("rdf", RDF.uri);
        model.setNsPrefix("rdfs", RDFS.uri);
        model.setNsPrefix("owl", OWL.NS);
        model.setNsPrefix("xsd", XSDDatatype.XSD + "#");
        
        loadRdfData(model, SCHEMA_FILE, Lang.RDFXML, "Schema OWL");
        loadRdfData(model, BASE_DATA_FILE, Lang.TURTLE, "Dados base TTL");
        loadInformacoesEmpresas(model, INFO_EMPRESAS_FILE);
        
        for (String filePath : PREGAO_FILES) {
            loadDadosPregaoExcel(model, filePath);
        }
        logger.info("--- Carregamento de todas as fontes de dados primárias concluído ---");
        return model;
    }

    /**
     * Executa uma consulta SPARQL no modelo de inferência de forma segura (thread-safe).
     * @param sparqlQuery A consulta SPARQL a ser executada.
     * @return Uma lista de mapas, onde cada mapa representa uma linha de resultado.
     */
    public List<Map<String, String>> executeQuery(String sparqlQuery) {
        lock.readLock().lock();
        try {
            if (infModel == null) {
                logger.error("ERRO CRÍTICO: Tentativa de consulta com modelo de inferência nulo.");
                return Collections.emptyList(); // Retorna lista vazia em vez de nulo para segurança
            }

            List<Map<String, String>> resultsList = new ArrayList<>();
            Query query = QueryFactory.create(sparqlQuery);

            try (QueryExecution qexec = QueryExecutionFactory.create(query, infModel)) {
                ResultSet rs = qexec.execSelect();
                List<String> resultVars = rs.getResultVars();

                while (rs.hasNext()) {
                    QuerySolution soln = rs.nextSolution();
                    Map<String, String> rowMap = new LinkedHashMap<>(); // Mantém a ordem das colunas
                    for (String varName : resultVars) {
                        RDFNode node = soln.get(varName);
                        String value = "N/A";
                        if (node != null) {
                            if (node.isLiteral()) {
                                value = node.asLiteral().getLexicalForm();
                            } else if (node.isResource()) {
                                value = node.asResource().getURI();
                            } else {
                                value = node.toString();
                            }
                        }
                        rowMap.put(varName, value);
                    }
                    resultsList.add(rowMap);
                }
            }
            return resultsList;
        } catch (Exception e) {
            logger.error("Erro durante a execução da consulta SPARQL: {}", e.getMessage(), e);
            return Collections.emptyList(); // Retorna lista vazia em caso de erro
        } finally {
            lock.readLock().unlock();
        }
    }
    
    // ===================================================================================
    // MÉTODOS HELPER (privados para encapsular a lógica de carregamento)
    // ===================================================================================

    private void loadRdfData(Model model, String resourcePath, Lang language, String description) throws IOException {
        logger.info("   Lendo {}: '{}'", description, resourcePath);
        try (InputStream in = new ClassPathResource(resourcePath).getInputStream()) {
            RDFDataMgr.read(model, in, language);
        } catch (IOException e) {
            logger.error("   ERRO FATAL: Não foi possível ler o recurso RDF essencial '{}'", resourcePath, e);
            throw e;
        }
    }

    private void loadInformacoesEmpresas(Model model, String resourcePath) throws IOException {
        logger.info(">> Carregando Informações de Empresas de: {}", resourcePath);
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream();
             Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            final int nomeEmpresaCol = 0, tickerCol = 1, setorCol = 5;

            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue; // Pula o cabeçalho

                String nomeEmpresa = getStringCellValue(row.getCell(nomeEmpresaCol));
                String ticker = getStringCellValue(row.getCell(tickerCol));
                String setor = getStringCellValue(row.getCell(setorCol));

                if (nomeEmpresa == null || ticker == null || setor == null) continue;

                Resource empresaResource = createResource(model, ONT_PREFIX + normalizarTexto(nomeEmpresa));
                addStatement(model, empresaResource, RDF.type, createResource(model, ONT_PREFIX + "Empresa_Capital_Aberto"));
                addStatement(model, empresaResource, RDFS.label, model.createLiteral(nomeEmpresa.trim(), "pt"));

                Resource setorResource = createResource(model, ONT_PREFIX + "Setor_" + normalizarTexto(setor));
                addStatement(model, setorResource, RDF.type, createResource(model, ONT_PREFIX + "Setor_Atuacao"));
                addStatement(model, setorResource, RDFS.label, model.createLiteral(setor.trim(), "pt"));
                addStatement(model, empresaResource, createProperty(model, "atuaEm"), setorResource);

                Resource vmResource = createResource(model, ONT_PREFIX + ticker.trim());
                addStatement(model, vmResource, RDF.type, createResource(model, "Valor_Mobiliario"));
                addStatement(model, vmResource, RDFS.label, model.createLiteral(ticker.trim()));
                addStatement(model, empresaResource, createProperty(model, "temValorMobiliarioNegociado"), vmResource);
                
                Resource codigoResource = createResource(model, ONT_PREFIX + ticker.trim() + "_Codigo");
                addStatement(model, codigoResource, RDF.type, createResource(model, "Codigo_Negociacao"));
                addStatement(model, codigoResource, createProperty(model, "ticker"), model.createLiteral(ticker.trim()));
                addStatement(model, vmResource, createProperty(model, "representadoPor"), codigoResource);
            }
        }
    }

    private void loadDadosPregaoExcel(Model model, String resourcePath) throws IOException {
        logger.info(">> Carregando Dados de Pregão de: {}", resourcePath);
        try (InputStream excelFile = new ClassPathResource(resourcePath).getInputStream();
             Workbook workbook = new XSSFWorkbook(excelFile)) {
            Sheet sheet = workbook.getSheetAt(0);
            SimpleDateFormat rdfDateFormat = new SimpleDateFormat("yyyy-MM-dd");

            final int tickerCol = 3, dataCol = 1, openCol = 7, highCol = 8, lowCol = 9, closeCol = 11, volumeCol = 15;

            for (Row row : sheet) {
                if (row.getRowNum() == 0) continue;

                String ticker = getStringCellValue(row.getCell(tickerCol));
                Date dataPregao = getDateCellValue(row.getCell(dataCol));

                if (ticker == null || !ticker.matches("^[A-Z]{4}\\d{1,2}$") || dataPregao == null) continue;

                String dataFmt = rdfDateFormat.format(dataPregao);
                Resource valorMobiliario = createResource(model, ONT_PREFIX + ticker.trim());

                // Cria uma instância única de Negociação para este ticker nesta data
                String negociadoUri = ONT_PREFIX + "Negociado_" + ticker.trim() + "_" + dataFmt;
                Resource negociadoResource = createResource(model, negociadoUri);
                addStatement(model, negociadoResource, RDF.type, createResource(model, "Negociado_Em_Pregao"));

                // Liga o Valor Mobiliário a esta negociação
                addStatement(model, valorMobiliario, createProperty(model, "negociado"), negociadoResource);

                // Cria e liga a instância do Pregão (dia)
                Resource pregaoResource = createResource(model, ONT_PREFIX + "Pregao_" + dataFmt);
                addStatement(model, pregaoResource, RDF.type, createResource(model, "Pregao"));
                addStatement(model, pregaoResource, createProperty(model, "ocorreEmData"), model.createTypedLiteral(dataFmt, XSDDatatype.XSDdate));
                addStatement(model, negociadoResource, createProperty(model, "negociadoDurante"), pregaoResource);

                // Adiciona as propriedades de preço e volume
                addNumericProperty(model, negociadoResource, createProperty(model, "precoAbertura"), getNumericCellValue(row.getCell(openCol)));
                addNumericProperty(model, negociadoResource, createProperty(model, "precoMaximo"), getNumericCellValue(row.getCell(highCol)));
                addNumericProperty(model, negociadoResource, createProperty(model, "precoMinimo"), getNumericCellValue(row.getCell(lowCol)));
                addNumericProperty(model, negociadoResource, createProperty(model, "precoFechamento"), getNumericCellValue(row.getCell(closeCol)));
                addNumericProperty(model, negociadoResource, createProperty(model, "volumeNegociacao"), getNumericCellValue(row.getCell(volumeCol)));
            }
        }
    }
    
    // --- Funções utilitárias para POI e Jena ---
    private String getStringCellValue(Cell cell) {
        if (cell == null) return null;
        CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
        switch (type) {
            case STRING: return cell.getStringCellValue().trim();
            case NUMERIC: return String.valueOf(cell.getNumericCellValue());
            default: return null;
        }
    }

    private Date getDateCellValue(Cell cell) {
        if (cell == null) return null;
        if (cell.getCellType() == CellType.NUMERIC && DateUtil.isCellDateFormatted(cell)) {
            return cell.getDateCellValue();
        } else if (cell.getCellType() == CellType.STRING) {
            String dateStr = cell.getStringCellValue().trim();
            for (String format : new String[]{"yyyy-MM-dd", "dd/MM/yyyy"}) {
                try { return new SimpleDateFormat(format).parse(dateStr); } catch (ParseException ignored) {}
            }
        }
        return null;
    }

    private double getNumericCellValue(Cell cell) {
        if (cell == null) return Double.NaN;
        CellType type = cell.getCellType() == CellType.FORMULA ? cell.getCachedFormulaResultType() : cell.getCellType();
        if (type == CellType.NUMERIC) return cell.getNumericCellValue();
        if (type == CellType.STRING) {
            try { return Double.parseDouble(cell.getStringCellValue().trim().replace(",", ".")); } catch (NumberFormatException e) { return Double.NaN; }
        }
        return Double.NaN;
    }

    private String normalizarTexto(String texto) {
        if (texto == null) return "";
        return Normalizer.normalize(texto.trim(), Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}+", "")
                .replaceAll("[^a-zA-Z0-9_]", "_");
    }
    
    private void saveInferredModelToFileSystem(InfModel modelToSave) {
        Path outputPath = Paths.get(INFERENCE_OUTPUT_FILENAME);
        try (OutputStream out = new BufferedOutputStream(Files.newOutputStream(outputPath))) {
            logger.info("Tentando salvar modelo inferido em: {}", outputPath.toAbsolutePath());
            RDFDataMgr.write(out, modelToSave, Lang.TURTLE);
            logger.info("Modelo inferido salvo com sucesso. A próxima inicialização será mais rápida.");
        } catch (IOException e) {
            logger.warn("Não foi possível salvar o modelo inferido em disco (permissões?). A reconstrução ocorrerá na próxima inicialização.", e);
        }
    }
    
    // Métodos wrapper para criação de recursos Jena, para um código mais limpo
    private Resource createResource(Model model, String uri) { return model.createResource(uri); }
    private Property createProperty(Model model, String localName) { return model.createProperty(ONT_PREFIX + localName); }
    private void addStatement(Model model, Resource s, Property p, RDFNode o) { if (s != null && p != null && o != null) model.add(s, p, o); }
    private void addNumericProperty(Model model, Resource s, Property p, double value) { if (!Double.isNaN(value)) addStatement(s, p, model.createTypedLiteral(value)); }
    private void validateBaseModelLoad(long size) { if (size < 100) logger.error("MODELO BASE SUSPEITOSAMENTE PEQUENO ({}) APÓS CARREGAMENTO!", size); }
}