import dotenv
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.document_loaders.unstructured import UnstructuredFileLoader 

dotenv.load_dotenv()

loader = UnstructuredFileLoader('gptembeddings\dataset_website-content-crawler.txt')
documents = loader.load()
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=10, separators=[" ", ",", "\n"])
docs = text_splitter.split_documents(documents)
faissIndex = FAISS.from_documents(docs, OpenAIEmbeddings(request_timeout=600))
faissIndex.save_local("faiss_docs")
