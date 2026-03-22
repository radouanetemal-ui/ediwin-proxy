from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

EDIWIN_BASE = "https://ediwin02.edicomgroup.com"
EDIWIN_USER = "FR.51501928162.000"
EDIWIN_PASSWORD = "UBA05SBZ"

def ediwin_post(path, token, body={}):
    headers = {"Accept-Encoding": "identity", "Content-Type": "application/json", "tokena": token}
    return requests.post(f"{EDIWIN_BASE}{path}", headers=headers, json=body)

def ediwin_get_doc(doc_id, token):
    headers = {"Accept-Encoding": "identity", "Content-Type": "application/json", "tokena": token}
    params = {"id": doc_id, "uuid": doc_id, "infoType": "data", "processDocumentData": "true", "volumeId": "100"}
    return requests.post(f"{EDIWIN_BASE}/api/documents/getDocument", headers=headers, params=params, json={})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/list-documents", methods=["POST"])
def list_documents():
    body = request.get_json() or {}
    token = body.get("token")
    date_from = body.get("from", "")
    date_to = body.get("to", "")
    if not token:
        return jsonify({"error": "token manquant"}), 400
    resp = ediwin_post("/api/documents/getConfiguredPrint", token, {"filter": {"from": date_from, "to": date_to, "type": "CUSTOM"}})
    if resp.status_code == 200:
        try:
            data = resp.json()
            ids = []
            for group in data:
                ids.extend(group.get("ids", []))
            return jsonify({"ids": ids, "count": len(ids)})
        except:
            return jsonify({"error": "parse", "body": resp.text[:300]}), 500
    return jsonify({"error": f"status {resp.status_code}", "body": resp.text[:300]}), 502

@app.route("/get-document", methods=["POST"])
def get_document():
    body = request.get_json() or {}
    token = body.get("token")
    doc_id = body.get("id")
    if not token or not doc_id:
        return jsonify({"error": "token et id requis"}), 400
    resp = ediwin_get_doc(doc_id, token)
    if resp.status_code == 200:
        try:
            return jsonify({"status": 200, "id": doc_id, "data": resp.json()})
        except:
            return jsonify({"error": "parse", "body": resp.text[:300]}), 500
    return jsonify({"error": f"status {resp.status_code}", "body": resp.text[:200]}), 502

@app.route("/get-all-documents", methods=["POST"])
def get_all_documents():
    body = request.get_json() or {}
    token = body.get("token")
    date_from = body.get("from", "")
    date_to = body.get("to", "")
    if not token:
        return jsonify({"error": "token manquant"}), 400
    list_resp = ediwin_post("/api/documents/getConfiguredPrint", token, {"filter": {"from": date_from, "to": date_to, "type": "CUSTOM"}})
    if list_resp.status_code != 200:
        return jsonify({"error": f"liste {list_resp.status_code}", "body": list_resp.text[:300]}), 502
    try:
        groups = list_resp.json()
    except:
        return jsonify({"error": "parse liste", "body": list_resp.text[:300]}), 500
    ids = []
    for group in groups:
        ids.extend(group.get("ids", []))
    documents = []
    for doc_id in ids:
        doc_resp = ediwin_get_doc(doc_id, token)
        if doc_resp.status_code == 200:
            try:
                documents.append({"id": doc_id, "data": doc_resp.json()})
            except:
                pass
    return jsonify({"documents": documents, "count": len(documents)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
