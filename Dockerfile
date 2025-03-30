FROM ubuntu:22.04

RUN apt update -y && apt upgrade -y
RUN apt install -y python3 python3-pip python3-venv ffmpeg

RUN mkdir /home/soulripper
WORKDIR /home/soulripper

COPY requirements.txt .
RUN python3 -m venv venv
RUN bash -c "source venv/bin/activate && pip install -r requirements.txt"

RUN echo "source /home/soulripper/venv/bin/activate" >> /root/.bashrc