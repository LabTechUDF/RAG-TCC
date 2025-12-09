"""
Script para analisar merged_clean.jsonl e testar queries com alta relevância.
Identifica artigos, temas e faz queries estratégicas para encontrar resultados com 80%+ de relevância.
"""
import json
import requests
import re
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any
import time


API_URL = "http://localhost:8000"
THRESHOLD_SCORE = 0.80  # 80% de relevância mínima


def carregar_merged_clean(filepath: str = "data/merged_clean.jsonl") -> List[Dict]:
    """Carrega e analisa merged_clean.jsonl."""
    print(f"📂 Carregando {filepath}...")
    
    docs = []
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 10000:  # Limita amostra para análise rápida
                break
            line = line.strip()
            if line:
                try:
                    docs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    print(f"✅ {len(docs)} documentos carregados (amostra)")
    return docs


def extrair_artigos(texto: str) -> List[str]:
    """Extrai referências a artigos de lei do texto."""
    # Padrões: art. 123, artigo 456, Art. 789, etc.
    patterns = [
        r'art\.?\s*(\d+)',
        r'artigo\s+(\d+)',
        r'Art\.?\s*(\d+)',
        r'ARTIGO\s+(\d+)'
    ]
    
    artigos = []
    for pattern in patterns:
        matches = re.findall(pattern, texto, re.IGNORECASE)
        artigos.extend(matches)
    
    return list(set(artigos))  # Remove duplicatas


def analisar_corpus(docs: List[Dict]) -> Dict[str, Any]:
    """Analisa corpus para extrair informações úteis."""
    print("\n🔍 Analisando corpus...")
    
    total = len(docs)
    clusters = Counter()
    artigos_counter = Counter()
    palavras_chave = Counter()
    tribunais = Counter()
    
    # Palavras-chave jurídicas importantes
    keywords = [
        "estelionato", "furto", "roubo", "homicídio", "tráfico",
        "execução penal", "progressão", "regime", "prisão preventiva",
        "habeas corpus", "recurso especial", "agravo", "apelação",
        "prescrição", "reincidência", "detração", "remição",
        "livramento condicional", "sursis", "pena", "sentença"
    ]
    
    for doc in docs:
        # Cluster
        cluster = doc.get("cluster_name", "")
        if cluster:
            clusters[cluster] += 1
        
        # Tribunal
        tribunal = doc.get("court", "")
        if tribunal:
            tribunais[tribunal] += 1
        
        # Conteúdo
        content = doc.get("content", "")
        title = doc.get("title", "")
        texto_completo = f"{title} {content}".lower()
        
        # Extrai artigos
        artigos = extrair_artigos(texto_completo)
        for artigo in artigos:
            artigos_counter[artigo] += 1
        
        # Palavras-chave
        for keyword in keywords:
            if keyword.lower() in texto_completo:
                palavras_chave[keyword] += 1
    
    stats = {
        "total_docs": total,
        "top_clusters": clusters.most_common(10),
        "top_artigos": artigos_counter.most_common(20),
        "top_palavras_chave": palavras_chave.most_common(20),
        "top_tribunais": tribunais.most_common(10)
    }
    
    return stats


def exibir_analise(stats: Dict[str, Any]):
    """Exibe análise do corpus."""
    print("\n" + "=" * 80)
    print("📊 ANÁLISE DO CORPUS")
    print("=" * 80)
    
    print(f"\n📚 Total de documentos analisados: {stats['total_docs']}")
    
    print("\n🏛️ Top 10 Clusters:")
    for cluster, count in stats['top_clusters']:
        print(f"  - {cluster}: {count}")
    
    print("\n📜 Top 20 Artigos mais citados:")
    for artigo, count in stats['top_artigos']:
        print(f"  - Art. {artigo}: {count} menções")
    
    print("\n🔑 Top 20 Palavras-chave jurídicas:")
    for palavra, count in stats['top_palavras_chave']:
        print(f"  - {palavra}: {count} docs")
    
    if stats['top_tribunais']:
        print("\n⚖️ Top 10 Tribunais:")
        for tribunal, count in stats['top_tribunais']:
            print(f"  - {tribunal}: {count}")
    
    print("=" * 80)


