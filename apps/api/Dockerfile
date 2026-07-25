# ============ البناء ============
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
# تبعيات التشغيل فقط — بلا pytest وruff في صورة الإنتاج
RUN pip install --prefix=/install .

# ============ التشغيل ============
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    AUTO_CREATE_SCHEMA=false

WORKDIR /app

COPY --from=builder /install /usr/local

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
# حزم البيانات الموثقة ببصماتها — بدونها لا يمكن بذر النص ولا الصرف
COPY data ./data

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

# الهجرات لا تُشغَّل تلقائيًا: تُنفَّذ بدور مالك منفصل عند النشر
# (راجع docs/DEPLOYMENT_AR.md). دور التطبيق لا يملك DDL.
# --forwarded-allow-ips لا تُضبط على * أبدًا: مع * يثق uvicorn بترويسة
# X-Forwarded-For من أي عميل، فيصير مفتاح حدّ المعدل قابلًا للتزوير
# ويسقط سقف محاولات تسجيل الدخول. تُمرَّر شبكة الوسيط وحدها.
ENV FORWARDED_ALLOW_IPS=172.16.0.0/12
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"$FORWARDED_ALLOW_IPS\""]
