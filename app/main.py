# app/main.py

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.services.parser import extract_text_from_bytes
from app.services.llm import UIAnalyzer
from app.services.figma_client import FigmaClient
from app.schemas import UIReport, UIReportResponse
import os
import json
import webbrowser
import threading

load_dotenv()

# Initialize LLM analyzer (supports both Groq and Gemini)
analyzer = UIAnalyzer()

# Initialize Figma client
figma_client = FigmaClient()

# --------------------------------------------
# LLM ANALYSIS → project name
# --------------------------------------------
def extract_project_name(text: str) -> str:
    try:
        import re
        import hashlib
        from datetime import datetime
        
        text_lower = text.lower()
        lines = [line.strip() for line in text.split('\n')[:50] if line.strip()]
        
        # Enhanced explicit project name patterns
        explicit_patterns = [
            r'(?:Product|Project|Application|App|System|Platform|Tool)\s*Name\s*:?\s*["\']?([A-Za-z][A-Za-z0-9\s&-]{2,35})["\']?',
            r'(?:Product|Project|Application|App|System|Platform|Tool)\s*:?\s*["\']?([A-Za-z][A-Za-z0-9\s&-]{2,35})["\']?',
            r'PRD\s*(?:for|of)?\s*:?\s*["\']?([A-Za-z][A-Za-z0-9\s&-]{2,35})["\']?',
            r'Title\s*:?\s*["\']?([A-Za-z][A-Za-z0-9\s&-]{2,35})["\']?',
            r'Name\s*:?\s*["\']?([A-Za-z][A-Za-z0-9\s&-]{2,35})["\']?',
            r'([A-Za-z][A-Za-z0-9\s&-]*(?:Calculator|App|Application|System|Platform|Tool|Manager|Portal|Dashboard))',
            r'"([A-Za-z][A-Za-z0-9\s&-]{3,35})"',
            r"'([A-Za-z][A-Za-z0-9\s&-]{3,35})'"
        ]
        
        # Search for explicit names in first 1000 characters
        for pattern in explicit_patterns:
            matches = re.findall(pattern, text[:1000], re.IGNORECASE)
            for match in matches:
                name = match.strip().title()
                name = re.sub(r'\s+', ' ', name).strip()
                # Filter out generic words and sentence fragments
                if (3 <= len(name) <= 35 and 
                    not any(skip in name.lower() for skip in ['document', 'page', 'section', 'prd', 'requirements', 'specification', 'the', 'and', 'for', 'is', 'to', 'provide', 'reliable', 'will', 'can', 'should', 'must'])):
                    return name
        
        # Look for titles in first lines (enhanced)
        for i, line in enumerate(lines[:15]):
            if 3 <= len(line) <= 50:
                # Skip metadata and common document words
                skip_words = ['http', 'www', '@', 'page', 'document', 'pdf', 'version', 'date', 'created', 'modified', 'author', 'subject']
                if any(skip in line.lower() for skip in skip_words):
                    continue
                
                # Check if line looks like a title (enhanced detection)
                if (line.istitle() or line.isupper() or 
                    re.match(r'^[A-Z][a-zA-Z0-9\s&-]+$', line) or
                    (i < 5 and len(line.split()) <= 6)):
                    
                    clean_title = re.sub(r'[^A-Za-z0-9\s&-]', ' ', line).strip()
                    clean_title = re.sub(r'\s+', ' ', clean_title)
                    
                    if (3 <= len(clean_title) <= 35 and 
                        not any(skip in clean_title.lower() for skip in ['document', 'page', 'section', 'requirements', 'is', 'to', 'provide', 'reliable', 'will', 'can', 'should', 'must'])):
                        return clean_title.title()
        
        # Extract domain-specific names with context
        domain_patterns = {
            'calculator': [
                r'([A-Za-z]+\s*Calculator)',
                r'([A-Za-z]+\s*Math\s*[A-Za-z]*)',
                r'(Scientific\s*[A-Za-z]*)',
                r'(Advanced\s*[A-Za-z]*)',
                r'([A-Za-z]*\s*Computation\s*[A-Za-z]*)'
            ],
            'chat': [
                r'([A-Za-z]+\s*(?:Chat|Messenger|Message))',
                r'([A-Za-z]+\s*Communication)',
                r'(Instant\s*[A-Za-z]*)',
                r'([A-Za-z]*\s*Talk\s*[A-Za-z]*)'
            ],
            'ecommerce': [
                r'([A-Za-z]+\s*(?:Shop|Store|Market))',
                r'([A-Za-z]+\s*Commerce)',
                r'([A-Za-z]+\s*Retail)',
                r'(Online\s*[A-Za-z]*)',
                r'([A-Za-z]*\s*Buy\s*[A-Za-z]*)'
            ],
            'banking': [
                r'([A-Za-z]+\s*(?:Bank|Finance|Pay))',
                r'([A-Za-z]+\s*Wallet)',
                r'([A-Za-z]+\s*Transaction)',
                r'(Digital\s*[A-Za-z]*)',
                r'([A-Za-z]*\s*Money\s*[A-Za-z]*)'
            ],
            'health': [
                r'([A-Za-z]+\s*(?:Health|Medical|Care))',
                r'([A-Za-z]+\s*Doctor)',
                r'([A-Za-z]+\s*Patient)',
                r'(Medical\s*[A-Za-z]*)',
                r'([A-Za-z]*\s*Clinic\s*[A-Za-z]*)'
            ],
            'food': [
                r'([A-Za-z]+\s*(?:Food|Restaurant|Recipe))',
                r'([A-Za-z]+\s*Kitchen)',
                r'([A-Za-z]+\s*Delivery)',
                r'(Fresh\s*[A-Za-z]*)',
                r'([A-Za-z]*\s*Meal\s*[A-Za-z]*)'
            ]
        }
        
        # Detect domain and extract specific names
        for domain, patterns in domain_patterns.items():
            if any(keyword in text_lower for keyword in [domain, domain.replace('ecommerce', 'shop')]):
                for pattern in patterns:
                    matches = re.findall(pattern, text[:800], re.IGNORECASE)
                    if matches:
                        name = matches[0].strip().title()
                        name = re.sub(r'\s+', ' ', name)
                        if 3 <= len(name) <= 30:
                            return name
        
        # Extract meaningful compound words and phrases
        compound_patterns = [
            r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b',  # CamelCase
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',  # Title Case phrases
            r'\b([A-Za-z]+[-_][A-Za-z]+)\b',  # Hyphenated/underscore
        ]
        
        for pattern in compound_patterns:
            matches = re.findall(pattern, text[:600])
            for match in matches:
                clean_match = re.sub(r'[-_]', ' ', match).title()
                if (3 <= len(clean_match) <= 30 and 
                    not any(skip in clean_match.lower() for skip in ['the', 'and', 'for', 'with', 'this', 'that'])):
                    return clean_match
        
        # Extract unique words and create meaningful combinations
        words = re.findall(r'\b[A-Z][a-z]{2,15}\b', text[:500])
        filtered_words = []
        
        # Enhanced word filtering
        skip_words = {
            'the', 'and', 'for', 'with', 'this', 'that', 'document', 'page', 'section', 
            'requirements', 'specification', 'description', 'overview', 'introduction',
            'chapter', 'part', 'appendix', 'figure', 'table', 'example', 'note'
        }
        
        for word in words:
            if (word.lower() not in skip_words and 
                len(word) >= 3 and 
                not word.lower().endswith('ing') and
                not word.lower().endswith('tion')):
                filtered_words.append(word)
        
        # Remove duplicates while preserving order
        unique_words = []
        seen = set()
        for word in filtered_words:
            if word.lower() not in seen:
                unique_words.append(word)
                seen.add(word.lower())
        
        # Create meaningful combinations
        if len(unique_words) >= 2:
            # Try different combinations
            combinations = [
                f"{unique_words[0]} {unique_words[1]}",
                f"{unique_words[0]} App",
                f"{unique_words[1]} System",
                f"{unique_words[0]} Platform"
            ]
            
            for combo in combinations:
                if len(combo) <= 30:
                    return combo
        
        elif len(unique_words) == 1:
            word = unique_words[0]
            # Add contextual suffix based on content
            if any(tech in text_lower for tech in ['api', 'service', 'backend']):
                return f"{word} Service"
            elif any(ui in text_lower for ui in ['ui', 'interface', 'frontend']):
                return f"{word} Interface"
            elif any(mobile in text_lower for mobile in ['mobile', 'app', 'android', 'ios']):
                return f"{word} App"
            else:
                return f"{word} System"
        
        # Content-based unique naming with timestamp
        content_words = re.findall(r'\b[a-zA-Z]{4,10}\b', text[:200])
        if content_words:
            # Use first meaningful word + timestamp for uniqueness
            base_word = content_words[0].title()
            timestamp = datetime.now().strftime("%m%d")
            return f"{base_word} App {timestamp}"
        
        # Final fallback with content hash for uniqueness
        content_hash = hashlib.md5(text[:200].encode()).hexdigest()[:6]
        return f"Project {content_hash.upper()}"
        
    except Exception as e:
        # Even fallback should be unique
        import time
        timestamp = str(int(time.time()))[-4:]
        return f"App {timestamp}"

