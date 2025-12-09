"""
Script de teste para validar implementação RAG SEEU.
Testa normalização, chunking e fluxo RAG completo.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.rag_schemas import (
    RagQueryRequest,
    MetadadosConsulta,
    ChunkingConfig,
    DocumentoParaChunking
)
from src.rag_normalizer import LegalQueryNormalizer
from src.chunking import DocumentChunker, preprocessar_texto_juridico


def test_normalizador():
    """Testa o normalizador jurídico."""
    print("\n" + "="*80)
    print("TESTE 1: NORMALIZADOR JURÍDICO")
    print("="*80)
    
    # Verifica se chave está configurada
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Configure OPENAI_API_KEY ou ANTHROPIC_API_KEY no .env")
        return False
    
    try:
        # Inicializa normalizador
        provider = os.getenv("LLM_PROVIDER", "openai")
        print(f"📋 Provider: {provider}")
        
        normalizer = LegalQueryNormalizer(provider=provider)
        
        # Query de teste
        query_teste = """
        Meu cliente está cumprindo pena em regime semiaberto há 2 anos, 
        não tem faltas graves, e gostaria de saber se ele pode progredir 
        para o regime aberto. O crime foi roubo qualificado.
        """
        
        print(f"\n📝 Query de teste: {query_teste.strip()}\n")
        
        # Normaliza
        resultado = normalizer.normalizar(query_teste)
        
        print("✅ Normalização bem-sucedida!\n")
        print(f"Intenção: {resultado.intencao}")
        print(f"Benefício/Tema: {resultado.tipoBeneficioOuTema}")
        print(f"Query RAG: {resultado.queryRAG}")
        print(f"\nDados de Execução Penal:")
        print(f"  - Regime: {resultado.dadosExecucaoPenal.regimeAtual}")
        print(f"  - Tempo cumprido: {resultado.dadosExecucaoPenal.tempoCumpridoAproximado}")
        print(f"  - Faltas graves: {resultado.dadosExecucaoPenal.faltasGraves}")
        print(f"  - Tipo de crime: {resultado.dadosExecucaoPenal.tipoCrime}")
        print(f"\nTemas: {', '.join(resultado.temaExecucao)}")
        print(f"Palavras-chave: {', '.join(resultado.palavrasChaveJuridicas)}")
        
        if resultado.observacoes:
            print(f"\nObservações: {resultado.observacoes}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chunking():
    """Testa o sistema de chunking."""
    print("\n" + "="*80)
    print("TESTE 2: CHUNKING DE DOCUMENTOS")
    print("="*80)
    
    try:
        # Texto de teste (decisão jurídica fictícia)
        texto_teste = """
        ACÓRDÃO
        
        Vistos, relatados e discutidos estes autos, acordam os Ministros da Quinta Turma 
        do Superior Tribunal de Justiça, por unanimidade, conhecer do habeas corpus e 
        conceder a ordem, nos termos do voto do Sr. Ministro Relator.
        
        RELATÓRIO
        
        Trata-se de habeas corpus, com pedido de liminar, impetrado em favor de FULANO DE TAL,
        contra decisão proferida pelo Tribunal de Justiça que indeferiu pedido de progressão
        de regime.
        
        Alega-se, em síntese, que o paciente cumpriu o requisito objetivo (1/6 da pena em
        regime semiaberto) e possui bom comportamento carcerário, fazendo jus à progressão
        para o regime aberto.
        
        VOTO
        
        O regime de progressão de pena é direito subjetivo do condenado, previsto no art. 112
        da Lei de Execução Penal. Preenchidos os requisitos objetivo (cumprimento de fração
        da pena) e subjetivo (bom comportamento carcerário), impõe-se a concessão do benefício.
        
        No caso concreto, verifica-se que o paciente cumpriu mais de 1/6 da pena em regime
        semiaberto e não possui faltas graves registradas. O laudo de comportamento carcerário
        atesta sua adequação às normas prisionais.
        
        Portanto, deve ser concedida a progressão ao regime aberto.
        
        DISPOSITIVO
        
        Ante o exposto, CONCEDO A ORDEM de habeas corpus para determinar a progressão do
        paciente ao regime aberto, nos termos da fundamentação.
        """ * 3  # Multiplica para criar texto maior
        
        # Preprocessa
        texto_limpo = preprocessar_texto_juridico(texto_teste)
        
        # Cria documento
        doc = DocumentoParaChunking(
            id="HC123456",
            texto=texto_limpo,
            metadata={
                "tribunal": "STJ",
                "numeroProcesso": "HC 123456/SP",
                "relator": "Min. Fulano",
                "dataJulgamento": "2023-05-10",
                "tema": "progressao_regime"
            }
        )
        
        print(f"📄 Documento: {doc.id}")
        print(f"📏 Tamanho original: {len(texto_limpo)} chars\n")
        
        # Configura chunking
        config = ChunkingConfig(
            tamanho_alvo=600,
            tamanho_min=400,
            tamanho_max=800,
            overlap=100
        )
        
        # Chunka
        chunker = DocumentChunker(config)
        chunks = chunker.chunk_documento(doc)
        
        print(f"✅ Chunking bem-sucedido!")
        print(f"📊 Total de chunks: {len(chunks)}\n")
        
        # Mostra primeiros 2 chunks
        for i, chunk in enumerate(chunks[:2]):
            print(f"--- Chunk {i} ---")
            print(f"ID: {chunk['idChunk']}")
            print(f"Tokens: {chunk['metadata']['tokensChunk']}")
            print(f"Posição: {chunk['metadata']['posicaoChunk']}/{chunk['metadata']['totalChunks']-1}")
            print(f"Texto (primeiros 200 chars): {chunk['texto'][:200]}...\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_request():
    """Testa estrutura de request RAG."""
    print("\n" + "="*80)
    print("TESTE 3: ESTRUTURA DE REQUEST")
    print("="*80)
    
    try:
        # Cria request
        request = RagQueryRequest(
            promptUsuario="Quais os requisitos para progressão de regime?",
            useRag=True,
            metadados=MetadadosConsulta(
                tribunal="STJ",
                anoMin=2020,
                anoMax=2024,
                tipoConsulta="jurisprudencia"
            ),
            k=10
        )
        
        print(f"✅ Request criado com sucesso!")
        print(f"📝 Prompt: {request.promptUsuario}")
        print(f"🔍 Use RAG: {request.useRag}")
        print(f"📊 K: {request.k}")
        print(f"🏛️ Tribunal: {request.metadados.tribunal}")
        print(f"📅 Período: {request.metadados.anoMin}-{request.metadados.anoMax}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Executa todos os testes."""
    print("\n" + "="*80)
    print("TESTES RAG SEEU - VALIDAÇÃO DA IMPLEMENTAÇÃO")
    print("="*80)
    
    resultados = []
    
    # Teste 1: Normalizador (requer chave LLM)
    if os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"):
        resultados.append(("Normalizador Jurídico", test_normalizador()))
    else:
        print("\n⚠️ Pulando teste do normalizador (sem chave LLM configurada)")
        print("💡 Configure OPENAI_API_KEY ou ANTHROPIC_API_KEY no .env")
    
    # Teste 2: Chunking (não requer chave)
    resultados.append(("Chunking", test_chunking()))
    
    # Teste 3: Request structure (não requer chave)
    resultados.append(("Estrutura Request", test_rag_request()))
    
    # Resumo
    print("\n" + "="*80)
    print("RESUMO DOS TESTES")
    print("="*80)
    
    for nome, sucesso in resultados:
        status = "✅ PASSOU" if sucesso else "❌ FALHOU"
        print(f"{status} - {nome}")
    
    total = len(resultados)
    passou = sum(1 for _, s in resultados if s)
    
    print(f"\n📊 Total: {passou}/{total} testes passaram")
    
    if passou == total:
        print("\n🎉 Todos os testes passaram!")
        return 0
    else:
        print("\n⚠️ Alguns testes falharam")
        return 1


if __name__ == "__main__":
    sys.exit(main())
