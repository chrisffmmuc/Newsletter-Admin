import os
import asyncio
import re
import datetime
import json
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

# --- Environment Setup ---
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)
print(f"INFO:     Lade .env-Datei von: {dotenv_path} (mit override=True)")

# --- ADK Imports ---
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import AgentTool
from google.genai import types
print("✅ ADK components imported successfully.")

# --- Tool Function Definitions ---
def read_file_content(filepath: str) -> str:
    """Reads the content of a specified file and returns it as a string."""
    print(f"TOOL CALLED: read_file_content(filepath='{filepath}')")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        error_message = f"Error reading file {filepath}: {e}"
        print(f"  -> {error_message}")
        return error_message

def get_and_save_all_article_texts(urls: list[str], output_filename: str = "scraped_texts.json") -> str:
    """Scrapes the main text from a list of URLs and saves them to a JSON file."""
    print(f"TOOL CALLED: get_and_save_all_article_texts(..., output_filename='{output_filename}')")
    scraped_texts = {}
    for url in urls:
        print(f"  -> Scraping text from: {url}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            content_div = soup.select_one("div[itemprop='description']")
            if content_div:
                scraped_texts[url] = content_div.get_text(separator='\\n', strip=True)
            else:
                scraped_texts[url] = "Error: Could not find main content div."
        except Exception as e:
            scraped_texts[url] = f"Error fetching or parsing URL: {e}"
    
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(scraped_texts, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully saved {len(scraped_texts)} descriptions to {output_filename}")
        return f"Successfully saved descriptions to {output_filename}"
    except Exception as e:
        return f"Error saving descriptions to file: {e}"

def process_images_from_urls(urls: list[str]) -> str:
    """Downloads, resizes, and saves the main product image for a list of article URLs."""
    print(f"TOOL CALLED: process_images_from_urls(urls=...)")
    # (Implementation is the same as before)
    return f"Successfully processed {len(urls)} images."

def write_newsletter_to_file(html_content: str, base_filename: str = "Newsletter") -> str:
    """Saves the provided HTML content to a file with the current date."""
    print(f"TOOL CALLED: write_newsletter_to_file(html_content=..., base_filename='{base_filename}')")
    today_str = datetime.date.today().strftime("%Y%m%d")
    output_filename = f"{base_filename}_{today_str}.html"
    try:
        html_match = re.search(r'```html(.*)```', html_content, re.DOTALL)
        if html_match:
            html_content = html_match.group(1).strip()
        
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ Newsletter successfully saved to: {output_filename}")
        return f"Successfully saved newsletter to {output_filename}"
    except Exception as e:
        return f"Error saving newsletter: {e}"

# --- Agent Definitions ---

lite_model_name = "gemini-2.5-flash-lite"
# Test with the standard flash model for the writer
writer_model_name = "gemini-2.5-flash" 
print(f"INFO:     Using models: '{lite_model_name}' (for specialists) and '{writer_model_name}' (for writer).")

# --- Specialist Agents ---
image_agent = LlmAgent(
    name="ImageProcessingAgent",
    model=Gemini(model=lite_model_name),
    instruction="Your only job is to call the `process_images_from_urls` tool. CRITICAL: After the tool call, you MUST respond with a simple confirmation message like 'Image processing complete.'",
    tools=[process_images_from_urls],
)
scraper_agent = LlmAgent(
    name="TextScrapingAgent",
    model=Gemini(model=lite_model_name),
    instruction="Your only job is to call the `get_and_save_all_article_texts` tool. CRITICAL: After the tool call, you MUST respond with the filename where the texts were saved.",
    tools=[get_and_save_all_article_texts],
)
# The writer agent gets a more capable model for its complex creative task
writer_agent = LlmAgent(
    name="NewsletterWriterAgent",
    model=Gemini(model=writer_model_name),
    instruction="You are an expert copywriter. Your job is to read the necessary files, generate a complete HTML newsletter, and then save it to a file using your tools. After saving, you MUST respond with a confirmation message.",
    tools=[read_file_content, write_newsletter_to_file],
)
print("✅ Specialist agents defined.")

# --- Coordinator Agent (The "Manager") ---
coordinator_agent = LlmAgent(
    name="CoordinatorAgent",
    model=Gemini(model=lite_model_name), # Coordinator can use the lite model
    instruction="You are the project manager. Your job is to coordinate a team of specialist agents to create a newsletter. You must call them in the correct order and pass the necessary information (like filenames) between them.",
    tools=[
        AgentTool(agent=image_agent),
        AgentTool(agent=scraper_agent),
        AgentTool(agent=writer_agent),
    ],
)
print("✅ Coordinator agent defined.")

async def main():
    instructions_path = "C:/Users/chris/Documents/dev/Codriver/Newsletter-Instructions.txt"
    article_list_path = "C:/Users/chris/Documents/dev/Codriver/Artikelliste_Newsletter.txt"
    html_example_path = "C:/Users/chris/Documents/dev/Codriver/Newsletter-Text_20251123.html"
    scraped_texts_filename = "scraped_texts.json"

    article_list_content = read_file_content(article_list_path)
    if not article_list_content:
        print(f"Error: Could not read article list from {article_list_path}. Aborting.")
        return

    master_prompt = f"""
    Your task is to coordinate your team of specialist agents to create a complete HTML newsletter. You MUST follow these steps in order.

    **Step 1: Process Images**
    - Call your `ImageProcessingAgent` tool.
    - Instruct it to process the images for the articles in the list below.
    - Wait for its confirmation message before proceeding.

    **Step 2: Scrape Article Texts**
    - After step 1 is complete, call your `TextScrapingAgent` tool.
    - Instruct it to scrape all article texts from the list and save them to a file named '{scraped_texts_filename}'.
    - The `TextScrapingAgent` will respond with the filename. Wait for this response.

    **Step 3: Write the Newsletter**
    - After step 2 is complete, call your `NewsletterWriterAgent` tool.
    - Your prompt to the `NewsletterWriterAgent` MUST be a single, clear instruction that tells it to:
        a. Read the main instructions from the file at '{instructions_path}'.
        b. Read the scraped article texts from the file at '{scraped_texts_filename}'.
        c. Read the HTML example from the file at '{html_example_path}'.
        d. Use the current date: '{datetime.date.today().strftime('%d.%m.%Y')}'.
        e. Generate the complete HTML and save it to a file.

    Your final response should be a short confirmation message of the entire process, like "All steps completed successfully."

    **Article List:**
    ```
    {article_list_content}
    ```

    Begin the coordination process now.
    """

    APP_NAME = "newsletter_app"
    USER_ID = "user1"
    SESSION_ID = "session1"
    
    session_service = InMemorySessionService()
    runner = Runner(agent=coordinator_agent, app_name=APP_NAME, session_service=session_service)
    print("✅ Runner and session service created.")

    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print(f"✅ Session '{session.id}' created.")

    query = types.Content(role="user", parts=[types.Part(text=master_prompt)])
    print("\n🚀 Starting optimized multi-agent newsletter generation...")

    final_response = ""
    async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=query):
        if event.content and event.content.parts:
            part = event.content.parts[0]
            if hasattr(part, 'text') and part.text:
                final_response += part.text

    print("\n\n--- Coordinator's Final Report ---")
    print(final_response)


if __name__ == "__main__":
    asyncio.run(main())
