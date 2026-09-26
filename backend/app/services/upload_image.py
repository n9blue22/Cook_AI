"""Ảnh user upload: chặn quá cỡ / không phải ảnh, xoay theo EXIF, thu nhỏ trước khi gửi vision (feature-spec mục 9)."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SIDE_PX = 1024  # Gemini tính token theo ô 768px — ảnh điện thoại 12MP tốn gấp nhiều lần mà không nhận diện tốt hơn
VISION_MIME = "image/jpeg"
JPEG_QUALITY = 85


class InvalidImageError(Exception):
    """File không đọc được như ảnh."""


class ImageTooLargeError(Exception):
    """Ảnh vượt MAX_UPLOAD_BYTES."""


def prepare_image_for_vision(data: bytes) -> bytes:
    """Ảnh bất kỳ (JPEG/PNG/WebP...) → JPEG cạnh dài ≤ MAX_SIDE_PX, đúng chiều theo EXIF."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageTooLargeError(f"Ảnh tối đa {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGB")  # điện thoại lưu ảnh xoay bằng cờ EXIF
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError("File không phải ảnh hợp lệ") from error
    image.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=JPEG_QUALITY)
    return output.getvalue()
