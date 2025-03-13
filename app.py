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
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Meta API setup
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
FacebookAdsApi.init(access_token=META_ACCESS_TOKEN)

# Cache settings
CACHE_FILE = "campaign_cache.json"
CACHE_DURATION = 3600

def format_budget(budget):
    """Convert budget from integer (e.g., 10000) to RM with 2 decimals (e.g., RM 100.00)"""
    if budget == "N/A" or not budget:
        return "N/A"
    return f"RM {float(budget) / 100:.2f}"

def format_caption(caption):
    """Split caption into a list of sentences or lines"""
    if caption == "N/A" or not caption:
        return ["N/A"]
    return [line.strip() for line in caption.split(". ") if line.strip()]

def fetch_meta_campaigns_from_api(account_id):
    fields = ["name", "objective", "daily_budget"]
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
                ads = adset.get_ads(
                    fields=["name", "creative"],
                    params={"filtering": [{"field": "effective_status", "operator": "IN", "value": ["ACTIVE"]}]}
                )
                ad_info = []
                for ad in ads:
                    creative_id = ad.get("creative", {}).get("id")
                    captions = []
                    headlines = []
                    if creative_id:
                        creative = AdCreative(creative_id).api_get(fields=["body", "title"])
                        captions = format_caption(creative.get("body", "N/A"))
                        headlines = [creative.get("title", "N/A")]
                    ad_info.append({
                        "name": ad.get("name", "N/A"),
                        "captions": captions,
                        "headlines": headlines
                    })
                
                locations = []
                geo = targeting.get("geo_locations", {})
                for loc_type in ["countries", "regions", "cities"]:
                    if loc_type in geo:
                        locations.extend(geo[loc_type] if loc_type == "countries" else [loc["name"] for loc in geo[loc_type]])
                if not locations:
                    locations = ["N/A"]

                audience_info.append({
                    "name": adset.get("name", "N/A"),
                    "age_min": targeting.get("age_min", "N/A"),
                    "age_max": targeting.get("age_max", "N/A"),
                    "locations": locations,
                    "ads": ad_info
                })

            campaigns.append({
                "name": campaign.get("name", "N/A"),
                "objective": " ".join(word.capitalize() for word in campaign.get("objective", "N/A").split("_")),
                "daily_budget": format_budget(campaign.get("daily_budget", "N/A")),
                "audience": audience_info
            })

        with open(CACHE_FILE, "w") as f:
            json.dump({"timestamp": time.time(), "campaigns": campaigns}, f)

    except FacebookRequestError as e:
        error_message = f"Error fetching Meta campaigns: {e}"
        logging.error(error_message)

    return campaigns, error_message

def get_meta_campaigns(account_id, force_refresh=False):
    if force_refresh or not os.path.exists(CACHE_FILE):
        logging.info("Fetching fresh data from API")
        return fetch_meta_campaigns_from_api(account_id)
    with open(CACHE_FILE, "r") as f:
        cache_data = json.load(f)
    logging.info(f"Loaded from cache: {cache_data['campaigns']}")
    return cache_data["campaigns"], None

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/campaigns')
def campaigns():
    meta_account_id = "act_1837837733021085"
    meta_campaigns, error_message = get_meta_campaigns(meta_account_id, force_refresh=False)
    logging.info(f"Rendering campaigns: {meta_campaigns}")
    return render_template('campaigns.html', meta_campaigns=meta_campaigns, error_message=error_message)

@app.route('/refresh_campaigns')
def refresh_campaigns():
    meta_account_id = "act_1837837733021085"
    fetch_meta_campaigns_from_api(meta_account_id)
    return redirect(url_for('campaigns'))

if __name__ == '__main__':
    app.run(debug=True)