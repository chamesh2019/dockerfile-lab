FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY app.py ./

EXPOSE 8080

ENTRYPOINT [ "python", "app.py" ]

CMD ["OK"]

