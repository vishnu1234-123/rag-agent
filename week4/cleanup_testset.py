import pandas as pd
import numpy as np
from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
import os
from dotenv import load_dotenv
load_dotenv()
embeddings=OpenAIEmbeddings(model="text-embedding-3-small")

df=pd.read_csv("week4/apple_10k_testset_100.csv")
print(f"Original: {len(df)} questions")

#remove duplicate questions
df=df.drop_duplicates(subset="user_input",keep="first")
print(f"After dedup: {len(df)} questions")

#flag unanswerable questions

unanswerable_pattern = (
    "does not provide|context does not|not mentioned|not specified|"
    "no information|not discussed|does not specify|not explicitly"
)

df["is_unanswerable"]=df["reference"].str.contains(
    unanswerable_pattern,case=False,na=False
)

print(f"\nUnanswerable questions: {df['is_unanswerable'].sum()}")
print(df[df["is_unanswerable"]]["user_input"].tolist())


question_vector=embeddings.embed_documents(df["user_input"].to_list())
question_vector=np.array(question_vector)

sim_matrix=cosine_similarity(question_vector)

threshold=0.92
semantic_dupes=[]

i_idx,j_idx=np.where(np.triu(sim_matrix,k=1)>threshold)
semantic_dupes=list(zip(i_idx,j_idx,sim_matrix[i_idx,j_idx]))

print(f"\nSemantic near-duplicate pairs (similarity > {threshold}): {len(semantic_dupes)}")

for i,j,score in semantic_dupes:
    print(f"\n Similarity:{score:.3f}")
    print(f"Q1: {df.iloc[int(i)]['user_input']}")
    print(f"Q2:{df.iloc[int(j)]['user_input']}")