# pull official base image
FROM python:3.9.6-alpine

# set work directory
WORKDIR /usr/src

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install psycopg2 dependencies
RUN apk add --no-cache postgresql-dev gcc python3-dev musl-dev

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/requirements.txt
RUN pip install -r requirements.txt

# copy entrypoint.sh
# COPY ./entrypoint.sh /usr/src/entrypoint.sh

# copy projectddd
COPY . /usr/src/

# run entrypoint.sh
ENTRYPOINT ["gunicorn", "wsgi:app", "--log-file", "-", "-b", "0.0.0.0:80"]
