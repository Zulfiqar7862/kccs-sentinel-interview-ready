# syntax=docker/dockerfile:1
# Two stages: build a wheel, then install it into a slim runtime image that runs as a non-root user.
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip build && python -m build --wheel --outdir /dist

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    KCCS_HOST=0.0.0.0 KCCS_PORT=8000 \
    KCCS_DATA_DIR=/data KCCS_WORKBOOK=/data/KCCS_Sentinel_Reference_Data_Pack.xlsx \
    KCCS_DB_PATH=/var/lib/kccs/kernel.sqlite KCCS_ARTIFACTS_DIR=/var/lib/kccs/artifacts \
    KCCS_LOG_FORMAT=json KCCS_AUTOLOAD=true
RUN useradd --system --uid 10001 --home /var/lib/kccs kccs && mkdir -p /var/lib/kccs /data && chown kccs /var/lib/kccs
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
USER kccs
WORKDIR /var/lib/kccs
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live').status==200 else 1)"
CMD ["kccs-evidence", "serve"]
