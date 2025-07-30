# Use a recent official Python image
FROM python:3.9-slim-bookworm

# Set working directory
WORKDIR /app

# Install ffmpeg + PyNaCl build deps
RUN apt-get update && \
    apt-get install -y ffmpeg libffi-dev libnacl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the code
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the bot
CMD ["python", "bot.py"]
