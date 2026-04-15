FROM odoo:18

# Install git, rsync, and PC/SC libraries for smart card reader support
USER root
RUN apt-get update && apt-get install -y \
    git \
    rsync \
    pcscd \
    pcsc-tools \
    libpcsclite1 \
    libpcsclite-dev \
    python3-pip \
    python3-dev \
    gcc \
    g++ \
    make \
    swig \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/* && \
    mkdir -p /scripts /var/cache/custom_addons_repo && chown -R odoo:odoo /scripts /var/cache/custom_addons_repo

# Install packaging early - required for parsing version specifiers in requirements.txt
RUN pip3 install --break-system-packages "packaging>=21.0"

# Copy and install GuardPro module dependencies (as root for system-wide installation)
COPY --chown=root:root custom_addons/guardpro/requirements.txt /tmp/guardpro-requirements.txt
RUN pip3 install --break-system-packages -r /tmp/guardpro-requirements.txt && rm /tmp/guardpro-requirements.txt

USER odoo

# Copy the pull-and-start script into the image
COPY --chown=odoo:odoo scripts/pull-and-start.sh /scripts/pull-and-start.sh
RUN chmod +x /scripts/pull-and-start.sh

# Set the pull-and-start script as the entrypoint
ENTRYPOINT ["/bin/bash", "/scripts/pull-and-start.sh"]

