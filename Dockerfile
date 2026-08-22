# ---- base image: slim Python, small and standard ----
FROM python:3.12-slim

# ---- system setup ----
# PYTHONUNBUFFERED: logs appear immediately (not buffered) — important for seeing output
# PYTHONDONTWRITEBYTECODE: don't write .pyc files in the container (keeps it clean)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ---- working directory inside the container ----
WORKDIR /app

# ---- install dependencies FIRST (layer caching) ----
# Copy ONLY requirements first. This layer is cached and only rebuilds when
# requirements.txt changes — so editing your code later won't reinstall packages.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- copy the application code + package config + the 12MB databases ----
# .dockerignore excludes the 227MB of junk, so this copies only what's needed.
COPY pyproject.toml .
COPY filingsiq/ ./filingsiq/

# ---- install the filingsiq package itself (so `from filingsiq...` works) ----
# --no-deps because requirements.txt already installed everything.
RUN pip install --no-cache-dir --no-deps -e .

# ---- the port the server listens on ----
EXPOSE 8000

# ---- command that runs when the container starts ----
# host 0.0.0.0 (not 127.0.0.1) so it's reachable from OUTSIDE the container.
CMD ["uvicorn", "filingsiq.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
