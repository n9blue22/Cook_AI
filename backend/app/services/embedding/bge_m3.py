"""EmbeddingProvider chạy local bằng BAAI/bge-m3 qua sentence-transformers (dense, 1024 chiều)."""

import asyncio

from sentence_transformers import SentenceTransformer

from app.services.embedding.provider import EmbeddingProvider

BGE_M3_MODEL_NAME = "BAAI/bge-m3"
ENCODE_BATCH_SIZE = 32


class BgeM3Provider(EmbeddingProvider):
    """Nạp model khi khởi tạo — lần đầu tự tải ~2.2GB về cache HuggingFace."""

    def __init__(self) -> None:
        self._model = SentenceTransformer(BGE_M3_MODEL_NAME)

    def encode(self, texts: list[str], show_progress_bar: bool = False) -> list[list[float]]:
        """Encode đồng bộ; vector đã chuẩn hoá L2 nên cosine distance tương đương dot product."""
        vectors = self._model.encode(
            texts, batch_size=ENCODE_BATCH_SIZE, normalize_embeddings=True, show_progress_bar=show_progress_bar,
        )
        return vectors.tolist()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Chạy encode trong thread riêng để không chặn event loop."""
        return await asyncio.to_thread(self.encode, texts)
