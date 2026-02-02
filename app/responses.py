from typing import Any, Dict
import xmltodict
from fastapi import Response
from fastapi.responses import JSONResponse

from app.config import settings

class SubsonicException(Exception):
    def __init__(self, code: int, message: str, fmt: str = "json"):
        self.code = code
        self.message = message
        self.fmt = fmt

class SubsonicResponse:
    @staticmethod
    def create(data: Dict[str, Any], fmt: str = "json", content_type: str = None) -> Response:
        """
        Creates a Subsonic-compliant response in JSON or XML.
        data: The dictionary content inside 'subsonic-response'.
              e.g. {"status": "ok", "musicFolders": ...}
        """
        
        # Ensure top-level wrapper if missing (helper convenience)
        if "subsonic-response" not in data:
            wrapped_data = {"subsonic-response": data}
        else:
            wrapped_data = data
            
        # Inject standard global attributes
        root = wrapped_data.get("subsonic-response")
        if isinstance(root, dict):
            # Only inject if not already present (to allow overrides if ever needed)
            if "type" not in root:
                root["type"] = "hifi-opensubsonic"
            if "serverVersion" not in root:
                root["serverVersion"] = settings.SERVER_VERSION
            if "openSubsonic" not in root:
                root["openSubsonic"] = True

        if fmt == "json":
            return JSONResponse(content=wrapped_data)
        
        elif fmt == "xml":
            # Convert dict to XML with attributes
            # We need to ensure status and version are attributes (@ prefixed)
            
            # Deep copy or new dict to avoid mutating original for other uses
            xml_data = wrapped_data.copy()
            root = xml_data.get("subsonic-response", {})
            
            # Remap specific top-level keys to attributes for XML
            if isinstance(root, dict):
                # Attributes list expanded to include new fields
                for key in ["status", "version", "xmlns", "type", "serverVersion", "openSubsonic"]:
                    if key in root:
                        root[f"@{key}"] = root.pop(key)
                
                # Also, Subsonic usually includes xmlns="http://subsonic.org/restapi"
                if "@xmlns" not in root:
                    root["@xmlns"] = "http://subsonic.org/restapi"
            
            xml_content = xmltodict.unparse(xml_data, pretty=True)
            return Response(content=xml_content, media_type="application/xml")
        
        else:
             return JSONResponse(content=wrapped_data)

    @staticmethod
    def error(code: int, message: str, fmt: str = "json", version: str = "1.16.1"):
        data = {
            "subsonic-response": {
                "@status": "failed", # XML attribute style
                "@version": version,
                "error": {
                    "@code": str(code),
                    "@message": message
                }
            }
        }
        # Adjust for JSON (Subsonic JSON format is slightly different usually, 
        # attributes are just keys, but let's stick to a cleaned version if needed)
        # Actually OpenSubsonic JSON spec says: 
        # "The JSON representation is a direct mapping of the XML."
        # Attributes are properties prefixed with @ in some specs? 
        # OpenSubsonic conventions:
        # "In JSON, attributes are represented as regular properties."
        # We might need a cleaner to strip @ for JSON if we want "clean" JSON, 
        # but standard Subsonic JSON often keeps them or just has them as keys.
        # Let's try to start with simple keys.
        
        if fmt == 'json':
            # Clean keys for JSON?
             data = {
                "subsonic-response": {
                    "status": "failed",
                    "version": version,
                    "error": {
                        "code": code,
                        "message": message
                    }
                }
            }
        
        return SubsonicResponse.create(data, fmt)
