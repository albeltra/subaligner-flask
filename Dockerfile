# Subaligner Ubuntu 20 Docker Image
FROM ubuntu:22.04 

ENV RELEASE_VERSION=${RELEASE_VERSION}
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Los_Angeles
ENV RELEASE_VERSION=0.3.0

RUN ["/bin/bash", "-c", "apt-get -y update &&\
    apt-get -y install ffmpeg &&\
    apt-get -y install espeak libespeak1 libespeak-dev espeak-data &&\
    apt-get -y install libsndfile-dev"]

RUN apt-get install -y wget

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O Miniconda3-latest-Linux-x86_64.sh &&\
    chmod +x Miniconda3-latest-Linux-x86_64.sh &&\
    bash Miniconda3-latest-Linux-x86_64.sh -b

ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"

RUN conda install -c conda-forge gxx

RUN wget -O /usr/share/keyrings/gpg-pub-moritzbunkus.gpg https://mkvtoolnix.download/gpg-pub-moritzbunkus.gpg

RUN apt update

RUN apt install -y mkvtoolnix

COPY ./subaligner-trained/ /subaligner

RUN cd /subaligner && python3 -m pip install -e.

RUN python3 -m pip install flask==1.1.4 gunicorn==20.1.0 pycountry pystack-debugger markupsafe==2.0.1

COPY app.py /scripts/ 

ENTRYPOINT ["gunicorn", "-b", "0.0.0.0", "--timeout", "600",  "--chdir", "/scripts", "app:app"]
