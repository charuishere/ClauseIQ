import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Notice we use BEDROCK_REGION because Nova Lite is currently only available in specific regions like us-east-1
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("BEDROCK_REGION", "us-east-1"))

def call_nova(prompt: str, retry: bool = True) -> dict:
    """
    Calls the Amazon Nova Lite model via the Bedrock Converse API.
    Expects a JSON string back. If parsing fails, retries once with an explicit fix instruction.
    """
    try:
        response = bedrock.converse(
            modelId="amazon.nova-lite-v1:0",
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            inferenceConfig={
                "maxTokens": 5120,
                "temperature": 0.0
            }
        )
        
        # The exact path to extract the text response from the Converse API
        output_text = response["output"]["message"]["content"][0]["text"]
        
        # Strip any accidental markdown formatting the AI might add (like ```json ... ```)
        output_text = output_text.strip()
        if output_text.startswith("```json"):
            output_text = output_text[7:]
        if output_text.startswith("```"):
            output_text = output_text[3:]
        if output_text.endswith("```"):
            output_text = output_text[:-3]
            
        return json.loads(output_text.strip())

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Nova output as JSON: {e}")
        if retry:
            logger.info("Retrying Nova call with explicit JSON instruction...")
            # If the AI messed up the JSON, we retry once and firmly remind it of the rules
            fix_prompt = prompt + "\n\nCRITICAL: Your previous response was not valid JSON. You MUST return ONLY valid JSON."
            return call_nova(fix_prompt, retry=False)
        else:
            raise Exception("Failed to get valid JSON from Nova after retry.")