def fazer_query(query: str, k: int = 5) -> Dict[str, Any]:
    """Faz query na API e retorna resultados."""
    try:
        response = requests.post(
            f"{API_URL}/search",
            json={"q": query, "k": k},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None


def gerar_queries_estrategicas(stats: Dict[str, Any]) -> List[str]:
    """Gera lista de queries estratégicas baseadas na análise."""
    queries = []
    
    # Queries específicas com múltiplos termos técnicos (maior chance de 80%+)
    queries.extend([
        # Variações das top 3 queries (78%, 77%, 76%)
        "habeas corpus execução penal progressão regime",
        "reincidência execução penal requisitos objetivos",
        "progressão regime execução penal lapso temporal",
        "habeas corpus execução penal prisão preventiva",
        "progressão regime fechado semiaberto requisitos",
        "reincidência execução penal agravante",
        
        # Prescrição (75%)
        "prescrição execução penal prazo",
        "prescrição execução penal interrupção",
        "prescrição pena execução penal",
        
        # Prisão preventiva com mais contexto
        "prisão preventiva requisitos execução penal",
        "prisão preventiva fundamentação necessidade",
        "prisão preventiva medidas cautelares alternativas",
        
        # Remição e detração com contexto
        "remição pena trabalho estudo execução penal",
        "detração penal execução preventiva",
        "remição pena execução penal dias trabalhados",
        
        # Livramento condicional específico
        "livramento condicional requisitos objetivos subjetivos",
        "livramento condicional execução penal progressão",
        
        # Regime prisional com mais detalhes
        "regime fechado progressão semiaberto requisitos",
        "regime semiaberto progressão aberto",
        "regime aberto execução penal requisitos",
        
        # Habeas corpus variações
        "habeas corpus execução penal ilegalidade",
        "habeas corpus execução penal constrangimento ilegal",
        
        # Penas alternativas
        "pena restritiva direitos execução penal",
        "prisão domiciliar execução penal requisitos",
        "sursis pena suspensa condicional",
        
        # Combinações artigos + execução
        "artigo 112 LEP progressão regime",
        "artigo 33 execução penal regime prisional",
        "artigo 121 homicídio execução penal",
        "artigo 157 roubo execução penal",
        
        # Termos muito específicos
        "exame criminológico progressão regime",
        "falta grave execução penal regressão",
        "bom comportamento carcerário progressão",
        "indulto comutação pena execução penal"
    ])
    
    return queries


def testar_queries(queries: List[str], threshold: float = THRESHOLD_SCORE) -> Dict[str, Any]:
    """Testa queries e identifica as com alta relevância."""
    print(f"\n🔬 Testando {len(queries)} queries...")
    print(f"🎯 Threshold de relevância: {threshold * 100}%\n")
    
    resultados_alto_score = []
    todas_queries_resultado = []
    
    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] Testando: '{query}'", end=" ")
        
        resultado = fazer_query(query, k=5)
        
        if resultado and resultado.get("results"):
            results = resultado["results"]
            max_score = max([r["score"] for r in results])
            avg_score = sum([r["score"] for r in results]) / len(results)
            
            query_info = {
                "query": query,
                "max_score": round(max_score, 4),
                "avg_score": round(avg_score, 4),
                "total_results": len(results),
                "top_result": {
                    "id": results[0]["id"],
                    "title": results[0]["title"],
                    "score": round(results[0]["score"], 4)
                }
            }
            
            todas_queries_resultado.append(query_info)
            
            if max_score >= threshold:
                print(f"✅ MAX: {max_score:.2%}")
                resultados_alto_score.append(query_info)
            else:
                print(f"⚠️ MAX: {max_score:.2%}")
        else:
            print("❌ Sem resultados")
        
        time.sleep(0.5)  # Evita sobrecarga da API
    
    return {
        "total_queries": len(queries),
        "queries_alto_score": resultados_alto_score,
        "todas_queries": todas_queries_resultado,
        "threshold": threshold
    }


def exibir_resultados(resultados: Dict[str, Any]):
    """Exibe resultados das queries."""
    print("\n" + "=" * 80)
    print(f"🎯 QUERIES COM ≥{resultados['threshold'] * 100}% DE RELEVÂNCIA")
    print("=" * 80)
    
    queries_alto = resultados["queries_alto_score"]
    
    if not queries_alto:
        print("\n❌ Nenhuma query atingiu o threshold!")
        print("\n💡 Top 10 queries por relevância:")
        todas = sorted(
            resultados["todas_queries"],
            key=lambda x: x["max_score"],
            reverse=True
        )[:10]
        
        for i, q in enumerate(todas, 1):
            print(f"\n{i}. Query: '{q['query']}'")
            print(f"   Max Score: {q['max_score']:.2%}")
            print(f"   Avg Score: {q['avg_score']:.2%}")
            print(f"   Top Result: {q['top_result']['title']} (ID: {q['top_result']['id']})")
    else:
        print(f"\n✅ {len(queries_alto)} queries atingiram o threshold!\n")
        
        # Ordena por max_score
        queries_alto_sorted = sorted(
            queries_alto,
            key=lambda x: x["max_score"],
            reverse=True
        )
        
        for i, q in enumerate(queries_alto_sorted, 1):
            print(f"{i}. Query: '{q['query']}'")
            print(f"   Max Score: {q['max_score']:.2%} | Avg: {q['avg_score']:.2%}")
            print(f"   Top Result: {q['top_result']['title']} (ID: {q['top_result']['id']})")
            print()
    
    print("=" * 80)


def salvar_relatorio(stats: Dict[str, Any], resultados: Dict[str, Any], output: str):
    """Salva relatório completo em JSON."""
    relatorio = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "corpus_stats": stats,
        "query_results": resultados
    }
    
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Relatório salvo em: {output_path}")


def main():
    """Execução principal."""
    print("=" * 80)
    print("🔍 ANÁLISE DE CORPUS E TESTE DE QUERIES")
    print("=" * 80)
    
    # 1. Carrega e analisa corpus
    docs = carregar_merged_clean()
    stats = analisar_corpus(docs)
    exibir_analise(stats)
    
    # 2. Gera queries estratégicas
    print("\n📝 Gerando queries estratégicas...")
    queries = gerar_queries_estrategicas(stats)
    print(f"✅ {len(queries)} queries geradas")
    
    # 3. Testa queries
    resultados = testar_queries(queries, threshold=THRESHOLD_SCORE)
    
    # 4. Exibe resultados
    exibir_resultados(resultados)
    
    # 5. Salva relatório
    salvar_relatorio(stats, resultados, "reports/inspect/query_analysis.json")
    
    print("\n✅ Análise concluída!")


if __name__ == "__main__":
    main()
