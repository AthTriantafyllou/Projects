# app/pipelines/rag_llm.py

import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough

from db import get_connection
from db_users import get_vector_store_for_user, get_vector_store_for_user_units
from pipelines.group_expansion import expand_group
from pipelines.query_type import detect_query_type, get_store_weights

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = "gpt-4o-mini"  # προσαρμόζεις αν θέλεις άλλο μοντέλο

# Weights ανά modality
IMG_W = 0.5
EQ_W = 0.7
TAB_W = 0.6

# Limits ανά modality & συνολικά
MAX_TEXT = 6
MAX_SUMMARY = 4
MAX_IMAGES = 2
MAX_EQUATIONS = 3
MAX_TABLES = 2
MAX_TOTAL = 12


# ------------------------------------------------------
# Helpers
# ------------------------------------------------------
def _generate_conversation_title(question: str, answer: str) -> str:
    """
    Απλή fallback λογική για τίτλο.
    Αν έχεις δικό σου LLM-based τίτλο, αντικατάστησέ το.
    """
    base = (question or "").strip()
    if len(base) > 60:
        base = base[:57] + "..."
    return base or "New chat"


def build_base_filter(user_id: int) -> Dict[str, Any]:
    """
    Βασικό Qdrant filter για όλα τα queries:
    - φιλτράρει πάντα σε user_id
    """
    return {
        "must": [
            {"key": "user_id", "match": user_id},
        ]
    }


def _add_modality_to_filter(base_filter: Dict[str, Any], modality: str) -> Dict[str, Any]:
    """
    Προσθέτει modality_type στο Qdrant filter.
    """
    f = dict(base_filter) if base_filter else {}
    must = list(f.get("must", []))
    must.append({"key": "modality_type", "match": modality})
    f["must"] = must
    return f


