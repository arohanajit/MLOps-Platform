FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY materialization.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the job
CMD ["python", "materialization.py"] 