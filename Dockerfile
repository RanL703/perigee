FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml uv.lock ./
COPY backend ./backend
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "perigee.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
