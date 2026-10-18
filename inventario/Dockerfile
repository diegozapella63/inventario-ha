# Inventário da casa: imagem do app (add-on) do Home Assistant.
# Só Python e a biblioteca padrão; nenhum pacote extra.
FROM python:3.12-alpine

RUN apk add --no-cache tzdata

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY app/ /app/
COPY seed/ /app/seed/

CMD ["python3", "/app/server.py"]