def _save_conversation_and_messages(
    user_id: int,
    conversation_id: Optional[str],
    question: str,
    answer: str,
) -> str:
    """
    Save conversation + messages.
    conversation_id is UUID (TEXT), not integer.
    """
    conn = get_connection()
    cur = conn.cursor()

    # -------------------------------
    # NEW CONVERSATION
    # -------------------------------
    if not conversation_id:
        cur.execute(
            """
            INSERT INTO conversations (user_id, title, updated_at, last_message_at)
            VALUES (%s, %s, NOW(), NOW())
            RETURNING id;
            """,
            (user_id, "New chat"),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("Failed to create conversation: no ID returned")

        conversation_id = str(row[0])   # UUID as string

        # save messages
        cur.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, 'user', %s)
            """,
            (conversation_id, question),
        )
        cur.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, 'assistant', %s)
            """,
            (conversation_id, answer),
        )

        # auto-title
        auto_title = _generate_conversation_title(question, answer)
        cur.execute(
            """
            UPDATE conversations
            SET title=%s, updated_at=NOW(), last_message_at=NOW()
            WHERE id=%s
            """,
            (auto_title, conversation_id),
        )

    # -------------------------------
    # EXISTING CONVERSATION
    # -------------------------------
    else:
        conversation_id = str(conversation_id)

        cur.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, 'user', %s)
            """,
            (conversation_id, question),
        )
        cur.execute(
            """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, 'assistant', %s)
            """,
            (conversation_id, answer),
        )
        cur.execute(
            """
            UPDATE conversations
            SET updated_at=NOW(), last_message_at=NOW()
            WHERE id=%s
            """,
            (conversation_id,),
        )

    conn.commit()
    cur.close()
    conn.close()
    return conversation_id


# ------------------------------------------------------
# Κύριο RAG Flow (multimodal + grouping)
# ------------------------------------------------------
async def run_rag_flow(
    user_id: int,
    assistant_name: str,
    mode: str,
    question: str,
    chat_enabled: bool,
    conversation_id: Optional[str],
    base_system_prompt: str,
    persona: str,
    tone: str,
    mode_prompt: str,
) -> Dict[str, Any]:
    """
    Πλήρης RAG flow:
    - multimodal retrieval (text, summary, image, equation, table)
    - group-aware expansion (ανακατασκευή ενότητας)
    - LLM call με history
    - αποθήκευση συζήτησης σε DB
    """

    assistant_name_lower = (assistant_name or "").lower()

    # Ενιαίο vector store ανά χρήστη (raw + summaries + images + tables + equations)
    store = get_vector_store_for_user_units(user_id)

    base_filter = build_base_filter(user_id)

    # Mode-specific συμπεριφορά
    is_script_mode = mode in [
        "script_breakdown",
        "scene_visual_direction",
        "location_visual_design",
        "character_visual_profile",
    ]
    is_legal_mode = mode in [
        "legal_analyze",
        "legal_summary",
        "issue_spotting",
        "questions_to_ask",
    ]

    if is_script_mode:
        k_raw = 8
        k_sum = 12
        RAW_THRESHOLD = 0.25
    elif is_legal_mode:
        k_raw = 10
        k_sum = 6
        RAW_THRESHOLD = 0.35
    else:
        k_raw = 4
        k_sum = 6
        RAW_THRESHOLD = 0.45

    k_img = 4
    k_eq = 4
    k_tbl = 4

    # --------------------------------------------------
    # 1) TEXT SEARCH (modality=text) → context_found
    # --------------------------------------------------
    text_filter = _add_modality_to_filter(base_filter, "text")
    raw_results = store.similarity_search_with_score(
        question,
        k=k_raw,
        #filter=text_filter,
    )

    best_raw = max([score for _, score in raw_results], default=0.0)
    context_found = best_raw >= RAW_THRESHOLD

    print(f"🔎 best_raw={best_raw:.4f}, context_found={context_found}, chat_enabled={chat_enabled}")
    # Αν δεν υπάρχει context και chat OFF → fixed μήνυμα
    if not context_found and not chat_enabled:
        answer = (
            "I couldn't find any information in your database "
            "related to what you asked. "
            "If you want me to look into external sources of knowledge, "
            "activate chat mode."
        )
        conversation_id = _save_conversation_and_messages(
            user_id=user_id,
            conversation_id=conversation_id,
            question=question,
            answer=answer,
        )
        return {
            "answer": answer,
            "conversation_id": conversation_id,
            "context_found": False,
            "used_chunks": {},
        }

    # --------------------------------------------------
    # 2) SUMMARY + IMAGE + EQUATION + TABLE SEARCHES
    # --------------------------------------------------
    def search_modality(modality: str, k: int):
        f = _add_modality_to_filter(base_filter, modality)
        return store.similarity_search_with_score(
            question,
            k=k,
            filter=f,
        )

    if context_found or chat_enabled:
        sum_results = search_modality("summary", k_sum)
        img_results = search_modality("image", k_img)
        eq_results = search_modality("equation", k_eq)
        tbl_results = search_modality("table", k_tbl)
    else:
        sum_results = []
        img_results = []
        eq_results = []
        tbl_results = []

    # --------------------------------------------------
    # 3) WEIGHTED FUSION (raw + summary + image + eq + table)
    # --------------------------------------------------
    query_type = detect_query_type(question)
    RAW_W, SUM_W, ENT_W = get_store_weights(query_type)  # ENT_W δεν χρησιμοποιείται πλέον

    def make_items(results, source: str):
        return [
            {"doc": doc, "score": float(score), "source": source}
            for doc, score in results
        ]

    all_items = []
    all_items.extend(make_items(raw_results, "raw"))
    all_items.extend(make_items(sum_results, "summary"))
    all_items.extend(make_items(img_results, "image"))
    all_items.extend(make_items(eq_results, "equation"))
    all_items.extend(make_items(tbl_results, "table"))

    def source_weight(src: str) -> float:
        if src == "raw":
            return RAW_W
        if src == "summary":
            return SUM_W
        if src == "image":
            return IMG_W
        if src == "equation":
            return EQ_W
        if src == "table":
            return TAB_W
        return 1.0

    for item in all_items:
        w = source_weight(item["source"])
        item["final_score"] = item["score"] * w

    all_items.sort(key=lambda x: x["final_score"], reverse=True)

    # --------------------------------------------------
    # 4) GROUP-AWARE SELECTION + EXPANSION
    # --------------------------------------------------
    counts = {"raw": 0, "summary": 0, "image": 0, "equation": 0, "table": 0}
    merged_blocks: List[str] = []
    seen_groups = set()

    for item in all_items:
        doc: Document = item["doc"]
        src = item["source"]

        # per-modality limits
        if src == "raw" and counts["raw"] >= MAX_TEXT:
            continue
        if src == "summary" and counts["summary"] >= MAX_SUMMARY:
            continue
        if src == "image" and counts["image"] >= MAX_IMAGES:
            continue
        if src == "equation" and counts["equation"] >= MAX_EQUATIONS:
            continue
        if src == "table" and counts["table"] >= MAX_TABLES:
            continue

        # global blocks limit
        if len(merged_blocks) >= MAX_TOTAL:
            break

        txt = (doc.page_content or "").strip()
        if not txt:
            continue

        group_id = doc.metadata.get("group_id")

        # Αν έχουμε ήδη επεξεργαστεί το group → skip
        if group_id and group_id in seen_groups:
            continue

        if group_id:
            expanded_block = expand_group(
                vector_store=store,
                base_filter=base_filter,
                seed_doc=doc,
                k=50,
            )
            if not expanded_block.strip():
                continue
            merged_blocks.append(expanded_block)
            seen_groups.add(group_id)
            counts[src] += 1
        else:
            # Fallback: με απλό prefix ανά modality
            prefix = ""
            if src == "summary":
                prefix = "[SUMMARY]\n"
            elif src == "equation":
                prefix = "[EQUATION]\n"
            elif src == "image":
                prefix = "[IMAGE]\n"
            elif src == "table":
                prefix = "[TABLE]\n"

            merged_blocks.append(prefix + txt)
            counts[src] += 1

    rag_context = "\n\n---\n\n".join(merged_blocks)

    # --------------------------------------------------
    # 5) LLM PROMPT (system + persona + tone + mode)
    # --------------------------------------------------
    if is_legal_mode:
        context_usage = (
            "You are analyzing legal documents for factual information only. "
            "Use ONLY the provided context, regardless of chat mode. "
            "Never provide legal advice, legal opinions, or recommendations. "
            "If the context does not contain enough information, say that you "
            "cannot find the answer in the user's documents."
        )
    else:
        if not chat_enabled:
            context_usage = (
                "Use ONLY the provided context. "
                "If the context is insufficient, respond that no relevant "
                "information was found in the user's documents."
            )
        else:
            context_usage = (
                "You may use your general knowledge if needed, but always "
                "prioritize the user's documents."
            )

    full_system_prompt = f"""
{base_system_prompt}

