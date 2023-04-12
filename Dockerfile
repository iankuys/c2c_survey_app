FROM tiangolo/uwsgi-nginx-flask:python3.11-2023-04-10

ENV TZ="America/Los_Angeles"
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .
