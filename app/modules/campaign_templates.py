"""Curated, transparent starting briefs for BrandForge campaign creation.

Templates accelerate a first campaign; they do not claim niche-specific facts or
replace the customer's own approved offer, proof, and compliance review.
"""

from typing import Dict, List


_TEMPLATES: List[Dict[str, str]] = [
    {
        "id": "blank",
        "name": "Start from scratch",
        "description": "Use your own brief and brand details.",
        "campaign_name": "",
        "product_name": "",
        "industry": "",
        "target_audience": "",
        "key_benefits": "",
    },
    {
        "id": "amazon-fba-listing",
        "name": "Amazon FBA Product Listing & Launch",
        "description": "Starter brief for an Amazon product launch. Supply verified features and purchase terms.",
        "campaign_name": "Amazon FBA Launch Campaign",
        "product_name": "Your Amazon Product",
        "industry": "E-commerce & Amazon FBA",
        "target_audience": "Amazon shoppers seeking verified quality, reliable delivery, and clear product features",
        "key_benefits": "",
    },
    {
        "id": "shopify-dtc-scale",
        "name": "Shopify DTC E-Commerce Scale",
        "description": "Starter brief for direct-to-consumer copy. Supply your approved benefits and offer.",
        "campaign_name": "DTC Scale Campaign",
        "product_name": "Your Shopify Brand Offer",
        "industry": "E-commerce & DTC",
        "target_audience": "Engaged online shoppers and social media buyers looking for distinctive brand solutions",
        "key_benefits": "",
    },
    {
        "id": "saas-product-hunt",
        "name": "SaaS Product Hunt & Tech Launch",
        "description": "B2B software starter brief. Specify the audience and verified capabilities.",
        "campaign_name": "SaaS Launch Campaign",
        "product_name": "Your Software Product",
        "industry": "B2B SaaS & Tech",
        "target_audience": "Founders, CTOs, marketing directors, and product teams looking to automate manual workflows",
        "key_benefits": "",
    },
    {
        "id": "agency-lead-generation",
        "name": "Agency lead generation",
        "description": "A practical B2B campaign outline for an agency offer.",
        "campaign_name": "Agency Growth Campaign",
        "product_name": "Your agency offer",
        "industry": "Marketing agency",
        "target_audience": "Founders and marketing leaders at growing businesses",
        "key_benefits": "",
    },
    {
        "id": "local-service-offer",
        "name": "Local service offer",
        "description": "For appointment-based or local service businesses.",
        "campaign_name": "Local Service Growth Campaign",
        "product_name": "Your service",
        "industry": "Local services",
        "target_audience": "People in your service area who need this service",
        "key_benefits": "",
    },
    {
        "id": "real-estate-listing",
        "name": "Real estate listing",
        "description": "A listing campaign focused on verifiable property details.",
        "campaign_name": "Property Listing Campaign",
        "product_name": "Property or listing name",
        "industry": "Real estate",
        "target_audience": "Qualified buyers looking in your target area",
        "key_benefits": "",
    },
    {
        "id": "restaurant-seasonal",
        "name": "Restaurant seasonal promotion",
        "description": "A local offer campaign for a seasonal menu or event.",
        "campaign_name": "Seasonal Promotion Campaign",
        "product_name": "Restaurant or seasonal menu",
        "industry": "Restaurant and hospitality",
        "target_audience": "Local diners and returning customers",
        "key_benefits": "",
    },
]


def list_campaign_templates() -> List[Dict[str, str]]:
    """Return copies so request code cannot mutate the in-process catalogue."""
    return [dict(template) for template in _TEMPLATES]
