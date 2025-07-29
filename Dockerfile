# ---- Stage 1: The Builder ----
FROM python:3.9-slim as builder

WORKDIR /app

# Copy only the requirements file to leverage Docker cache
COPY requirements.txt .

# Install dependencies
# Using --no-cache-dir makes the layer smaller
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: The Final Image ----
FROM python:3.9-slim

WORKDIR /app

# Copy the installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# Copy your application code into the container
COPY process_pdfs.py .

# This is the command that will run when the container starts.
# It executes your script, which is designed to find PDFs in /app/input
# and write JSONs to /app/output.
CMD ["python", "process_pdfs.py"]