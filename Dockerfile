# Subaligner Ubuntu 20 Docker Image
FROM ubuntu:20.04 

ENV RELEASE_VERSION=${RELEASE_VERSION}
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Los_Angeles
ENV RELEASE_VERSION=0.3.0

RUN ["/bin/bash", "-c", "apt-get -y update &&\
    apt-get -y install ffmpeg &&\
    apt-get -y install espeak libespeak1 libespeak-dev espeak-data &&\
    apt-get -y install libsndfile-dev &&\
    apt-get -y install python3-dev &&\
    apt-get -y install python3-tk &&\
    apt-get -y install python3-pip &&\
    python3 -m pip install --upgrade pip"]

COPY ./subaligner-trained/ /subaligner

RUN cd /subaligner && python3 -m pip install -e.

RUN python3 -m pip install flask gunicorn

RUN apt-get install -y wget

RUN wget -O /usr/share/keyrings/gpg-pub-moritzbunkus.gpg https://mkvtoolnix.download/gpg-pub-moritzbunkus.gpg

RUN apt update

RUN apt install -y mkvtoolnix

COPY app.py /scripts/ 

ENTRYPOINT ["gunicorn", "-b", "0.0.0.0", "--timeout", "600",  "--chdir", "/scripts", "app:app"]
