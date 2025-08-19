#!/usr/bin/env python3
"""
Pharmacy Tools
Advanced tools for pharmacy analysis, medication database operations, and prescription planning.
"""

import json
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Union
import psycopg2
from psycopg2.extras import RealDictCursor
import time
import random

from pathlib import Path
import sys
import os

# Add the project root and backend to Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_path))

from app.core.config import settings
# Remove all imports from configurations.pharmacy_config since they are not used in the medication search tool

from langchain_core.tools import Tool

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User profile configuration for YouTube authentication
YOUTUBE_USER_PROFILE_PATH = getattr(settings, 'YOUTUBE_USER_PROFILE_PATH', None)
BROWSER_TYPE = getattr(settings, 'YOUTUBE_BROWSER_TYPE', 'chrome')

# Rate limiting configuration
YOUTUBE_REQUEST_DELAY = 2.0  # Minimum seconds between YouTube API requests
YOUTUBE_MAX_REQUESTS_PER_MINUTE = 10  # Maximum requests per minute
_last_youtube_request_time = 0
_youtube_request_count = 0
_youtube_request_window_start = 0

# Enhanced transcript configuration
YOUTUBE_LANGUAGES = ['en', 'en-US', 'en-GB', 'es', 'fr', 'de']  # Try multiple languages
YOUTUBE_PROXIES = []  # Can be populated with proxy servers if needed

def get_youtube_transcript_with_fallback(api, video_id: str) -> Optional[str]:
    """
    Try to get YouTube transcript with multiple language fallbacks.
    """
    for language in YOUTUBE_LANGUAGES:
        try:
            transcript = api.fetch(video_id, languages=[language])
            full_text = " ".join([snippet.text for snippet in transcript.snippets])
            logger.info(f"Successfully extracted transcript in {language}: {len(full_text)} characters")
            return full_text
        except Exception as e:
            logger.debug(f"Failed to get transcript in {language}: {e}")
            continue
    
    return None


# --- Pharmacy Medication Search Tool ---
import re
import urllib.parse
import asyncio
from typing import List, Dict, Any, Optional

try:
    from serpapi import GoogleSearch
    from youtube_transcript_api import YouTubeTranscriptApi
    from pyppeteer import launch
except ImportError:
    GoogleSearch = None
    YouTubeTranscriptApi = None
    launch = None

from langchain_community.utilities.google_serper import GoogleSerperAPIWrapper

import requests
from bs4 import BeautifulSoup

def apply_youtube_rate_limit():
    """
    Apply rate limiting for YouTube API requests to avoid IP blocking.
    Implements both per-request delays and per-minute request limits.
    """
    global _last_youtube_request_time, _youtube_request_count, _youtube_request_window_start
    
    current_time = time.time()
    
    # Reset request count if we're in a new minute window
    if current_time - _youtube_request_window_start >= 60:
        _youtube_request_count = 0
        _youtube_request_window_start = current_time
    
    # Check if we've hit the per-minute limit
    if _youtube_request_count >= YOUTUBE_MAX_REQUESTS_PER_MINUTE:
        wait_time = 60 - (current_time - _youtube_request_window_start)
        if wait_time > 0:
            logger.info(f"Rate limit reached. Waiting {wait_time:.1f}s for next minute window...")
            time.sleep(wait_time)
            _youtube_request_count = 0
            _youtube_request_window_start = time.time()
    
    # Apply minimum delay between requests
    time_since_last = current_time - _last_youtube_request_time
    if time_since_last < YOUTUBE_REQUEST_DELAY:
        delay = YOUTUBE_REQUEST_DELAY - time_since_last
        # Add small random jitter to avoid synchronized requests
        jitter = random.uniform(0.1, 0.5)
        total_delay = delay + jitter
        logger.info(f"Applying rate limit delay: {total_delay:.1f}s")
        time.sleep(total_delay)
    
    # Update tracking variables
    _last_youtube_request_time = time.time()
    _youtube_request_count += 1

