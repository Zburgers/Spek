# RAG Document Processing System

This document explains the RAG (Retrieval-Augmented Generation) system implemented for document processing and querying.

## Overview

The RAG system allows users to upload documents (PDF, TXT, DOCX) and query them using natural language questions. The system extracts text from documents, processes them into chunks, and uses Google Gemini AI to answer questions based on the document content.

## Architecture

### Backend Components

1. **DocumentProcessor Service** (`src/app/services/document_processor.py`)
   - Handles text extraction from various file formats
   - Cleans and normalizes extracted text
   - Splits text into manageable chunks with overlap
   - Supports PDF, TXT, and DOCX file types

2. **RAGService** (`src/app/services/rag_service.py`)
   - Manages document querying using RAG approach
   - Finds relevant text chunks using keyword-based similarity
   - Generates answers using Google Gemini AI with context
   - Returns confidence scores and relevant excerpts

3. **Document API** (`src/app/api/v1/documents.py`)
   - RESTful endpoints for document operations
   - Background processing for uploaded documents
   - Status tracking and error handling

4. **Database Models** (`src/app/models/document.py`)
   - Stores document metadata and content
   - Tracks processing status and extracted text

### Frontend Components

1. **Documents Page** (`static/documents.html`)
   - User interface for document management
   - Upload interface with drag-and-drop support
   - Document library with status indicators
   - Query interface for natural language questions

2. **JavaScript Client** (`static/js/documents.js`)
   - Handles file uploads and processing
   - Manages real-time status updates
   - Provides interactive querying interface

## Features

### Document Upload
- **Supported Formats**: PDF, TXT, DOCX
- **File Size Limit**: 10MB per file
- **Processing**: Asynchronous background processing
- **Status Tracking**: Real-time updates on processing progress

### Document Processing Pipeline
1. **Upload**: File is uploaded and stored with hex encoding
2. **Background Processing**: 
   - Text extraction using appropriate parser
   - Text cleaning and normalization
   - Status updates in database
3. **Ready for Querying**: Processed documents become queryable

### RAG Querying
1. **Text Chunking**: Documents split into overlapping segments
2. **Relevance Scoring**: Keyword-based similarity scoring
3. **Context Retrieval**: Most relevant chunks selected
4. **AI Generation**: Gemini AI generates answers using context
5. **Response**: Answer with confidence score and source excerpts

## API Endpoints

### Document Upload
```
POST /api/v1/documents/upload
Content-Type: multipart/form-data

Body: file (multipart upload)
```

### List Documents
```
GET /api/v1/documents
```

### Get Document
```
GET /api/v1/documents/{document_id}
```

### Query Document
```
POST /api/v1/documents/query
Content-Type: application/json

{
  "document_id": "uuid",
  "query": "What does this document say about...?",
  "session_id": "optional"
}
```

## Document States

- **uploaded**: File uploaded, waiting for processing
- **processing**: Text extraction in progress
- **processed**: Ready for querying
- **error**: Processing failed
- **unsupported_type**: File type not supported

## Configuration

### Required Environment Variables
```bash
AI_API_KEY=your_google_gemini_api_key
```

### Dependencies
```python
pypdf>=4.0.0          # PDF text extraction
python-docx>=1.1.0    # DOCX text extraction
google-genai>=0.5.4   # Google Gemini AI client
```

## Usage Examples

### Basic Document Query Flow
1. User uploads a PDF document about cats
2. System extracts text: "Cats are independent animals..."
3. User asks: "What does the document say about cat behavior?"
4. System finds relevant chunks mentioning cats and behavior
5. Gemini AI generates response using the relevant context
6. User receives answer with confidence score and source excerpts

### Frontend Usage
1. Navigate to `/documents`
2. Drag and drop or click to upload a document
3. Wait for processing (status updates automatically)
4. Click on processed document to select it
5. Type a natural language question
6. View AI-generated answer with sources

## Technical Details

### Text Chunking Algorithm
- **Chunk Size**: 800 characters (configurable)
- **Overlap**: 100 characters to maintain context
- **Boundary Detection**: Attempts to break at sentence/word boundaries
- **Context Preservation**: Overlapping chunks ensure no information loss

### Relevance Scoring
- **Keyword Matching**: Intersection of query and chunk terms
- **Exact Phrase Bonus**: +0.5 score for exact phrase matches
- **Normalization**: Scores normalized to 0-1 range
- **Threshold**: Only chunks with relevance > 0 returned

### AI Integration
- **Model**: gemini-2.0-flash-001
- **Temperature**: 0.3 (factual responses)
- **Max Tokens**: 1024
- **Context Window**: Up to 5 most relevant chunks

## Future Enhancements

### Planned Improvements
1. **Embedding-based Similarity**: Replace keyword matching with semantic embeddings
2. **Vector Database**: Store and search document embeddings efficiently
3. **Multi-document Queries**: Query across multiple documents simultaneously
4. **Advanced Chunking**: Semantic-aware chunking strategies
5. **Citation Tracking**: Precise location references in source documents

### Performance Optimizations
1. **Caching**: Cache frequently accessed chunks and embeddings
2. **Batch Processing**: Process multiple documents efficiently
3. **Incremental Updates**: Update only changed document parts
4. **Compression**: Optimize storage of processed text

## Testing

The system includes comprehensive tests:
- **Unit Tests**: Document processor and RAG service functionality
- **Mocked Dependencies**: External AI API calls mocked for testing
- **Error Handling**: Various failure scenarios tested
- **Edge Cases**: Empty documents, unsupported formats, etc.

Run tests with:
```bash
python -m pytest tests/test_document_processor.py
python -m pytest tests/test_rag_service.py
```

## Troubleshooting

### Common Issues

1. **"AI_API_KEY not configured"**
   - Ensure Google Gemini API key is set in environment variables

2. **"Unsupported file type"**
   - Only PDF, TXT, and DOCX files are supported
   - Check file extension and MIME type

3. **"Document processing failed"**
   - File may be corrupted or password-protected
   - Check document format and integrity

4. **"No relevant content found"**
   - Query may be too specific or unrelated to document content
   - Try broader or different question phrasing

### Debug Mode
Enable debug logging to see detailed processing information:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```