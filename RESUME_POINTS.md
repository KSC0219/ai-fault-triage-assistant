# Resume content: AI Network Fault Triage Assistant

## Project entry (paste into the PROJECTS section)

**AI Network Fault Triage Assistant (RAG + LLM Agent)** | [github.com/<username>/ai-fault-triage-assistant]
Python | LLM (Claude API) | RAG | ChromaDB | FastAPI | Streamlit | Docker

- Built an AI assistant that triages network faults from plain-English descriptions, suggesting the likely root cause, severity and fix while citing similar historical tickets.
- Implemented a RAG pipeline: embedded 150 resolved fault tickets with sentence-transformers and stored them in a ChromaDB vector database for semantic search.
- Developed an LLM agent with tool calling that searches past faults, queries device history and opens tickets through a Spring Boot REST API, returning structured, schema-validated results.
- Built an evaluation harness on a 50-question test set, reaching 96% retrieval hit@1 and 94% triage accuracy; used error analysis to change the scoring method, improving accuracy from 90% to 94%.
- Added guardrails (grounded answers with citations, permission-gated actions, step limits, an offline fallback), served the system via a FastAPI REST API and a Streamlit UI, and containerised it with Docker; covered it with 11 pytest tests, including a mocked LLM.

## Shorter version (if space is tight)

**AI Network Fault Triage Assistant** | Python, Claude API, RAG, ChromaDB, FastAPI
- Built a RAG + LLM-agent assistant that retrieves similar past network faults from a ChromaDB vector store and suggests root causes with citations, integrated with a Spring Boot API via tool calling.
- Evaluated it on a 50-question test set (96% retrieval hit@1, 94% triage accuracy); served it via FastAPI and Streamlit, and containerised it with Docker.

## Add to TECHNICAL SKILLS

- **AI / ML:** LLMs, RAG, prompt engineering, LLM tool calling / agents, embeddings, vector databases (ChromaDB), Scikit-learn
- **Frameworks:** FastAPI, Streamlit, Spring Boot
- **Tools:** Docker, pytest, Postman

## Updated professional summary (optional)

Software Engineer with experience in Python, Java and REST APIs, building AI applications with LLMs, retrieval-augmented generation (RAG) and vector databases. Built an LLM-agent system integrated with a Spring Boot backend, with a focus on evaluation, testing and clean code.

## Interview prep: questions you should be able to answer

1. **What is RAG, and why use it instead of just asking the LLM?** It grounds answers in your organisation's own past tickets, reduces hallucination, and lets you cite sources. The model doesn't know your network's history.
2. **How do embeddings and vector search work?** Text becomes a vector (384 dimensions for MiniLM), and similar meanings sit close together. ChromaDB finds the nearest neighbours by cosine similarity.
3. **How does tool calling work?** The model receives JSON schemas for the tools. It replies with a `tool_use` block, the code runs the tool and sends back a `tool_result`, and the loop repeats until `submit_triage` is called.
4. **How did you stop the agent from doing something harmful?** Ticket creation needs explicit user permission, the agent has a step limit, the output is schema-validated, and there's a fallback to offline mode.
5. **How did you evaluate it?** 50 hand-written queries, phrased differently from the knowledge base, measured with hit@k and MRR for retrieval and accuracy for triage. Error analysis led to similarity-weighted voting, which took accuracy from 0.90 to 0.94.
6. **How do you test code that calls an LLM?** A scripted fake client returns predetermined tool calls, so the loop logic is tested without an API key or cost.
7. **Why is the data synthetic?** Real NOC tickets are confidential. The schema matches real exports, so real data can be dropped in.
8. **What would you improve?** Hybrid BM25 + vector search, a re-ranker, LLM-as-judge evaluation, and auto-indexing of newly resolved tickets.
