# Use Ubuntu 22.04 as a base image for more recent glibc
FROM ubuntu:22.04

# Set up the environment
WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1

# Copy your project files
COPY . /app

# Update and install required dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg python3-pip && \
    python3 -m pip install --upgrade pip setuptools wheel && \
    bash install_ffmpeg.sh && \
    pip install -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Expose port for health checks
EXPOSE 8080

# Run the application
CMD ["python3", "start.py"]