# --------------------------------------------
# FIGMA API INTEGRATION
# --------------------------------------------
import requests
import datetime
import uuid
import time
import urllib.parse



def create_unique_filename(project_name: str, domain: str) -> str:
    """Create unique filename with domain prefix and timestamp"""
    domain_prefixes = {
        'healthcare': 'MED',
        'fintech': 'FIN',
        'education': 'EDU',
        'food': 'FOOD',
        'ecommerce': 'SHOP',
        'general': 'APP'
    }
    
    # Get domain prefix
    prefix = domain_prefixes.get(domain, 'APP')
    
    # Create timestamp
    timestamp = datetime.datetime.now().strftime("%m%d_%H%M")
    
    # Create unique ID
    unique_id = str(uuid.uuid4())[:6]
    
    # Build unique name
    return f"[{prefix}] {project_name} - {timestamp} - {unique_id}"



# --------------------------------------------
# BUILD UI REPORT WITH LLM ANALYSIS (Groq/Gemini)
# --------------------------------------------
def detect_domain_from_text(text: str) -> str:
    """Detect domain type from PDF text with priority for functional applications"""
    text_lower = text.lower()
    
    # PRIORITY 1: Functional Applications (what the app DOES)
    # These take precedence over technical implementation details
    
    # Calculator - highest priority for math operations
    if any(word in text_lower for word in ['calculator', 'calc', 'arithmetic', 'mathematical', 'computation', 'add', 'subtract', 'multiply', 'divide']):
        return 'calculator'
    
    # Chat/Communication apps
    if any(word in text_lower for word in ['chat', 'messaging', 'messenger', 'communication', 'conversation']):
        return 'chat'
    
    # E-commerce apps
    if any(word in text_lower for word in ['ecommerce', 'e-commerce', 'shop', 'shopping', 'cart', 'product', 'buy', 'sell', 'store', 'retail']):
        return 'ecommerce'
    
    # Healthcare apps
    if any(word in text_lower for word in ['health', 'medical', 'doctor', 'patient', 'hospital', 'clinic', 'medicine', 'treatment']):
        return 'healthcare'
    
    # Finance apps
    if any(word in text_lower for word in ['finance', 'bank', 'banking', 'investment', 'trading', 'wallet', 'cryptocurrency', 'loan', 'financial']):
        return 'fintech'
    
    # Food apps
    if any(word in text_lower for word in ['food', 'restaurant', 'delivery', 'recipe', 'cooking', 'meal', 'dining', 'kitchen', 'chef']):
        return 'food'
    
    # Productivity apps
    if any(word in text_lower for word in ['todo', 'task', 'reminder', 'productivity', 'organize']):
        return 'productivity'
    
    # Education apps
    if any(word in text_lower for word in ['education', 'learning', 'course', 'student', 'teacher', 'school', 'university', 'academic']):
        return 'education'
    
    # PRIORITY 2: Technical/Development Tools (only if no functional app detected)
    
    # Security tools
    if any(word in text_lower for word in ['scan', 'scanning', 'code scan', 'vulnerability', 'security scan', 'static analysis', 'penetration', 'audit']):
        return 'security'
    
    # Development tools
    if any(word in text_lower for word in ['code analysis', 'code review', 'static code', 'code quality', 'linting', 'refactoring', 'debugging']):
        return 'development'
    
    # Architecture tools
    if 'system architecture' in text_lower or ('architecture' in text_lower and 'agent' in text_lower):
        return 'architecture'
    
    # Testing tools
    if 'unit test' in text_lower or ('unit' in text_lower and 'test' in text_lower and 'agent' in text_lower):
        return 'testing'
    
    # Coding tools
    if 'coding agent' in text_lower or ('coding' in text_lower and 'agent' in text_lower):
        return 'coding'
    
    # PRIORITY 3: Fallback based on keyword density
    # Only use this if no specific functional or technical patterns found
    
    functional_domains = {
        'calculator': ['calculator', 'calc', 'arithmetic', 'mathematical', 'computation', 'numbers', 'formula', 'add', 'subtract', 'multiply', 'divide'],
        'chat': ['chat', 'messaging', 'messenger', 'communication', 'conversation'],
        'ecommerce': ['ecommerce', 'e-commerce', 'shop', 'shopping', 'cart', 'product', 'buy', 'sell', 'store', 'retail'],
        'healthcare': ['health', 'medical', 'doctor', 'patient', 'hospital', 'clinic', 'medicine', 'treatment'],
        'fintech': ['finance', 'bank', 'banking', 'investment', 'trading', 'wallet', 'cryptocurrency', 'loan', 'financial'],
        'food': ['food', 'restaurant', 'delivery', 'recipe', 'cooking', 'meal', 'dining', 'kitchen', 'chef'],
        'education': ['education', 'learning', 'course', 'student', 'teacher', 'school', 'university', 'academic'],
        'productivity': ['todo', 'task', 'reminder', 'productivity', 'organize']
    }
    
    # Count functional keywords first
    functional_counts = {domain: sum(1 for word in keywords if word in text_lower) 
                        for domain, keywords in functional_domains.items()}
    
    max_functional = max(functional_counts, key=functional_counts.get)
    if functional_counts[max_functional] > 0:
        return max_functional
    
    # If no functional domain found, check technical domains
    technical_domains = {
        'security': ['scan', 'scanning', 'vulnerability', 'security', 'penetration', 'audit', 'compliance', 'threat', 'risk'],
        'development': ['code', 'coding', 'programming', 'developer', 'software', 'api', 'function', 'algorithm', 'debug', 'git', 'repository', 'framework', 'library', 'script', 'syntax'],
        'architecture': ['architecture', 'system', 'design', 'infrastructure', 'microservices', 'scalability', 'deployment', 'cloud', 'aws', 'kubernetes', 'docker'],
        'testing': ['test', 'testing', 'unit', 'automation', 'qa', 'quality', 'junit', 'pytest', 'mocha', 'jest', 'selenium', 'cypress']
    }
    
    technical_counts = {domain: sum(1 for word in keywords if word in text_lower) 
                       for domain, keywords in technical_domains.items()}
    
    max_technical = max(technical_counts, key=technical_counts.get)
    return max_technical if technical_counts[max_technical] > 0 else 'calculator'

