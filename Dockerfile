# Subaligner Ubuntu 20 Docker Image
FROM ubuntu:20.04

ENV RELEASE_VERSION=${RELEASE_VERSION}
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Los_Angeles
ENV RELEASE_VERSION=0.3.0

COPY /subaligner-trained/ /subaligner

RUN cd /subaligner

RUN ["/bin/bash", "-c", "apt-get -y update &&\
    apt-get -y install ffmpeg &&\
    apt-get -y install espeak libespeak1 libespeak-dev espeak-data &&\
    apt-get -y install libsndfile-dev &&\
    apt-get -y install python3-dev &&\
    apt-get -y install python3-tk &&\
    apt-get -y install python3-pip &&\
    python3 -m pip install --upgrade pip &&\
    python3 -m pip install \"subaligner==${RELEASE_VERSION}\" &&\
    python3 -m pip install \"subaligner[harmony]==${RELEASE_VERSION}\""]

RUN python3 -m pip install flask gunicorn

COPY app.py /scripts/

RUN wget -O /usr/share/keyrings/gpg-pub-moritzbunkus.gpg https://mkvtoolnix.download/gpg-pub-moritzbunkus.gpg

RUN apt update

RUN apt install -y mkvtoolnix

ENTRYPOINT ["gunicorn", "-b", "0.0.0.0",  "--chdir", "/scripts", "app:app"]
