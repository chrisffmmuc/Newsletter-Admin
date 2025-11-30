# Capstone Project: The Automated E-Commerce Newsletter Agent

This project, developed as part of the Kaggle "Agents Intensive" course, automates the creation of a product newsletter for the e-commerce company "Amadoro Weinversand".

## Problem Statement

Creating a weekly or bi-weekly product newsletter is a time-consuming, manual, and error-prone process. For a typical e-commerce business, the workflow involves:

1.  **Selecting Products:** Manually choosing which products to feature.
2.  **Gathering Assets:** Finding product descriptions, prices, and images from the webshop.
3.  **Processing Images:** Manually resizing and optimizing images for email delivery.
4.  **Uploading Assets:** Manually uploading these images to the web server to get public URLs.
5.  **Writing Content:** Composing an introduction, formatting the product descriptions, and ensuring all links and prices are correct.
6.  **Assembling HTML:** Piecing everything together into a valid HTML email template.

This process can take hours and is highly susceptible to copy-paste errors, especially with prices, which can lead to customer dissatisfaction and legal issues. The goal of this project was to automate this entire workflow using an agentic system.

## Why agents?

This problem is perfectly suited for an agent-based solution rather than a simple script for several key reasons:

1.  **Multi-Step, Multi-Modal Workflow:** The process involves more than just data processing. It requires interacting with external systems (web scraping, file uploads), processing different data types (text, images), and performing creative tasks (writing an introduction). An agent can seamlessly switch between these different modes of operation.
2.  **Orchestration of Complex Tasks:** The workflow has a clear, dependent sequence of steps. An agent, particularly a "Coordinator" or "Manager" agent, is the ideal paradigm for orchestrating this sequence, ensuring one step completes before the next begins.
3.  **Reasoning and Synthesis:** The final step requires more than just data formatting. The `NewsletterWriterAgent` needs to read and understand multiple sources of information (instructions, scraped data, an HTML template, the current date) and synthesize them into a coherent, creative, and contextually relevant piece of writing. This is a core strength of LLMs.
4.  **Flexibility and Extensibility:** An agent-based architecture is modular. We can easily swap out specialist agents or add new ones (e.g., an agent to A/B test introductions) without rewriting the entire system.

## What you created

The final solution is a **Multi-Agent System** where a high-level **Coordinator Agent** manages a team of four specialist agents. The system is designed for efficiency and robustness by decoupling the agents through the filesystem.

The architecture is as follows:

### 1. Multi-agent system

The project is a clear and robust implementation of a **multi-agent system**, featuring a classic **Coordinator/Manager** architecture with multiple specialist agents.

*   **Architecture Overview:** The system is composed of one `CoordinatorAgent` that manages a team of four specialist agents. This demonstrates a hierarchical and sequential agent workflow.

*   **The Coordinator (`CoordinatorAgent`):**
    *   This agent acts as the "project manager." Its sole purpose is to understand a high-level plan and delegate tasks to the appropriate specialists.
    *   Its tools are not Python functions, but the other agents themselves, wrapped in `AgentTool`. This is a direct implementation of the agent-as-a-tool concept.

*   **The Specialists:** Each of the four specialist agents demonstrates a clear separation of concerns:
    1.  **`ImageProcessingAgent`:** A specialist responsible only for downloading and resizing images.
    2.  **`UploadAgent`:** A specialist that uses Playwright to handle the complex, stateful task of logging into a web backend and uploading files.
    3.  **`TextScrapingAgent`:** A specialist that scrapes and structures web content.
    4.  **`NewsletterWriterAgent`:** A creative specialist that uses a more powerful model (`gemini-2.5-flash`) to perform the complex reasoning and synthesis task of writing the final HTML.

*   **Sequential Workflow:** The `master_prompt` explicitly instructs the `CoordinatorAgent` to follow a sequential workflow, waiting for the output of one agent (e.g., the file paths from the `ImageProcessingAgent`) before calling the next (the `UploadAgent`). This demonstrates a controlled, predictable agent orchestration.

### 2. Tools (Custom)

The project makes extensive use of powerful **custom tools**, which are bespoke Python functions designed to give the agents real-world capabilities beyond simple text generation.

*   **File I/O and Data Persistence:**
    *   `get_and_save_all_article_texts`: This tool doesn't just return data; it interacts with the filesystem to save its results to `scraped_texts.json`, decoupling the workflow.
    *   `upload_images_and_get_urls`: Similarly, this tool saves its results to `uploaded_image_urls.json`.
    *   `write_newsletter_to_file`: The final tool in the chain, which persists the agent's ultimate creative output into a dated HTML file.
    *   `read_file_content`: Empowers the `NewsletterWriterAgent` to read its own context from the filesystem, making the system highly efficient in token usage.

