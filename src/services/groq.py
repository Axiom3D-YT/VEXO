
import aiohttp
import logging
import os
import json
import time

logger = logging.getLogger(__name__)

class GroqService:
    """Service to interact with Groq API for generating DJ scripts."""
    
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    
    DEFAULT_PROMPT_COMPONENTS = {
        "role": """You are a Cool, Knowledgeable Music Curator. You're not a radio DJ with a "voice"; you're that friend who always knows the perfect song for the moment. Your vibe is authentic, relaxed, and conversational.""",
        "task": "Write a short, natural intro for the specified track.",
        "word_count": "Keep it under 40 words.",
        "output_format": """Return a valid JSON object with the following keys:
- "song": The song title (string)
- "artist": The artist name (string)
- "genre": The inferred genre (string)
- "release_date": The release year (string)
- "text": The intro script (string)""",
        "guidelines": """Natural Flow: Avoid "radio announcer" clichés. Talk like a real person.
Connection: Focus on how the song *feels* or the specific moment it fits.
The Reveal: Have 1/3 chance to mention the Artist and Song (naturally).
Rhythm: Use natural pauses.""",
        "vocal_cues": "Do NOT include any stage directions or bracketed text."
    }

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY not found in environment variables. Groq service will be disabled.")

    def construct_prompt(self, components: dict | None = None) -> str:
        """Construct a system prompt from components."""
        c = components or self.DEFAULT_PROMPT_COMPONENTS
        
        # Merge with defaults if keys are missing
        final_c = self.DEFAULT_PROMPT_COMPONENTS.copy()
        if components:
            final_c.update(components)
            
        return f"""ROLE:
{final_c.get('role')}
TASK:
{final_c.get('task')}
TEXT MAX WORD COUNT:
{final_c.get('word_count')}
OUTPUT FORMAT:
{final_c.get('output_format')}
STRICT GUIDELINES:
{final_c.get('guidelines')}
Vocal Cues:
{final_c.get('vocal_cues')}"""
            
    async def generate_script(self, song_title: str, artist_name: str, system_prompt: str | dict = None, model: str = None, fallback_model: str = None) -> dict | None:
        """
        Generate a DJ script for a song with fallback support.
        Returns the FULL JSON response (including metadata).
        """
        if not self.api_key:
            return None

        prompt_str = ""
        if isinstance(system_prompt, dict):
             prompt_str = self.construct_prompt(system_prompt)
        elif isinstance(system_prompt, str) and system_prompt:
             prompt_str = system_prompt
        else:
             prompt_str = self.construct_prompt(None)

        # Define models to try
        models_to_try = []
        if model:
            models_to_try.append(model)
        if fallback_model and fallback_model != model:
            models_to_try.append(fallback_model)
        
        # If no models specified or all exhausted, ensure we have a default
        if not models_to_try:
            models_to_try.append("groq/compound-mini")

        user_content = f"Song: {song_title}\nArtist: {artist_name}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        for current_model in models_to_try:
            logger.info(f"GroqService requesting script using model: {current_model}")
            
            payload = {
                "model": current_model,
                "messages": [
                    {"role": "system", "content": prompt_str},
                    {"role": "user",   "content": user_content}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }

            start_time = time.time()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.API_URL, headers=headers, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            content = data["choices"][0]["message"]["content"]
                            try:
                                json_content = json.loads(content)
                                # Validate key fields
                                if "text" in json_content:
                                    elapsed = time.time() - start_time
                                    logger.info(f"Groq generated script+metadata for '{song_title}' in {elapsed:.2f}s using {current_model}")
                                    return json_content
                                else:
                                    logger.warning(f"Groq response missing 'text' field: {json_content}")
                            except json.JSONDecodeError:
                                logger.error(f"Groq returned invalid JSON from {current_model}: {content}")
                                continue 
                        elif resp.status == 401:
                            logger.error("Groq authentication failed. Check API key.")
                            return None # Auth fails for all models
                        elif resp.status == 429:
                            logger.warning(f"Groq rate limit hit for {current_model}. Trying fallback if available...")
                        else:
                            text = await resp.text()
                            logger.error(f"Groq API error {resp.status} for {current_model}: {text}")
                            
            except Exception as e:
                logger.error(f"Failed to generate Groq script with {current_model}: {e}")
            
        logger.error("All Groq models failed to generate script.")
        return None
