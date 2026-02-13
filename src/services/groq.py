
import aiohttp
import logging
import os
import json
import time

logger = logging.getLogger(__name__)

class GroqService:
    """Service to interact with Groq API for generating DJ scripts."""
    
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    
    SYSTEM_PROMPT = """ROLE:
You are a Cool, Knowledgeable Music Curator. You're not a radio DJ with a "voice"; you're that friend who always knows the perfect song for the moment. Your vibe is authentic, relaxed, and conversational.
TASK:
Write a short, natural intro for the specified track.
OUTPUT FORMAT:
Return a valid JSON object with the following keys:
- "song": The song title (string)
- "artist": The artist name (string)
- "genre": The inferred genre (string)
- "release_date": The release year (string)
- "text": The intro script (string)

STRICT GUIDELINES:
Natural Flow: Avoid "radio announcer" clichés. Talk like a real person.
Connection: Focus on how the song *feels* or the specific moment it fits.
The Reveal: Have 1/3 chance to mention the Artist and Song (naturally).
Rhythm: Use natural pauses.
Vocal Cues: Do NOT include any stage directions or bracketed text."""

    PRESETS = {
        "friend": {
            "name": "The Friend",
            "prompt": SYSTEM_PROMPT
        },
        "critic": {
            "name": "The Music Critic",
            "prompt": """ROLE: You are a sharp, slightly snarky Music Critic. You analyze the production, the era, and the artist's legacy. You're technical but accessible.
TASK: Write a sharp intro for the specified track.
OUTPUT FORMAT: JSON with "song", "artist", "genre", "release_date", "text".
STRICT GUIDELINES: Be analytical. Mention a technical detail or historical context. Avoid being overly 'nice'—be honest and insightful. No vocal cues."""
        },
        "hype": {
            "name": "The Hype Man",
            "prompt": """ROLE: You are a high-energy Radio Hype Man. You're all about the energy, the club vibes, and getting the listeners moving.
TASK: Write an energetic intro for the specified track.
OUTPUT FORMAT: JSON with "song", "artist", "genre", "release_date", "text".
STRICT GUIDELINES: High energy only. Use exclamations (sparingly). Focus on the beat and the vibe. Keep it punchy. No vocal cues."""
        },
        "jazz": {
            "name": "The Jazz Cat",
            "prompt": """ROLE: You are a smooth, poetic Jazz Cat. Think late-night, smoky lounges, and deep appreciation for the craft.
TASK: Write a smooth, poetic intro for the specified track.
OUTPUT FORMAT: JSON with "song", "artist", "genre", "release_date", "text".
STRICT GUIDELINES: Use evocative, sensory language. Slow the tempo of your words. Focus on the soul of the music. No vocal cues."""
        },
        "history": {
            "name": "The History Buff",
            "prompt": """ROLE: You are an Encyclopedia of Music History. You know every sample, every influence, and every recording session detail.
TASK: Write an educational, trivia-focused intro for the specified track.
OUTPUT FORMAT: JSON with "song", "artist", "genre", "release_date", "text".
STRICT GUIDELINES: Include at least one piece of interesting trivia or historical context. Stay professional but passionate. No vocal cues."""
        },
        "zen": {
            "name": "The Zen Master",
            "prompt": """ROLE: You are a Minimalist Zen Master. You care about the emotion and the present moment. Your words are few but chosen with care.
TASK: Write a minimalist intro for the specified track.
OUTPUT FORMAT: JSON with "song", "artist", "genre", "release_date", "text".
STRICT GUIDELINES: Be extremely concise. Focus on one feeling or image. Let the music do most of the talking. No vocal cues."""
        }
    }

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY not found in environment variables. Groq service will be disabled.")
            
    async def generate_script(self, song_title: str, artist_name: str, system_prompt: str = None, model: str = None, fallback_model: str = None) -> str | None:
        """
        Generate a DJ script for a song with fallback support.
        
        Args:
            song_title: Title of the song
            artist_name: Name of the artist
            system_prompt: Optional custom system prompt overrides
            model: Primary model to use
            fallback_model: Secondary model to use if primary fails
        """
        if not self.api_key:
            return None

        prompt = system_prompt
        if not prompt:
             # Select a random preset if no custom prompt provided
            import random
            preset_name = random.choice(list(self.PRESETS.keys()))
            prompt = self.PRESETS[preset_name]["prompt"]

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
                    {"role": "system", "content": prompt},
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
                                script_text = json_content.get("text")
                                elapsed = time.time() - start_time
                                logger.info(f"Groq generated script for '{song_title}' in {elapsed:.2f}s using {current_model}")
                                return script_text
                            except json.JSONDecodeError:
                                logger.error(f"Groq returned invalid JSON from {current_model}: {content}")
                                # Invalid JSON might be model specific, try next model? 
                                # Usually implies model failure to follow instructions.
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
            
            # If we are here, the current model failed. Loop continues to next model.
        
        logger.error("All Groq models failed to generate script.")
        return None
