"""
LoanLens AI — Service Layer

All pipeline services:
  - extraction_service  → PDF text extraction (PyMuPDF + Gemini Vision OCR)
  - chunking_service    → Semantic document chunking
  - vector_service      → ChromaDB vector storage + Gemini embeddings
  - gemini_service      → Gemini RAG analysis + Ask AI
  - insight_engine      → Rule-based risk scoring + normalization
  - analysis_service    → Pipeline orchestrator
  - document_service    → Document CRUD
"""