Persona:
{persona}

Tone:
{tone}

Mode: {mode}

Mode instructions:
{mode_prompt}

Context usage rules:
{context_usage}

You receive multimodal context including:
- RAW text chunks
- hierarchical summaries
- extracted equations (LaTeX or inline)
- extracted images (captions + OCR)
- extracted tables (flattened)

Always answer in clean Markdown.
"""

    # --------------------------------------------------
    # 6) LOAD HISTORY
    # --------------------------------------------------
    history_messages = []

    if conversation_id:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT role, content
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (conversation_id,),
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()

            # reverse για oldest → newest
            rows = rows[::-1]
            for role, content in rows:
                if role == "user":
                    history_messages.append(("human", content))
                else:
                    history_messages.append(("assistant", content))
        except Exception as e:
            print("❌ Error loading conversation history:", e)

    prompt_messages = [("system", full_system_prompt)]
    prompt_messages.extend(history_messages)
    prompt_messages.append(
        (
            "human",
            f"User question:\n{question}\n\nFused RAG context:\n{rag_context}",
        )
    )

    prompt = ChatPromptTemplate.from_messages(prompt_messages)

    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=0,
        api_key=OPENAI_API_KEY,
    )

    chain = (
        {
            "question": RunnablePassthrough(),
            "context": lambda _: rag_context,
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    # Αν και η run_rag_flow είναι async, εδώ χρησιμοποιούμε sync invoke,
    # που είναι ΟΚ μέσα σε async context.
    answer = chain.invoke(question)

    # --------------------------------------------------
    # 7) SAVE CONVERSATION + MESSAGES
    # --------------------------------------------------
    conversation_id = _save_conversation_and_messages(
        user_id=user_id,
        conversation_id=conversation_id,
        question=question,
        answer=answer,
    )

    return {
        "answer": answer,
        "conversation_id": conversation_id,
        "context_found": context_found,
        "used_chunks": counts,
    }


async def run_rag_flow_teacher(
    user_id: int,
    assistant_name: str,
    mode: str,
    question: str,
    chat_enabled: bool,
    conversation_id: Optional[str],
    base_system_prompt: str,
    persona: str,
    tone: str,
    mode_prompt: str,
    teacher_context: str,
) -> Dict[str, Any]:
    """
    Πλήρης RAG flow:
    - multimodal retrieval (text, summary, image, equation, table)
    - group-aware expansion (ανακατασκευή ενότητας)
    - LLM call με history
    - αποθήκευση συζήτησης σε DB
    """

    rag_context = teacher_context
    #print(f"🔎 teacher_context={teacher_context}, chat_enabled={chat_enabled}")

    # --------------------------------------------------
    # 5) LLM PROMPT (system + persona + tone + mode)
    # --------------------------------------------------
    if not chat_enabled:
        context_usage = (
            "Use ONLY the provided context. "
            "If the context is insufficient, respond that no relevant "
            "information was found in the user's documents."
        )
    else:
        context_usage = (
            "You may use your general knowledge if needed, but always "
            "prioritize the user's documents."
        )

# Οδηγία LaTeX με τετραπλές αγκύλες για να επιβιώσουν από το διπλό rendering
#latex_example = "E = \\\\frac{{{{1}}}}{{{{2}}}}KA^2"
    

    full_system_prompt = f"""
{base_system_prompt}

