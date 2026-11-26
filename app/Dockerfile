FROM python:3.11-slim

WORKDIR /opt/app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# NL2SQL 引擎与 Schema 提示词
COPY nl2sql/nl2sql_core.py ./nl2sql/nl2sql_core.py
COPY nl2sql/schema_prompt.txt ./nl2sql/schema_prompt.txt
COPY app/app.py ./app/app.py
COPY app/chart_engine.py ./app/chart_engine.py
# 中国地图 GeoJSON（DataV，含南海诸岛），供图表引擎渲染省份分布
COPY screen/vendor/china.json ./app/china.json

EXPOSE 8501
CMD ["streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
