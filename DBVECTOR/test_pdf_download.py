#!/usr/bin/env python3
"""
Script de teste para debug do endpoint de download de PDF.
Testa a busca de documentos pelo case_number.
"""
import sys
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.factory import get_faiss_store
from src import embeddings
import re


def test_document_search(doc_id: str):
    """
    Testa busca de documento simulando o endpoint de download.
    """
    print(f"\n{'='*80}")
    print(f"🔍 TESTANDO BUSCA PARA: {doc_id}")
    print(f"{'='*80}\n")
    
    # Carrega store
    print("📁 Carregando FAISS store...")
    store = get_faiss_store()
    print(f"✅ Store carregado: {store.get_doc_count()} documentos\n")
    
    # Extrai números do doc_id
    extracted_numbers = re.findall(r'\d{4,}', doc_id)
    print(f"🔢 Números extraídos: {extracted_numbers}\n")
    
    if not extracted_numbers:
        print("❌ Nenhum número extraído do ID!")
        return None
    
    # Estratégia 1: Busca vetorial com o número
    print("📊 ESTRATÉGIA 1: Busca vetorial com número extraído")
    print("-" * 80)
    
    for num in extracted_numbers[:3]:
        print(f"\n🔍 Buscando por: '{num}'")
        query_vector = embeddings.encode_single_text(num)
        results = store.search(query_vector, k=50)
        
        print(f"   Encontrados {len(results)} resultados")
        
        # Analisa os primeiros 10 resultados
        for i, result in enumerate(results[:10], 1):
            meta = result.doc.meta or {}
            case_number = meta.get("case_number", "")
            raw_seq = meta.get("raw_seq_documento", "")
            title = result.doc.title or "Sem título"
            
            # Verifica match
            match_type = []
            if case_number and num in str(case_number):
                match_type.append(f"case_number={case_number}")
            if raw_seq and num in str(raw_seq):
                match_type.append(f"raw_seq={raw_seq}")
            
            status = "✅ MATCH!" if match_type else "❌ No match"
            
            print(f"   [{i:2d}] {status}")
            print(f"        Score: {result.score:.4f}")
            print(f"        ID: {result.doc.id}")
            print(f"        Title: {title[:60]}...")
            print(f"        case_number: {case_number}")
            print(f"        raw_seq_documento: {raw_seq}")
            if match_type:
                print(f"        MATCH: {', '.join(match_type)}")
            print()
    
    # Estratégia 2: Busca direta por case_number nos metadados
    print("\n📊 ESTRATÉGIA 2: Varredura nos metadados")
    print("-" * 80)
    
    # Busca ampla para análise
    print(f"🔍 Buscando 500 documentos aleatórios para análise...")
    query_vector = embeddings.encode_single_text(extracted_numbers[0])
    results = store.search(query_vector, k=500)
    
    matches = []
    for result in results:
        meta = result.doc.meta or {}
        case_number = str(meta.get("case_number", ""))
        
        # Verifica se algum número extraído está no case_number
        for num in extracted_numbers:
            if num in case_number:
                matches.append({
                    'doc': result.doc,
                    'score': result.score,
                    'case_number': case_number,
                    'matched_num': num
                })
                break
    
    print(f"\n✅ Encontrados {len(matches)} documentos com match no case_number!\n")
    
    if matches:
        print("🎯 TOP 5 MATCHES:")
        print("-" * 80)
        for i, match in enumerate(matches[:5], 1):
            doc = match['doc']
            meta = doc.meta or {}
            print(f"\n[{i}] Score: {match['score']:.4f}")
            print(f"    ID: {doc.id}")
            print(f"    Title: {doc.title or 'Sem título'}")
            print(f"    case_number: {match['case_number']}")
            print(f"    Matched: '{match['matched_num']}' in case_number")
            print(f"    Tribunal: {meta.get('tribunal', 'N/A')}")
            print(f"    raw_seq_documento: {meta.get('raw_seq_documento', 'N/A')}")
            print(f"    Text preview: {doc.text[:100]}...")
        
        return matches[0]['doc']
    else:
        print("❌ Nenhum documento encontrado com case_number matching!")
        
        # Debug: mostra alguns case_numbers dos resultados
        print("\n🔍 SAMPLE de case_numbers nos resultados (primeiros 10):")
        for i, result in enumerate(results[:10], 1):
            meta = result.doc.meta or {}
            case_num = meta.get("case_number", "N/A")
            print(f"   [{i:2d}] case_number: {case_num}")
        
        return None


def main():
    """Testa múltiplos IDs."""
    test_cases = [
        "stj_hc_280533",
        "stj_hc_563878",
        "stj_hc_482345",
        "144280533",  # case_number direto
    ]
    
    for doc_id in test_cases:
        result = test_document_search(doc_id)
        
        if result:
            print(f"\n{'='*80}")
            print(f"✅ SUCESSO! Documento encontrado para: {doc_id}")
            print(f"{'='*80}\n")
        else:
            print(f"\n{'='*80}")
            print(f"❌ FALHA! Documento não encontrado para: {doc_id}")
            print(f"{'='*80}\n")
        
        # Pausa entre testes
        if doc_id != test_cases[-1]:
            input("\n⏸️  Pressione ENTER para continuar para o próximo teste...\n")


if __name__ == "__main__":
    main()
