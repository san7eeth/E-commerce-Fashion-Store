
import numpy as np
import tensorflow as tf
from PIL import Image
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input
from tensorflow.keras.layers import GlobalMaxPooling2D
from numpy.linalg import norm
import spacy
from ecommerceapp.models import Product, Category, ProductSize
from django.db.models import Q
import re
from collections import Counter
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Load the ResNet50 model for image search
model = ResNet50(weights="imagenet", include_top=False, input_shape=(224, 224, 3))
model = tf.keras.Sequential([model, GlobalMaxPooling2D()])
model.trainable = False  # Prevent updates to weights

# Load spaCy NLP model with entity recognition
nlp = spacy.load("en_core_web_sm")

# Common product attribute synonyms
ATTRIBUTE_SYNONYMS = {
    "color": ["color", "colour", "shade", "tone", "hue"],
    "material": ["material", "fabric", "made of", "made from", "built with", "constructed with"],
    "price": ["price", "cost", "rate", "value", "worth", "budget"],
    "category": ["category", "type", "kind", "sort", "group", "class"],
    "sizes": ["size", "dimension", "measurement", "length", "width", "height"]
}

# Common product qualifiers
QUALIFIERS = {
    "budget": ["cheap", "inexpensive", "affordable", "budget-friendly", "economical", "low-cost", "bargain"],
    "premium": ["premium", "luxury", "high-end", "expensive", "top-quality", "high-quality"],
    "size": ["small", "medium", "large", "extra large", "tiny", "huge", "compact", "oversized"],
    "new": ["new", "latest", "recent", "newest", "fresh", "just launched", "just released"],
    "popular": ["popular", "trending", "bestselling", "best-selling", "top-rated", "highly rated"]
}

# Cache for database values
DB_CACHE = {
    "colors": set(),
    "categories": {},
    "names": set(),
    "materials": set(),
    "commodities": set(),
    "descriptions": set(),
    "brands": set(),
    "sizes": set(),
    "size_types": set(),
    "loaded": False
}

def ensure_string(value):
    """Convert value to string if it's not None, otherwise return empty string."""
    if value is None:
        return ""
    return str(value)

def extract_features(img_file):
    """Extract AI features from an image file."""
    try:
        img = Image.open(img_file)  # Open image using PIL
        img = img.convert("RGB")  # Ensure it's in RGB mode
        img = img.resize((224, 224))  # Resize image
        img_array = np.array(img)  # Convert to NumPy array
        expanded_img_array = np.expand_dims(img_array, axis=0)
        preprocessed_img = preprocess_input(expanded_img_array)
        result = model.predict(preprocessed_img).flatten()
        normalized_result = result / norm(result)
        return normalized_result
    except Exception as e:
        logger.error(f"Feature extraction error: {e}")
        return None

def load_db_cache():
    """Load database values into cache for faster lookup."""
    if not DB_CACHE["loaded"]:
        DB_CACHE["colors"] = {ensure_string(color).lower() for color in Product.objects.exclude(color__isnull=True).values_list("color", flat=True)}
        DB_CACHE["categories"] = {ensure_string(cat).lower(): cat for cat in Category.objects.values_list("name", flat=True)}
        DB_CACHE["names"] = {ensure_string(name).lower() for name in Product.objects.exclude(name__isnull=True).values_list("name", flat=True)}
        DB_CACHE["materials"] = {ensure_string(mat).lower() for mat in Product.objects.exclude(material__isnull=True).values_list("material", flat=True)}
        DB_CACHE["commodities"] = {ensure_string(com).lower() for com in Product.objects.exclude(commodity__isnull=True).values_list("commodity", flat=True)}
        DB_CACHE["descriptions"] = {ensure_string(desc).lower() for desc in Product.objects.exclude(description__isnull=True).values_list("description", flat=True)}
        DB_CACHE["brands"] = {ensure_string(brand).lower() for brand in Product.objects.exclude(brand__isnull=True).values_list("brand__brand_name", flat=True)}
        DB_CACHE["sizes"] = {ensure_string(size).lower() for size in ProductSize.objects.exclude(size_type__isnull=True).values_list("size_type", flat=True)}
        DB_CACHE["size_types"] = {ensure_string(size_type).lower() for size_type in Product.objects.exclude(size_type__isnull=True).values_list("size_type", flat=True)}
        DB_CACHE["loaded"] = True
        logger.info("Database cache loaded successfully")

