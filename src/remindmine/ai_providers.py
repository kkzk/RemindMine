"""AI プロバイダ基底クラスとプロバイダ実装。

サポートプロバイダ：
- Ollama: ローカル実行での LLM/Embedding 処理
- OpenAI: OpenAI API を利用した LLM/Embedding 処理

設計方針：
- 共通インターフェースを保ち、切り替え時の影響を最小化
- エラーハンドリングと代替手段（フォールバック）を含む
- プロバイダ固有の設定をカプセル化
"""

import logging
import requests
import json
from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from openai import OpenAI

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """AI プロバイダの基底クラス。"""
    
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """複数テキストを埋め込みベクトルへ変換。"""
        pass
    
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """検索クエリを埋め込みベクトルへ変換。"""
        pass
    
    @abstractmethod
    def generate_completion(self, prompt: str) -> Optional[str]:
        """プロンプトから回答を生成。"""
        pass


class OllamaProvider(AIProvider):
    """Ollama プロバイダ実装。"""
    
    def __init__(self, base_url: str = "http://localhost:11434", 
                 model: str = "llama3.2", 
                 embedding_model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
        self.embedding_model = embedding_model
        self.default_dimension = 384  # Default embedding dimension
        logger.info(f"Initialized Ollama provider: {base_url}, model: {model}")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """複数テキストを埋め込みベクトルへ変換。"""
        embeddings = []
        for text in texts:
            embedding = self._get_embedding(text)
            if embedding:
                embeddings.append(embedding)
            else:
                # Fallback to zeros if embedding fails
                embeddings.append([0.0] * self.default_dimension)
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """検索クエリを埋め込みベクトルへ変換。"""
        embedding = self._get_embedding(text)
        return embedding if embedding else [0.0] * self.default_dimension
    
    def generate_completion(self, prompt: str) -> Optional[str]:
        """プロンプトから回答を生成。"""
        try:
            url = f"{self.base_url}/api/generate"
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            response = requests.post(url, json=data, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("response")
        except Exception as e:
            logger.error(f"Failed to generate completion with Ollama: {e}")
            return None
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Ollama API へリクエストを送り埋め込みを取得。"""
        try:
            url = f"{self.base_url}/api/embeddings"
            data = {
                "model": self.embedding_model,
                "prompt": text
            }
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get("embedding")
        except Exception as e:
            logger.error(f"Failed to get embedding from Ollama: {e}")
            return None


class OpenAIProvider(AIProvider):
    """OpenAI プロバイダ実装。"""
    
    def __init__(self, api_key: str, 
                 model: str = "gpt-4o-mini",
                 embedding_model: str = "text-embedding-3-small",
                 base_url: Optional[str] = None):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        self.model = model
        self.embedding_model = embedding_model
        
        # Initialize OpenAI client
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = OpenAI(**client_kwargs)
        self.default_dimension = 1536  # Default for text-embedding-3-small
        logger.info(f"Initialized OpenAI provider: model: {model}, embedding: {embedding_model}")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """複数テキストを埋め込みベクトルへ変換。"""
        try:
            # OpenAI API supports batch embedding
            response = self.client.embeddings.create(
                input=texts,
                model=self.embedding_model
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"Failed to get embeddings from OpenAI: {e}")
            # Fallback to zeros
            return [[0.0] * self.default_dimension for _ in texts]
    
    def embed_query(self, text: str) -> List[float]:
        """検索クエリを埋め込みベクトルへ変換。"""
        try:
            response = self.client.embeddings.create(
                input=[text],
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to get embedding from OpenAI: {e}")
            return [0.0] * self.default_dimension
    
    def generate_completion(self, prompt: str) -> Optional[str]:
        """プロンプトから回答を生成。"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to generate completion with OpenAI: {e}")
            return None


def create_ai_provider(provider_type: str, config: Any) -> AIProvider:
    """設定に基づいてプロバイダを作成。
    
    Args:
        provider_type: "ollama" or "openai"
        config: Config オブジェクト
        
    Returns:
        初期化されたプロバイダインスタンス
        
    Raises:
        ValueError: 不正なプロバイダタイプまたは設定不備
    """
    if provider_type.lower() == "ollama":
        return OllamaProvider(
            base_url=config.ollama_base_url,
            model=config.ollama_model,
            embedding_model=config.ollama_embedding_model
        )
    elif provider_type.lower() == "openai":
        return OpenAIProvider(
            api_key=config.openai_api_key,
            model=config.openai_model,
            embedding_model=config.openai_embedding_model,
            base_url=config.openai_base_url
        )
    else:
        raise ValueError(f"Unsupported AI provider: {provider_type}")
