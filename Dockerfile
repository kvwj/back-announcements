FROM python:3-slim

ENV TZ=America/Denver

COPY requirements.txt /opt/app/requirements.txt

COPY set_announcement_file.py /opt/app/set_announcement_file.py

COPY start_announcements.sh /opt/app/start_announcements.sh

RUN chmod +x /opt/app/start_announcements.sh

WORKDIR /opt/app

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    cifs-utils \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

ENTRYPOINT ["/bin/bash", "/opt/app/start_announcements.sh"]
