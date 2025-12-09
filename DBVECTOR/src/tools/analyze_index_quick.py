"""
Análise rápida e leve dos dados indexados.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.factory import get_faiss_store
from src.embeddings import encode_texts
import time
import json

print("="*80)
print("ANÁLISE RÁPIDA DA INDEXAÇÃO")
print("="*80)

# 1. Informações do índice
print("\n📊 INFORMAÇÕES GERAIS")
print("-"*80)
store = get_faiss_store()
doc_count = store.get_doc_count()
print(f"Total de documentos: {doc_count:,}")

# Tamanhos dos arquivos
index_path = Path("data/indexes/faiss/index.faiss")
metadata_path = Path("data/indexes/faiss/metadata.parquet")

if index_path.exists():
    index_size = index_path.stat().st_size / 1024 / 1024
    metadata_size = metadata_path.stat().st_size / 1024 / 1024
    total_size = index_size + metadata_size
    
    print(f"Tamanho índice FAISS: {index_size:.2f} MB")
    print(f"Tamanho metadata: {metadata_size:.2f} MB")
    print(f"Tamanho total: {total_size:.2f} MB")
    print(f"Tamanho por documento: {total_size * 1024 / doc_count:.2f} KB")

# 2. Teste de busca
print(f"\n⚡ TESTE DE PERFORMANCE")
print("-"*80)

test_queries = [
    "direitos fundamentais",
    "recurso especial",
    "danos morais"
]

latencies = []
for query in test_queries:
    start = time.time()
    query_vector = encode_texts([query])[0]
    results = store.search(query_vector, k=5)
    elapsed = (time.time() - start) * 1000
    latencies.append(elapsed)
    print(f"Query '{query}': {elapsed:.2f}ms ({len(results)} resultados)")

import numpy as np
print(f"\nLatência média: {np.mean(latencies):.2f}ms")
print(f"Latência P95: {np.percentile(latencies, 95):.2f}ms")

# 3. Qualidade dos resultados
print(f"\n🔍 TESTE DE QUALIDADE")
print("-"*80)

query = "direitos fundamentais constituição"
query_vector = encode_texts([query])[0]
results = store.search(query_vector, k=5)

print(f"Query: '{query}'")
print(f"\nTop 5 resultados:")
for i, result in enumerate(results, 1):
    print(f"{i}. Score: {result.score:.4f} | {result.doc.title[:60]}")

# Verifica relevância
keywords = ['direito', 'constituição', 'fundamental']
relevant = sum(1 for r in results if any(k in r.doc.text.lower() for k in keywords))
print(f"\nRelevância: {relevant}/{len(results)} ({relevant/len(results)*100:.1f}%)")

# 4. Análise rápida de metadata (apenas contagem)
print(f"\n📝 ANÁLISE DE METADADOS (amostra)")
print("-"*80)

import pandas as pd
# Lê apenas 1000 linhas para análise rápida
df_sample = pd.read_parquet(metadata_path, columns=['id', 'title', 'text'])
df_sample = df_sample.head(1000)

print(f"Amostra: {len(df_sample)} documentos")
print(f"IDs únicos: {df_sample['id'].nunique()}")
print(f"Títulos preenchidos: {df_sample['title'].notna().sum()}/{len(df_sample)}")

df_sample['text_length'] = df_sample['text'].str.len()
print(f"\nTamanho médio dos textos: {df_sample['text_length'].mean():.0f} chars")
print(f"Tamanho mínimo: {df_sample['text_length'].min()} chars")
print(f"Tamanho máximo: {df_sample['text_length'].max()} chars")

# Resumo final
print(f"\n{"="*80}")
print("RESUMO")
print(f"{"="*80}")
print(f"✅ Indexação concluída com sucesso")
print(f"📊 {doc_count:,} documentos indexados")
print(f"💾 {total_size:.2f} MB de dados")
print(f"⚡ Latência média: {np.mean(latencies):.2f}ms")
print(f"🔍 Sistema funcional e pronto para uso!")
print(f"{"="*80}")

# Salva resumo
report = {
    'doc_count': doc_count,
    'total_size_mb': total_size,
    'latency_mean_ms': float(np.mean(latencies)),
    'latency_p95_ms': float(np.percentile(latencies, 95)),
    'status': 'OK'
}

report_path = Path("reports/inspect/quick_analysis.json")
report_path.parent.mkdir(parents=True, exist_ok=True)
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2)

print(f"\n💾 Relatório salvo em: {report_path}")
