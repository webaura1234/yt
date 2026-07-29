FROM python:3.12.1-bookworm

RUN apt remove imagemagick -y

# Install ImageMagick from source via SoftCreatR/imei ("ImageMagick Easy Install",
# https://github.com/SoftCreatR/imei), pinned to a specific signed release instead of
# tracking the "main" bootstrap target, for reproducible builds.
ENV RELEASE_TAG=im-7.1.2-29_aom-3.13.3_heif-1.23.1_jxl-0.12.0
RUN t=$(mktemp) && \
    wget 'https://dist.1-2.dev/imei.sh' -qO "$t" && \
    bash "$t" && \
    rm "$t"

# Set the working directory
WORKDIR /app


# Copy the requirements.txt file into the container
COPY requirements.txt /app/requirements.txt

# Set up Python virtual environment
RUN python3.12 -m venv /venv
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

# Use CMD to start cron in the foreground
CMD /venv/bin/python3 /app/main.py
