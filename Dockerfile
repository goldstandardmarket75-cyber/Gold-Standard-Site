FROM python:3.12-slim
WORKDIR/app
COPY requirements.txt.
RUN pip install-no-chache-dir-r requirements.txt
COPY..
ENV PORT=10000
EXPOSE 10000
CMD["python","app.py"]
