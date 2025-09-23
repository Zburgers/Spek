#!/usr/bin/env python3
"""
Manual API smoke test for Spek backend at http://localhost:8000

Constraints:
- Designed to run from host against the Dockerized app (no docker commands).
- Uses a Bearer token provided via environment variable SPEK_TOKEN.
- Exercises key flows: list docs, upload chat-specific doc, list chat docs, query doc,
  associate/deselect docs for a chat, delete doc, and verify deletion.

Usage:
  SPEK_TOKEN='<access_token>' python3 -m src.scripts.manual_api_test --chat-id <uuid> [--file path]

Notes:
- If you don't have a chat UUID, you can skip chat-specific steps with --skip-chat.
- Upload uses a small text file by default if --file isn't provided.
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import uuid
from pathlib import Path

import requests

BASE_URL = os.environ.get("SPEK_BASE_URL", "http://localhost:8000")
TOKEN = os.environ.get("SPEK_TOKEN")


def auth_headers():
    if not TOKEN:
        print("ERROR: SPEK_TOKEN env var not set.")
        sys.exit(1)
    return {"Authorization": f"Bearer {TOKEN}"}


def pretty(obj):
    return json.dumps(obj, indent=2, default=str)


def list_documents():
    r = requests.get(f"{BASE_URL}/api/v1/documents", headers=auth_headers())
    r.raise_for_status()
    docs = r.json()
    print(f"Documents ({len(docs)}):\n{pretty(docs)}\n")
    return docs


def get_document(doc_id):
    r = requests.get(f"{BASE_URL}/api/v1/documents/{doc_id}", headers=auth_headers())
    r.raise_for_status()
    return r.json()


def ensure_test_file(path: Path) -> Path:
    if path.exists():
        return path
    path.write_text("Hello Spek RAG!\nThis is a test document.", encoding="utf-8")
    return path


def upload_chat_document(chat_id: uuid.UUID, file_path: Path) -> dict:
    filename = file_path.name
    mime, _ = mimetypes.guess_type(str(file_path))
    mime = mime or "text/plain"
    with open(file_path, "rb") as f:
        files = {"file": (filename, f, mime)}
        r = requests.post(
            f"{BASE_URL}/api/v1/chats/{chat_id}/documents/upload",
            headers=auth_headers(),
            files=files,
        )
    r.raise_for_status()
    data = r.json()
    print(f"Uploaded: {pretty(data)}\n")
    return data


def get_chat_documents(chat_id: uuid.UUID) -> dict:
    r = requests.get(
        f"{BASE_URL}/api/v1/chats/{chat_id}/documents",
        headers=auth_headers(),
    )
    r.raise_for_status()
    data = r.json()
    print(f"Chat docs: {pretty(data)}\n")
    return data


def query_document(doc_id: uuid.UUID, question: str) -> dict:
    payload = {"document_id": str(doc_id), "query": question}
    r = requests.post(
        f"{BASE_URL}/api/v1/documents/query",
        headers={**auth_headers(), "Content-Type": "application/json"},
        json=payload,
    )
    r.raise_for_status()
    data = r.json()
    print(f"Query result: {pretty(data)}\n")
    return data


def associate_documents(chat_id: uuid.UUID, doc_ids: list[str], selected: bool = True) -> dict:
    payload = {"document_ids": doc_ids, "selected": selected}
    r = requests.post(
        f"{BASE_URL}/api/v1/chats/{chat_id}/documents",
        headers={**auth_headers(), "Content-Type": "application/json"},
        json=payload,
    )
    r.raise_for_status()
    data = r.json()
    print(f"Associate result: {pretty(data)}\n")
    return data


def remove_document_from_chat(chat_id: uuid.UUID, document_id: uuid.UUID) -> dict:
    r = requests.delete(
        f"{BASE_URL}/api/v1/chats/{chat_id}/documents/{document_id}",
        headers=auth_headers(),
    )
    r.raise_for_status()
    data = r.json()
    print(f"Remove from chat result: {pretty(data)}\n")
    return data


def delete_document(doc_id: uuid.UUID) -> dict:
    r = requests.delete(f"{BASE_URL}/api/v1/documents/{doc_id}", headers=auth_headers())
    r.raise_for_status()
    data = r.json()
    print(f"Deleted: {pretty(data)}\n")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-id", type=str, help="UUID of chat for chat-specific tests")
    parser.add_argument("--file", type=str, default="/tmp/spek_test_doc.txt", help="Path to file to upload")
    parser.add_argument("--skip-chat", action="store_true", help="Skip chat-specific tests")
    parser.add_argument("--question", type=str, default="What does the test file say?", help="Question to query the document with")
    args = parser.parse_args()

    # List documents first
    list_documents()

    chat_id = None
    if not args.skip_chat:
        if not args.chat_id:
            print("--chat-id is required unless --skip-chat is set.")
            sys.exit(2)
        try:
            chat_id = uuid.UUID(args.chat_id)
        except Exception:
            print("--chat-id must be a valid UUID")
            sys.exit(2)

    test_path = ensure_test_file(Path(args.file))

    uploaded = None
    if chat_id:
        uploaded = upload_chat_document(chat_id, test_path)
        # Confirm it appears in chat docs
        chat_docs = get_chat_documents(chat_id)
        # Query the document (may return mock/placeholder answer)
        try:
            query_document(uuid.UUID(uploaded["document_id"]), args.question)
        except Exception as e:
            print(f"Query failed (this may be expected if RAG not fully configured): {e}")
        # Associate/deselect example
        associate_documents(chat_id, [uploaded["document_id"]], selected=True)
        remove_document_from_chat(chat_id, uuid.UUID(uploaded["document_id"]))

    # Delete path test if we uploaded
    if uploaded:
        delete_document(uuid.UUID(uploaded["document_id"]))
        # Verify not in the list anymore
        docs_after = list_documents()
        still_there = any(d.get("uuid") == uploaded["document_id"] for d in docs_after)
        print(f"Verification: deleted doc present? {still_there}")

    print("Manual API test completed.")


if __name__ == "__main__":
    main()
