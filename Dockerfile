FROM python:3.12.8-slim

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

VOLUME ["/app/operators"]

CMD [ "python", "main.py" ]