def extract_detailed_pdf_content(text: str) -> dict:
    """Extract comprehensive details from PDF content"""
    import re
    
    # Detect app type first
    text_lower = text.lower()
    is_calculator = any(word in text_lower for word in ['calculator', 'calc', 'arithmetic', 'mathematical', 'computation'])
    
    if is_calculator:
        # Calculator-specific extraction
        features = []
        calc_features = re.findall(r'(?:basic|scientific|advanced|memory|history|operations?)\s*([a-zA-Z\s]{5,30})', text, re.IGNORECASE)
        features.extend([f.strip().title() for f in calc_features])
        
        # Calculator operations
        operations = re.findall(r'(?:add|subtract|multiply|divide|square|root|sin|cos|tan|log)\w*', text, re.IGNORECASE)
        features.extend([op.title() for op in operations])
        
        # Default calculator features if none found
        if not features:
            features = ['Basic Operations', 'Scientific Functions', 'Memory Storage', 'History View']
        
        return {
            'business_requirements': [f'Calculator must support {f.lower()}' for f in features[:4]],
            'user_personas': ['Student', 'Engineer', 'Accountant'],
            'technical_specs': ['Python Backend', 'GUI Interface', 'Mathematical Library'],
            'workflows': ['Input Numbers', 'Select Operation', 'Display Result', 'Store History'],
            'data_entities': ['Number', 'Operation', 'Result', 'History'],
            'security_requirements': ['Input Validation', 'Error Handling']
        }
    
    # Generic extraction for other apps
    business_patterns = [
        r'(?:requirement|must|should|shall)\s*:?\s*([^.\n]{20,100})',
        r'(?:business|functional)\s+(?:requirement|need)\s*:?\s*([^.\n]{20,100})',
        r'(?:user|customer)\s+(?:story|need|requirement)\s*:?\s*([^.\n]{20,100})'
    ]
    
    business_reqs = []
    for pattern in business_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        business_reqs.extend([m.strip() for m in matches])
    
    # Extract user personas/roles
    persona_patterns = [
        r'(?:user|actor|persona|role)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        r'(?:as\s+a|as\s+an)\s+([a-z]+(?:\s+[a-z]+)*)',
        r'(?:admin|manager|customer|client|developer|tester)'
    ]
    
    personas = set()
    for pattern in persona_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        personas.update([m.strip().title() for m in matches if len(m.strip()) > 2])
    
    # Extract technical specifications
    tech_patterns = [
        r'(?:API|endpoint|service|database|framework|technology)\s*:?\s*([^.\n]{10,80})',
        r'(?:using|built with|powered by)\s+([A-Z][a-zA-Z\s]{5,30})',
        r'(?:integration|connect|sync)\s+(?:with|to)\s+([A-Z][a-zA-Z\s]{5,30})'
    ]
    
    tech_specs = []
    for pattern in tech_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        tech_specs.extend([m.strip() for m in matches])
    
    # Extract workflows/processes
    workflow_patterns = [
        r'(?:step|process|workflow|flow)\s*\d*\s*:?\s*([^.\n]{15,100})',
        r'(?:first|then|next|finally|after)\s+([^.\n]{15,80})',
        r'\d+\.\s*([A-Z][^.\n]{15,80})'
    ]
    
    workflows = []
    for pattern in workflow_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        workflows.extend([m.strip() for m in matches])
    
    # Extract data models/entities
    entity_patterns = [
        r'(?:entity|model|object|class)\s*:?\s*([A-Z][a-zA-Z]{3,20})',
        r'(?:table|collection|schema)\s*:?\s*([A-Z][a-zA-Z]{3,20})',
        r'(?:field|attribute|property)\s*:?\s*([a-zA-Z_]{3,20})'
    ]
    
    entities = set()
    for pattern in entity_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        entities.update([m.strip() for m in matches if len(m.strip()) > 2])
    
    # Extract security/compliance requirements
    security_patterns = [
        r'(?:security|authentication|authorization|encryption|compliance)\s*:?\s*([^.\n]{15,80})',
        r'(?:GDPR|HIPAA|SOX|PCI|OAuth|JWT|SSL)\s*([^.\n]{0,50})'
    ]
    
    security_reqs = []
    for pattern in security_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        security_reqs.extend([m.strip() for m in matches if m.strip()])
    
    return {
        'business_requirements': list(set(business_reqs))[:8],
        'user_personas': list(personas)[:6],
        'technical_specs': list(set(tech_specs))[:8],
        'workflows': list(set(workflows))[:6],
        'data_entities': list(entities)[:8],
        'security_requirements': list(set(security_reqs))[:6]
    }

