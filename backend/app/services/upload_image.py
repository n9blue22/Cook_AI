"""Ảnh user upload: chặn quá cỡ / không phải ảnh, xoay theo EXIF, thu nhỏ trước khi gửi vision (feature-spec mục 9)."""

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SIDE_PX = 1024  # Gemini tính token theo ô 768px — ảnh điện thoại 12MP tốn gấp nhiều lần mà không nhận diện tốt hơn
VISION_MIME = "image/jpeg"
JPEG_QUALITY = 85
# Chống "bom giải nén": file PNG vài KB có thể khai 100.000×100.000 px → giải nén ra hàng chục GB RAM.
# 50MP vẫn nhận ảnh 48MP của điện thoại; giải nén RGB ≈ 150MB — vừa RAM server nhỏ.
MAX_IMAGE_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS  # Pillow: vượt → DecompressionBombWarning, vượt 2 lần → DecompressionBombError
PIXELS_TOO_LARGE_MESSAGE = "Ảnh có độ phân giải quá lớn"


class InvalidImageError(Exception):
    """File không đọc được như ảnh."""


class ImageTooLargeError(Exception):
    """Ảnh vượt MAX_UPLOAD_BYTES hoặc MAX_IMAGE_PIXELS."""


def prepare_image_for_vision(data: bytes) -> bytes:
    """Ảnh bất kỳ (JPEG/PNG/WebP...) → JPEG cạnh dài ≤ MAX_SIDE_PX, đúng chiều theo EXIF."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageTooLargeError(f"Ảnh tối đa {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)  # cảnh báo cũng coi là lỗi
            image = Image.open(io.BytesIO(data))  # chỉ đọc header, chưa giải nén điểm ảnh
            _reject_huge_resolution(image)
            image = ImageOps.exif_transpose(image).convert("RGB")  # điện thoại lưu ảnh xoay bằng cờ EXIF
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ImageTooLargeError(PIXELS_TOO_LARGE_MESSAGE) from error
    except (UnidentifiedImageError, OSError) as error:
        raise InvalidImageError("File không phải ảnh hợp lệ") from error
    image.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=JPEG_QUALITY)
    return output.getvalue()


def _reject_huge_resolution(image: Image.Image) -> None:
    """Kiểm từ kích thước khai trong header — trước khi Pillow cấp RAM giải nén."""
    width, height = image.size
    if width * height > MAX_IMAGE_PIXELS:
        raise ImageTooLargeError(PIXELS_TOO_LARGE_MESSAGE)
