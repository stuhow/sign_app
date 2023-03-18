FROM tensorflow/tensorflow:2.10.0

COPY sign_app sign_app
COPY examples examples
COPY requirements.txt requirements.txt
COPY .streamlit .streamlit
# COPY setup.py setup.py

RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
RUN pip install -r requirements.txt

EXPOSE 8501


ENTRYPOINT ["streamlit", "run", "sign_app/streamlit_app_cloud.py", "--server.port=8501", "--server.address=0.0.0.0"]
# CMD streamlit run sign_app/streamlit_app_cloud.py