def extract_colors_from_pdf(text: str) -> str:
    """Extract colors from PDF, generate dynamic colors if none found"""
    import re
    import random
    
    color_patterns = {
        'primary': [r'primary\s*:?\s*(#[0-9A-Fa-f]{6})', r'Primary\s*:?\s*(#[0-9A-Fa-f]{6})', r'PRIMARY\s*:?\s*(#[0-9A-Fa-f]{6})', r'main\s*color\s*:?\s*(#[0-9A-Fa-f]{6})', r'brand\s*color\s*:?\s*(#[0-9A-Fa-f]{6})'],
        'secondary': [r'secondary\s*:?\s*(#[0-9A-Fa-f]{6})', r'Secondary\s*:?\s*(#[0-9A-Fa-f]{6})', r'SECONDARY\s*:?\s*(#[0-9A-Fa-f]{6})'],
        'accent': [r'accent\s*:?\s*(#[0-9A-Fa-f]{6})', r'Accent\s*:?\s*(#[0-9A-Fa-f]{6})', r'ACCENT\s*:?\s*(#[0-9A-Fa-f]{6})', r'highlight\s*:?\s*(#[0-9A-Fa-f]{6})'],
        'background': [r'background\s*:?\s*(#[0-9A-Fa-f]{6})', r'Background\s*:?\s*(#[0-9A-Fa-f]{6})', r'BACKGROUND\s*:?\s*(#[0-9A-Fa-f]{6})']
    }
    
    extracted_colors = {}
    for color_type, patterns in color_patterns.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                extracted_colors[color_type] = matches[0]
                break
    
    all_hex_colors = re.findall(r'#[0-9A-Fa-f]{6}', text)
    if all_hex_colors and len(extracted_colors) < 3:
        if 'primary' not in extracted_colors and len(all_hex_colors) > 0:
            extracted_colors['primary'] = all_hex_colors[0]
        if 'secondary' not in extracted_colors and len(all_hex_colors) > 1:
            extracted_colors['secondary'] = all_hex_colors[1]
        if 'accent' not in extracted_colors and len(all_hex_colors) > 2:
            extracted_colors['accent'] = all_hex_colors[2]
    
    if extracted_colors:
        color_parts = [f"{k}: {v}" for k, v in extracted_colors.items()]
        return f"PDF-specified colors - {', '.join(color_parts)}"
    
    # Generate dynamic random colors
    def generate_color():
        return f"#{random.randint(0, 255):02X}{random.randint(0, 255):02X}{random.randint(0, 255):02X}"
    
    primary = generate_color()
    secondary = generate_color()
    accent = generate_color()
    
    return f"Dynamic colors - primary: {primary}, secondary: {secondary}, accent: {accent}"

