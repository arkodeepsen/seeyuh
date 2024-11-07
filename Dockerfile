# Use Ubuntu 22.04 as a base image for more recent glibc
FROM ubuntu:22.04

# Set up the environment
WORKDIR /app

# Copy your project files
COPY . /app

# Update and install required dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg python3-pip && \
    bash install_ffmpeg.sh && \
    pip install -r requirements.txt

# Run the application
CMD ["python3", "start.py"]
