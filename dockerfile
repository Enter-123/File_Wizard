# Use slim Python image
FROM python:3.10-slim

# Install system dependencies (ffmpeg, etc.)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Cloud Run uses $PORT env variable
ENV PORT=8080

# Start Flask app with Gunicorn
CMD ["gunicorn", "-b", ":8080", "main:app"]