FROM python:3.9

ADD requirements.txt .
ADD requirements.dev.txt .

RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt -r requirements.dev.txt

ADD tails_server ./tails_server
ADD bin ./bin
ADD README.md ./
ADD setup.py ./

RUN pip3 install --no-cache-dir -e .

ENTRYPOINT ["/bin/bash", "-c", "tails-server \"$@\""]

