FROM python:3.9-slim

WORKDIR /mbase

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "." ]