"""Embed chunks with OpenAI and store them in ChromaDB."""

import hashlib
import os
import sys
import time
import tomllib
from pathlib import Path

import chromadb
from openai import OpenAI

from src.chunk import chunk_documents
from src.clean import clean_documents
from src.load import DOCS_FOLDER, load_documents


EMBEDDING_MODEL = "text-embedding-3-small"
CHROMA_FOLDER = "chroma_db"
SECRETS_FILE = Path(".streamlit/secrets.toml")
BATCH_SIZE = 100


def get_api_key():
    """Find the OpenAI key, without writing it in code."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if key != "":
        return key

    if SECRETS_FILE.exists():
        with open(SECRETS_FILE, "rb") as file:
            secrets = tomllib.load(file)
        key = secrets.get("OPENAI_API_KEY", "")

    if key == "":
        message = (
            "No OpenAI API key found. Add OPENAI_API_KEY "
            "to .streamlit/secrets.toml."
        )
        raise RuntimeError(message)
    return key


def get_collection(model=EMBEDDING_MODEL):
    """Open (or create) the ChromaDB collection for a model."""
    client = chromadb.PersistentClient(path=CHROMA_FOLDER)
    collection = client.get_or_create_collection(
        name=f"tephra-{model}",
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )
    return collection


def embed_texts(openai_client, texts, model=EMBEDDING_MODEL):
    """Turn a list of texts into embeddings, in batches."""
    embeddings = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        response = openai_client.embeddings.create(
            model=model,
            input=batch,
        )
        for item in response.data:
            embeddings.append(item.embedding)
    return embeddings


def file_hash(metadata):
    """Make a fingerprint of a file from its contents."""
    file_path = DOCS_FOLDER / metadata["folder"] / metadata["source"]
    contents = file_path.read_bytes()
    return hashlib.sha256(contents).hexdigest()


def group_by_source(chunks):
    """Group chunks into lists, one list per file."""
    groups = {}
    for chunk in chunks:
        source = chunk["metadata"]["source"]
        if source not in groups:
            groups[source] = []
        groups[source].append(chunk)
    return groups


def find_stored_hashes(collection):
    """Find the fingerprint saved for each file already stored."""
    stored = collection.get(include=["metadatas"])
    stored_hashes = {}
    for metadata in stored["metadatas"]:
        stored_hashes[metadata["source"]] = metadata["file_hash"]
    return stored_hashes


def store_file_chunks(collection, openai_client, chunks,
                      current_hash, model):
    """Embed one file's chunks and add them to ChromaDB."""
    ids = []
    texts = []
    metadatas = []
    for chunk in chunks:
        metadata = dict(chunk["metadata"])
        metadata["file_hash"] = current_hash
        ids.append(metadata["chunk_id"])
        texts.append(chunk["text"])
        metadatas.append(metadata)

    embeddings = embed_texts(openai_client, texts, model)
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def build_database(model=EMBEDDING_MODEL):
    """Embed new or changed files and skip unchanged ones."""
    start_time = time.perf_counter()

    documents, failed_files = load_documents()
    cleaned = clean_documents(documents)
    chunks = chunk_documents(cleaned)
    if len(chunks) == 0:
        raise RuntimeError("No chunks to store. Check data/docs.")

    openai_client = OpenAI(api_key=get_api_key())
    collection = get_collection(model)
    stored_hashes = find_stored_hashes(collection)
    groups = group_by_source(chunks)

    skipped = 0
    embedded = 0
    for source in groups:
        file_chunks = groups[source]
        current_hash = file_hash(file_chunks[0]["metadata"])

        if stored_hashes.get(source) == current_hash:
            skipped = skipped + 1
            continue

        if source in stored_hashes:
            collection.delete(where={"source": source})

        store_file_chunks(collection, openai_client,
                          file_chunks, current_hash, model)
        embedded = embedded + 1

    removed = 0
    for source in stored_hashes:
        if source not in groups:
            collection.delete(where={"source": source})
            removed = removed + 1

    seconds = time.perf_counter() - start_time
    print(f"Model: {model}")
    print(f"Files embedded: {embedded}")
    print(f"Files skipped (unchanged): {skipped}")
    print(f"Files removed: {removed}")
    print(f"Chunks in database: {collection.count()}")
    print(f"Time taken: {seconds:.1f} seconds")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        build_database(sys.argv[1])
    else:
        build_database()