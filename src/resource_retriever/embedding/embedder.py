"""Sentence-embedding wrapper around a local, CPU-only sentence-transformers model."""

from sentence_transformers import SentenceTransformer

from resource_retriever.config import AppConfig


class Embedder:
    """Wraps a SentenceTransformer model so the rest of the app never imports the library directly.

    Exposes `.tokenizer` (the model's own HF fast tokenizer) so `chunking/chunker.py` can compute
    exact token windows and char offsets against the same tokenizer that will actually embed the text.
    """

    def __init__(self, app_config: AppConfig):
        self._model = SentenceTransformer(app_config.embedding_model_name)
        self._normalize = app_config.normalize_embeddings
        self._query_prefix = app_config.query_prefix
        self._document_prefix = app_config.document_prefix

    @property
    def tokenizer(self):
        return self._model.tokenizer

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [self._document_prefix + text for text in texts]
        return self._encode(prefixed)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([self._query_prefix + text])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=self._normalize, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]
