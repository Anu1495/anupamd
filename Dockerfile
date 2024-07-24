FROM rasa/rasa:3.5.0
WORKDIR '/app'
COPY . /app
USER root
WORKDIR /app
COPY . /app
COPY ./data /app/data
# COPY ./faiss_docs /app/faiss_docs
# COPY ./gptembeddings /app/gptembeddings
# COPY ./models /app/models
RUN  rasa train
VOLUME /app
VOLUME /app/data
VOLUME /app/models
CMD ["run","-m","/app/models","--enable-api","--cors","*","--debug" ,"--endpoints", "endpoints.yml", "-p","4005","--debug"]