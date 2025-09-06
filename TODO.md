### 🚧 In Progress
1. **STF Data Collection**
   - ✅ Working `stf_clipboard` spider (tested, produces data)
   - 🔄 Testing new `stf_legal` spider
   - 📝 Focus on criminal law decisions (art. 171 §3 - estelionato previdenciário)

### 📋 Next Steps
1. **Vector Database Setup**
   - [ ] Set up FAISS dockerized
   - [ ] Configure vector storage for STF legal content
   - [ ] Test embedding generation

2. **Data Processing**
   - [ ] Collect quality STF legal decisions
   - [ ] Create embeddings/chunks for legal content
   - [ ] Focus on art. 171 §3 criminal cases
   - [ ] Implement text chunking for long decisions

3. **RAG Implementation**
   - [ ] Build retrieval system
   - [ ] Test query-document matching
   - [ ] Create API endpoints for legal queries