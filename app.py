from flask import Flask, jsonify, request
import requests
import xml.etree.ElementTree as ET
import base64

app = Flask(__name__)

EDIWIN_BASE = "https://ediwin02.edicomgroup.com"
EDIWIN_USER = "FR.51501928162.000"
EDIWIN_PASSWORD = "UBA05SBZ"


def login_ediwin():
        resp = requests.post(
                    f"{EDIWIN_BASE}/api/main/login",
                    json={"user": EDIWIN_USER, "password": EDIWIN_PASSWORD, "domain": "businessmail"},
                    headers={"Accept-Encoding": "identity", "Content-Type": "application/json"},
                    allow_redirects=True
        )
        try:
                    data = resp.json()
                    token = data.get("tokena") or data.get("token")
                    if token:
                                    return token
        except Exception:
                    pass
                for cookie in resp.cookies:
                            if "token" in cookie.name.lower():
                                            return cookie.value
                                    return None


def ediwin_post(path, token, body=None):
        if body is None:
                    body = {}
    headers = {"Accept-Encoding": "identity", "Content-Type": "application/json", "tokena": token}
    return requests.post(f"{EDIWIN_BASE}{path}", headers=headers, json=body)


def ediwin_get_doc(doc_id, token):
        headers = {"Accept-Encoding": "identity", "Content-Type": "application/json", "tokena": token}
    params = {"id": doc_id, "uuid": doc_id, "infoType": "data", "processDocumentData": "true", "volumeId": "100"}
    return requests.post(f"{EDIWIN_BASE}/api/documents/getDocument", headers=headers, params=params, json={})


def extract_pdf_from_xml(xml_content):
        try:
                    if isinstance(xml_content, str):
                                    xml_bytes = xml_content.encode("iso-8859-1", errors="replace")
        else:
            xml_bytes = xml_content
                    root = ET.fromstring(xml_bytes)
                    attachment = root.find(".//Attachment")
                    if attachment is None:
                                    return None, None
                                filename = attachment.get("Name", "facture.pdf")
                    data_elem = attachment.find("Data")
                    if data_elem is None or not data_elem.text:
                                    return None, filename
                                return data_elem.text.strip(), filename
        except Exception as e:
        return None, str(e)


@app.route("/health", methods=["GET"])
def health():
        return jsonify({"status": "ok"})


@app.route("/login", methods=["POST"])
def login():
        token = login_ediwin()
        if token:
                    return jsonify({"token": token})
                return jsonify({"error": "Login failed"}), 401


@app.route("/list-documents", methods=["POST"])
def list_documents():
        body = request.get_json() or {}
    token = body.get("token") or login_ediwin()
    if not token:
                return jsonify({"error": "No token"}), 401
            date_from = body.get("from", "2026-01-01T00:00:00.000Z")
    date_to = body.get("to", "2026-12-31T23:59:59.000Z")
    resp = ediwin_post(
                "/api/documents/getDocuments",
                token,
                {"from": date_from, "to": date_to, "processDocumentData": True, "volumeId": 100}
    )
    try:
                data = resp.json()
                ids = []
                if isinstance(data, dict):
                                items = data.get("list") or data.get("documents") or data.get("data") or []
                                if isinstance(items, list):
                                                    for item in items:
                                                                            if isinstance(item, dict):
                                                                                                        doc_id = item.get("id") or item.get("uuid")
                                                                                                        if doc_id:
                                                                                                                                        ids.append(doc_id)
                                                                                elif isinstance(data.get("ids"), list):
                                                                        ids = data["ids"]
                                                                return jsonify({"ids": ids, "raw": data})
    except Exception as e:
        return jsonify({"error": str(e), "raw": resp.text[:500]}), 500


@app.route("/get-document", methods=["POST"])
def get_document():
        body = request.get_json() or {}
    token = body.get("token") or login_ediwin()
    if not token:
                return jsonify({"error": "No token"}), 401
            doc_id = body.get("id")
    if not doc_id:
                return jsonify({"error": "Missing id"}), 400
            resp = ediwin_get_doc(doc_id, token)
    try:
                content_type = resp.headers.get("Content-Type", "")
                if "xml" in content_type or resp.text.strip().startswith("<"):
                                pdf_b64, filename = extract_pdf_from_xml(resp.content)
                                if pdf_b64:
                                                    return jsonify({"pdf_base64": pdf_b64, "filename": filename or f"{doc_id}.pdf"})
                                                return jsonify({"error": "PDF not found in XML", "raw": resp.text[:500]}), 500
                            data = resp.json()
        return jsonify(data)
except Exception as e:
        return jsonify({"error": str(e), "raw": resp.text[:500]}), 500


if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000)
