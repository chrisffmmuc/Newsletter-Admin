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
from playwright.async_api import async_playwright

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
        return f"Error reading file {filepath}: {e}"

def get_and_save_all_article_texts(urls: list[str], output_filename: str = "scraped_texts.json") -> str:
    """Scrapes structured data (description, price, etc.) from URLs and saves to a JSON file."""
    print(f"TOOL CALLED: get_and_save_all_article_texts(..., output_filename='{output_filename}')")
    scraped_data = {}
    for url in urls:
        print(f"  -> Scraping data from: {url}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            article_data = {}
            
            # Scrape description
            desc_div = soup.select_one("div[itemprop='description']")
            article_data['description'] = desc_div.get_text(separator='\\n', strip=True) if desc_div else "N/A"
            
            # Scrape price
            price_p = soup.select_one(".product-detail-price")
            article_data['price'] = price_p.get_text(strip=True) if price_p else "N/A"
            
            # Scrape unit content
            unit_span = soup.select_one(".price-unit-content")
            article_data['unit_content'] = unit_span.get_text(strip=True) if unit_span else "N/A"
            
            # Scrape price per unit
            ref_span = soup.select_one(".price-unit-reference-content")
            article_data['price_per_unit'] = ref_span.get_text(strip=True) if ref_span else "N/A"
            
            scraped_data[url] = article_data
            
        except Exception as e:
            scraped_data[url] = {"error": f"Error fetching or parsing URL: {e}"}
    
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(scraped_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully saved structured data for {len(scraped_data)} articles to {output_filename}")
        return f"Successfully saved structured data to {output_filename}"
    except Exception as e:
        return f"Error saving data to file: {e}"

def process_images_from_urls(urls: list[str]) -> list[str]:
    """Downloads, resizes, and saves images, returning a list of their absolute file paths."""
    print(f"TOOL CALLED: process_images_from_urls(urls=...)")
    TARGET_HEIGHT = 300
    processed_files = []
    def get_image_url(article_url):
        try:
            r = requests.get(article_url); r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            meta = soup.find("meta", property="og:image")
            if meta and meta.get("content"): return meta["content"]
            img = soup.select_one(".product--image-container img, div.image-slider--item img")
            if img and "src" in img.attrs:
                url = img["src"]
                if url.startswith("//"): return "https:" + url
                if url.startswith("/"): return f"{article_url.split('/')[0]}//{article_url.split('/')[2]}{url}"
                return url
        except: return None
    for url in urls:
        img_url = get_image_url(url)
        if not img_url:
            print(f"  -> No image URL found for {url}.")
            continue
        try:
            r = requests.get(img_url); r.raise_for_status()
            img = Image.open(BytesIO(r.content))
            ratio = img.width / img.height
            new_fn = f"{os.path.splitext(os.path.basename(img_url.split('?')[0]))[0]}_300.jpg"
            img.resize((int(300*ratio), 300), Image.LANCZOS).convert("RGB").save(new_fn, "JPEG")
            processed_files.append(os.path.abspath(new_fn))
        except Exception as e: print(f"  -> Failed for {url}: {e}")
    print(f"✅ Image processing complete. Saved {len(processed_files)} files.")
    return processed_files

async def upload_images_and_get_urls(file_paths: list[str], output_filename: str = "uploaded_image_urls.json") -> str:
    """Uploads images and saves their public URLs to a JSON file."""
    print(f"TOOL CALLED: upload_images_and_get_urls for {len(file_paths)} files...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto("https://www.amadoro.de/admin#/login/")
            await page.get_by_role("textbox", name="Benutzername").fill(os.getenv("AMADORO_LOGIN"))
            await page.get_by_role("textbox", name="Passwort").fill(os.getenv("AMADORO_PASSWORD"))
            await page.get_by_role("button", name="Anmelden").click()
            await page.get_by_text("Inhalte").click()
            await page.get_by_label("Hauptnavigation").get_by_role("link", name="Medien").click()
            await page.get_by_role("button", name="Folder thumbnail Migration").click()
            await page.get_by_role("button", name="Folder thumbnail Aktionen").click()

            async with page.expect_file_chooser() as fc_info:
                await page.get_by_role("button", name="Dateien hochladen").click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(file_paths)

            try:
                modal = page.locator("div.sw-duplicated-media-v2")
                await modal.wait_for(state="visible", timeout=3000)
                await page.get_by_text("Hochladen und ersetzen").click()
                if await page.get_by_role("checkbox", name=re.compile("Auswahl merken")).is_visible():
                    await page.get_by_role("checkbox", name=re.compile("Auswahl merken")).check()
                await page.get_by_role("button", name="Datei ersetzen").click()
                await modal.wait_for(state="hidden", timeout=10000)
            except Exception:
                print("No 'duplicate file' modal appeared.")

            await page.locator("[role=banner]").first.wait_for(state="visible", timeout=5000)
            await page.wait_for_selector("[role=banner]", state="hidden", timeout=15000)
            print("Upload confirmed.")

            while await page.get_by_role("button", name="Weitere laden").is_visible():
                await page.get_by_role("button", name="Weitere laden").click()
                try:
                    await page.get_by_role("button", name="Weitere laden").wait_for(state="visible", timeout=5000)
                except Exception:
                    break
            
            urls = {}
            for path in file_paths:
                name = os.path.basename(path)
                alt_name = os.path.splitext(name)[0]
                article_img = page.locator(f"img.sw-media-preview-v2__item[alt='{alt_name}']").first
                await article_img.wait_for(state="visible", timeout=5000)
                url = await article_img.get_attribute("src")
                urls[name] = url
            
            print(f"✅ Successfully collected {len(urls)} image URLs.")
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(urls, f, ensure_ascii=False, indent=2)
            return f"Successfully saved image URLs to {output_filename}"
        finally:
            await context.close()
            await browser.close()

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
lite_model_name = "gemini-2.5-flash"
writer_model_name = "gemini-2.5-pro"
print(f"INFO:     Using models: '{lite_model_name}' (for specialists) and '{writer_model_name}' (for writer).")

image_agent = LlmAgent(name="ImageProcessingAgent", model=Gemini(model=lite_model_name), instruction="Your only job is to call the `process_images_from_urls` tool. CRITICAL: After the tool call, you MUST respond with the list of file paths returned by the tool.", tools=[process_images_from_urls])
upload_agent = LlmAgent(name="UploadAgent", model=Gemini(model=lite_model_name), instruction="Your only job is to call the `upload_images_and_get_urls` tool. CRITICAL: After the tool call, you MUST respond with the filename of the saved URL dictionary.", tools=[upload_images_and_get_urls])
scraper_agent = LlmAgent(name="TextScrapingAgent", model=Gemini(model=lite_model_name), instruction="Your only job is to call the `get_and_save_all_article_texts` tool. CRITICAL: After the tool call, you MUST respond with the filename where the texts were saved.", tools=[get_and_save_all_article_texts])
writer_agent = LlmAgent(name="NewsletterWriterAgent", model=Gemini(model=writer_model_name), instruction="You are an expert copywriter. Your job is to read files containing structured data (JSON), generate a complete HTML newsletter ensuring price accuracy, and then save it to a file using your tool. CRITICAL: After saving, you MUST respond with a confirmation message.", tools=[read_file_content, write_newsletter_to_file])
print("✅ Specialist agents defined.")

coordinator_agent = LlmAgent(
    name="CoordinatorAgent",
    model=Gemini(model=lite_model_name),
    instruction="You are the project manager. Coordinate your team of agents to create a newsletter. Call them in the correct order and pass the necessary data (file paths, URLs) between them. Your job is only finished when the writer agent confirms the file has been saved.",
    tools=[AgentTool(agent=image_agent), AgentTool(agent=upload_agent), AgentTool(agent=scraper_agent), AgentTool(agent=writer_agent)],
)
print("✅ Coordinator agent defined.")

async def main():
    instructions_path = "C:/Users/chris/Documents/dev/Codriver/Newsletter-Instructions.txt"
    article_list_path = "C:/Users/chris/Documents/dev/Codriver/Artikelliste_Newsletter.txt"
    html_example_path = "C:/Users/chris/Documents/dev/Codriver/Newsletter-Text_20251123.html"
    scraped_texts_filename = "scraped_texts.json"
    image_urls_filename = "uploaded_image_urls.json"

    article_list_content = read_file_content(article_list_path)
    if not article_list_content:
        print(f"Error: Could not read article list from {article_list_path}. Aborting.")
        return

    master_prompt = f"""
    Your task is to coordinate your team of specialist agents to create a complete HTML newsletter. You MUST follow these steps in order.

    **Step 1: Process Images**
    - Call your `ImageProcessingAgent` tool to process the images for the articles in the list below. It will return a list of local file paths.

    **Step 2: Upload Images**
    - Take the list of file paths from Step 1 and call your `UploadAgent` tool to upload them and save the resulting public URLs to a file named '{image_urls_filename}'.

    **Step 3: Scrape Article Texts**
    - Call your `TextScrapingAgent` tool to scrape all article texts and save them to '{scraped_texts_filename}'.

    **Step 4: Write the Newsletter**
    - Call your `NewsletterWriterAgent` tool. Your prompt to it MUST be a single, clear instruction that tells it to:
        a. Read instructions from '{instructions_path}'.
        b. Read the structured article data (including prices) from '{scraped_texts_filename}'.
        c. Read the HTML example from '{html_example_path}'.
        d. Read the public image URLs from '{image_urls_filename}'.
        e. Use the current date: '{datetime.date.today().strftime('%d.%m.%Y')}'.
        f. Generate the complete HTML, ensuring all prices, units, and price-per-unit values are 100% accurate based on the scraped data, and then save it to a file.

    Your final response should be a short confirmation message.

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
    print("\n🚀 Starting full end-to-end newsletter generation...")

    final_response = ""
    async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=query):
        if event.content and event.content.parts and hasattr(event.content.parts[0], 'text') and event.content.parts[0].text:
            final_response += event.content.parts[0].text

    print("\n\n--- Coordinator's Final Report ---")
    print(final_response)


if __name__ == "__main__":
    asyncio.run(main())
