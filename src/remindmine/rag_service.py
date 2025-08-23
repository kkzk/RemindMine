"""RAG service using ChromaDB for issue similarity search."""

import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
import requests
import json
import os

logger = logging.getLogger(__name__)


class OllamaEmbeddings:
    """Simple Ollama embeddings wrapper."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents."""
        embeddings = []
        for text in texts:
            embedding = self._get_embedding(text)
            if embedding:
                embeddings.append(embedding)
            else:
                # Fallback to zeros if embedding fails
                embeddings.append([0.0] * 384)  # Default dimension
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        embedding = self._get_embedding(text)
        return embedding if embedding else [0.0] * 384
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding from Ollama."""
        try:
            url = f"{self.base_url}/api/embeddings"
            data = {
                "model": self.model,
                "prompt": text
            }
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get("embedding")
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return None


class RAGService:
    """RAG service for issue search and advice generation."""
    
    def __init__(self, chromadb_path: str, ollama_base_url: str, ollama_model: str):
        """Initialize RAG service.
        
        Args:
            chromadb_path: Path to ChromaDB storage
            ollama_base_url: Ollama base URL
            ollama_model: Ollama model name
        """
        self.chromadb_path = chromadb_path
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Initialize embeddings
        self.embeddings = OllamaEmbeddings(ollama_base_url, ollama_model)
        
        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="redmine_issues",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Text splitter for long documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        # prompts directory
        self.prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')

    def _load_prompt_template(self, filename: str) -> Optional[str]:
        path = os.path.join(self.prompts_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load prompt template {filename}: {e}")
            return None
    
    def index_issues(self, issues: List[Dict[str, Any]]) -> None:
        """Index issues into ChromaDB.
        
        Args:
            issues: List of issue dictionaries from Redmine
        """
        logger.info(f"Indexing {len(issues)} issues...")
        
        # Clear existing collection by deleting and recreating it
        try:
            self.chroma_client.delete_collection("redmine_issues")
        except Exception as e:
            logger.debug(f"Collection deletion failed (may not exist): {e}")
        
        # Recreate collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="redmine_issues",
            metadata={"hnsw:space": "cosine"}
        )
        
        documents = []
        metadatas = []
        ids = []
        
        for issue in issues:
            # Create document content
            content = self._create_issue_content(issue)
            
            # Split content if too long
            chunks = self.text_splitter.split_text(content)
            
            for i, chunk in enumerate(chunks):
                doc_id = f"issue_{issue['id']}_chunk_{i}"
                documents.append(chunk)
                metadatas.append({
                    "issue_id": issue['id'],
                    "subject": issue.get('subject', ''),
                    "status": issue.get('status', {}).get('name', ''),
                    "priority": issue.get('priority', {}).get('name', ''),
                    "tracker": issue.get('tracker', {}).get('name', ''),
                    "chunk_index": i
                })
                ids.append(doc_id)
        
        if documents:
            # Add to collection (ChromaDB will generate embeddings automatically)
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
        logger.info(f"Indexed {len(documents)} document chunks")
    
    def search_similar_issues(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search for similar issues.
        
        Args:
            query: Search query
            n_results: Number of results to return
            
        Returns:
            List of similar issue chunks with metadata
        """
        try:
            # Search in ChromaDB using text query
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            similar_issues = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    
                    similar_issues.append({
                        'content': doc,
                        'metadata': metadata,
                        'similarity': 1 - distance  # Convert distance to similarity
                    })
            
            return similar_issues
            
        except Exception as e:
            logger.error(f"Failed to search similar issues: {e}")
            return []
    
    def generate_advice(self, issue_description: str, similar_issues: List[Dict[str, Any]]) -> str:
        """Generate advice based on similar issues.
        
        Args:
            issue_description: New issue description
            similar_issues: List of similar issues from search
            
        Returns:
            Generated advice text
        """
        # Create context from similar issues
        context = self._create_context(similar_issues)
        
        # Create prompt
        prompt = self._create_advice_prompt(issue_description, context)
        
        # Generate response using Ollama
        try:
            url = f"{self.ollama_base_url}/api/generate"
            data = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(url, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            advice = result.get("response", "申し訳ございませんが、アドバイスの生成に失敗しました。")
            return advice.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate advice: {e}")
            return "申し訳ございませんが、AIアドバイスの生成中にエラーが発生しました。"
    
    def generate_advice_for_issue(self, issue: Dict[str, Any]) -> Optional[str]:
        """Generate advice for a specific issue.
        
        Args:
            issue: Issue dictionary from Redmine API
            
        Returns:
            Generated advice text or None if generation fails
        """
        try:
            # Create issue description for search
            issue_description = self._create_issue_content(issue)
            
            # Search for similar issues
            similar_issues = self.search_similar_issues(issue_description, n_results=5)
            
            # Generate advice
            advice = self.generate_advice(issue_description, similar_issues)
            
            if advice and advice.strip() and advice != "申し訳ございませんが、AIアドバイスの生成中にエラーが発生しました。":
                return f"AI自動アドバイス:\n\n{advice}"
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate advice for issue {issue.get('id', 'unknown')}: {e}")
            return None
    
    def _create_issue_content(self, issue: Dict[str, Any]) -> str:
        """Create searchable content from issue data.
        
        Args:
            issue: Issue dictionary
            
        Returns:
            Formatted content string
        """
        content_parts = []
        
        # Subject
        if issue.get('subject'):
            content_parts.append(f"件名: {issue['subject']}")
        
        # Description
        if issue.get('description'):
            content_parts.append(f"説明: {issue['description']}")
        
        # Status, Priority, Tracker
        if issue.get('status'):
            content_parts.append(f"ステータス: {issue['status'].get('name', '')}")
        if issue.get('priority'):
            content_parts.append(f"優先度: {issue['priority'].get('name', '')}")
        if issue.get('tracker'):
            content_parts.append(f"トラッカー: {issue['tracker'].get('name', '')}")
        
        # Journals (comments)
        if issue.get('journals'):
            for journal in issue['journals']:
                if journal.get('notes'):
                    content_parts.append(f"コメント: {journal['notes']}")
        
        return "\n".join(content_parts)
    
    def _create_context(self, similar_issues: List[Dict[str, Any]]) -> str:
        """Create context string from similar issues.
        
        Args:
            similar_issues: List of similar issues
            
        Returns:
            Context string
        """
        if not similar_issues:
            return "関連する過去の事例は見つかりませんでした。"
        
        context_parts = []
        context_parts.append("関連する過去の事例:")
        
        for i, issue in enumerate(similar_issues[:3]):  # Top 3 results
            metadata = issue.get('metadata', {})
            content = issue.get('content', '')
            similarity = issue.get('similarity', 0)
            
            context_parts.append(f"\n事例 {i+1} (類似度: {similarity:.2f}):")
            context_parts.append(f"Issue ID: {metadata.get('issue_id')}")
            context_parts.append(f"件名: {metadata.get('subject')}")
            context_parts.append(f"内容: {content[:500]}...")  # Truncate long content
        
        return "\n".join(context_parts)
    
    def _create_advice_prompt(self, issue_description: str, context: str) -> str:
        template = self._load_prompt_template('advice.txt')
        if not template:
            # Fallback to minimal prompt if template missing
            return f"課題:\n{issue_description}\n\n{context}\n\nアドバイス:"
        return (template
                .replace('{{ISSUE_DESCRIPTION}}', issue_description)
                .replace('{{CONTEXT}}', context))
