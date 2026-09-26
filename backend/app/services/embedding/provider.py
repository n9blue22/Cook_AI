"""Interface trừu tượng cho model tạo embedding phục vụ vector search."""

from abc import ABC, abstractmethod

# Phải khớp cột recipe_embeddings.embedding vector(1024) trong migration
EMBEDDING_DIMENSIONS = 1024


class EmbeddingProvider(ABC):
    """Biến text thành vector; mọi implementation phải trả đúng EMBEDDING_DIMENSIONS chiều."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Trả về một vector cho mỗi text, cùng thứ tự với đầu vào."""
