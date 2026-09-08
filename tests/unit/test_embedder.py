from unittest.mock import MagicMock, patch

import numpy as np

from resource_retriever.config import AppConfig
from resource_retriever.embedding.embedder import Embedder


def _fake_model(dim: int = 4):
    model = MagicMock()
    model.tokenizer = MagicMock(name="tokenizer")
    model.encode.side_effect = lambda texts, **kwargs: np.zeros((len(texts), dim))
    return model


def test_embed_documents_returns_one_vector_per_text(tmp_path):
    # Arrange
    app_config = AppConfig(data_dir=tmp_path)
    with patch("resource_retriever.embedding.embedder.SentenceTransformer", return_value=_fake_model(dim=4)):
        embedder = Embedder(app_config)

        # Act
        vectors = embedder.embed_documents(["first chunk", "second chunk", "third chunk"])

    # Assert
    assert len(vectors) == 3
    assert all(len(vector) == 4 for vector in vectors)


def test_embed_query_prepends_configured_query_prefix(tmp_path):
    # Arrange
    app_config = AppConfig(data_dir=tmp_path, query_prefix="query: ")
    fake_model = _fake_model(dim=4)
    with patch("resource_retriever.embedding.embedder.SentenceTransformer", return_value=fake_model):
        embedder = Embedder(app_config)

        # Act
        embedder.embed_query("quadratics")

    # Assert
    called_texts = fake_model.encode.call_args[0][0]
    assert called_texts == ["query: quadratics"]


def test_tokenizer_property_exposes_the_underlying_model_tokenizer(tmp_path):
    # Arrange
    app_config = AppConfig(data_dir=tmp_path)
    fake_model = _fake_model(dim=4)
    with patch("resource_retriever.embedding.embedder.SentenceTransformer", return_value=fake_model):
        embedder = Embedder(app_config)

        # Act
        tokenizer = embedder.tokenizer

    # Assert
    assert tokenizer is fake_model.tokenizer