*   **Web Interaction (Scraping & Automation):**
    *   The scraping and image-finding logic uses the `requests` and `BeautifulSoup` libraries, demonstrating how agents can be equipped to parse and understand live web pages.
    *   The `upload_images_and_get_urls` tool uses **`playwright`** to perform complex browser automation, including logging into a password-protected admin panel, navigating menus, and handling file chooser dialogs. This is a very advanced form of custom tooling.

*   **Image Processing:**
    *   The `process_images_from_urls` tool uses the `Pillow` library to perform image manipulation (resizing and converting formats), a non-trivial task for an agent system.

The use of these custom tools grounds the agent system in reality, allowing it to perform a complete, end-to-end business workflow.

### 3. Sessions & Memory

The project correctly implements and relies on **Sessions & State Management** to enable its complex, multi-step workflow.

*   **`InMemorySessionService`:** The system is explicitly initialized with an `InMemorySessionService`. While simple, this is the foundational layer for agent memory.

*   **Stateful Coordination:** The entire operation runs within a single session (`session1`) for the `CoordinatorAgent`. This is not just a detail; it is **absolutely critical** for the project's success. The session allows the `CoordinatorAgent` to maintain context across multiple tool calls. For example:
    1.  It calls the `ImageProcessingAgent`. The result (a list of file paths) is added to the session history.
    2.  The agent then reasons about its next step. It looks at its history, finds the list of file paths, and uses that data to formulate the correct call to the `UploadAgent`.
    3.  This continues for all four steps, with the agent building upon the results of previous tool calls stored in its short-term session memory.

Without the session, each call would be stateless, and the `CoordinatorAgent` would have no memory of the file paths or URLs, making the orchestration impossible. This demonstrates a clear understanding of how session state enables complex, sequential agentic tasks.

## Demo

To run the project, a user simply executes the `newsletter_multi_agent.py` script from their terminal:
```sh
python newsletter_multi_agent.py
```
The script uses the file "Artikelliste_Newsletter.txt" including a manually defined list of URLs (of www.amadoro.de Webshop) to be included in the newsletter. This configuration file can be changed upfront script execution to create a newsletter for other articles, as needed.

The script then provides a real-time log of the agent's actions. At the end it gives a confirmation message `✅ Newsletter successfully saved to: Newsletter_YYYYMMDD.html` and the `CoordinatorAgent` prints its final report, such as "All steps completed successfully."

The user can then open the newly created `Newsletter_YYYYMMDD.html` file in their browser to see the final product.
This final Newsletter can then be pasted as html in a third Party tool for sending it to the recipients; I'm using SuperMailer for recipient handling and sending.

See provided screenshots of execution: 
a) Real-time log until newsletter completion, and 
b) Screenshot of opened newsletter in browser preview.


## The Build

*   **Core Framework:** Google Agent Development Kit (ADK)
*   **Language:** Python
*   **LLM Models:**
    *   `gemini-2.5-flash`: Used for the efficient, task-oriented Coordinator, Image, Upload, and Scraper agents.
    *   `gemini-2.5-pro`: Used for the `NewsletterWriterAgent` to provide the extra reasoning power needed for the complex creative and synthesis task.
*   **Key Libraries:**
    *   `google-generativeai`: Provides the core connectivity for the ADK.
    *   `requests` & `BeautifulSoup4`: Used for the robust web scraping of article data.
    *   `Pillow`: Used for all image processing (resizing, converting).
    *   `playwright`: Used for browser automation to handle the webshop login and file upload process.
    *   `asyncio`: Used to run the asynchronous agent framework.

## If I had more time, this is what I'd do

*   **Error Handling & Retries:** Implement more robust error handling within the coordinator's logic. If a specialist agent fails, the coordinator could retry the step or report a more specific failure message instead of just stopping.
*   **Dynamic Product Selection:** Create a new `ProductSelectionAgent` that could connect to a sales database or analytics API to automatically select the best products to feature in the newsletter (e.g., new arrivals, best-sellers, or items with high inventory).
*   **A/B Testing Agent:** Add an agent that takes the final generated content and creates two versions with different introductions or subject lines, allowing for A/B testing of the newsletter's performance.
*   **Full CI/CD Automation:** Integrate the script into a CI/CD pipeline (like GitHub Actions) that runs automatically on a schedule (e.g., every Tuesday), making the entire process truly "headless" and fully automated.
*   **Vector Database for Content:** Instead of reading from a static HTML example, the `writer_agent` could retrieve stylistic examples from a vector database of past successful newsletters, allowing it to adapt its tone and style over time.