def get_ngrams_custom(text, n_range=(1, 3)):
    """Generate n-grams from text without using NLTK."""
    tokens = text.lower().split()
    all_ngrams = []
    for n in range(n_range[0], n_range[1] + 1):
        for i in range(len(tokens) - n + 1):
            all_ngrams.append(" ".join(tokens[i:i+n]))
    return all_ngrams

def extract_product_attributes(query):
    """Extract attributes from user input using enhanced NLP techniques."""
    load_db_cache()
    doc = nlp(query.lower())
    
    extracted_attributes = {
        "color": None,
        "category": None,
        "price_range": None,
        "name": None,
        "material": None,
        "commodity": None,
        "description": None,
        "brand": None,
        "sizes": None,
        "size_type": None,
        "qualifiers": [],
        "raw_query": query.lower()
    }
    
    query_ngrams = get_ngrams_custom(query)
    
    color_matches = [ng for ng in query_ngrams if any(color in ng for color in DB_CACHE["colors"])]
    if color_matches:
        extracted_attributes["color"] = max(color_matches, key=len)
    
    category_matches = [ng for ng in query_ngrams if ng in DB_CACHE["categories"]]
    if category_matches:
        extracted_attributes["category"] = DB_CACHE["categories"][max(category_matches, key=len)]
    
    material_matches = [ng for ng in query_ngrams if any(mat in ng for mat in DB_CACHE["materials"])]
    if material_matches:
        extracted_attributes["material"] = max(material_matches, key=len)
    
    brand_matches = [ng for ng in query_ngrams if any(brand in ng for brand in DB_CACHE["brands"])]
    if brand_matches:
        extracted_attributes["brand"] = max(brand_matches, key=len)
    
    size_matches = [ng for ng in query_ngrams if any(size in ng for size in DB_CACHE["sizes"])]
    if size_matches:
        extracted_attributes["sizes"] = max(size_matches, key=len)
    
    size_type_matches = [ng for ng in query_ngrams if ng in DB_CACHE["size_types"]]
    if size_type_matches:
        extracted_attributes["size_type"] = max(size_type_matches, key=len)
    
    for qualifier_type, qualifier_terms in QUALIFIERS.items():
        for term in qualifier_terms:
            if term in query.lower():
                extracted_attributes["qualifiers"].append(qualifier_type)
    
    price_patterns = [
        r"(?:under|below|less than|cheaper than|not more than|maximum|max|up to)\s*(?:\$|₹|€|£|¥)?\s*(\d+(?:\.\d+)?)",
        r"(?:above|over|more than|greater than|at least|minimum|min|starting from|from)\s*(?:\$|₹|€|£|¥)?\s*(\d+(?:\.\d+)?)",
        r"(?:between|from)\s*(?:\$|₹|€|£|¥)?\s*(\d+(?:\.\d+)?)\s*(?:and|to|-)\s*(?:\$|₹|€|£|¥)?\s*(\d+(?:\.\d+)?)",
        r"(?:\$|₹|€|£|¥)\s*(\d+(?:\.\d+)?)"
    ]
    
    extracted_attributes["price_range"] = {"min": None, "max": None}
    
    if "budget" in extracted_attributes["qualifiers"]:
        extracted_attributes["price_range"]["max"] = 50
    if "premium" in extracted_attributes["qualifiers"]:
        extracted_attributes["price_range"]["min"] = 100
    
    for pattern in price_patterns:
        matches = re.search(pattern, query.lower())
        if matches:
            if pattern.startswith(r"(?:under|below"):
                extracted_attributes["price_range"]["max"] = float(matches.group(1))
            elif pattern.startswith(r"(?:above|over"):
                extracted_attributes["price_range"]["min"] = float(matches.group(1))
            elif pattern.startswith(r"(?:between|from") and len(matches.groups()) >= 2:
                extracted_attributes["price_range"]["min"] = float(matches.group(1))
                extracted_attributes["price_range"]["max"] = float(matches.group(2))
            elif pattern.startswith(r"(?:\$|₹|€|£|¥)"):
                exact_price = float(matches.group(1))
                extracted_attributes["price_range"]["min"] = exact_price * 0.9
                extracted_attributes["price_range"]["max"] = exact_price * 1.1
    
    for entity in doc.ents:
        if entity.label_ == "PRODUCT" or entity.label_ == "ORG":
            extracted_attributes["name"] = entity.text
        if entity.label_ == "GPE" or entity.label_ == "LOC":
            if not extracted_attributes["description"]:
                extracted_attributes["description"] = entity.text
            else:
                extracted_attributes["description"] += " " + entity.text
    
    logger.debug(f"Extracted attributes: {extracted_attributes}")
    return extracted_attributes

