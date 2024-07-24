FROM amodi252/rasa_sdk_backend:4055
WORKDIR /app
COPY requirements.txt requirements.txt
COPY ./faiss_docs ./faiss_docs
COPY ./gptembeddings ./gptembeddings
COPY ./dbc.sh ./dbc.sh
USER root
RUN ["chmod", "+x", "./dbc.sh"]
RUN ./dbc.sh
RUN pip install --verbose -r requirements.txt
# EXPOSE 4055
# CMD ["rasa", "run", "actions", "-p", "4055"]
USER 1001