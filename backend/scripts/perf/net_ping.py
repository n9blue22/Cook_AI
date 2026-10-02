"""Độ trễ mạng tới Supabase: TCP connect, TLS, 1 lượt REST nhỏ với kết nối mới vs kết nối giữ sẵn."""

import os
import socket
import ssl
import statistics
import sys
import time

import httpx

sys.path.insert(0, os.getcwd())
from app.core.config import require_env  # noqa: E402

url = require_env("SUPABASE_URL")
host = url.split("//")[1]
headers = {"apikey": require_env("SUPABASE_PUBLISHABLE_KEY")}
path = "/rest/v1/allergens?select=id&limit=1"


def ms(t):
    return round((time.perf_counter() - t) * 1000, 1)


addr = socket.getaddrinfo(host, 443)[0][4]
print("resolved", addr[0])
tcp, tls = [], []
for _ in range(5):
    t = time.perf_counter()
    s = socket.create_connection((host, 443), timeout=10)
    tcp.append(ms(t))
    t = time.perf_counter()
    ss = ssl.create_default_context().wrap_socket(s, server_hostname=host)
    tls.append(ms(t))
    ss.close()
print("TCP connect ms", tcp, "median", statistics.median(tcp))
print("TLS handshake ms", tls, "median", statistics.median(tls))

fresh = []
for _ in range(5):
    t = time.perf_counter()
    with httpx.Client() as c:
        c.get(url + path, headers=headers).raise_for_status()
    fresh.append(ms(t))
print("REST select 1 row, NEW connection each:", fresh, "median", statistics.median(fresh))
warm = []
with httpx.Client() as c:
    c.get(url + path, headers=headers)
    for _ in range(10):
        t = time.perf_counter()
        c.get(url + path, headers=headers).raise_for_status()
        warm.append(ms(t))
print("REST select 1 row, KEEP-ALIVE:", warm, "median", statistics.median(warm))
with httpx.Client() as c:
    r = c.get(url + path, headers=headers)
    print("cf-ray / server:", r.headers.get("cf-ray"), r.headers.get("server"), r.headers.get("sb-gateway-version"))
