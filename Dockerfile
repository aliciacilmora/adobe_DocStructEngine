# ---- Stage 1: The Builder ----
# Use a full Python image to install dependencies
FROM python:3.9-slim as builder

WORKDIR /app

# Copy only the requirements file to leverage Docker cache
COPY requirements.txt .

# Install dependencies
# Using --no-cache-dir makes the layer smaller
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: The Final Image ----
# Use a lean base image for the final product
FROM python:3.9-slim

WORKDIR /app

# Copy the installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# Copy your application code into the container
# Make sure your Python script is named 'your_script_1a.py'
COPY your_script_1a.py .

# This is the command that will run when the container starts.
# It executes your script, which is designed to find PDFs in /app/input
# and write JSONs to /app/output.
CMD ["python", "docstruct.py"]