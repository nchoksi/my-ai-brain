from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CREDENTIALS_FILE = PROJECT_ROOT / "credential-googleusercontent.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_credentials():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE,
                SCOPES,
            )

            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return creds


def extract_text(document):
    text_parts = []

    for structural_element in document["body"]["content"]:
        paragraph = structural_element.get("paragraph")

        if not paragraph:
            continue

        for element in paragraph.get("elements", []):
            text_run = element.get("textRun")

            if text_run:
                text_parts.append(
                    text_run.get("content", "")
                )

    return "".join(text_parts)


def read_google_doc(document_id: str) -> str:
    credentials = get_credentials()

    docs_service = build(
        "docs",
        "v1",
        credentials=credentials,
    )

    document = (
        docs_service.documents()
        .get(documentId=document_id)
        .execute()
    )

    text = extract_text(document)

    return f"Document: {document['title']}\n\n{text}"


def search_google_docs(query: str) -> str:
    credentials = get_credentials()

    drive_service = build(
        "drive",
        "v3",
        credentials=credentials,
    )

    safe_query = query.replace("'", "\\'")

    drive_query = (
        "mimeType='application/vnd.google-apps.document' "
        "and trashed=false "
        f"and name contains '{safe_query}'"
    )

    result = (
        drive_service.files()
        .list(
            q=drive_query,
            fields="files(id, name, modifiedTime)",
            pageSize=10,
        )
        .execute()
    )

    files = result.get("files", [])

    if not files:
        return f"No Google Docs found matching '{query}'."

    lines = []

    for file in files:
        lines.append(
            f"Title: {file['name']}\n"
            f"Document ID: {file['id']}\n"
            f"Modified: {file.get('modifiedTime', 'unknown')}"
        )

    return "\n\n".join(lines)