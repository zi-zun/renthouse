FROM registry.cn-beijing.aliyuncs.com/chen_ali/fastapi:py3.12-u24-1.0

COPY ./ /app/

RUN set -ex \
    && pip install -r /app/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app/
EXPOSE 8000
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
#uvicorn  main:app --host 0.0.0.0 --port 8000