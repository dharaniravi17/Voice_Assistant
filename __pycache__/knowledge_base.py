import pandas as pd

# Load the knowledge base
df = pd.read_csv("electronics_tools_knowledge_base.csv")

# Convert it into a dictionary
knowledge_base = {row["question"].lower(): row["answer"] for _, row in df.iterrows()}

def get_answer(query):
    query = query.lower()
    return knowledge_base.get(query, "I'm not sure about that. Can you rephrase?")
