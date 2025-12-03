FROM python:3.9-bookworm

WORKDIR /code

# Install system dependencies required for OpenCV
RUN apt-get update && apt-get install -y \
	libgl1 \
	libglib2.0-0 \
	&& rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Create a non-root user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user . $HOME/app

CMD ["python", "app.py"]
