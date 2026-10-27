FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends bash \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
# Add dependencies needed by your Skills here and rebuild the image.
# Example: RUN pip install --no-cache-dir openpyxl==3.1.5
