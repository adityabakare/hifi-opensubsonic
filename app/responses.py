from typing import Any, Dict
import xmltodict
from fastapi import Response
from fastapi.responses import JSONResponse

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

        if fmt == "json":
            return JSONResponse(content=wrapped_data)
        
        elif fmt == "xml":
            # Convert dict to XML
            # xmltodict.unparse can do this.
            # We need to ensure the root element is subsonic-response with xmlns
            # But normally we just pass the dict structure that matches.
            xml_content = xmltodict.unparse(wrapped_data, pretty=True)
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
