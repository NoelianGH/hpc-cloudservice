FROM python:3.12-slim
WORKDIR /app
COPY worker.py .
RUN useradd -u 10001 worker
USER worker
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-u", "worker.py"]