"""
Script de avaliação de recuperação para RAG Jurídico.
Calcula métricas: Precision@K, Recall@K, MRR, nDCG.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import math

from src import config, embeddings
from src.storage.factory import get_store


def load_qa_dataset(filepath: Path) -> List[Dict[str, Any]]:
    """Carrega dataset de avaliação (Q&A pairs)."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """
    Calcula Precision@K.
    
    P@K = (# docs relevantes nos top-K) / K
    """
    if k == 0:
        return 0.0
    
    top_k = retrieved_ids[:k]
    relevant_retrieved = len([doc_id for doc_id in top_k if doc_id in relevant_ids])
    
    return relevant_retrieved / k


def recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """
    Calcula Recall@K.
    
    R@K = (# docs relevantes nos top-K) / (# total de docs relevantes)
    """
    if len(relevant_ids) == 0:
        return 0.0
    
    top_k = retrieved_ids[:k]
    relevant_retrieved = len([doc_id for doc_id in top_k if doc_id in relevant_ids])
    
    return relevant_retrieved / len(relevant_ids)


def mean_reciprocal_rank(retrieved_ids: List[str], relevant_ids: List[str]) -> float:
    """
    Calcula MRR (Mean Reciprocal Rank) para uma query.
    
    MRR = 1 / (posição do primeiro doc relevante)
    Se nenhum doc relevante, retorna 0.
    """
    for i, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / i
    
    return 0.0


def dcg_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """
    Calcula DCG@K (Discounted Cumulative Gain).
    
    DCG@K = Σ (rel_i / log2(i + 1)) para i=1..K
    onde rel_i = 1 se doc é relevante, 0 caso contrário.
    """
    dcg = 0.0
    top_k = retrieved_ids[:k]
    
    for i, doc_id in enumerate(top_k, start=1):
        relevance = 1.0 if doc_id in relevant_ids else 0.0
        dcg += relevance / math.log2(i + 1)
    
    return dcg


def ndcg_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """
    Calcula nDCG@K (Normalized DCG).
    
    nDCG@K = DCG@K / IDCG@K
    onde IDCG@K é o DCG ideal (todos docs relevantes no topo).
    """
    if len(relevant_ids) == 0:
        return 0.0
    
    # DCG real
    actual_dcg = dcg_at_k(retrieved_ids, relevant_ids, k)
    
    # IDCG: ordenação ideal (todos relevantes no topo)
    ideal_ranking = relevant_ids + [f"dummy_{i}" for i in range(k)]
    ideal_dcg = dcg_at_k(ideal_ranking, relevant_ids, k)
    
    if ideal_dcg == 0.0:
        return 0.0
    
    return actual_dcg / ideal_dcg


def evaluate_query(
    query: str,
    relevant_ids: List[str],
    store,
    k: int = 5
) -> Dict[str, float]:
    """
    Avalia uma query e retorna métricas.
    """
    # Gera embedding da query
    query_vector = embeddings.encode_single_text(query)
    
    # Busca documentos
    results = store.search(query_vector, k=k)
    retrieved_ids = [result.doc.id for result in results]
    
    # Calcula métricas
    metrics = {
        f"p@{k}": precision_at_k(retrieved_ids, relevant_ids, k),
        f"r@{k}": recall_at_k(retrieved_ids, relevant_ids, k),
        "mrr": mean_reciprocal_rank(retrieved_ids, relevant_ids),
        f"ndcg@{k}": ndcg_at_k(retrieved_ids, relevant_ids, k),
    }
    
    return metrics, retrieved_ids


def evaluate_dataset(
    qa_data: List[Dict[str, Any]],
    store,
    k: int = 5
) -> Dict[str, Any]:
    """
    Avalia dataset completo e retorna métricas agregadas.
    """
    all_metrics = []
    query_details = []
    
    for item in qa_data:
        qid = item["qid"]
        pergunta = item["pergunta"]
        relevant_ids = item["doc_ids_relevantes"]
        
        # Avalia query
        metrics, retrieved_ids = evaluate_query(pergunta, relevant_ids, store, k)
        all_metrics.append(metrics)
        
        # Detalhes para debug
        query_details.append({
            "qid": qid,
            "pergunta": pergunta,
            "relevant_ids": relevant_ids,
            "retrieved_ids": retrieved_ids,
            **metrics
        })
    
    # Média das métricas
    avg_metrics = {}
    for key in all_metrics[0].keys():
        avg_metrics[key] = sum(m[key] for m in all_metrics) / len(all_metrics)
    
    return {
        "num_queries": len(qa_data),
        "k": k,
        "avg_metrics": avg_metrics,
        "query_details": query_details
    }


def main():
    """CLI principal para avaliação de recuperação."""
    parser = argparse.ArgumentParser(
        description="Avalia métricas de recuperação (P@K, R@K, MRR, nDCG)"
    )
    parser.add_argument(
        "--qa",
        type=str,
        required=True,
        help="Caminho para dataset QA (JSONL com qid, pergunta, doc_ids_relevantes)"
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Valor de K para métricas @K (default: 5)"
    )
    parser.add_argument(
        "--backend",
        type=str,
        default=config.SEARCH_BACKEND,
        choices=["faiss", "opensearch"],
        help=f"Backend de busca (default: {config.SEARCH_BACKEND})"
    )
    parser.add_argument(
        "--report",
        type=str,
        default="reports/eval/retrieval_metrics.json",
        help="Caminho para salvar relatório JSON"
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="reports/eval/retrieval_metrics.csv",
        help="Caminho para salvar CSV com detalhes por query"
    )
    parser.add_argument(
        "--min-p",
        type=float,
        default=config.MIN_P5,
        help=f"Threshold mínimo de Precision@K (default: {config.MIN_P5})"
    )
    parser.add_argument(
        "--min-ndcg",
        type=float,
        default=config.MIN_NDCG5,
        help=f"Threshold mínimo de nDCG@K (default: {config.MIN_NDCG5})"
    )
    
    args = parser.parse_args()
    
    # Valida arquivo QA
    qa_path = Path(args.qa)
    if not qa_path.exists():
        print(f"❌ Erro: Arquivo não encontrado: {qa_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"📊 Avaliação de Recuperação")
    print(f"📄 Dataset: {qa_path}")
    print(f"🔍 Backend: {args.backend}")
    print(f"📏 K: {args.k}")
    print()
    
    # Configura backend
    import os
    original_backend = os.getenv("SEARCH_BACKEND")
    os.environ["SEARCH_BACKEND"] = args.backend
    
    try:
        # Carrega dataset
        qa_data = load_qa_dataset(qa_path)
        print(f"✅ {len(qa_data)} queries carregadas")
        
        # Inicializa store
        print(f"🔧 Inicializando {args.backend} store...")
        store = get_store()
        doc_count = store.get_doc_count()
        print(f"📚 {doc_count} documentos disponíveis")
        
        if doc_count == 0:
            print("❌ Erro: Nenhum documento indexado!", file=sys.stderr)
            sys.exit(1)
        
        # Executa avaliação
        print()
        print("🔍 Executando avaliação...")
        results = evaluate_dataset(qa_data, store, k=args.k)
        
        # Exibe resultados
        print()
        print("=" * 60)
        print("📈 Resultados:")
        print(f"   Queries avaliadas: {results['num_queries']}")
        print(f"   K: {results['k']}")
        print()
        
        avg = results["avg_metrics"]
        print(f"   Precision@{args.k}: {avg[f'p@{args.k}']:.4f}")
        print(f"   Recall@{args.k}: {avg[f'r@{args.k}']:.4f}")
        print(f"   MRR: {avg['mrr']:.4f}")
        print(f"   nDCG@{args.k}: {avg[f'ndcg@{args.k}']:.4f}")
        print("=" * 60)
        
        # Salva relatório JSON
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print()
        print(f"💾 Relatório JSON salvo em: {report_path}")
        
        # Salva CSV
        if args.csv:
            csv_path = Path(args.csv)
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            
            import csv
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                if results["query_details"]:
                    fieldnames = list(results["query_details"][0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for detail in results["query_details"]:
                        # Converte listas para strings
                        row = detail.copy()
                        row["relevant_ids"] = ",".join(row["relevant_ids"])
                        row["retrieved_ids"] = ",".join(row["retrieved_ids"])
                        writer.writerow(row)
            
            print(f"💾 CSV salvo em: {csv_path}")
        
        # Gating: verifica thresholds
        print()
        pk_key = f"p@{args.k}"
        ndcg_key = f"ndcg@{args.k}"
        
        p_value = avg[pk_key]
        ndcg_value = avg[ndcg_key]
        
        failed = False
        
        if p_value < args.min_p:
            print(f"❌ FALHA: Precision@{args.k} = {p_value:.4f} < {args.min_p}")
            failed = True
        else:
            print(f"✅ OK: Precision@{args.k} = {p_value:.4f} >= {args.min_p}")
        
        if ndcg_value < args.min_ndcg:
            print(f"❌ FALHA: nDCG@{args.k} = {ndcg_value:.4f} < {args.min_ndcg}")
            failed = True
        else:
            print(f"✅ OK: nDCG@{args.k} = {ndcg_value:.4f} >= {args.min_ndcg}")
        
        if failed:
            print()
            print("❌ Avaliação não passou nos thresholds mínimos!")
            sys.exit(2)
        else:
            print()
            print("✅ Avaliação aprovada!")
            sys.exit(0)
    
    except Exception as e:
        print(f"❌ Erro durante avaliação: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # Restaura backend original
        if original_backend:
            os.environ["SEARCH_BACKEND"] = original_backend
        else:
            os.environ.pop("SEARCH_BACKEND", None)


if __name__ == "__main__":
    main()
