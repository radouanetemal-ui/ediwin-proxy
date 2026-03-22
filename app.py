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


@app.route("/list-documents", methods=["POST"])
def list_documents():
    body = request.get_json() or {}
    date_from = body.get("from", "")
    date_to = body.get("to", "")
    token = body.get("token") or login_ediwin()
    if not token:
        return jsonify({"error": "login echoue"}), 500
    resp = ediwin_post(
        "/api/documents/getConfiguredPrint",
        token,
        {"filter": {"from": date_from, "to": date_to, "type": "CUSTOM"}}
    )
    if resp.status_code == 200:
        try:
            data = resp.json()
            ids = []
            for group in data:
                ids.extend(group.get("ids", []))
            return jsonify({"ids": ids, "count": len(ids)})
        except Exception:
            return jsonify({"error": "parse", "body": resp.text[:300]}), 500
    return jsonify({"error": f"status {resp.status_code}", "body": resp.text[:300]}), 502


@app.route("/get-document", methods=["POST"])
def get_document():
    body = request.get_json() or {}
    doc_id = body.get("id")
    if not doc_id:
        return jsonify({"error": "id requis"}), 400
    token = body.get("token") or login_ediwin()
    if not token:
        return jsonify({"error": "login echoue"}), 500
    resp = ediwin_get_doc(doc_id, token)
    if resp.status_code != 200:
        return jsonify({"error": f"status {resp.status_code}", "body": resp.text[:200]}), 502
    try:
        data = resp.json()
        xml_content = data.get("docContent", {}).get("data", "")
        if not xml_content:
            return jsonify({"error": "docContent vide", "raw": str(data)[:300]}), 500
        pdf_b64, filename = extract_pdf_from_xml(xml_content)
        if pdf_b64:
            return jsonify({"status": 200, "id": doc_id, "filename": filename, "pdf_base64": pdf_b64, "type": "pdf"})
        xml_b64 = base64.b64encode(xml_content.encode("iso-8859-1", errors="replace")).decode("utf-8")
        return jsonify({"status": 200, "id": doc_id, "filename": f"STEF-{doc_id}.xml", "pdf_base64": xml_b64, "type": "xml"})
    except Exception as e:
        return jsonify({"error": str(e), "body": resp.text[:300]}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
