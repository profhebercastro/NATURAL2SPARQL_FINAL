package com.example.Program;

import org.apache.jena.rdf.model.InfModel;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.reasoner.Reasoner;
import org.apache.jena.reasoner.ReasonerRegistry;
import org.apache.jena.riot.Lang;
import org.apache.jena.riot.RDFDataMgr;
import com.example.Program.ontology.Ontology; // <-- IMPORT CORRIGIDO

import java.io.FileOutputStream;
import java.io.OutputStream;

public class OfflineInferenceGenerator {

    public static void main(String[] args) {
        System.out.println("======================================================");
        System.out.println("--- INICIANDO GERAÇÃO OFFLINE DO MODELO INFERIDO ---");
        System.out.println("======================================================");

        try {
            Ontology ontologyHelper = new Ontology();
            System.out.println("[PASSO 1/4] Instância de Ontology criada.");

            Model baseModel = ontologyHelper.buildBaseModelFromSources();
            System.out.println("[PASSO 2/4] Modelo base construído com " + baseModel.size() + " triplas.");
            if (baseModel.isEmpty()) {
                System.err.println("ERRO: Modelo base está vazio. Verifique os caminhos e o conteúdo dos arquivos Excel.");
                return;
            }

            System.out.println("[PASSO 3/4] Aplicando RDFS Reasoner para criar o modelo de inferência...");
            Reasoner reasoner = ReasonerRegistry.getRDFSReasoner();
            InfModel infModel = ModelFactory.createInfModel(reasoner, baseModel);
            System.out.println("             -> Modelo inferido criado com " + infModel.size() + " triplas totais.");

            String outputFilename = "src/main/resources/ontology_inferred_final.ttl";
            System.out.println("[PASSO 4/4] Salvando modelo inferido em: " + outputFilename);
            try (OutputStream out = new FileOutputStream(outputFilename)) {
                RDFDataMgr.write(out, infModel, Lang.TURTLE);
            }
            
            System.out.println("\n======================================================");
            System.out.println("--- SUCESSO! GERAÇÃO OFFLINE CONCLUÍDA. ---");
            System.out.println("======================================================");

        } catch (Exception e) {
            System.err.println("\n!!!!!!!! FALHA DURANTE A GERAÇÃO OFFLINE !!!!!!!");
            e.printStackTrace();
        }
    }
}