# Enhanced dynamic prompt generation
def generate_dynamic_prompt(text: str, project_name: str, domain: str) -> str:
    """Generate detailed context-aware prompt with comprehensive PDF analysis"""
    # Extract detailed content
    detailed_content = extract_detailed_pdf_content(text)
    
    # Original screen and feature detection
    screen_keywords = ["login", "signup", "home", "dashboard", "profile", "cart", "checkout", "menu", "search", "settings", "booking", "payment"]
    screens = [s for s in screen_keywords if s in text.lower()][:5]
    
    feature_keywords = ["search", "filter", "payment", "notification", "chat", "map", "calendar", "upload", "analytics"]
    features = [f for f in feature_keywords if f in text.lower()][:6]
    
    # Extract PDF colors first - now always returns colors
    pdf_colors = extract_colors_from_pdf(text)
    
    # Domain-specific colors and styles - PDF colors will always be used now
    domain_configs = {
        "security": {
            "colors": pdf_colors,
            "style": "secure, alert-focused, vulnerability-oriented with clear status indicators",
            "screens": screens if screens else ["scan", "vulnerabilities", "reports", "settings"]
        },
        "development": {
            "colors": pdf_colors,
            "style": "code-focused, analytical, developer-friendly with syntax highlighting",
            "screens": screens if screens else ["analysis", "code", "reports", "settings"]
        },
        "calculator": {
            "colors": pdf_colors,
            "style": "clean, functional, number-focused with clear operation buttons",
            "screens": screens if screens else ["calculator", "operations", "history", "settings"]
        },
        "chat": {
            "colors": pdf_colors,
            "style": "friendly, conversational, message-focused",
            "screens": screens if screens else ["chats", "contacts", "profile", "settings"]
        },
        "productivity": {
            "colors": pdf_colors,
            "style": "organized, efficient, task-focused",
            "screens": screens if screens else ["tasks", "calendar", "projects", "settings"]
        },
        "food": {
            "colors": pdf_colors,
            "style": "appetizing, warm, inviting with food imagery",
            "screens": screens if screens else ["browse", "restaurant", "cart", "checkout", "tracking"]
        },
        "healthcare": {
            "colors": pdf_colors,
            "style": "clean, trustworthy, accessible with health icons",
            "screens": screens if screens else ["booking", "dashboard", "records", "consultation"]
        },
        "fintech": {
            "colors": pdf_colors,
            "style": "secure, professional, data-focused with charts",
            "screens": screens if screens else ["dashboard", "transactions", "transfer", "analytics"]
        },
        "ecommerce": {
            "colors": pdf_colors,
            "style": "attractive, product-focused, easy navigation",
            "screens": screens if screens else ["home", "products", "cart", "checkout"]
        },
        "education": {
            "colors": pdf_colors,
            "style": "engaging, clear, progress-oriented",
            "screens": screens if screens else ["courses", "dashboard", "lessons", "profile"]
        }
    }
    
    config = domain_configs.get(domain, {
        "colors": pdf_colors,
        "style": "clean, modern, user-friendly",
        "screens": screens if screens else ["home", "dashboard", "profile"]
    })
    
    # Build navigation flow
    screen_list = config["screens"]
    navigation_instructions = "\n".join([
        f"- Screen {i+1} ({screen.upper()}): Add buttons/cards that navigate to Screen {i+2 if i+1 < len(screen_list) else 1} on click"
        for i, screen in enumerate(screen_list)
    ])
    
    # Extract detailed content for enhanced prompting
    detailed_content = extract_detailed_pdf_content(text)
    
    prompt = f"""Design UI for '{project_name}'.

=== EXTRACTED PDF CONTENT ===
BUSINESS REQUIREMENTS:
{chr(10).join([f'• {req}' for req in detailed_content['business_requirements'][:5]]) if detailed_content['business_requirements'] else '• Core business functionality'}

USER PERSONAS/ROLES:
{', '.join(detailed_content['user_personas'][:4]) if detailed_content['user_personas'] else 'General Users'}

TECHNICAL SPECIFICATIONS:
{chr(10).join([f'• {spec}' for spec in detailed_content['technical_specs'][:4]]) if detailed_content['technical_specs'] else '• Standard web technologies'}

WORKFLOWS/PROCESSES:
{chr(10).join([f'• {flow}' for flow in detailed_content['workflows'][:4]]) if detailed_content['workflows'] else '• Standard user workflows'}

DATA ENTITIES:
{', '.join(detailed_content['data_entities'][:6]) if detailed_content['data_entities'] else 'User, Content, Settings'}

SECURITY REQUIREMENTS:
{chr(10).join([f'• {sec}' for sec in detailed_content['security_requirements'][:3]]) if detailed_content['security_requirements'] else '• Standard authentication'}

=== UI DESIGN SPECIFICATIONS ===
COLOR SCHEME (APPLY TO ALL COMPONENTS):
{config['colors']}

DESIGN STYLE:
{config['style']}

SCREENS: {', '.join(screen_list)}
FEATURES: {', '.join(features) if features else 'core functionality'}

NAVIGATION:
{navigation_instructions}

COLOR APPLICATION (CRITICAL):
1. gradient_banner: gradient primary→secondary, WHITE text, text_shadow
2. filter_chips: accent color background, WHITE text
3. event_cards: gradient secondary→accent, WHITE text on gradient
4. section_heading: primary color background, WHITE text
5. elevated_container: gradient accent→primary, WHITE text
6. floating_action_button: gradient primary→secondary, WHITE icon
7. All buttons: primary color, WHITE text
8. All cards: box_shadow with primary color

TEXT RULES:
- ALL text on colored backgrounds MUST be WHITE
- Headings on gradients: WHITE with shadow
- Never dark text on dark backgrounds

INTERACTIONS:
- onClick navigation between screens
- Gradient backgrounds on ALL components
- Hover states (lighten 10%)
- 300ms transitions

=== CONTENT INTEGRATION ===
Incorporate the extracted business requirements, user personas, and workflows into the UI design.
Create screens that reflect the actual processes and data entities found in the PDF.
Ensure the design supports the identified technical specifications and security requirements.

Document Content: {text[:1000]}

REQUIRED: Create a UI that reflects the ACTUAL PDF content, not generic templates."""
    
    return prompt

