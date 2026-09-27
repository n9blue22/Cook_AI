"""Lỗi nghiệp vụ dùng chung cho dữ liệu riêng của user (tủ lạnh, nhật ký, công thức đã lưu)."""

from postgrest.exceptions import APIError

FOREIGN_KEY_VIOLATION = "23503"


class NotFoundError(Exception):
    """Không có dòng này — hoặc thuộc user khác (RLS ẩn đi, không phân biệt với "không tồn tại")."""


class InvalidReferenceError(Exception):
    """Id trỏ tới nguyên liệu / công thức không có trong danh mục."""


def is_foreign_key_violation(error: APIError) -> bool:
    """PostgREST trả lỗi Postgres 23503 khi ghi id không tồn tại vào cột khoá ngoại."""
    return error.code == FOREIGN_KEY_VIOLATION
