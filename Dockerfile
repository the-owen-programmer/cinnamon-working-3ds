FROM devkitpro/devkitarm:20260221

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    make \
    ffmpeg \
    ca-certificates \
    git \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir Pillow --break-system-packages

WORKDIR /workspace

CMD ["bash"]
