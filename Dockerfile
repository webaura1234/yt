FROM python:3.12.1-bookworm

# No ImageMagick: subtitles are rasterised with Pillow (see
# utils/video.render_text_image), so the image needs no external image binary.
# ffmpeg comes from imageio-ffmpeg, which moviepy pulls in.

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
