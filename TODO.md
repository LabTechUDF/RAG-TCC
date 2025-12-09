### 🚧 In Progress
1. **STF Data Collection**
   - ✅ Working `stf_jurisprudencia` spider (tested, produces data)
   - 📝 Focus on criminal law decisions (art. 171 §3 - estelionato previdenciário)

2. **✨ RAG SEEU Implementation (NEW - 2024-12-08)**
   - ✅ **Schemas Pydantic** - Estruturas de dados para RAG jurídico (`src/rag_schemas.py`)
   - ✅ **Normalização Jurídica** - Query rewriting com LLM (`src/rag_normalizer.py`)
   - ✅ **Serviço RAG Orquestrador** - Fluxo completo RAG (`src/rag_service.py`)
   - ✅ **Endpoint `/api/rag/query`** - API principal para consultas SEEU
   - ✅ **Sistema de Chunking** - Quebra inteligente de documentos (`src/chunking.py`)
   - ✅ **Cálculo de Relevância Relativa** - Normalização softmax de scores
   - ✅ **Templates de Prompt** - Normalizador + SEEU especializados
   - ✅ **Documentação Completa** - README, exemplos e testes
   - 📝 **Status**: Core implementado, pronto para integração com dados reais

### 📋 Next Steps
1. **Vector Database Setup**
   - [x] Set up FAISS dockerized
   - [x] Configure vector storage for STF legal content
   - [x] Test embedding generation

2. **Data Processing**
   - [ ] Collect quality STF legal decisions
   - [ ] **Adaptar pipeline de indexação para usar chunking** 🆕
   - [ ] Create embeddings/chunks for legal content
   - [ ] Focus on art. 171 §3 criminal cases
   - [x] Implement text chunking for long decisions ✅

3. **RAG Implementation**
   - [x] Build retrieval system ✅
   - [x] Test query-document matching ✅
   - [x] Create API endpoints for legal queries ✅
   - [ ] **Integrar com dados STF/STJ reais** 🆕
   - [ ] **Testar fluxo completo end-to-end** 🆕
   - [ ] **Adicionar filtros de metadados na busca** 🆕