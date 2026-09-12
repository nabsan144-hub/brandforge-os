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
        "description": "Compliance-aware Amazon listing with 5 benefit-rich bullet points and search optimization.",
        "campaign_name": "Amazon FBA Launch Campaign",
        "product_name": "Your Amazon Product",
        "industry": "E-commerce & Amazon FBA",
        "target_audience": "Amazon shoppers seeking verified quality, reliable delivery, and clear product features",
        "key_benefits": "Premium materials, verified durability, easy setup, backed by 30-day money-back guarantee, fast shipping",
    },
    {
        "id": "shopify-dtc-scale",
        "name": "Shopify DTC E-Commerce Scale",
        "description": "High-converting direct-to-consumer campaign with ad angles, landing page copy, and email sequence.",
        "campaign_name": "DTC Scale Campaign",
        "product_name": "Your Shopify Brand Offer",
        "industry": "E-commerce & DTC",
        "target_audience": "Engaged online shoppers and social media buyers looking for distinctive brand solutions",
        "key_benefits": "Distinctive design, customer-proven results, transparent ingredients/materials, bundle discounts, hassle-free returns",
    },
    {
        "id": "saas-product-hunt",
        "name": "SaaS Product Hunt & Tech Launch",
        "description": "B2B SaaS launch kit: executive positioning, LinkedIn thought leadership, ad hooks, and email onboarding.",
        "campaign_name": "SaaS Launch Campaign",
        "product_name": "Your Software Product",
        "industry": "B2B SaaS & Tech",
        "target_audience": "Founders, CTOs, marketing directors, and product teams looking to automate manual workflows",
        "key_benefits": "Save 10+ hours weekly, zero complex setup, instant team collaboration, bank-grade encryption, native integrations",
    },
    {
        "id": "agency-lead-generation",
        "name": "Agency lead generation",
        "description": "A practical B2B campaign outline for an agency offer.",
        "campaign_name": "Agency Growth Campaign",
        "product_name": "Your agency offer",
        "industry": "Marketing agency",
        "target_audience": "Founders and marketing leaders at growing businesses",
        "key_benefits": "Clear strategy, faster campaign production, transparent reporting, specialist support",
    },
    {
        "id": "local-service-offer",
        "name": "Local service offer",
        "description": "For appointment-based or local service businesses.",
        "campaign_name": "Local Service Growth Campaign",
        "product_name": "Your service",
        "industry": "Local services",
        "target_audience": "People in your service area who need this service",
        "key_benefits": "Convenient booking, clear service details, trusted local team, responsive support",
    },
    {
        "id": "real-estate-listing",
        "name": "Real estate listing",
        "description": "A listing campaign focused on verifiable property details.",
        "campaign_name": "Property Listing Campaign",
        "product_name": "Property or listing name",
        "industry": "Real estate",
        "target_audience": "Qualified buyers looking in your target area",
        "key_benefits": "Verified property details, location advantages, viewing availability, clear next step",
    },
    {
        "id": "restaurant-seasonal",
        "name": "Restaurant seasonal promotion",
        "description": "A local offer campaign for a seasonal menu or event.",
        "campaign_name": "Seasonal Promotion Campaign",
        "product_name": "Restaurant or seasonal menu",
        "industry": "Restaurant and hospitality",
        "target_audience": "Local diners and returning customers",
        "key_benefits": "Seasonal menu, welcoming experience, convenient reservation or ordering, local appeal",
    },
]


def list_campaign_templates() -> List[Dict[str, str]]:
    """Return copies so request code cannot mutate the in-process catalogue."""
    return [dict(template) for template in _TEMPLATES]
