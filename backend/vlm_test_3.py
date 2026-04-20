import asyncio
import json
import os
import sys
from dotenv import load_dotenv

# Ensure the local environment is set
load_dotenv()

# Add current dir to sys.path to allow imports from services
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.vlm_service import VLMService

async def main():
    vlm = VLMService()
    image_path = "accident_snapshot.jpg"
    
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found.")
        return
        
    print(f"Analyzing {image_path} from the recent test run...")
    
    context = {
        "city": "Sentinel City",
        "intersection": "Sector 7 North"
    }
    
    result = await vlm.analyse_image(image_path, context=context)
    
    print("\n--- VLM VISION INTELLIGENCE ---")
    print(json.dumps(result, indent=2))
    print("--------------------------------\n")

if __name__ == "__main__":
    asyncio.run(main())
