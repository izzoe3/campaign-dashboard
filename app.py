from flask import Flask, render_template, redirect, url_for
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.exceptions import FacebookRequestError
from dotenv import load_dotenv
import os
import json
import time

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Meta API setup
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
FacebookAdsApi.init(access_token=META_ACCESS_TOKEN)

# Cache settings
CACHE_FILE = "campaign_cache.json"
CACHE_DURATION = 3600  # Cache duration in seconds (1 hour)

def format_budget(budget):
    """Convert budget from integer (e.g., 10000) to formatted string (e.g., $100.00)"""
    if budget == "N/A" or not budget:
        return "N/A"
    return f"${float(budget) / 100:.2f}"  # Meta budgets are in cents

def format_caption(caption):
    """Split caption into a list of sentences or lines"""
    if caption == "N/A" or not caption:
        return ["N/A"]
    return [line.strip() for line in caption.split(". ") if line.strip()]  # Split by sentence

# Function to fetch Meta campaigns from API
def fetch_meta_campaigns_from_api(account_id):
    fields = [
        "name", "objective", "status", "daily_budget", "lifetime_budget",
        "spend_cap", "start_time", "stop_time"
    ]
    campaigns = []
    error_message = None
    try:
        account = AdAccount(account_id)
        campaign_data = account.get_campaigns(
            fields=fields,
            params={"filtering": [{"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}]}
        )
        for campaign in campaign_data:
            adsets = campaign.get_ad_sets(
                fields=["name", "targeting"],
                params={"filtering": [{"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}]}
            )
            audience_info = []
            for adset in adsets:
                targeting = adset.get("targeting", {})
                audience_info.append({
                    "name": adset.get("name", "N/A"),
                    "age_min": targeting.get("age_min", "N/A"),
                    "age_max": targeting.get("age_max", "N/A"),
                    "geo_locations": ", ".join(targeting.get("geo_locations", {}).get("countries", ["N/A"])),
                    "interests": ", ".join(interest["name"] for interest in targeting.get("interests", [])) or "N/A"
                })

            ads = campaign.get_ads(fields=["name", "creative"])
            captions = []
            headlines = []
            for ad in ads:
                creative_id = ad.get("creative", {}).get("id")
                if creative_id:
                    creative = AdCreative(creative_id).api_get(fields=["body", "title"])
                    captions.extend(format_caption(creative.get("body", "N/A")))  # Split captions into sentences
                    headlines.append(creative.get("title", "N/A"))

            campaigns.append({
                "name": campaign.get("name", "N/A"),
                "objective": " ".join(word.capitalize() for word in campaign.get("objective", "N/A").split("_")),
                "status": campaign.get("status", "N/A"),
                "daily_budget": format_budget(campaign.get("daily_budget", "N/A")),
                "lifetime_budget": format_budget(campaign.get("lifetime_budget", "N/A")),
                "spend_cap": format_budget(campaign.get("spend_cap", "N/A")),
                "start_time": campaign.get("start_time", "N/A"),
                "stop_time": campaign.get("stop_time", "N/A"),
                "audience": audience_info,
                "captions": captions,
                "headlines": headlines
            })

        # Save to cache
        with open(CACHE_FILE, "w") as f:
            json.dump({"timestamp": time.time(), "campaigns": campaigns}, f)

    except FacebookRequestError as e:
        error_message = f"Error fetching Meta campaigns: {e}"
        print(error_message)

    return campaigns, error_message

# Function to get campaigns (from cache or API)
def get_meta_campaigns(account_id, force_refresh=False):
    if force_refresh or not os.path.exists(CACHE_FILE):
        return fetch_meta_campaigns_from_api(account_id)

    # Load from cache
    with open(CACHE_FILE, "r") as f:
        cache_data = json.load(f)
    return cache_data["campaigns"], None

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/campaigns')
def campaigns():
    meta_account_id = "act_1837837733021085"  # Replace with your correct ad account ID
    meta_campaigns, error_message = get_meta_campaigns(meta_account_id, force_refresh=False)
    return render_template('campaigns.html', meta_campaigns=meta_campaigns, error_message=error_message)

@app.route('/refresh_campaigns')
def refresh_campaigns():
    meta_account_id = "act_1837837733021085"  # Replace with your correct ad account ID
    fetch_meta_campaigns_from_api(meta_account_id)  # Force refresh
    return redirect(url_for('campaigns'))

if __name__ == '__main__':
    app.run(debug=True)