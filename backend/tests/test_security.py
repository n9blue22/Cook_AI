"""JWT (chữ ký, hạn, aud, iss, chống đổi thuật toán), luật mật khẩu + HIBP, chống bom giải nén, lỗi không lộ nội bộ."""

import asyncio
import base64
import hashlib
import hmac
import io
import json
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from PIL import Image
from postgrest.exceptions import APIError

from app.api.errors import INTERNAL_ERROR_MESSAGE
from app.core.config import get_settings
from app.main import create_app
from app.services.auth_tokens import JwtVerifier, UnauthenticatedError
from app.services.password_policy import is_password_pwned, password_problems
from app.services.upload_image import MAX_IMAGE_PIXELS, ImageTooLargeError, prepare_image_for_vision

SUPABASE = "https://supabase.test"
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
PUBLIC_PEM = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
)


def _token(**overrides) -> str:
    claims = {
        "sub": "user-1", "aud": "authenticated", "iss": f"{SUPABASE}/auth/v1", "role": "authenticated",
        "exp": int(time.time()) + 600, **overrides,
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="ES256", headers={"kid": "k1"})


def _verify(token: str):
    verifier = JwtVerifier(SUPABASE)
    verifier._jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=PRIVATE_KEY.public_key()))
    return asyncio.run(verifier.verify(token))


def test_valid_token_gives_current_user() -> None:
    assert _verify(_token()).id == "user-1"


@pytest.mark.parametrize("bad_token", [
    _token(exp=int(time.time()) - 10),  # hết hạn
    _token(iss="https://ke-gia-mao.test/auth/v1"),
    _token(aud="anon"),
    _token(role="anon"),
    _token(is_anonymous=True),
    _token()[:-4] + "AAAA",  # sửa chữ ký
    jwt.encode({"sub": "user-1", "aud": "authenticated", "iss": f"{SUPABASE}/auth/v1"}, None, algorithm="none"),
])
def test_invalid_tokens_are_rejected(bad_token: str) -> None:
    with pytest.raises(UnauthenticatedError):
        _verify(bad_token)


def test_algorithm_confusion_hs256_with_public_key_is_rejected() -> None:
    """Tấn công kinh điển: ký HS256 bằng chính khoá công khai (ai cũng có) — không được chấp nhận."""
    forged = _hs256_forged()
    with pytest.raises(UnauthenticatedError):
        _verify(forged)


def _hs256_forged() -> str:
    """JWT HS256 ký bằng khoá công khai PEM — tự dựng vì PyJWT (đúng) không cho ký kiểu này."""

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"sub": "attacker", "aud": "authenticated", "role": "authenticated",
                              "iss": f"{SUPABASE}/auth/v1", "exp": int(time.time()) + 600}).encode())
    signature = b64(hmac.new(PUBLIC_PEM, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def test_password_rules() -> None:
    assert password_problems("Dung-mat-khau-1!") == []
    assert set(password_problems("abcdefgh")) == {"ít nhất 1 chữ hoa", "ít nhất 1 chữ số", "ít nhất 1 ký tự đặc biệt"}
    assert password_problems("Ab1!")[0] == "tối thiểu 8 ký tự"


def test_hibp_outage_does_not_block_signup() -> None:
    down = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    assert asyncio.run(is_password_pwned("Dung-mat-khau-1!", down)) is False


def _png(width: int, height: int) -> bytes:
    output = io.BytesIO()
    Image.new("1", (width, height)).save(output, format="PNG")  # ảnh 1-bit toàn đen: file vài KB
    return output.getvalue()


@pytest.mark.parametrize("side", [8000, 11000])  # 64MP (vượt ngưỡng) và 121MP (vượt 2 lần → Pillow tự chặn)
def test_decompression_bomb_is_rejected_before_decoding(side: int) -> None:
    data = _png(side, side)
    assert len(data) < 2 * 1024 * 1024 and side * side > MAX_IMAGE_PIXELS  # file nhỏ, khai kích thước khổng lồ
    with pytest.raises(ImageTooLargeError):
        prepare_image_for_vision(data)


def test_normal_photo_still_passes() -> None:
    output = io.BytesIO()
    Image.new("RGB", (4000, 3000), "red").save(output, format="JPEG")  # 12MP như ảnh điện thoại
    assert Image.open(io.BytesIO(prepare_image_for_vision(output.getvalue()))).size == (1024, 768)


LEAK_MARKERS = ("Traceback", "select ", "public.user_profiles", "E:\\", "/srv/", ".py", "42P01", "relation")


@pytest.mark.parametrize("error", [
    RuntimeError('select * from public.user_profiles — file E:\\Project\\app.py, line 12'),
    APIError({"message": 'relation "public.user_profiles" does not exist', "code": "42P01", "hint": None, "details": "select *"}),
])
def test_unhandled_errors_return_generic_500_without_internals(error: Exception) -> None:
    app = create_app(get_settings())

    async def boom() -> None:
        raise error

    app.add_api_route("/boom", boom)
    response = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 500 and response.json() == {"detail": INTERNAL_ERROR_MESSAGE}
    assert not any(marker in response.text for marker in LEAK_MARKERS)