def build_ui_report(project_name: str, text: str, domain: str = "ecommerce") -> tuple:
    try:
        # Extract detailed content for enhanced reporting
        detailed_content = extract_detailed_pdf_content(text)
        
        # Generate enhanced prompt
        dynamic_prompt = generate_dynamic_prompt(text, project_name, domain)
        ui_data = analyzer.generate_ui_spec(dynamic_prompt)
        
        if not ui_data or not ui_data.get("screens"):
            raise ValueError("LLM returned empty or invalid response")
        
        # Enhance summary with extracted details
        enhanced_summary = f"""{ui_data.get("summary", "AI-generated UI specification")}
        
📋 BUSINESS REQUIREMENTS: {len(detailed_content['business_requirements'])} identified
👥 USER PERSONAS: {', '.join(detailed_content['user_personas'][:3]) if detailed_content['user_personas'] else 'General Users'}
⚙️ TECHNICAL SPECS: {len(detailed_content['technical_specs'])} specifications
🔄 WORKFLOWS: {len(detailed_content['workflows'])} processes identified
🗃️ DATA ENTITIES: {', '.join(detailed_content['data_entities'][:4]) if detailed_content['data_entities'] else 'Standard entities'}
🔒 SECURITY: {len(detailed_content['security_requirements'])} requirements"""
            
        report = UIReport(
            project_name=ui_data.get("project_name", project_name),
            summary=enhanced_summary,
            screens=ui_data.get("screens", []),
            styles=ui_data.get("styles", {}),
            navigation_flow=ui_data.get("navigation_flow", []),
            prototype_settings=ui_data.get("prototype_settings", {})
        )
        return report, dynamic_prompt
    except Exception as e:
        print(f"LLM Error: {e}")
        retry_prompt = f"Create a UI for: {project_name}. Context: {text[:1000]}"
        ui_data = analyzer.generate_ui_spec(retry_prompt)
        report = UIReport(
            project_name=ui_data.get("project_name", project_name),
            summary=ui_data.get("summary", "AI-generated UI specification"),
            screens=ui_data.get("screens", []),
            styles=ui_data.get("styles", {}),
            navigation_flow=ui_data.get("navigation_flow", []),
            prototype_settings=ui_data.get("prototype_settings", {})
        )
        return report, retry_prompt

