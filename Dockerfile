FROM python:3.10-slim

# Install system deps & clean cache in one layer (smaller image)
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set workdir first
WORKDIR /FileToLink

# Copy requirements first (better layer caching)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -U pip && \
    pip3 install --no-cache-dir -U -r requirements.txt

# Copy rest of code
COPY . .

# Tell Koyeb which port your web server listens on
EXPOSE 8080

# Pass PORT so your app can read it
ENV PORT=8080

CMD ["python", "bot.py"]
