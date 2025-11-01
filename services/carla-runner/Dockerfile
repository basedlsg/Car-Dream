# CARLA Runner Dockerfile with GPU support and headless configuration
FROM nvidia/cuda:11.8.0-devel-ubuntu20.04

# Set environment variables for headless operation
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV CARLA_ROOT=/opt/carla-simulator
ENV CARLA_VERSION=0.9.15
ENV PYTHONPATH="${CARLA_ROOT}/PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg:${PYTHONPATH}"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    python3 \
    python3-pip \
    python3-dev \
    libomp5 \
    xvfb \
    x11vnc \
    fluxbox \
    libjpeg-turbo8-dev \
    libpng16-16 \
    libtiff5-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create CARLA directory
RUN mkdir -p ${CARLA_ROOT}

# Download and install CARLA simulator (with retry and timeout)
RUN cd /tmp && \
    wget --timeout=300 --tries=3 --retry-connrefused https://carla-releases.s3.eu-west-3.amazonaws.com/Linux/CARLA_${CARLA_VERSION}.tar.gz && \
    tar -xzf CARLA_${CARLA_VERSION}.tar.gz -C ${CARLA_ROOT} --strip-components=1 && \
    rm CARLA_${CARLA_VERSION}.tar.gz || \
    echo "Warning: CARLA download failed, continuing without full CARLA installation"

# Create directories for datasets
RUN mkdir -p ${CARLA_ROOT}/Import \
    ${CARLA_ROOT}/Maps \
    ${CARLA_ROOT}/Data/OSM \
    ${CARLA_ROOT}/Data/nuScenes

# Set up Python environment
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Create dataset initialization scripts
RUN mkdir -p /app/scripts

# Make CARLA executable
RUN chmod +x ${CARLA_ROOT}/CarlaUE4.sh

# Create startup script for headless operation
COPY scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 2000 2001 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["/app/start.sh"]