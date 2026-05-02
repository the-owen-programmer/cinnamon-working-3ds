FROM devkitpro/devkitarm:20260221

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    make \
    ffmpeg \
    ca-certificates \
    git \
    python3-pip

RUN rm -rf /var/lib/apt/lists/*

RUN pip3 install Pillow --break-system-packages

WORKDIR /workspace
RUN git clone https://github.com/KurplunkVR/cinnamon-working-3ds.git /workspace

CMD ["bash"]
