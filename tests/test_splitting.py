from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def test_splitter_respects_chunk_size():
    "chunks should not exceed chunk_size significantly"
    text="word "*1000
    doc=Document(page_content=text)

    splitter=RecursiveCharacterTextSplitter(chunk_size=100,chunk_overlap=0)
    chunks=splitter.split_documents([doc])

    for chunk in chunks:
        assert len(chunk.page_content)<=110

def test_splitter_overlap_works():
    "consecutive chunks should share overlapping content"
    text="A"*50+"B"*50+"C"*50
    doc=Document(page_content=text)

    splitter=RecursiveCharacterTextSplitter(chunk_size=60,chunk_overlap=20)
    chunks=splitter.split_documents([doc])

    assert len(chunks)>=2
    overlap_region=chunks[0].page_content[-20:]
    assert overlap_region in chunks[1].page_content

def test_add_start_index():
    "start index metadata should track position in original doc"

    text="X"*200
    doc=Document(page_content=text)
    splitter=RecursiveCharacterTextSplitter(
        chunk_size=50,
        chunk_overlap=0,
        add_start_index=True
    )
    chunks=splitter.split_documents([doc])
    assert chunks[0].metadata["start_index"]==0
    assert chunks[1].metadata["start_index"]==50