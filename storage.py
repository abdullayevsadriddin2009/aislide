"""Hugging Face Storage Buckets (S3-mos) — hujjatlarning doimiy nusxasi.

Render'ning bepul tarifida disk vaqtinchalik: qayta ishga tushgandan keyin
`DATA_DIR/files` dagi fayllar yo'qoladi va Mini App "Fayl topilmadi" derdi.
Bucket sozlangan bo'lsa, har bir hujjat u yerga ham yuklanadi va uning havolasi
bazaga yoziladi.

Faqat stdlib ishlatiladi (boto3 kerak emas): AWS SigV4 imzosi qo'lda hisoblanadi.
Sozlamalar (Render -> Environment):
    HF_S3_ENDPOINT          https://<namespace>.s3.hf.co
    HF_S3_BUCKET            bucket nomi (namespace ichida)
    HF_S3_ACCESS_KEY_ID     HFAK...
    HF_S3_SECRET_ACCESS_KEY ...
    HF_S3_PUBLIC_URL        ixtiyoriy: havola uchun asosiy manzil
"""
import hashlib
import hmac
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import config

REGION = "us-east-1"
TIMEOUT = 60
_EMPTY_HASH = hashlib.sha256(b"").hexdigest()


def _endpoint():
    """(base_url, host, path_prefix) yoki (None, None, None)."""
    raw = str(getattr(config, "HF_S3_ENDPOINT", "") or "").strip().rstrip("/")
    if not raw:
        return None, None, ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urllib.parse.urlparse(raw)
    return f"{parsed.scheme}://{parsed.netloc}", parsed.netloc, parsed.path.rstrip("/")


def _bucket():
    """Bucket nomi. `namespace/bucket` ko'rinishida berilsa ham ishlaydi."""
    raw = str(getattr(config, "HF_S3_BUCKET", "") or "").strip().strip("/")
    return raw.rsplit("/", 1)[-1] if raw else ""


def enabled():
    """Bucket to'liq sozlanganmi (aks holda yuklash o'tkazib yuboriladi)."""
    base, _, _ = _endpoint()
    return bool(base and _bucket()
                and getattr(config, "HF_S3_ACCESS_KEY_ID", "")
                and getattr(config, "HF_S3_SECRET_ACCESS_KEY", ""))


def _quote(value, safe="/-_.~"):
    return urllib.parse.quote(str(value), safe=safe)


def _sign(key, message):
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _authorization(method, path, payload_hash, amz_date):
    base, host, _ = _endpoint()
    datestamp = amz_date[:8]
    canonical_headers = (f"host:{host}\n"
                         f"x-amz-content-sha256:{payload_hash}\n"
                         f"x-amz-date:{amz_date}\n")
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join([
        method, path, "", canonical_headers, signed_headers, payload_hash])
    scope = f"{datestamp}/{REGION}/s3/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amz_date, scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()])
    secret = str(config.HF_S3_SECRET_ACCESS_KEY)
    key = _sign(("AWS4" + secret).encode("utf-8"), datestamp)
    key = _sign(key, REGION)
    key = _sign(key, "s3")
    key = _sign(key, "aws4_request")
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return (f"AWS4-HMAC-SHA256 Credential={config.HF_S3_ACCESS_KEY_ID}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}")


def public_url(key):
    """Bucket faylining ochiq manzili (bucket public bo'lishi kerak)."""
    quoted = _quote(key, safe="/-_.~")
    override = str(getattr(config, "HF_S3_PUBLIC_URL", "") or "").strip().rstrip("/")
    if override:
        return f"{override}/{quoted}"
    _, host, prefix = _endpoint()
    namespace = ""
    if prefix:
        namespace = prefix.lstrip("/").split("/")[0]
    elif host:
        namespace = host.split(".")[0]
    bucket = _bucket()
    if not namespace or not bucket:
        return ""
    # Bucket'lar versiyalanmaydi: manzilda `main` (revision) bo'lmaydi.
    return (f"https://huggingface.co/buckets/{namespace}/{_quote(bucket, safe='')}"
            f"/resolve/{quoted}")


def upload_bytes(data, key, content_type="application/octet-stream"):
    """Fayl baytlarini bucketga yuklaydi va ochiq havolasini qaytaradi.

    Xato bo'lsa None qaytaradi — bu generatsiyani to'xtatmaydi.
    """
    if not enabled():
        return None
    try:
        base, host, prefix = _endpoint()
        payload = bytes(data or b"")
        path = f"{prefix}/{_quote(_bucket(), safe='')}/{_quote(key, safe='/-_.~')}"
        payload_hash = hashlib.sha256(payload).hexdigest()
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        headers = {
            "Authorization": _authorization("PUT", path, payload_hash, amz_date),
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            "Content-Type": content_type or "application/octet-stream",
            "Content-Length": str(len(payload)),
        }
        request = urllib.request.Request(base + path, data=payload, method="PUT",
                                         headers=headers)
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            if response.status not in (200, 201, 204):
                print(f"[storage] HF S3 javobi: HTTP {response.status}", flush=True)
                return None
        url = public_url(key)
        print(f"[storage] HF S3 ga yuklandi: {key}", flush=True)
        return url or None
    except Exception as exc:
        print(f"[storage] HF S3 yuklash xatosi: {exc}", flush=True)
        return None


def upload_file(path, key, content_type="application/octet-stream"):
    """Diskdagi faylni bucketga yuklaydi."""
    try:
        with open(path, "rb") as handle:
            return upload_bytes(handle.read(), key, content_type)
    except Exception as exc:
        print(f"[storage] faylni o'qib bo'lmadi ({path}): {exc}", flush=True)
        return None
