from flask import Flask, jsonify, request
import requests
import xml.etree.ElementTree as ET
import base64
import re

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

def extract_pdf_from_xml(xml_content):
    """Extrait le PDF base64 et le nom du fichier depuis le XML Business@Mail"""
    try:
        # Nettoyer l'encodage si necessaire
        if isinstance(xml_content, str):
            xml_bytes = xml_content.encode('iso-8859-1', errors='replace')
        else:
            xml_bytes = xml_content
        
        root = ET.fromstring(xml_bytes)
        
        # Chercher la balise Attachment
        attachment = root.find('.//Attachment')
        if attachment is None:
            return None, None
        
        filename = attachment.get('Name', 'facture.pdf')
        data_elem = attachment.find('Data')
        if data_elem is None or not data_elem.text:
            return None, filename
        
        # Le contenu est deja en base64
        pdf_b64 = data_elem.text.strip()
        return pdf_b64, filename
    except Exception as e:
        return None, str(e)

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
    if resp.status_code != 200:
        return jsonify({"error": f"status {resp.status_code}", "body": resp.text[:200]}), 502
    
    try:
        data = resp.json()
        xml_content = data.get("docContent", {}).get("data", "")
        
        if not xml_content:
            return jsonify({"error": "docContent vide", "data": data}), 500
        
        # Extraire le PDF du XML
        pdf_b64, filename = extract_pdf_from_xml(xml_content)
        
        if pdf_b64:
            return jsonify({
                "status": 200,
                "id": doc_id,
                "filename": filename,
                "pdf_base64": pdf_b64,
                "type": "pdf"
            })
        else:
            # Pas de PDF dans le XML - retourner le XML brut
            xml_b64 = base64.b64encode(xml_content.encode('iso-8859-1', errors='replace')).decode('utf-8')
            return jsonify({
                "status": 200,
                "id": doc_id,
                "filename": f"STEF-{doc_id}.xml",
                "pdf_base64": xml_b64,
                "type": "xml"
            })
    except Exception as e:
        return jsonify({"error": str(e), "body": resp.text[:300]}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
