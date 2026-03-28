import asyncio
import base64
import json
import logging
import os
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class VLMService:
    """
    Service for Visual Language Model analysis using HuggingFace Inference API.
    Used for analyzing accident snapshots and user-reported images.
    """
    
    def __init__(self, api_token: str = None, model_id: str = "Qwen/Qwen2.5-VL-72B-Instruct"):
        self.api_token = api_token or os.getenv("HUGGINGFACE_API_TOKEN")
        self.model_id = model_id
        # Use the correct router-based API endpoint (OpenAI-compatible)
        self.api_url = "https://router.huggingface.co/v1/chat/completions"
        
    def _encode_image(self, image_path: str) -> str:
        """Encode local image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def analyse_image(self, image_source: str, context: dict = None) -> dict:
        """
        Analyse an image using the VLM via HuggingFace Inference API.
        image_source can be a local file path or a public URL.
        """
        if not self.api_token:
            logger.error("HuggingFace API Token missing. VLM analysis skipped.")
            return {"error": "API token missing"}

        try:
            # Prepare image data
            image_data = None
            if image_source.startswith(('http://', 'https://')):
                # It's a URL
                image_data = image_source
            elif os.path.exists(image_source):
                # It's a local file
                b64_image = self._encode_image(image_source)
                image_data = f"data:image/jpeg;base64,{b64_image}"
            else:
                logger.error(f"Image source not found: {image_source}")
                return {"error": "Image not found"}

            # Build prompt
            system_msg = (
                "You are an expert traffic accident analyst AI for an emergency dispatch center. "
                "Analyze the provided image focusing on road safety and incident reporting. "
                "Follow these strict rules:\n"
                "1. Specifically identify the vehicle types involved (e.g., SUV, Sports Car, Truck).\n"
                "2. Do NOT hallucinate motorcycles, riders, or pedestrians unless they are clearly and definitively visible in the evidence.\n"
                "3. Assess severity based on visible structural damage and deployment of safety features (like airbags or smoke).\n"
                "Respond ONLY in this JSON format:\n"
                "{\n"
                '  "road_blocked": true | false,\n'
                '  "severity": "minor" | "moderate" | "major" | "critical",\n'
                '  "ambulance_needed": true | false,\n'
                '  "summary": "<2-sentence factual description of the specific vehicles and the nature of the collision>"\n'
                "}"
            )

            prompt = (
                f"Analyze this incident image in {context.get('city', 'the city')}. "
                f"Intersection: {context.get('intersection', 'Unknown')}. "
                "Describe the visual evidence of any collision or blockage."
            )

            headers = {"Authorization": f"Bearer {self.api_token}"}
            payload = {
                "model": self.model_id,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data}}
                        ]
                    }
                ],
                "parameters": {"max_new_tokens": 512, "temperature": 0.1}
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    logger.error(f"HF Inference API Error: {response.status_code} - {response.text}")
                    return {"error": f"API Error {response.status_code}"}

                result = response.json()
                # Serverless Inference API might return list of choices or direct content depending on model config
                # Usually for chat-completion types: result['choices'][0]['message']['content']
                content = ""
                if isinstance(result, list) and len(result) > 0:
                    content = result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    if "choices" in result:
                        content = result["choices"][0]["message"]["content"]
                    else:
                        content = result.get("generated_text", str(result))

                # Extract JSON from content (some models wrap it in markdown block)
                if "{" in content and "}" in content:
                    json_str = content[content.find("{"):content.rfind("}")+1]
                    try:
                        analysis = json.loads(json_str)
                        return {
                            **analysis,
                            "analyzed_at": datetime.now(timezone.utc).isoformat(),
                            "model": self.model_id
                        }
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse VLM JSON output: {content}")
                        return {"error": "Invalid JSON from VLM", "raw_content": content}
                
                return {"error": "No JSON found in VLM output", "raw_content": content}

        except Exception as e:
            logger.exception(f"Exception in VLMService.analyse_image: {e}")
            return {"error": str(e)}