def google_search(query: str, site: Optional[str] = None, max_results: int = 10) -> List[str]:
    api_key = "75885909dc660d544bb5dba225d2698c52e9fc78"
    google_serper = GoogleSerperAPIWrapper(serper_api_key=api_key)
    # Add site restriction if provided
    if site:
        query = f"{query} site:{site}"
    # Use the .results() method for structured output
    results = google_serper.results(query)
    # Extract links from 'organic' results if present
    links = []
    for item in results.get("organic", []):
        url = item.get("link")
        if url:
            links.append(url)
    return links

def extract_video_id(url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    return qs.get("v", [None])[0]

async def check_youtube_video_with_profile(url: str, target_nutrient: str = "protein", amount: int = 30) -> Dict[str, Any]:
    """
    Check YouTube video using browser automation with user profile for authentication.
    This allows access to age-restricted or login-required videos.
    """
    if not launch:
        logger.warning("Pyppeteer not available, falling back to basic method")
        return check_youtube_video_basic(url, target_nutrient, amount)
    
    video_id = extract_video_id(url)
    if not video_id:
        return {"url": url, "matched": False, "error": "Invalid YouTube URL"}
    
    browser_args = ['--no-sandbox', '--disable-setuid-sandbox']
    
    # Add user profile if configured
    if YOUTUBE_USER_PROFILE_PATH and os.path.exists(YOUTUBE_USER_PROFILE_PATH):
        if BROWSER_TYPE.lower() == "chrome":
            browser_args.extend([
                f'--user-data-dir={YOUTUBE_USER_PROFILE_PATH}',
                '--profile-directory=Default'  # or specify a specific profile
            ])
        logger.info(f"Using user profile: {YOUTUBE_USER_PROFILE_PATH}")
    
    browser = None
    try:
        browser = await launch(
            headless=False,  # Set to True for headless mode
            args=browser_args,
            executablePath=None  # Let pyppeteer find the browser
        )
        page = await browser.newPage()
        
        # Navigate to YouTube video
        await page.goto(f"https://www.youtube.com/watch?v={video_id}", {
            'waitUntil': 'networkidle2',
            'timeout': 30000
        })
        
        # Wait for page to load and check if transcript is available
        try:
            # Look for transcript button/option
            await page.waitForSelector('[aria-label*="transcript" i], [aria-label*="captions" i]', {'timeout': 5000})
            
            # Try to click transcript/captions button
            transcript_button = await page.querySelector('[aria-label*="transcript" i], [aria-label*="captions" i]')
            if transcript_button:
                await transcript_button.click()
                await page.waitFor(2000)  # Wait for transcript to load
                
                # Extract transcript text
                transcript_elements = await page.querySelectorAll('.ytd-transcript-segment-renderer')
                transcript_text = ""
                for element in transcript_elements:
                    text = await page.evaluate('(element) => element.textContent', element)
                    transcript_text += text + " "
                
                # Check for target nutrient in transcript
                if re.search(rf"{target_nutrient}", transcript_text, re.IGNORECASE):
                    return {
                        "url": url, 
                        "matched": True, 
                        "source": "youtube_profile", 
                        "method": "transcript"
                    }
        except Exception as transcript_error:
            logger.info(f"Transcript not available or accessible: {transcript_error}")
        
        # Fallback: Check video title and description
        try:
            title_element = await page.querySelector('h1.ytd-video-primary-info-renderer')
            title = await page.evaluate('(element) => element.textContent', title_element) if title_element else ""
            
            description_element = await page.querySelector('#description-text')
            description = await page.evaluate('(element) => element.textContent', description_element) if description_element else ""
            
            combined_text = f"{title} {description}"
            if re.search(rf"{target_nutrient}", combined_text, re.IGNORECASE):
                return {
                    "url": url, 
                    "matched": True, 
                    "source": "youtube_profile", 
                    "method": "title_description"
                }
        except Exception as desc_error:
            logger.warning(f"Could not extract title/description: {desc_error}")
        
        return {"url": url, "matched": False, "source": "youtube_profile"}
        
    except Exception as e:
        logger.error(f"Error checking YouTube video with profile: {e}")
        return {"url": url, "matched": False, "error": str(e)}
    finally:
        if browser:
            await browser.close()

def check_youtube_video_basic(url: str, target_nutrient: str = "protein", amount: int = 30) -> Dict[str, Any]:
    """
    Basic YouTube video checking without user profile (fallback method).
    """
    if not YouTubeTranscriptApi:
        return {"url": url, "matched": False, "error": "YouTube transcript API not available"}
    
    video_id = extract_video_id(url)
    if not video_id:
        return {"url": url, "matched": False, "error": "Invalid YouTube URL"}
    
    # Apply rate limiting before making YouTube API request
    apply_youtube_rate_limit()
    
    try:
        # Create API instance and fetch transcript with language fallbacks
        api = YouTubeTranscriptApi()
        full_text = get_youtube_transcript_with_fallback(api, video_id)
        
        if full_text:
            logger.info(f"Extracted transcript: {len(full_text)} characters")
            
            # Check for target nutrient in transcript
            if re.search(rf"{target_nutrient}", full_text, re.IGNORECASE):
                nutrient_matches = len(re.findall(rf"{target_nutrient}", full_text, re.IGNORECASE))
                return {
                    "url": url, 
                    "matched": True, 
                    "source": "youtube_basic", 
                    "method": "transcript",
                    "matches": nutrient_matches,
                    "transcript_length": len(full_text)
                }
        else:
            raise Exception("No transcript available in supported languages")
    except Exception as transcript_exc:
        logger.info(f"Transcript extraction failed: {transcript_exc}")
        
        # Check if it's a rate limiting error
        if "blocking requests" in str(transcript_exc).lower() or "ipblocked" in str(transcript_exc).lower():
            logger.warning("YouTube IP blocking detected. Consider using proxy or waiting longer between requests.")
            # Apply exponential backoff for rate limit errors
            backoff_delay = random.uniform(30, 60)  # Wait 30-60 seconds
            logger.info(f"Applying backoff delay: {backoff_delay:.1f}s")
            time.sleep(backoff_delay)
        
        # Fallback: scrape video description for nutrient keyword
        try:
            video_page = requests.get(f"https://www.youtube.com/watch?v={video_id}")
            soup = BeautifulSoup(video_page.text, "html.parser")
            # YouTube descriptions are in <meta name="description" content="...">
            desc_tag = soup.find("meta", attrs={"name": "description"})
            description = desc_tag.get("content", "") if desc_tag else ""
            if re.search(rf"{target_nutrient}", description, re.IGNORECASE):
                return {
                    "url": url, 
                    "matched": True, 
                    "source": "youtube_basic", 
                    "method": "description"
                }
            return {
                "url": url, 
                "matched": False, 
                "source": "youtube_basic", 
                "error": "Transcript unavailable, description checked",
                "fallback_attempted": True
            }
        except Exception as fallback_exc:
            return {
                "url": url, 
                "matched": False, 
                "source": "youtube_basic", 
                "error": f"Transcript and description fetch failed: {fallback_exc}"
            }
    
    return {"url": url, "matched": False, "source": "youtube_basic"}

def check_youtube_video(url: str, target_nutrient: str = "protein", amount: int = 30) -> Dict[str, Any]:
    """
    Main YouTube video checking function that chooses between profile and basic methods.
    """
    if YOUTUBE_USER_PROFILE_PATH and os.path.exists(YOUTUBE_USER_PROFILE_PATH):
        # Use async method with user profile
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(check_youtube_video_with_profile(url, target_nutrient, amount))
            return result
        finally:
            loop.close()
    else:
        # Use basic method without profile
        return check_youtube_video_basic(url, target_nutrient, amount)

async def extract_nutrients_from_page(url: str, target_nutrient: str = "protein", amount: int = 30) -> Dict[str, Any]:
    """
    Extract nutrients from web pages. Falls back to basic HTTP scraping when browser automation fails.
    """
    # First try browser automation
    if launch:
        try:
            browser = await launch(headless=True, args=['--no-sandbox'])
            page = await browser.newPage()
            await page.goto(url, {'waitUntil': 'networkidle2'})
            content = await page.content()
            
            # Look for specific nutrient amounts
            if re.search(fr"{amount}\s*g\s+{target_nutrient}", content, re.IGNORECASE):
                return {"url": url, "matched": True, "source": "web_browser", "method": "browser_automation"}
            
            await browser.close()
        except Exception as e:
            logger.warning(f"Browser automation failed: {e}")
            # Continue to fallback method
    
    # Fallback to basic HTTP scraping
    return extract_nutrients_from_page_basic(url, target_nutrient, amount)

def extract_nutrients_from_page_basic(url: str, target_nutrient: str = "protein", amount: int = 30) -> Dict[str, Any]:
    """
    Enhanced web scraping that extracts detailed content for prescription planning.
    Works on all platforms including Apple Silicon.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Extract structured content
        content_data = extract_structured_content(soup, target_nutrient, amount)
        
        # Get clean text content
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Generic nutrient patterns that work for any nutrient
        nutrient_patterns = [
            rf"{amount}\s*g\s+{target_nutrient}",           # "30g protein"
            rf"{target_nutrient}.*?{amount}\s*g",           # "protein: 30g"
            rf"{amount}\s*grams?\s+{target_nutrient}",      # "30 grams protein"
            rf"{target_nutrient}.*?{amount}\s*grams?",      # "protein: 30 grams"
            rf"{amount}\s*g\s+of\s+{target_nutrient}",      # "30g of protein"
            rf"{target_nutrient}:\s*{amount}\s*g",          # "protein: 30g"
            rf"{target_nutrient}\s*\({amount}g\)",          # "protein (30g)"
            rf"{amount}g\s+{target_nutrient}",              # "30g protein"
        ]
        
        # Check for specific amount matches first (highest priority)
        for pattern in nutrient_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                result = {
                    "url": url, 
                    "matched": True, 
                    "source": "web_basic", 
                    "method": "http_scraping",
                    "matches": len(matches),
                    "match_type": "specific_amount",
                    "target_amount": amount,
                    "target_nutrient": target_nutrient
                }
                # Add extracted content
                result.update(content_data)
                return result
        
        # Fallback: look for the nutrient name without specific amounts
        general_nutrient_matches = re.findall(rf"\b{target_nutrient}\b", text, re.IGNORECASE)
        if general_nutrient_matches:
            result = {
                "url": url, 
                "matched": True, 
                "source": "web_basic", 
                "method": "http_scraping",
                "matches": len(general_nutrient_matches),
                "match_type": "general_mention",
                "target_nutrient": target_nutrient,
                "note": f"Found {len(general_nutrient_matches)} mentions of {target_nutrient} but no specific {amount}g amounts"
            }
            # Add extracted content even for general matches
            result.update(content_data)
            return result
        
        return {
            "url": url, 
            "matched": False, 
            "source": "web_basic", 
            "method": "http_scraping",
            "target_nutrient": target_nutrient,
            "target_amount": amount
        }
        
    except Exception as e:
        return {
            "url": url, 
            "matched": False, 
            "source": "web_basic", 
            "error": str(e),
            "target_nutrient": target_nutrient,
            "target_amount": amount
        }

def extract_structured_content(soup: BeautifulSoup, target_nutrient: str, amount: int) -> Dict[str, Any]:
    """
    Extract structured content including medications, prescription plans, and pharmacyal information.
    """
    content = {
        "title": "",
        "description": "",
        "medications": [],
        "prescription_plan": [],
        "pharmacyal_info": [],
        "ingredients": [],
        "instructions": [],
        "tips": [],
        "content_summary": ""
    }
    
    try:
        # Extract title
        title_tag = soup.find('title') or soup.find('h1')
        if title_tag:
            content["title"] = title_tag.get_text().strip()
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            desc_content = meta_desc.get('content')
            if desc_content:
                content["description"] = desc_content.strip()
        
        # Extract medications (look for medication-specific structures)
        medications = []
        medication_selectors = [
            '.medication', '.medication-card', '[itemtype*="Medication"]',
            '.medication-content', '.medication-details', '.prescription-medication'
        ]
        
        for selector in medication_selectors:
            medication_elements = soup.select(selector)
            for medication in medication_elements[:5]:  # Limit to first 5 medications
                medication_text = medication.get_text().strip()
                if len(medication_text) > 50:  # Only include substantial content
                    medications.append(medication_text[:500])  # Limit length
        
        content["medications"] = medications
        
        # Extract prescription plan information
        prescription_plan = []
        prescription_selectors = [
            '.prescription-plan', '.daily-plan', '.menu', '.prescription-schedule',
            '.breakfast', '.lunch', '.dinner', '.snack'
        ]
        
        for selector in prescription_selectors:
            prescription_elements = soup.select(selector)
            for prescription in prescription_elements[:10]:  # Limit to first 10 prescriptions
                prescription_text = prescription.get_text().strip()
                if len(prescription_text) > 30:
                    prescription_plan.append(prescription_text[:300])
        
        content["prescription_plan"] = prescription_plan
        
        # Extract ingredients lists
        ingredients = []
        ingredient_selectors = [
            '.ingredients', '.ingredient-list', 'ul li', '.medication-ingredients'
        ]
        
        for selector in ingredient_selectors:
            ingredient_elements = soup.select(selector)
            for ingredient in ingredient_elements[:20]:  # Limit to first 20 ingredients
                ingredient_text = ingredient.get_text().strip()
                if len(ingredient_text) > 5 and len(ingredient_text) < 100:
                    # Filter for likely ingredients (contains numbers or common medication words)
                    if re.search(r'\d+|cup|tbsp|tsp|oz|lb|gram|protein|chicken|beef|fish|egg', ingredient_text, re.IGNORECASE):
                        ingredients.append(ingredient_text)
        
        content["ingredients"] = list(set(ingredients))  # Remove duplicates
        
        # Extract cooking instructions
        instructions = []
        instruction_selectors = [
            '.instructions', '.directions', '.method', '.steps',
            '.medication-instructions', 'ol li'
        ]
        
        for selector in instruction_selectors:
            instruction_elements = soup.select(selector)
            for instruction in instruction_elements[:15]:  # Limit to first 15 steps
                instruction_text = instruction.get_text().strip()
                if len(instruction_text) > 20:
                    instructions.append(instruction_text[:200])
        
        content["instructions"] = instructions
        
        # Extract pharmacyal information
        pharmacyal_info = []
        pharmacy_selectors = [
            '.pharmacy', '.pharmacyal-info', '.macros', '.pharmacy-facts',
            '.calories', '.protein-content', '.carbs', '.fat'
        ]
        
        for selector in pharmacy_selectors:
            pharmacy_elements = soup.select(selector)
            for pharmacy in pharmacy_elements[:10]:
                pharmacy_text = pharmacy.get_text().strip()
                if len(pharmacy_text) > 10:
                    pharmacyal_info.append(pharmacy_text[:150])
        
        content["pharmacyal_info"] = pharmacyal_info
        
        # Extract tips and notes
        tips = []
        tip_selectors = [
            '.tips', '.notes', '.advice', '.recommendations',
            '.chef-tips', '.cooking-tips'
        ]
        
        for selector in tip_selectors:
            tip_elements = soup.select(selector)
            for tip in tip_elements[:5]:
                tip_text = tip.get_text().strip()
                if len(tip_text) > 20:
                    tips.append(tip_text[:200])
        
        content["tips"] = tips
        
        # Create a content summary
        all_content = []
        if content["title"]:
            all_content.append(f"Title: {content['title']}")
        if content["description"]:
            all_content.append(f"Description: {content['description']}")
        if content["medications"]:
            all_content.append(f"Medications: {len(content['medications'])} found")
        if content["prescription_plan"]:
            all_content.append(f"Prescription Plan: {len(content['prescription_plan'])} items")
        if content["ingredients"]:
            all_content.append(f"Ingredients: {len(content['ingredients'])} items")
        if content["instructions"]:
            all_content.append(f"Instructions: {len(content['instructions'])} steps")
        
        content["content_summary"] = " | ".join(all_content)
        
        # Clean up empty lists
        content = {k: v for k, v in content.items() if v}
        
    except Exception as e:
        logger.warning(f"Error extracting structured content: {e}")
        content["extraction_error"] = str(e)
    
    return content

def parse_pharmacy_query(query: str) -> Optional[Dict[str, Any]]:
    # Try to extract explicit pattern first
    match = re.search(r"(lunch|dinner|breakfast)?\s*.*?(\d+)\s*g\s*(protein|carbs|fat)", query, re.IGNORECASE)
    if match:
        return {
            "prescription": match.group(1) or "prescription",
            "nutrient": match.group(3).lower(),
            "amount": int(match.group(2))
        }
    # Try to infer nutrient and amount from context
    nutrient = None
    amount = None
    for n in ["protein", "carbs", "fat"]:
        if n in query.lower():
            nutrient = n
            break
    # Try to find any number followed by 'g' (e.g., '150g')
    amount_match = re.search(r"(\d+)\s*g", query, re.IGNORECASE)
    if amount_match:
        amount = int(amount_match.group(1))
    # Default to protein and 30g if not found
    if not nutrient:
        nutrient = "protein"
    if not amount:
        amount = 30
    return {
        "prescription": "prescription",
        "nutrient": nutrient,
        "amount": amount
    }

def decide_content_type(query: str) -> str:
    if "video" in query or "youtube" in query or "how to" in query:
        return "youtube"
    return "web"

async def search_and_filter_pharmacy(query: str) -> Dict[str, Any]:
    parsed = parse_pharmacy_query(query)
    if not parsed:
        return {"error": "Please specify your nutrient target like '30g protein for lunch'"}
    source = decide_content_type(query)
    search_site = "youtube.com" if source == "youtube" else None
    search_results = google_search(query, site=search_site)
    print(f"Raw search results from SerpAPI: {search_results}")
    all_results = []
    if source == "youtube":
        for url in search_results:
            print(f"Checking YouTube URL: {url}")
            try:
                res = check_youtube_video(url, parsed['nutrient'], parsed['amount'])
                if res is None:
                    res = {"url": url, "matched": False, "source": "youtube", "error": "Transcript fetch failed or unavailable"}
            except Exception as e:
                res = {"url": url, "matched": False, "source": "youtube", "error": str(e)}
            all_results.append(res)
    else:
        # Fix async event loop management
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                asyncio.gather(*[
                    extract_nutrients_from_page(url, parsed['nutrient'], parsed['amount']) for url in search_results
                ])
            )
            all_results = results
        except Exception as e:
            logger.error(f"Error in async web scraping: {e}")
            # Fallback: return basic results without content analysis
            all_results = [{"url": url, "matched": False, "source": "web", "error": str(e)} for url in search_results]
    return {
        "query": query,
        "nutrient_target": parsed,
        "results": all_results
    }

# Register as a LangChain Tool
from langchain.tools import Tool
pharmacy_medication_search_tool = Tool(
    name="PharmacyMedicationSearch",
    func=search_and_filter_pharmacy,
    description="Searches Google and YouTube for medication information or videos that match a specific medication query (e.g., 'side effects of lisinopril')."
)

# Export main class
__all__ = ['PharmacyToolkit'] 