def calculate_query_relevance(product, query_attributes):
    """Calculate relevance score for a product based on query attributes."""
    relevance_score = 0
    matched_fields = 0
    
    product_color = ensure_string(product.color).lower() if hasattr(product, 'color') else ""
    product_category_name = ensure_string(product.category.name).lower() if hasattr(product, 'category') and product.category else ""
    product_material = ensure_string(product.material).lower() if hasattr(product, 'material') else ""
    product_brand = ensure_string(product.brand.brand_name).lower() if hasattr(product, 'brand') else ""
    product_name = ensure_string(product.name).lower() if hasattr(product, 'name') else ""
    product_description = ensure_string(product.description).lower() if hasattr(product, 'description') else ""
    product_sizes = {ensure_string(size.size_type).lower() for size in product.sizes.all()} if hasattr(product, 'sizes') else set()
    product_size_type = ensure_string(product.size_type).lower() if hasattr(product, 'size_type') else ""
    
    if query_attributes["color"] and query_attributes["color"] in product_color:
        relevance_score += 10
        matched_fields += 1
    
    if query_attributes["category"] and query_attributes["category"].lower() == product_category_name:
        relevance_score += 15
        matched_fields += 1
    
    if query_attributes["material"] and query_attributes["material"] in product_material:
        relevance_score += 8
        matched_fields += 1
    
    if query_attributes["brand"] and query_attributes["brand"] in product_brand:
        relevance_score += 12
        matched_fields += 1
    
    if query_attributes["sizes"] and query_attributes["sizes"] in product_sizes:
        relevance_score += 8
        matched_fields += 1
    
    if query_attributes["size_type"] and query_attributes["size_type"] == product_size_type:
        relevance_score += 5
        matched_fields += 1
    
    if hasattr(product, 'price') and product.price is not None:
        min_price = query_attributes["price_range"].get("min")
        max_price = query_attributes["price_range"].get("max")
        if (min_price is None or product.price >= min_price) and (max_price is None or product.price <= max_price):
            relevance_score += 8
            matched_fields += 1
    
    if "budget" in query_attributes["qualifiers"] and hasattr(product, 'price') and product.price and product.price < 50:
        relevance_score += 5
    
    if "premium" in query_attributes["qualifiers"] and hasattr(product, 'price') and product.price and product.price > 100:
        relevance_score += 5
    
    query_tokens = query_attributes["raw_query"].split()
    if product_name:
        name_similarity = len(set(query_tokens) & set(product_name.split()))
        relevance_score += name_similarity
        if name_similarity > 0:
            matched_fields += 1
    
    if product_description:
        description_similarity = len(set(query_tokens) & set(product_description.split()))
        relevance_score += description_similarity * 0.5
        if description_similarity > 0:
            matched_fields += 1
    
    return {
        "product": product,
        "score": relevance_score,
        "matched_fields": matched_fields
    }

def search_products_by_nlp(query):
    """Perform enhanced NLP-based product search considering multiple attributes.
    
    Args:
        query (str): The search query string.
    
    Returns:
        list: A sorted list of Product objects, ordered by relevance score.
              Returns an empty list if no products match.
    """
    extracted_attrs = extract_product_attributes(query)
    logger.debug(f"Applying filters for query: {query}")
    
    # Start with all visible products
    products = Product.objects.filter(is_visible=True)
    filters = Q()
    
    if extracted_attrs["color"]:
        filters |= Q(color__icontains=extracted_attrs["color"])
    
    if extracted_attrs["category"]:
        filters |= Q(category__name__iexact=extracted_attrs["category"])
    
    if extracted_attrs["material"]:
        filters |= Q(material__icontains=extracted_attrs["material"])
    
    if extracted_attrs["brand"]:
        filters |= Q(brand__brand_name__icontains=extracted_attrs["brand"])
    
    if extracted_attrs["sizes"]:
        filters &= Q(sizes__size_type__iexact=extracted_attrs["sizes"])
    
    if extracted_attrs["size_type"]:
        filters |= Q(size_type__iexact=extracted_attrs["size_type"])
    
    if extracted_attrs["price_range"]["min"] is not None:
        filters |= Q(price__gte=extracted_attrs["price_range"]["min"])
    
    if extracted_attrs["price_range"]["max"] is not None:
        filters |= Q(price__lte=extracted_attrs["price_range"]["max"])
    
    if extracted_attrs["raw_query"]:
        search_terms = extracted_attrs["raw_query"].split()
        for term in search_terms:
            if len(term) > 2:
                term_filter = (
                    Q(name__icontains=term) |
                    Q(description__icontains=term) |
                    Q(commodity__icontains=term)
                )
                filters |= term_filter
    
    if filters:
        products = products.filter(filters).distinct()
        logger.debug(f"Filtered products count: {products.count()}")
    
    # Fallback keyword search if no products match
    if not products.exists():
        logger.debug("No products found with initial filters, falling back to keyword search")
        all_words = extracted_attrs["raw_query"].lower().split()
        significant_words = [word for word in all_words if len(word) > 3]
        for word in significant_words:
            keyword_filter = (
                Q(name__icontains=word) |
                Q(description__icontains=word) |
                Q(material__icontains=word) |
                Q(color__icontains=word) |
                Q(brand__brand_name__icontains=word) |
                Q(commodity__icontains=word)
            )
            products = Product.objects.filter(is_visible=True).filter(keyword_filter).distinct()
            if products.exists():
                logger.debug(f"Fallback found {products.count()} products for keyword: {word}")
                break
    
    # Calculate relevance scores and sort
    product_scores = []
    for product in products:
        relevance_score = calculate_query_relevance(product, extracted_attrs)
        product_scores.append((product, relevance_score["score"]))
    
    product_scores.sort(key=lambda x: x[1], reverse=True)
    result = [product for product, score in product_scores]
    logger.debug(f"Returning {len(result)} products for query: {query}")
    return result

