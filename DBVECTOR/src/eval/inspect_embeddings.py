"""
Script de inspeção de embeddings.
Detecta vetores inválidos, colapsados e duplicatas densas.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

from src import config, embeddings


def load_embeddings_from_jsonl(filepath: Path) -> np.ndarray:
    """
    Carrega embeddings de arquivo JSONL.
    Assume que cada linha tem campo 'vector'.
    """
    vectors = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            doc = json.loads(line)
            if "vector" in doc:
                vectors.append(doc["vector"])
    
    return np.array(vectors, dtype=np.float32)


def load_embeddings_from_npy(filepath: Path) -> np.ndarray:
    """Carrega embeddings de arquivo .npy."""
    return np.load(filepath)


def generate_embeddings_from_jsonl(filepath: Path) -> np.ndarray:
    """
    Gera embeddings on-the-fly de arquivo JSONL.
    Procura por campos de texto comuns: text, content, body, conteudo, resumo, summary, title.
    """
    # Lista de campos de texto a verificar (em ordem de prioridade)
    text_fields = ["text", "content", "body", "conteudo", "resumo", "summary", "title"]
    
    texts = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            # Procura pelo primeiro campo de texto disponível
            text = None
            for field in text_fields:
                if field in doc and isinstance(doc[field], str) and doc[field].strip():
                    text = doc[field].strip()
                    break
            
            if text:
                texts.append(text)
    
    if not texts:
        raise ValueError(
            f"Nenhum texto encontrado no arquivo '{filepath}'. "
            f"Campos verificados: {', '.join(text_fields)}"
        )
    
    print(f"🔧 Gerando embeddings para {len(texts)} textos...")
    vectors = embeddings.encode_texts(texts)
    
    return vectors


def inspect_embeddings(vectors: np.ndarray, near_dupes_threshold: float = 0.995) -> Dict[str, Any]:
    """
    Inspeciona embeddings e retorna relatório.
    
    Args:
        vectors: Array de vetores (N x D)
        near_dupes_threshold: Threshold de similaridade para near-duplicates
    
    Returns:
        Dicionário com métricas de inspeção
    """
    num_vectors, dim = vectors.shape
    
    # 1. Dimensão
    expected_dim = config.EMBEDDING_DIM
    dim_ok = (dim == expected_dim)
    
    # 2. NaN/Inf
    has_nan = np.isnan(vectors).any()
    has_inf = np.isinf(vectors).any()
    num_nan = np.isnan(vectors).sum()
    num_inf = np.isinf(vectors).sum()
    
    # 3. Norma L2
    norms = np.linalg.norm(vectors, axis=1)
    norm_mean = float(np.mean(norms))
    norm_p5 = float(np.percentile(norms, 5))
    norm_p95 = float(np.percentile(norms, 95))
    
    # Detecta colapso (normas muito baixas)
    collapsed = (norms < 0.1).sum()
    collapsed_pct = (collapsed / num_vectors) * 100
    
    # 4. Distribuição de distâncias (amostragem)
    # Amostra no máximo 1000 pares para não explodir memória
    sample_size = min(num_vectors, 1000)
    sample_indices = np.random.choice(num_vectors, size=sample_size, replace=False)
    sample_vectors = vectors[sample_indices]
    
    # Normaliza para cosine similarity
    sample_normalized = sample_vectors / (np.linalg.norm(sample_vectors, axis=1, keepdims=True) + 1e-8)
    
    # Calcula matriz de similaridade
    similarity_matrix = np.dot(sample_normalized, sample_normalized.T)
    
    # Remove diagonal (auto-similaridade)
    mask = ~np.eye(sample_size, dtype=bool)
    similarities = similarity_matrix[mask]
    
    sim_mean = float(np.mean(similarities))
    sim_p5 = float(np.percentile(similarities, 5))
    sim_p95 = float(np.percentile(similarities, 95))
    
    # 5. Near-duplicates (similaridade >= threshold)
    # Conta pares únicos com alta similaridade
    near_dupes = 0
    
    # Para evitar O(N²), amostra se muitos vetores
    if num_vectors > 1000:
        check_size = 1000
        check_indices = np.random.choice(num_vectors, size=check_size, replace=False)
        check_vectors = vectors[check_indices]
    else:
        check_vectors = vectors
    
    # Normaliza
    check_normalized = check_vectors / (np.linalg.norm(check_vectors, axis=1, keepdims=True) + 1e-8)
    
    # Matriz de similaridade
    sim_matrix = np.dot(check_normalized, check_normalized.T)
    
    # Conta pares acima do threshold (excluindo diagonal)
    upper_triangle = np.triu(sim_matrix, k=1)
    near_dupes = (upper_triangle >= near_dupes_threshold).sum()
    
    # Extrapola para dataset completo se foi amostrado
    if num_vectors > 1000:
        scale_factor = (num_vectors / check_size) ** 2
        near_dupes = int(near_dupes * scale_factor)
    
    near_dupes_pct = (near_dupes / (num_vectors * (num_vectors - 1) / 2)) * 100
    
    # Relatório (converte todos os valores NumPy para tipos nativos Python)
    report = {
        "num_vectors": int(num_vectors),
        "dimension": int(dim),
        "expected_dimension": int(expected_dim),
        "dimension_ok": bool(dim_ok),
        "has_nan": bool(has_nan),
        "has_inf": bool(has_inf),
        "num_nan": int(num_nan),
        "num_inf": int(num_inf),
        "norm_l2": {
            "mean": round(float(norm_mean), 4),
            "p5": round(float(norm_p5), 4),
            "p95": round(float(norm_p95), 4)
        },
        "collapsed_vectors": int(collapsed),
        "collapsed_pct": round(float(collapsed_pct), 2),
        "cosine_similarity": {
            "mean": round(float(sim_mean), 4),
            "p5": round(float(sim_p5), 4),
            "p95": round(float(sim_p95), 4)
        },
        "near_duplicates": {
            "count": int(near_dupes),
            "pct": round(float(near_dupes_pct), 4),
            "threshold": float(near_dupes_threshold)
        }
    }
    
    return report


def main():
    """CLI principal para inspeção de embeddings."""
    parser = argparse.ArgumentParser(
        description="Inspeciona embeddings para detectar problemas"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Arquivo de entrada (.npy, .jsonl com 'vector' ou .jsonl com 'text')"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="auto",
        choices=["auto", "npy", "vectors-jsonl", "generate"],
        help="Modo de carregamento (default: auto)"
    )
    parser.add_argument(
        "--report",
        type=str,
        default="reports/inspect/embeddings_summary.json",
        help="Caminho para salvar relatório JSON"
    )
    parser.add_argument(
        "--near-dupes-threshold",
        type=float,
        default=0.995,
        help="Threshold de similaridade para near-duplicates (default: 0.995)"
    )
    parser.add_argument(
        "--near-dupes-max-pct",
        type=float,
        default=config.NEAR_DUPES_MAX_PCT,
        help=f"% máxima de near-duplicates (default: {config.NEAR_DUPES_MAX_PCT})"
    )
    
    args = parser.parse_args()
    
    # Valida arquivo de entrada
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Erro: Arquivo não encontrado: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"🔍 Inspeção de Embeddings")
    print(f"📄 Input: {input_path}")
    print()
    
    # Determina modo
    mode = args.mode
    if mode == "auto":
        if input_path.suffix == ".npy":
            mode = "npy"
        else:
            # Tenta detectar se tem 'vector' ou campos de texto
            text_fields = ["text", "content", "body", "conteudo", "resumo", "summary", "title"]
            with open(input_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    sample = json.loads(first_line)
                    if "vector" in sample:
                        mode = "vectors-jsonl"
                    elif any(field in sample for field in text_fields):
                        mode = "generate"
                    else:
                        print(f"❌ Erro: Não foi possível determinar formato do arquivo. "
                              f"Campos esperados: 'vector' ou um de {text_fields}", file=sys.stderr)
                        sys.exit(1)
    
    print(f"🔧 Modo: {mode}")
    
    # Carrega embeddings
    try:
        if mode == "npy":
            vectors = load_embeddings_from_npy(input_path)
        elif mode == "vectors-jsonl":
            vectors = load_embeddings_from_jsonl(input_path)
        elif mode == "generate":
            vectors = generate_embeddings_from_jsonl(input_path)
        else:
            print(f"❌ Erro: Modo inválido: {mode}", file=sys.stderr)
            sys.exit(1)
        
        print(f"✅ {len(vectors)} vetores carregados (dim={vectors.shape[1]})")
    
    except Exception as e:
        print(f"❌ Erro ao carregar embeddings: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Executa inspeção
    print()
    print("🔍 Executando inspeção...")
    report = inspect_embeddings(vectors, near_dupes_threshold=args.near_dupes_threshold)
    
    # Exibe resultados
    print()
    print("=" * 60)
    print("📈 Resultados:")
    print(f"   Vetores: {report['num_vectors']}")
    print(f"   Dimensão: {report['dimension']} (esperado: {report['expected_dimension']})")
    print()
    
    print("🔬 Validação:")
    print(f"   Dimensão OK: {report['dimension_ok']}")
    print(f"   NaN: {report['num_nan']} {'❌' if report['has_nan'] else '✅'}")
    print(f"   Inf: {report['num_inf']} {'❌' if report['has_inf'] else '✅'}")
    print()
    
    print("📏 Norma L2:")
    print(f"   Média: {report['norm_l2']['mean']:.4f}")
    print(f"   P5: {report['norm_l2']['p5']:.4f}")
    print(f"   P95: {report['norm_l2']['p95']:.4f}")
    print(f"   Colapsados: {report['collapsed_vectors']} ({report['collapsed_pct']:.2f}%)")
    print()
    
    print("🔍 Similaridade (Cosine):")
    print(f"   Média: {report['cosine_similarity']['mean']:.4f}")
    print(f"   P5: {report['cosine_similarity']['p5']:.4f}")
    print(f"   P95: {report['cosine_similarity']['p95']:.4f}")
    print()
    
    print("🔁 Near-Duplicates:")
    print(f"   Threshold: {report['near_duplicates']['threshold']}")
    print(f"   Count: {report['near_duplicates']['count']}")
    print(f"   %: {report['near_duplicates']['pct']:.4f}%")
    print("=" * 60)
    
    # Salva relatório
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print()
    print(f"💾 Relatório salvo em: {report_path}")
    
    # Gating: verifica problemas críticos
    print()
    failed = False
    
    if report["has_nan"]:
        print(f"❌ FALHA: Vetores contêm NaN ({report['num_nan']} valores)")
        failed = True
    
    if report["has_inf"]:
        print(f"❌ FALHA: Vetores contêm Inf ({report['num_inf']} valores)")
        failed = True
    
    if report["near_duplicates"]["pct"] > args.near_dupes_max_pct:
        print(f"❌ FALHA: Near-duplicates = {report['near_duplicates']['pct']:.4f}% > {args.near_dupes_max_pct}%")
        failed = True
    else:
        print(f"✅ OK: Near-duplicates = {report['near_duplicates']['pct']:.4f}% <= {args.near_dupes_max_pct}%")
    
    if failed:
        print()
        print("❌ Inspeção encontrou problemas críticos!")
        sys.exit(2)
    else:
        print()
        print("✅ Inspeção aprovada!")
        sys.exit(0)


if __name__ == "__main__":
    main()