# --------------------------------------------
# FASTAPI APP
# --------------------------------------------
app = FastAPI()

# Add CORS middleware with specific configuration for Figma plugin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "https://www.figma.com",
        "https://figma.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "*",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin"
    ],
)

# --------------------------------------------
# Chrome DevTools endpoint (silences 404 errors)
# --------------------------------------------
@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def devtools():
    return {}

@app.get("/upload-and-report", response_class=HTMLResponse)
async def upload_form():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PDF to Figma Generator</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            @keyframes gradientShift {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            
            @keyframes fadeInUp {
                from { opacity: 0; transform: translateY(30px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            @keyframes pulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.05); }
            }
            
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(-45deg, #667eea, #764ba2, #f093fb, #f5576c, #4facfe, #00f2fe);
                background-size: 400% 400%;
                animation: gradientShift 15s ease infinite;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            
            .container {
                background: rgba(255, 255, 255, 0.15);
                backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 32px;
                padding: 48px;
                box-shadow: 0 25px 50px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.3);
                max-width: 520px;
                width: 100%;
                text-align: center;
                animation: fadeInUp 0.8s ease;
            }
            
            .logo { 
                font-size: 56px; 
                margin-bottom: 16px;
                animation: pulse 2s ease-in-out infinite;
                filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.2));
            }
            
            h1 { 
                color: #ffffff; 
                font-size: 32px; 
                font-weight: 800; 
                margin-bottom: 12px;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
                background: linear-gradient(135deg, #ffffff, #f0f0f0);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .subtitle { 
                color: rgba(255, 255, 255, 0.9); 
                font-size: 18px; 
                margin-bottom: 40px;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
            }
            
            .upload-area {
                border: 2px dashed rgba(255, 255, 255, 0.4);
                border-radius: 24px;
                padding: 48px 24px;
                margin-bottom: 32px;
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                cursor: pointer;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                position: relative;
                overflow: hidden;
            }
            
            .upload-area::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
                transition: left 0.5s;
            }
            
            .upload-area:hover {
                border-color: rgba(255, 255, 255, 0.8);
                background: rgba(255, 255, 255, 0.2);
                transform: translateY(-4px);
                box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            }
            
            .upload-area:hover::before {
                left: 100%;
            }
            
            .upload-icon { 
                font-size: 56px; 
                color: rgba(255, 255, 255, 0.8); 
                margin-bottom: 20px;
                filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
            }
            
            .upload-text { 
                color: rgba(255, 255, 255, 0.95); 
                font-size: 18px; 
                font-weight: 600;
                margin-bottom: 8px;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
            }
            
            .upload-hint { 
                color: rgba(255, 255, 255, 0.7); 
                font-size: 14px;
            }
            
            #file-input { display: none; }
            
            .file-info {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 20px;
                padding: 20px;
                margin-bottom: 32px;
                display: none;
                backdrop-filter: blur(10px);
                animation: fadeInUp 0.5s ease;
            }
            
            .file-name { 
                color: #ffffff; 
                font-weight: 700; 
                margin-bottom: 6px;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
            }
            
            .file-size { 
                color: rgba(255, 255, 255, 0.8); 
                font-size: 14px;
            }
            
            .generate-btn {
                background: linear-gradient(135deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4);
                background-size: 300% 300%;
                animation: gradientShift 3s ease infinite;
                color: white;
                border: none;
                border-radius: 20px;
                padding: 20px 40px;
                font-size: 18px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                width: 100%;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
                position: relative;
                overflow: hidden;
            }
            
            .generate-btn::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
                transition: left 0.5s;
            }
            
            .generate-btn:hover {
                transform: translateY(-3px) scale(1.02);
                box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
            }
            
            .generate-btn:hover::before {
                left: 100%;
            }
            
            .generate-btn:active {
                transform: translateY(-1px) scale(0.98);
            }
            
            .generate-btn:disabled { 
                opacity: 0.6; 
                cursor: not-allowed;
                transform: none;
            }
            
            .loading { 
                display: none; 
                color: rgba(255, 255, 255, 0.9); 
                font-size: 16px; 
                margin-top: 20px;
                animation: pulse 1.5s ease-in-out infinite;
            }
            
            .result {
                display: none;
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 20px;
                padding: 24px;
                margin-top: 32px;
                backdrop-filter: blur(10px);
                animation: fadeInUp 0.6s ease;
            }
            
            .result h3 {
                color: #ffffff;
                margin-bottom: 12px;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
            }
            
            .result p {
                color: rgba(255, 255, 255, 0.9);
                margin-bottom: 16px;
            }
            
            .figma-link { 
                color: #ffffff; 
                text-decoration: none; 
                font-weight: 700;
                word-break: break-all;
                background: linear-gradient(135deg, #ff6b6b, #4ecdc4);
                padding: 12px 24px;
                border-radius: 12px;
                display: inline-block;
                transition: all 0.3s ease;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
            }
            
            .figma-link:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🎨</div>
            <h1>UI/UX Agent</h1>
            <p class="subtitle">Transform documents into stunning, dynamic UI designs with professional color schemes</p>
            
            <form id="upload-form" action="/upload-and-report" method="post" enctype="multipart/form-data">
                <div class="upload-area" onclick="document.getElementById('file-input').click()">
                    <div class="upload-icon">📄</div>
                    <div class="upload-text">Click to upload or drag and drop</div>
                    <div class="upload-hint">PDF, DOCX files supported</div>
                    <input type="file" id="file-input" name="file" accept=".pdf,.docx,.doc" required>
                </div>
                
                <div class="file-info" id="file-info">
                    <div class="file-name" id="file-name"></div>
                    <div class="file-size" id="file-size"></div>
                </div>
                
                <button type="submit" class="generate-btn" id="generate-btn" disabled>
                    🚀 Generate Figma Design
                </button>
                
                <div class="loading" id="loading">⏳ Analyzing document and generating design...</div>
                <div class="result" id="result">
                    <h3>✅ Design Generated Successfully!</h3>
                    <p>Your Figma design is ready:</p>
                    <a href="#" id="figma-link" class="figma-link" target="_blank">Open Figma Design</a>
                </div>
            </form>
        </div>
        
        <script>
            const fileInput = document.getElementById('file-input');
            const fileInfo = document.getElementById('file-info');
            const fileName = document.getElementById('file-name');
            const fileSize = document.getElementById('file-size');
            const generateBtn = document.getElementById('generate-btn');
            
            fileInput.addEventListener('change', function() {
                const file = this.files[0];
                if (file) {
                    fileName.textContent = file.name;
                    fileSize.textContent = (file.size / 1024 / 1024).toFixed(2) + ' MB';
                    fileInfo.style.display = 'block';
                    generateBtn.disabled = false;
                }
            });
        </script>
    </body>
    </html>
    """

# --------------------------------------------
# POST Endpoint (Generate Figma Link + Report)
# --------------------------------------------
@app.post("/upload-and-report", response_model=UIReportResponse)
async def create_upload_file(file: UploadFile = File(...)):
    file_bytes = await file.read()
    text = extract_text_from_bytes(file_bytes, file.content_type)
    
    if not text.strip():
        text = "Create a modern mobile application"

    # Use uploaded filename as project name
    import os
    project_name = os.path.splitext(file.filename)[0].replace('_', ' ').replace('-', ' ').title()
    domain = detect_domain_from_text(text)
    
    report, prompt_used = build_ui_report(project_name, text, domain)
    
    # Create unique filename for Figma
    unique_project_name = create_unique_filename(project_name, domain)
    
    # Create Figma file with error handling
    try:
        figma_url = figma_client.create_figma_file(unique_project_name)
    except Exception as e:
        print(f"Figma API error: {e}")
        figma_url = None
    
    global latest_report_data, latest_prompt_used
    latest_report_data = report.dict()
    latest_prompt_used = prompt_used
    
    return UIReportResponse(
        figma_url=figma_url,
        report=report,
        prompt_used=prompt_used
    )

# --------------------------------------------
# Upload endpoint for Figma plugin
# --------------------------------------------
@app.post("/upload", response_model=UIReportResponse)
async def upload_for_plugin(file: UploadFile = File(...)):
    return await create_upload_file(file)

@app.get("/favicon.ico")
async def favicon():
    return {"message": "No favicon"}

# --------------------------------------------
# Sample report endpoint
# --------------------------------------------
@app.post("/sample-report")
def sample_report():
    """Generate report from sample document and auto-open Figma"""
    sample_path = os.getenv("SAMPLE_DOCUMENT_PATH", "./sample-data/ecommerce_uiux_report.pdf")
    
    try:
        with open(sample_path, "rb") as f:
            file_bytes = f.read()
        
        text = extract_text_from_bytes(file_bytes, "application/pdf")
        project_name = extract_project_name(text) if text.strip() else "Sample-Project"
        domain = detect_domain_from_text(text)
        
        report, prompt_used = build_ui_report(project_name, text, domain)
        
        # Create unique filename for Figma
        unique_project_name = create_unique_filename(project_name, domain)
        
        # Create Figma file with error handling
        try:
            figma_url = figma_client.create_figma_file(unique_project_name)
        except Exception as e:
            print(f"Figma API error: {e}")
            figma_url = None
        
        return UIReportResponse(
            figma_url=figma_url,
            report=report,
            prompt_used=prompt_used
        )
    except Exception as e:
        return {"error": f"Could not process sample document: {e}"}

# Store latest report and prompt globally for auto-fetch
latest_report_data = None
latest_prompt_used = None

@app.get("/latest-report")
def get_latest_report():
    """Get the most recent report for auto-plugin fetching"""
    if latest_report_data:
        return {
            "status": "success",
            "report": latest_report_data
        }
    else:
        return {
            "status": "no_data",
            "message": "No recent reports available"
        }

@app.get("/latest-prompt")
def get_latest_prompt():
    """Get the most recent prompt used for generation"""
    if latest_prompt_used:
        return {
            "status": "success",
            "prompt": latest_prompt_used
        }
    else:
        return {
            "status": "no_data",
            "message": "No recent prompt available. Upload a PDF first."
        }

@app.options("/latest-report")
def options_latest_report():
    """Handle CORS preflight for latest-report endpoint"""
    from fastapi import Response
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true"
        }
    )

@app.get("/")
def root():
    return {"message": "Server is running"}