Persona: {persona}
Tone: {tone}
Mode: {mode} ({mode_prompt})

### CRITICAL INSTRUCTIONS:
### HOW TO HANDLE IMAGES:
If you see an "IMAGE_URL_TO_DISPLAY" in the context, you MUST show it.
Use this EXACT format: ![caption](URL)
Do not just link to it. Embed it.
Important: Match all the images with the appropriate text

### PLAIN TEXT MATHEMATICS (NO CODE)
The user's screen CANNOT render LaTeX or math blocks. You MUST write equations as plain, beautiful text:
- **Multiplication**: Use the middle dot ( · ) ONLY. Never use \cdot, or [ ].
- **Exponents**: Use Unicode superscript numbers (e.g., x², y³). Example: Write x² + y² = 0.
- **Subscripts**: Use Unicode subscript numbers.
- **Fractions**: Use a simple slash (e.g., 1/2).
- **Format**: Do NOT wrap equations in brackets [ ] or backticks. Write them inline as normal text.
- **Style**: Avoid raw LaTeX code like \frac or \text. The goal is the math to look like a textbook, not like code.

### HOW TO HANDLE QUOTES:
Keep the original line breaks for poems and quotes.
   
Context usage: {context_usage}

Always answer in clean Markdown. Use LaTeX for ALL mathematical expressions.
"""


    # --------------------------------------------------
    # 6) LOAD HISTORY
    # --------------------------------------------------
    history_messages = []

    if conversation_id:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT role, content
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (conversation_id,),
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()

            # reverse για oldest → newest
            rows = rows[::-1]
            for role, content in rows:
                # ΚΡΙΣΙΜΟ: Κάνουμε escape τα άγκιστρα στο περιεχόμενο του ιστορικού
                # για να μην τα εκλαμβάνει η LangChain ως μεταβλητές prompt
                safe_content = content.replace("{", "{{").replace("}", "}}")         
                if role == "user":
                    history_messages.append(("human", safe_content))
                else:
                    history_messages.append(("assistant", safe_content))
        except Exception as e:
            print("❌ Error loading conversation history:", e)


    prompt_messages = [("system", full_system_prompt)]
    prompt_messages.extend(history_messages)

    # Στο σημείο 5 πριν το prompt_messages.append
    safe_rag_context = rag_context.replace("{", "{{").replace("}", "}}")
    safe_question = question.replace("{", "{{").replace("}", "}}")   

    prompt_messages.append(
        (
            "human",
            f"User question:\n{safe_question}\n\nFused RAG context:\n{safe_rag_context}",
        )
    )
    
    # prompt_messages.append(
        # (
            # "human",
            # f"User question:\n{question}\n\nFused RAG context:\n{rag_context}",
        # )
    # )

    prompt = ChatPromptTemplate.from_messages(prompt_messages)

    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=0,
        api_key=OPENAI_API_KEY,
    )

    chain = (
        {
            "question": RunnablePassthrough(),
            "context": lambda _: rag_context,
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    # Αν και η run_rag_flow είναι async, εδώ χρησιμοποιούμε sync invoke,
    # που είναι ΟΚ μέσα σε async context.
    answer = chain.invoke(question)

    print(f"🔎 ΑΙ_answer={answer}")
    
    # --------------------------------------------------
    # 7) SAVE CONVERSATION + MESSAGES
    # --------------------------------------------------
    conversation_id = _save_conversation_and_messages(
        user_id=user_id,
        conversation_id=conversation_id,
        question=question,
        answer=answer,
    )
    
    counts = {"raw": 0, "summary": 0, "image": 0, "equation": 0, "table": 0}
    
    return {
        "answer": answer,
        "conversation_id": conversation_id,
        "context_found": True,
        "used_chunks": counts,
    }