def recommend_related_products(product_id, limit=10):
    """Recommend related products based on similarities."""
    try:
        source_product = Product.objects.get(id=product_id)
        related_products = Product.objects.filter(
            category=source_product.category,
            is_visible=True
        ).exclude(id=product_id)
        
        price_min = source_product.price * 0.8 if source_product.price else None
        price_max = source_product.price * 1.2 if source_product.price else None
        
        attribute_similar = Q()
        if source_product.color:
            attribute_similar |= Q(color__iexact=source_product.color)
        if source_product.material:
            attribute_similar |= Q(material__iexact=source_product.material)
        if source_product.brand:
            attribute_similar |= Q(brand=source_product.brand)
        source_sizes = {size.size_type.lower() for size in source_product.sizes.all()}
        if source_sizes:
            attribute_similar |= Q(sizes__size_type__in=source_sizes)
        
        query = Q(category=source_product.category) | attribute_similar
        if price_min is not None and price_max is not None:
            query |= (Q(price__gte=price_min) & Q(price__lte=price_max))
        
        related_products = Product.objects.filter(query, is_visible=True).exclude(id=product_id).distinct()
        
        product_scores = []
        for product in related_products:
            score = 0
            if product.category == source_product.category:
                score += 10
            
            if source_product.price and product.price:
                price_diff = abs(source_product.price - product.price)
                if source_product.price > 0:
                    price_sim = max(0, 1 - (price_diff / source_product.price))
                    score += price_sim * 5
            
            source_color = ensure_string(source_product.color).lower()
            product_color = ensure_string(product.color).lower()
            if source_color and product_color and source_color == product_color:
                score += 3
            
            source_material = ensure_string(source_product.material).lower()
            product_material = ensure_string(product.material).lower()
            if source_material and product_material and source_material == product_material:
                score += 3
            
            source_brand = ensure_string(source_product.brand.brand_name).lower()
            product_brand = ensure_string(product.brand.brand_name).lower()
            if source_brand and product_brand and source_brand == product_brand:
                score += 4
            
            product_sizes = {size.size_type.lower() for size in product.sizes.all()}
            if source_sizes and product_sizes and source_sizes & product_sizes:
                score += 3
            
            product_scores.append((product, score))
        
        product_scores.sort(key=lambda x: x[1], reverse=True)
        return [product for product, _ in product_scores[:limit]]
    
    except Product.DoesNotExist:
        logger.warning(f"Product with id {product_id} not found")
        return []

def search_products_by_image(image_file, limit=10):
    """Search products by image similarity using feature vectors."""
    try:
        query_features = extract_features(image_file)
        if query_features is None:
            logger.warning("Failed to extract features from image")
            return []
        
        product_scores = []
        for product in Product.objects.filter(feature_vector__isnull=False, is_visible=True):
            product_features = product.get_feature_vector()
            if product_features is not None:
                similarity = cosine_similarity([query_features], [product_features])[0][0]
                product_scores.append((product, similarity))
        
        product_scores.sort(key=lambda x: x[1], reverse=True)
        return [product for product, _ in product_scores[:limit]]
    except Exception as e:
        logger.error(f"Image search error: {e}")
        return []
