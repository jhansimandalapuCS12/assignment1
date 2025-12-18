import json
import os
import re
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException

try:
    from groq import Groq  # type: ignore
except ImportError:
    Groq = None  # type: ignore


PROMPT_TEMPLATE = """
You are a world-class senior UI/UX designer creating MODERN APP DESIGNS.

✅ REQUIRED UI VOCABULARY: gradient_banner, elevated_container, rounded_card, filter_chips, event_cards, section_heading, bottom_sheet, floating_action_button, overlay, box_shadow

OUTPUT PURE JSON (no markdown):

{
  "project_name": "Extract from document",
  "summary": "Modern app description",
  "screens": [
    {
      "name": "Screen Name",
      "layout": {
        "sections": [
          {
            "component": "gradient_banner",
            "gradient": "linear #FF6B6B → #4ECDC4",
            "height": 280,
            "title_style": "Poppins 800 42px white",
            "subtitle_style": "Inter 500 18px rgba(255,255,255,0.9)",
            "padding": 40,
            "overlay": "rgba(0,0,0,0.3)"
          },
          {
            "component": "filter_chips",
            "chip_style": {
              "background": "rgba(255,255,255,0.15)",
              "selected_background": "#FF6B6B",
              "text_color": "white",
              "border_radius": 25,
              "padding_x": 24,
              "padding_y": 12,
              "box_shadow": "0 4px 15px rgba(0,0,0,0.1)"
            },
            "items": ["Category1", "Category2", "Category3"]
          },
          {
            "component": "event_cards",
            "card_style": {
              "background": "white",
              "border_radius": 24,
              "box_shadow": "0 8px 32px rgba(0,0,0,0.12)",
              "padding": 24,
              "gradient_overlay": "linear #667eea → #764ba2",
              "text_style": "Inter 700 20px white",
              "image_overlay": true
            },
            "grid_columns": 2,
            "spacing": 16
          },
          {
            "component": "section_heading",
            "title": "Featured Items",
            "icon": "star-filled",
            "title_style": "Poppins 800 28px #2D3748",
            "icon_color": "#FFD700",
            "padding": 24
          },
          {
            "component": "elevated_container",
            "background": "linear #f093fb → #f5576c",
            "border_radius": 20,
            "box_shadow": "0 12px 40px rgba(240,147,251,0.4)",
            "padding": 32,
            "content_style": "Inter 600 16px white"
          },
          {
            "component": "bottom_sheet",
            "background": "white",
            "border_radius": 32,
            "box_shadow": "0 -8px 24px rgba(0,0,0,0.2)",
            "height": 400,
            "handle_color": "#E2E8F0"
          },
          {
            "component": "floating_action_button",
            "gradient": "linear #FF6B6B → #FF8E8E",
            "size": 64,
            "icon": "plus",
            "box_shadow": "0 8px 16px rgba(255,107,107,0.4)",
            "position": "bottom-right"
          }
        ]
      },
      "description": "Modern screen with gradient banners and elevated cards"
    }
  ],
  "styles": {
    "colors": {
      "primary": "#FF6B6B",
      "secondary": "#4ECDC4",
      "accent": "#FFE66D",
      "background": "#F8F9FA",
      "surface": "#FFFFFF"
    },
    "typography": {
      "display": "Poppins 800",
      "heading": "Poppins 700",
      "subheading": "Poppins 600",
      "body": "Inter 500",
      "caption": "Inter 400"
    },
    "components": [
      "gradient_banner",
      "filter_chips",
      "event_cards",
      "elevated_container",
      "rounded_card",
      "section_heading",
      "floating_action_button",
      "bottom_sheet"
    ]
  }
}

🎨 DESIGN REQUIREMENTS:
- ALWAYS use modern UI components (gradient_banner, event_cards, filter_chips, bottom_sheet, floating_action_button)
- FORCE gradients, shadows, rounded corners on EVERYTHING
- Use vibrant color palettes (#FF6B6B, #4ECDC4, #FFE66D)
- Every component needs box_shadow and border_radius
- Text must be Poppins 700+ or Inter 500+
- All containers must be elevated_container or rounded_card
- Include floating_action_button for primary actions
- Use bottom_sheet for secondary content and actions

Document:
"{DOCUMENT_TEXT}"
"""


class UIAnalyzer:
    def __init__(self, groq_model: Optional[str] = None) -> None:
        self.groq_model = groq_model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is missing.")
        if Groq is None:
            raise RuntimeError("groq python package missing. Install: pip install groq")
        
        self._groq_client = Groq(api_key=api_key)

    def generate_ui_spec(self, document_text: str) -> Dict[str, Any]:
        if not document_text.strip():
            document_text = "Create a modern e-commerce application with colorful UI design"

        # Extract content-specific information
        content_analysis = self._analyze_document_content(document_text)
        
        excerpt = document_text[:3000]
        prompt = self._build_content_aware_prompt(excerpt, content_analysis)
        
        raw_output = self._call_groq_with_retry(prompt)
        parsed = self._safe_parse_json(raw_output, document_text)

        # Enhance with extracted content
        parsed = self._enhance_with_content(parsed, content_analysis)
        
        # Force content-specific elements
        parsed = self._force_content_specificity(parsed, content_analysis)
        
        # Debug output
        print(f"Final parsed project_name: {parsed.get('project_name')}")
        print(f"Content analysis project_name: {content_analysis['project_name']}")
        print(f"Features: {content_analysis['features']}")
        print(f"Sections: {content_analysis['sections']}")

        if not isinstance(parsed, dict):
            raise HTTPException(status_code=502, detail="LLM returned invalid JSON.")

        return parsed
    
    def _generate_multiple_screens(self, content_analysis: Dict) -> list:
        """Generate multiple screens based on PDF sections and features"""
        screens = []
        
        # Generate screens based on sections
        sections = content_analysis.get('sections', [])
        features = content_analysis.get('features', [])
        colors = content_analysis.get('colors', {})
        
        # Create unique screen names from PDF content
        screen_names = []
        
        # Use actual sections from PDF as screen names
        for section in sections[:3]:
            screen_names.append(section)
        
        # Add feature-based screens with PDF context
        for i, feature in enumerate(features[:2]):
            if feature not in screen_names:
                screen_names.append(feature)
        
        # Ensure minimum screens with content-specific names
        if len(screen_names) < 3:
            additional_names = [f"{content_analysis['app_type']} Dashboard", f"{features[0]} Details" if features else "Technical Details"]
            screen_names.extend([name for name in additional_names if name not in screen_names])
        
        screen_names = screen_names[:5]  # Max 5 screens
        
        for i, screen_name in enumerate(screen_names):
            # Generate unique content for each screen based on PDF content
            screen_title = content_analysis['project_name'] if i == 0 else screen_name
            screen_subtitle = f"Your {content_analysis['app_type']} solution" if i == 0 else f"{screen_name} Management"
            
            # Use different features for each screen
            screen_features = features[i:i+4] if len(features) > i else features
            if len(screen_features) < 4:
                screen_features.extend([f"{screen_name} Feature {j+1}" for j in range(4-len(screen_features))])
            
            screen = {
                "name": screen_name,
                "layout": {
                    "sections": [
                        {
                            "component": "gradient_banner" if i == 0 else "section_heading",
                            "gradient": f"linear {colors.get('primary', '#6366F1')} → {colors.get('secondary', '#8B5CF6')}" if i == 0 else None,
                            "height": 280 if i == 0 else None,
                            "title": screen_title,
                            "subtitle": screen_subtitle if i == 0 else None,
                            "background": colors.get('primary', '#6366F1') if i != 0 else None,
                            "text_color": "#FFFFFF" if i != 0 else None
                        },
                        {
                            "component": "filter_chips" if i == 0 else "event_cards",
                            "items": screen_features[:4] if i == 0 else None,
                            "grid_columns": 2 if i != 0 else None,
                            "cardTitle": f"{screen_name} Cards" if i != 0 else None,
                            "gradient": f"linear {colors.get('secondary', '#8B5CF6')} → {colors.get('accent', '#06B6D4')}" if i != 0 else None
                        },
                        {
                            "component": "elevated_container",
                            "title": f"{screen_name} Details" if i > 0 else "Core Features",
                            "gradient": f"linear {colors.get('accent', '#06B6D4')} → {colors.get('primary', '#6366F1')}"
                        }
                    ]
                },
                "description": f"{screen_name} for {content_analysis['project_name']} - {content_analysis['app_type']}",
                "interactions": [],
                "component_states": []
            }
            
            # Clean up None values
            for section in screen["layout"]["sections"]:
                screen["layout"]["sections"] = [{k: v for k, v in s.items() if v is not None} for s in screen["layout"]["sections"]]
            
            screens.append(screen)
        
        return screens
    
    def _get_content_based_title(self, screen_name: str, features: list, index: int) -> str:
        """Generate content-based card titles instead of generic 'Cards'"""
        import hashlib
        
        # Use screen name + index to get unique feature
        screen_hash = int(hashlib.md5(screen_name.encode()).hexdigest()[:2], 16)
        feature_index = (screen_hash + index) % len(features) if features else 0
        
        if features and feature_index < len(features):
            return features[feature_index]
        
        # Content-specific alternatives based on screen name
        alternatives = {
            'technical': 'Technical Specifications',
            'frontend': 'Frontend Components', 
            'backend': 'Backend Services',
            'testing': 'Test Cases',
            'quality': 'Quality Metrics',
            'analysis': 'Analysis Reports',
            'implementation': 'Implementation Guide',
            'architecture': 'Architecture Overview',
            'management': 'Resource Management',
            'analytics': 'Performance Analytics',
            'settings': 'Configuration Settings'
        }
        
        for key, value in alternatives.items():
            if key.lower() in screen_name.lower():
                return value
        
        return f"{screen_name} Overview"
    
    def _get_content_based_detail(self, screen_name: str, features: list, sections: list, index: int) -> str:
        """Generate content-based detail titles instead of generic 'Details'"""
        import hashlib
        
        # Use screen name hash to get unique section/feature
        screen_hash = int(hashlib.md5(screen_name.encode()).hexdigest()[2:4], 16)
        
        if sections:
            section_index = (screen_hash + index + 1) % len(sections)
            return f"{sections[section_index]} Information"
        
        if features:
            feature_index = (screen_hash + index + 2) % len(features)
            return f"{features[feature_index]} Configuration"
        
        # Content-specific alternatives
        detail_alternatives = {
            'technical': 'Technical Documentation',
            'frontend': 'Frontend Architecture', 
            'backend': 'Backend Configuration',
            'testing': 'Testing Framework',
            'quality': 'Quality Standards',
            'analysis': 'Analysis Results',
            'implementation': 'Implementation Steps',
            'architecture': 'System Design',
            'management': 'Management Console',
            'analytics': 'Analytics Dashboard',
            'settings': 'Settings Panel'
        }
        
        for key, value in detail_alternatives.items():
            if key.lower() in screen_name.lower():
                return value
        
        return f"{screen_name} Information"
    
    def _extract_key_phrases(self, text: str) -> list:
        """Extract key phrases from document for better context"""
        import re
        
        # Extract phrases after common indicators
        phrases = []
        
        # Phrases after "is", "are", "will", "can"
        action_phrases = re.findall(r'(?:is|are|will|can)\s+([a-zA-Z\s]{10,50})', text, re.IGNORECASE)
        phrases.extend([p.strip() for p in action_phrases])
        
        # Phrases in quotes
        quoted_phrases = re.findall(r'"([^"]{5,50})"', text)
        phrases.extend(quoted_phrases)
        
        # Important noun phrases
        noun_phrases = re.findall(r'\b(?:the|a|an)\s+([A-Z][a-zA-Z\s]{5,30})', text)
        phrases.extend([p.strip() for p in noun_phrases])
        
        # Clean and return unique phrases
        clean_phrases = [p for p in phrases if len(p.split()) >= 2 and len(p) <= 40]
        return list(dict.fromkeys(clean_phrases))[:10]
    
    def _force_content_specificity(self, parsed: Dict, content_analysis: Dict) -> Dict:
        """Force the design to be content-specific, not generic"""
        # Always use extracted project name
        parsed['project_name'] = content_analysis['project_name']
        
        # Update summary to be content-specific
        parsed['summary'] = f"{content_analysis['project_name']} - {content_analysis['app_type']} with {', '.join(content_analysis['features'][:3])}"
        
        # Force content-specific colors
        parsed['styles']['colors'] = content_analysis['colors']
        
        # Update all screens to use content-specific data
        for i, screen in enumerate(parsed.get('screens', [])):
            # Update screen names with PDF content
            if i == 0:
                screen['name'] = content_analysis['sections'][0] if content_analysis['sections'] else f"{content_analysis['features'][0]} Overview" if content_analysis['features'] else "Main Overview"
            else:
                section_name = content_analysis['sections'][i] if i < len(content_analysis['sections']) else content_analysis['features'][i-1] if i-1 < len(content_analysis['features']) else "Secondary View"
                screen['name'] = section_name
            
            # Update screen descriptions
            screen['description'] = f"{screen['name']} for {content_analysis['project_name']} - {content_analysis['app_type']}"
            
            # Update sections within each screen
            for section in screen.get('layout', {}).get('sections', []):
                if section.get('component') == 'gradient_banner':
                    section['title'] = content_analysis['project_name']
                    section['subtitle'] = f"Your {content_analysis['app_type']} solution"
                    section['gradient'] = f"linear {content_analysis['colors']['primary']} → {content_analysis['colors']['secondary']}"
                
                elif section.get('component') == 'filter_chips':
                    section['items'] = content_analysis['features']
                
                elif section.get('component') == 'section_heading':
                    if content_analysis['sections']:
                        section['title'] = content_analysis['sections'][0]
                    section['background'] = content_analysis['colors']['primary']
                
                elif section.get('component') == 'event_cards':
                    section['cardTitle'] = f"{content_analysis['features'][0]} Cards" if content_analysis['features'] else "Feature Cards"
                    section['gradient'] = f"linear {content_analysis['colors']['secondary']} → {content_analysis['colors']['accent']}"
                
                elif section.get('component') == 'elevated_container':
                    section['title'] = content_analysis['sections'][1] if len(content_analysis['sections']) > 1 else f"{content_analysis['app_type']} Features"
                    section['gradient'] = f"linear {content_analysis['colors']['accent']} → {content_analysis['colors']['primary']}"
        
        return parsed

    def _call_groq_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                response = self._groq_client.chat.completions.create(
                    model=self.groq_model,
                    temperature=0.2,
                    max_tokens=3000,
                    timeout=45,
                    messages=[
                        {"role": "system", "content": "You are a senior UI/UX designer. Analyze the document content carefully and extract REAL project information. Create content-specific designs, not generic templates. Output only valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    time.sleep(wait_time)
                    continue
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise e
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    def _build_simple_prompt_old(self, document_text: str) -> str:
        # Extract key information from document
        app_type = self._detect_app_type(document_text)
        color_scheme = self._suggest_color_scheme(document_text)
        
        # Extract key phrases and titles from document
        import re
        
        # Find potential titles (lines with title case or all caps)
        lines = document_text.split('\n')[:30]
        title_patterns = [
            r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$',  # Title Case
            r'^[A-Z\s]+$',  # ALL CAPS
            r'^\d+\.\s*([A-Z][a-z]+(\s+[A-Z][a-z]+)*)$'  # Numbered titles
        ]
        
        titles = []
        for line in lines:
            line = line.strip()
            if 5 <= len(line) <= 60:
                for pattern in title_patterns:
                    if re.match(pattern, line):
                        titles.append(line)
                        break
        
        # Extract features/keywords
        feature_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', document_text)
        features = list(set([f for f in feature_words if 3 <= len(f) <= 20]))[:8]
        
        return f"""
Document Content:
{document_text[:1500]}

Based on this SPECIFIC document, create a UNIQUE UI design. Extract REAL content from the document:

1. ANALYZE the document and identify:
   - What type of app/system this is about
   - Key features mentioned
   - Target audience
   - Main functionality

2. CREATE content-specific UI elements:
   - Use ACTUAL project name from document
   - Extract REAL feature names for filter chips
   - Use ACTUAL section titles from document
   - Choose colors that match the domain

3. GENERATE multiple screens based on document content

Output ONLY valid JSON:
{{
  "project_name": "[Extract REAL project name from document - not generic]",
  "summary": "[What this specific app does based on document analysis]",
  "screens": [
    {{
      "name": "[Main screen name from document purpose]",
      "layout": {{
        "sections": [
          {{
            "component": "gradient_banner",
            "gradient": "linear {color_scheme['primary']} → {color_scheme['secondary']}",
            "height": 280,
            "title": "[ACTUAL title from document]",
            "subtitle": "[ACTUAL subtitle/description from document]"
          }},
          {{
            "component": "filter_chips",
            "items": ["[Feature1 from doc]", "[Feature2 from doc]", "[Feature3 from doc]", "[Feature4 from doc]"]
          }},
          {{
            "component": "event_cards",
            "grid_columns": 2,
            "cardTitle": "[Card title from document content]",
            "gradient": "linear {color_scheme['primary']} → {color_scheme['accent']}"
          }},
          {{
            "component": "section_heading",
            "title": "[Section heading from document]",
            "background": "{color_scheme['primary']}",
            "text_color": "#FFFFFF"
          }},
          {{
            "component": "elevated_container",
            "title": "[Container title from document]",
            "gradient": "linear {color_scheme['secondary']} → {color_scheme['accent']}"
          }}
        ]
      }},
      "description": "[Screen description based on document purpose]"
    }},
    {{
      "name": "[Second screen from document features]",
      "layout": {{
        "sections": [
          {{
            "component": "section_heading",
            "title": "[Another section from document]",
            "background": "{color_scheme['secondary']}"
          }},
          {{
            "component": "rounded_card",
            "title": "[Card content from document]",
            "background": "linear {color_scheme['accent']} → {color_scheme['primary']}"
          }},
          {{
            "component": "bottom_sheet",
            "title": "[Bottom sheet title from document]"
          }}
        ]
      }},
      "description": "[Second screen description]"
    }}
  ],
  "styles": {{
    "colors": {{
      "primary": "{color_scheme['primary']}",
      "secondary": "{color_scheme['secondary']}",
      "accent": "{color_scheme['accent']}",
      "background": "#F8F9FA",
      "surface": "#FFFFFF"
    }},
    "typography": {{
      "display": "Poppins 800",
      "heading": "Poppins 700",
      "body": "Inter 500"
    }}
  }}
}}

CRITICAL: Do NOT use generic templates. Extract REAL content from the document and create UI that matches the specific project described.
"""
    
    def _detect_app_type(self, text: str) -> str:
        text_lower = text.lower()
        
        # Enhanced keyword detection with more specific terms
        tech_keywords = ['code', 'coding', 'programming', 'software', 'developer', 'api', 'function', 'algorithm', 'debug', 'git', 'repository', 'framework', 'library', 'script', 'syntax', 'testing', 'unit test', 'automation', 'qa', 'quality', 'junit', 'pytest']
        healthcare_keywords = ['health', 'medical', 'doctor', 'patient', 'hospital', 'clinic', 'medicine', 'healthcare', 'treatment', 'diagnosis', 'prescription']
        fintech_keywords = ['finance', 'financial', 'bank', 'banking', 'investment', 'trading', 'wallet', 'cryptocurrency', 'loan', 'payment', 'transaction', 'money', 'credit', 'debit']
        education_keywords = ['education', 'learning', 'course', 'student', 'teacher', 'school', 'university', 'academic', 'curriculum', 'assignment', 'grade', 'exam']
        food_keywords = ['food', 'restaurant', 'delivery', 'recipe', 'cooking', 'meal', 'dining', 'kitchen', 'chef', 'menu', 'order']
        ecommerce_keywords = ['ecommerce', 'e-commerce', 'shop', 'shopping', 'cart', 'product', 'store', 'retail', 'buy', 'sell', 'marketplace', 'catalog', 'purchase']
        
        # Count with weighted scoring
        tech_count = sum(2 if word in text_lower else 0 for word in tech_keywords)
        healthcare_count = sum(2 if word in text_lower else 0 for word in healthcare_keywords)
        fintech_count = sum(2 if word in text_lower else 0 for word in fintech_keywords)
        education_count = sum(2 if word in text_lower else 0 for word in education_keywords)
        food_count = sum(2 if word in text_lower else 0 for word in food_keywords)
        ecommerce_count = sum(1 if word in text_lower else 0 for word in ecommerce_keywords)
        
        # Return the domain with the highest keyword count
        counts = {
            'tech app': tech_count,
            'healthcare app': healthcare_count,
            'fintech app': fintech_count,
            'education app': education_count,
            'food delivery app': food_count,
            'e-commerce app': ecommerce_count
        }
        
        max_domain = max(counts, key=counts.get)
        print(f"Domain detection: {counts}, Selected: {max_domain}")
        return max_domain if counts[max_domain] > 0 else 'tech app'
    
    def _suggest_color_scheme(self, text: str) -> Dict[str, str]:
        """Generate truly dynamic colors based on PDF content analysis"""
        import re
        import hashlib
        
        text_lower = text.lower()
        
        # Extract brand colors from PDF if mentioned
        hex_colors = re.findall(r'#[0-9A-Fa-f]{6}', text)
        if hex_colors:
            primary = hex_colors[0]
            secondary = hex_colors[1] if len(hex_colors) > 1 else self._adjust_color(primary, -20, 10)
            accent = hex_colors[2] if len(hex_colors) > 2 else self._adjust_color(primary, 60, -10)
        else:
            # Content-based color generation
            primary, secondary, accent = self._generate_content_colors(text_lower)
        
        # Dynamic background and surface colors based on primary
        background = self._lighten_color(primary, 95)
        surface = self._lighten_color(primary, 98)
        
        # Dynamic text colors based on contrast
        primary_text = self._get_contrast_color(primary)
        secondary_text = self._get_contrast_color(secondary)
        accent_text = self._get_contrast_color(accent)
        background_text = self._get_contrast_color(background)
        surface_text = self._get_contrast_color(surface)
        
        return {
            'primary': primary,
            'secondary': secondary,
            'accent': accent,
            'background': background,
            'surface': surface,
            'primary_text': primary_text,
            'secondary_text': secondary_text,
            'accent_text': accent_text,
            'background_text': background_text,
            'surface_text': surface_text,
            'gradient_start': self._adjust_color(primary, -10, 5),
            'gradient_end': self._adjust_color(secondary, 10, 5)
        }
    
    def _generate_content_colors(self, text_lower: str) -> tuple:
        """Generate colors based on content keywords and context"""
        import hashlib
        
        # Content-based color mapping
        color_keywords = {
            # Security/Scanning - Red family
            'security': ('#DC2626', '#B91C1C', '#F59E0B'),
            'scan': ('#EF4444', '#DC2626', '#F97316'),
            'vulnerability': ('#B91C1C', '#991B1B', '#EA580C'),
            
            # Healthcare - Blue/Green family
            'health': ('#0EA5E9', '#06B6D4', '#10B981'),
            'medical': ('#0284C7', '#0891B2', '#059669'),
            'hospital': ('#0369A1', '#0E7490', '#047857'),
            
            # Finance - Blue/Green family
            'finance': ('#1E40AF', '#3B82F6', '#10B981'),
            'bank': ('#1E3A8A', '#2563EB', '#059669'),
            'payment': ('#1D4ED8', '#3B82F6', '#0D9488'),
            
            # Technology - Dark/Cyan family
            'tech': ('#374151', '#6B7280', '#06B6D4'),
            'code': ('#1F2937', '#4B5563', '#0891B2'),
            'software': ('#111827', '#374151', '#0E7490'),
            
            # Education - Purple/Blue family
            'education': ('#7C3AED', '#8B5CF6', '#3B82F6'),
            'learning': ('#6D28D9', '#7C3AED', '#2563EB'),
            'course': ('#5B21B6', '#6D28D9', '#1D4ED8'),
            
            # Food - Orange/Red family
            'food': ('#EA580C', '#F97316', '#DC2626'),
            'restaurant': ('#C2410C', '#EA580C', '#B91C1C'),
            'delivery': ('#9A3412', '#C2410C', '#991B1B'),
            
            # E-commerce - Purple/Pink family
            'shop': ('#7C3AED', '#EC4899', '#F59E0B'),
            'ecommerce': ('#6D28D9', '#DB2777', '#D97706'),
            'marketplace': ('#5B21B6', '#BE185D', '#B45309'),
            
            # Calculator - Blue/Orange family
            'calculator': ('#2563EB', '#1D4ED8', '#F59E0B'),
            'math': ('#1E40AF', '#1E3A8A', '#EA580C'),
            'computation': ('#1D4ED8', '#1E40AF', '#D97706')
        }
        
        # Find matching keywords
        matched_colors = None
        for keyword, colors in color_keywords.items():
            if keyword in text_lower:
                matched_colors = colors
                break
        
        if matched_colors:
            return matched_colors
        
        # Generate unique colors based on content hash
        content_hash = hashlib.md5(text_lower.encode()).hexdigest()
        
        # Use different parts of hash for different colors
        primary_hue = int(content_hash[:2], 16) * 360 // 255
        secondary_hue = (primary_hue + 120) % 360
        accent_hue = (primary_hue + 240) % 360
        
        # Generate professional saturation and lightness
        saturation = 60 + (int(content_hash[2:4], 16) % 25)  # 60-85%
        lightness = 45 + (int(content_hash[4:6], 16) % 15)   # 45-60%
        
        primary = self._hsl_to_hex(primary_hue, saturation, lightness)
        secondary = self._hsl_to_hex(secondary_hue, saturation - 10, lightness + 5)
        accent = self._hsl_to_hex(accent_hue, saturation + 5, lightness - 5)
        
        return (primary, secondary, accent)
    
    def _adjust_color(self, hex_color: str, hue_shift: int, lightness_shift: int) -> str:
        """Adjust a hex color by shifting hue and lightness"""
        # Convert hex to HSL, adjust, convert back
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        h, s, l = self._rgb_to_hsl(r, g, b)
        
        h = (h + hue_shift) % 360
        l = max(0, min(100, l + lightness_shift))
        
        return self._hsl_to_hex(h, s, l)
    
    def _lighten_color(self, hex_color: str, target_lightness: int) -> str:
        """Create a lighter version of a color"""
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        h, s, l = self._rgb_to_hsl(r, g, b)
        return self._hsl_to_hex(h, max(10, s - 40), target_lightness)
    
    def _get_contrast_color(self, hex_color: str) -> str:
        """Calculate optimal text color for given background color"""
        # Convert hex to RGB
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        
        # Calculate luminance
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        
        # Generate contrasting color based on luminance
        if luminance > 0.6:  # Light background
            # Use dark color variations instead of pure black
            h, s, l = self._rgb_to_hsl(r, g, b)
            return self._hsl_to_hex(h, min(80, s + 20), max(15, l - 70))
        else:  # Dark background
            # Use light color variations instead of pure white
            h, s, l = self._rgb_to_hsl(r, g, b)
            return self._hsl_to_hex(h, max(10, s - 30), min(95, l + 60))
    
    def _rgb_to_hsl(self, r: int, g: int, b: int) -> tuple:
        """Convert RGB to HSL"""
        r, g, b = r/255.0, g/255.0, b/255.0
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        diff = max_val - min_val
        
        # Lightness
        l = (max_val + min_val) / 2
        
        if diff == 0:
            h = s = 0
        else:
            # Saturation
            s = diff / (2 - max_val - min_val) if l > 0.5 else diff / (max_val + min_val)
            
            # Hue
            if max_val == r:
                h = (g - b) / diff + (6 if g < b else 0)
            elif max_val == g:
                h = (b - r) / diff + 2
            else:
                h = (r - g) / diff + 4
            h /= 6
        
        return (int(h * 360), int(s * 100), int(l * 100))
    
    def _hsl_to_hex(self, h: int, s: int, l: int) -> str:
        """Convert HSL to HEX color"""
        h = h / 360
        s = s / 100
        l = l / 100
        
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        
        if s == 0:
            r = g = b = l
        else:
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    
    def _analyze_document_content(self, text: str) -> Dict[str, Any]:
        """Extract specific content from document for UI generation"""
        import re
        import time
        
        # Skip first 10 lines to avoid document headers
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        content_lines = lines[10:] if len(lines) > 10 else lines
        content_text = '\n'.join(content_lines)
        
        # Extract project name using improved method
        project_name = self._extract_project_title(text)
        
        # Clean up project name if it's too generic
        if any(generic in project_name.lower() for generic in ['dynamic project', 'document analysis', 'product overview']):
            # Try to find a better name from the content
            better_names = re.findall(r'(?:Project|System|Application|Platform|Tool|Agent)\s*:?\s*([A-Z][A-Za-z\s]{5,30})', text, re.IGNORECASE)
            if better_names:
                project_name = f"{better_names[0].strip()} {str(int(time.time()))[-4:]}"
        
        # Extract meaningful features from PDF content
        features = []
        
        # Look for PRD-specific features first
        prd_features = []
        
        # Unit test specific patterns
        test_patterns = [
            r'\b(Unit\s+Test[a-zA-Z\s]*)',
            r'\b(Test\s+Case[a-zA-Z\s]*)',
            r'\b(Code\s+Coverage[a-zA-Z\s]*)',
            r'\b(Test\s+Automation[a-zA-Z\s]*)',
            r'\b(Quality\s+Assurance[a-zA-Z\s]*)',
            r'\b(Bug\s+Detection[a-zA-Z\s]*)',
            r'\b(Test\s+Generation[a-zA-Z\s]*)',
            r'\b(Code\s+Analysis[a-zA-Z\s]*)',
        ]
        
        for pattern in test_patterns:
            matches = re.findall(pattern, content_text, re.IGNORECASE)
            prd_features.extend([m.strip().title() for m in matches])
        
        # Look for bullet points and numbered lists (skip first 10 lines)
        bullet_features = re.findall(r'[•\-\*]\s*([A-Za-z][A-Za-z\s]{3,40})', content_text)
        features.extend([f.strip().title()[:40] for f in bullet_features])
        
        # Add PRD-specific features first
        features = prd_features + features
        
        # Look for key phrases after colons
        colon_features = re.findall(r':\s*([A-Z][A-Za-z\s]{3,40})', content_text)
        features.extend([f.strip().title()[:40] for f in colon_features])
        
        # Extract important nouns and phrases (minimum 5 characters)
        important_words = re.findall(r'\b([A-Z][a-z]{5,15})\b', content_text)
        features.extend(important_words)
        
        # Expanded common words to filter out document metadata
        common_words = {
            # Original common words
            'the', 'and', 'for', 'with', 'this', 'that', 'from', 'they', 'have', 'will', 'been', 'were',
            # Document metadata words
            'document', 'page', 'section', 'overview', 'description', 'requirements', 'requirement',
            'specification', 'specifications', 'introduction', 'conclusion', 'appendix', 'summary',
            # Generic project terms
            'project', 'product', 'report', 'analysis', 'version', 'draft', 'final', 'review',
            # PDF metadata
            'chapter', 'contents', 'table', 'figure', 'index', 'reference', 'references'
        }
        
        # Filter: minimum 5 characters, not in common words
        features = [f for f in features if f.lower() not in common_words and len(f) >= 5]
        features = list(dict.fromkeys(features))[:6]  # Remove duplicates while preserving order
        
        # If no features found, extract from document content dynamically
        if len(features) < 4:
            # Extract meaningful words from document (skip first 10 lines, minimum 5 chars)
            meaningful_words = re.findall(r'\b([A-Z][a-z]{5,12})\b', content_text)
            # Filter out common words
            filtered_words = [w for w in meaningful_words if w.lower() not in common_words]
            features.extend(filtered_words[:4-len(features)])
            
        # Final fallback - generate from document hash
        if len(features) < 4:
            import hashlib
            doc_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            generic_features = [f'Feature {doc_hash[:2]}', f'Component {doc_hash[2:4]}', f'Module {doc_hash[4:6]}', f'System {doc_hash[6:8]}']
            features.extend(generic_features[:4-len(features)])
        
        # Extract sections/headings from PDF content
        sections = []
        for line in lines:
            # Numbered sections (1. Section Name)
            if re.match(r'^\d+\.\s*(.+)$', line):
                section_text = re.match(r'^\d+\.\s*(.+)$', line).group(1).strip()
                if len(section_text) > 3:
                    sections.append(section_text[:50])  # Keep full text up to 50 chars
            
            # Section headers ending with colon
            elif line.endswith(':') and 5 <= len(line) <= 80:
                sections.append(line[:-1].strip()[:50])
            
            # ALL CAPS headings
            elif re.match(r'^[A-Z][A-Z\s]{5,50}$', line):
                sections.append(line.title()[:50])
            
            # Title Case headings
            elif re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', line) and 5 <= len(line) <= 80:
                sections.append(line[:50])
            
            # Headers with special formatting (===, ---, etc.)
            elif re.match(r'^[=\-]{3,}\s*([A-Za-z\s]+)\s*[=\-]{3,}$', line):
                header = re.match(r'^[=\-]{3,}\s*([A-Za-z\s]+)\s*[=\-]{3,}$', line).group(1).strip()
                if header:
                    sections.append(header.title()[:50])
        
        # Remove duplicates and ensure we have meaningful sections
        sections = list(dict.fromkeys(sections))[:5]
        if not sections:
            # Generate sections from document content
            import hashlib
            doc_hash = hashlib.md5(text.encode()).hexdigest()[:6]
            sections = [f'Section {doc_hash[:2]}', f'Module {doc_hash[2:4]}', f'Component {doc_hash[4:6]}']
        
        # Detect app type and get domain-specific content
        app_type = self._detect_app_type(text)
        color_scheme = self._suggest_color_scheme(text)
        
        return {
            'project_name': project_name,
            'app_type': app_type,
            'features': features[:4] if features else ['Feature 1', 'Feature 2', 'Feature 3', 'Feature 4'],
            'sections': sections[:3] if sections else ['Main Section', 'Secondary Section'],
            'colors': color_scheme,
            'keywords': re.findall(r'\b[a-zA-Z]{4,12}\b', text)[:20]
        }
    
    def _build_content_aware_prompt(self, document_text: str, content_analysis: Dict) -> str:
        """Build prompt with extracted content"""
        # Extract key phrases and context from document
        key_phrases = self._extract_key_phrases(document_text)
        
        # Generate dynamic gradient combinations
        gradient_1 = f"linear {content_analysis['colors']['gradient_start']} → {content_analysis['colors']['gradient_end']}"
        gradient_2 = f"linear {content_analysis['colors']['secondary']} → {content_analysis['colors']['accent']}"
        gradient_3 = f"linear {content_analysis['colors']['accent']} → {content_analysis['colors']['primary']}"
        
        return f"""
ANALYZE this SPECIFIC document and create a UNIQUE, DYNAMIC UI design based ENTIRELY on the PDF content:

DOCUMENT CONTENT:
{document_text[:2000]}

EXTRACTED ANALYSIS:
- Project Name: {content_analysis['project_name']}
- App Type: {content_analysis['app_type']}
- Key Features: {', '.join(content_analysis['features'])}
- Main Sections: {', '.join(content_analysis['sections'])}
- User Personas: {', '.join(content_analysis.get('personas', []))}
- Workflows: {', '.join(content_analysis.get('workflows', []))}
- Dynamic Colors: {content_analysis['colors']['primary']}, {content_analysis['colors']['secondary']}, {content_analysis['colors']['accent']}

CRITICAL INSTRUCTIONS:
1. ONLY use content from the PDF - NO generic templates or calculator references
2. Screen names MUST match the app type and features from the document
3. Navigation flow MUST reflect the actual user workflows in the PDF
4. Component titles MUST use exact terminology from the document
5. Create screens that match the business requirements and user personas
6. Apply the EXACT color scheme from the PDF
7. Use glassmorphism, gradients, and modern effects

DYNAMIC SCREEN GENERATION RULES:
- For food delivery: home/browse → restaurant_detail → cart → checkout → tracking
- For e-commerce: products → product_detail → cart → checkout → orders
- For healthcare: dashboard → appointments → records → prescriptions
- For fintech: accounts → transactions → payments → analytics
- For education: courses → course_detail → assignments → progress

Output ONLY valid JSON with REAL PDF content:

{{
  "project_name": "{content_analysis['project_name']}",
  "summary": "{content_analysis['app_type']} with {', '.join(content_analysis['features'][:3])}",
  "screens": [
    {{
      "name": "{content_analysis['sections'][0] if content_analysis['sections'] else content_analysis['features'][0] + ' Screen'}",
      "layout": {{
        "sections": [
          {{
            "component": "gradient_banner",
            "gradient": "{gradient_1}",
            "height": 280,
            "title": "{content_analysis['project_name']}",
            "subtitle": "{content_analysis['app_type']}",
            "animation": "fade-in-up",
            "overlay": "rgba(0,0,0,0.15)",
            "blur_effect": true
          }},
          {{
            "component": "filter_chips",
            "items": {content_analysis['features']},
            "chip_style": {{
              "gradient": "{gradient_2}",
              "hover_scale": 1.05,
              "shadow": "0 4px 15px rgba(0,0,0,0.2)",
              "border_radius": 25,
              "glassmorphism": true
            }}
          }},
          {{
            "component": "section_heading",
            "title": "{content_analysis['sections'][0] if content_analysis['sections'] else content_analysis['features'][0]}",
            "background": "{content_analysis['colors']['primary']}",
            "text_color": "#FFFFFF",
            "icon": "sparkles",
            "animated": true
          }},
          {{
            "component": "event_cards",
            "grid_columns": 2,
            "cardTitle": "{content_analysis['features'][0]} Items",
            "gradient": "{gradient_2}",
            "card_style": {{
              "border_radius": 24,
              "shadow": "0 10px 40px rgba(0,0,0,0.15)",
              "hover_transform": "translateY(-8px)",
              "transition": "all 0.3s ease",
              "glassmorphism": true
            }}
          }},
          {{
            "component": "elevated_container",
            "title": "{content_analysis['sections'][1] if len(content_analysis['sections']) > 1 else content_analysis['features'][1]}",
            "gradient": "{gradient_3}",
            "elevation": 8,
            "border_radius": 20,
            "animation": "slide-in-right"
          }}
        ]
      }},
      "description": "Primary screen for {content_analysis['project_name']}",
      "navigatesTo": "{content_analysis['features'][1] if len(content_analysis['features']) > 1 else 'Details'}"
    }},
    {{
      "name": "{content_analysis['features'][1] if len(content_analysis['features']) > 1 else 'Details'} Screen",
      "layout": {{
        "sections": [
          {{
            "component": "section_heading",
            "title": "{content_analysis['features'][1] if len(content_analysis['features']) > 1 else 'Details'}",
            "background": "{content_analysis['colors']['secondary']}",
            "text_color": "#FFFFFF"
          }},
          {{
            "component": "rounded_card",
            "title": "{content_analysis['features'][1] if len(content_analysis['features']) > 1 else 'Information'} Details",
            "background": "{gradient_3}",
            "shadow": "0 15px 50px rgba(0,0,0,0.2)",
            "border_radius": 28
          }},
          {{
            "component": "action_button",
            "title": "Proceed to {content_analysis['features'][2] if len(content_analysis['features']) > 2 else 'Next'}",
            "gradient": "{gradient_1}",
            "navigatesTo": "{content_analysis['features'][2] if len(content_analysis['features']) > 2 else 'Next'}"
          }}
        ]
      }},
      "description": "Detailed view for {content_analysis['features'][1] if len(content_analysis['features']) > 1 else 'content'}",
      "navigatesTo": "{content_analysis['features'][2] if len(content_analysis['features']) > 2 else 'Completion'}"
    }},
    {{
      "name": "{content_analysis['features'][2] if len(content_analysis['features']) > 2 else 'Completion'} Screen",
      "layout": {{
        "sections": [
          {{
            "component": "section_heading",
            "title": "{content_analysis['features'][2] if len(content_analysis['features']) > 2 else 'Completion'}",
            "background": "{content_analysis['colors']['primary']}",
            "text_color": "#FFFFFF"
          }},
          {{
            "component": "status_card",
            "title": "{content_analysis['features'][2] if len(content_analysis['features']) > 2 else 'Status'} Information",
            "gradient": "{gradient_2}",
            "border_radius": 24
          }}
        ]
      }},
      "description": "Final screen for {content_analysis['features'][2] if len(content_analysis['features']) > 2 else 'process completion'}"
    }}
  ],
  "styles": {{
    "colors": {{
      "primary": "{content_analysis['colors']['primary']}",
      "secondary": "{content_analysis['colors']['secondary']}",
      "accent": "{content_analysis['colors']['accent']}",
      "background": "{content_analysis['colors']['background']}",
      "surface": "{content_analysis['colors']['surface']}",
      "gradient_1": "{gradient_1}",
      "gradient_2": "{gradient_2}",
      "gradient_3": "{gradient_3}"
    }},
    "typography": {{
      "display": "Poppins 800",
      "heading": "Poppins 700",
      "body": "Inter 500"
    }},
    "effects": {{
      "glassmorphism": true,
      "shadows": "dynamic",
      "animations": "smooth",
      "transitions": "300ms ease"
    }}
  }}
}}
"""
    
    def _enhance_with_content(self, parsed: Dict, content_analysis: Dict) -> Dict:
        """Enhance parsed JSON with extracted content"""
        if not parsed.get('project_name') or parsed['project_name'] in ['Generated UI', 'Modern App']:
            parsed['project_name'] = content_analysis['project_name']
        
        # Update colors if generic
        if parsed.get('styles', {}).get('colors', {}).get('primary') == '#FF6B6B':
            parsed['styles']['colors'] = content_analysis['colors']
        
        # Update filter items if generic
        for screen in parsed.get('screens', []):
            for section in screen.get('layout', {}).get('sections', []):
                if section.get('component') == 'filter_chips' and section.get('items'):
                    if any('Category' in item for item in section['items']):
                        section['items'] = content_analysis['features']
        
        return parsed
    
    def _get_domain_content(self, app_type: str) -> dict:
        domain_content = {
            'tech app': {
                'project_name': 'Code Analysis Platform',
                'summary': 'Advanced development tool with code analysis',
                'screen_name': 'Developer Dashboard',
                'banner_title': 'Code Analysis',
                'banner_subtitle': 'Enhance your development workflow',
                'section_title': '⚡ Code Quality',
                'filter_items': '["Analysis", "Testing", "Debugging", "Performance"]',
                'description': 'Developer dashboard with code metrics'
            },
            'healthcare app': {
                'project_name': 'HealthCare Portal',
                'summary': 'Modern healthcare app with patient management',
                'screen_name': 'Patient Dashboard',
                'banner_title': 'Welcome to HealthCare',
                'banner_subtitle': 'Your health, our priority',
                'section_title': '🏥 Recent Appointments',
                'filter_items': '["Appointments", "Medical Records", "Prescriptions", "Lab Results"]',
                'description': 'Healthcare dashboard with patient information'
            },
            'fintech app': {
                'project_name': 'Financial Dashboard',
                'summary': 'Secure fintech app with financial management',
                'screen_name': 'Account Overview',
                'banner_title': 'Your Finances',
                'banner_subtitle': 'Manage your money smartly',
                'section_title': '💰 Account Balance',
                'filter_items': '["Accounts", "Transactions", "Investments", "Cards"]',
                'description': 'Financial dashboard with account overview'
            },
            'education app': {
                'project_name': 'Learning Platform',
                'summary': 'Interactive education app with course management',
                'screen_name': 'Learning Dashboard',
                'banner_title': 'Continue Learning',
                'banner_subtitle': 'Expand your knowledge',
                'section_title': '📚 My Courses',
                'filter_items': '["Courses", "Assignments", "Grades", "Resources"]',
                'description': 'Educational platform with course tracking'
            },
            'food delivery app': {
                'project_name': 'Food Delivery Platform',
                'summary': 'Food delivery app with restaurant browsing and order tracking',
                'screen_name': 'Browse Restaurants',
                'banner_title': 'Order Food Now',
                'banner_subtitle': 'Delicious meals delivered fast',
                'section_title': '🍽️ Popular Restaurants',
                'filter_items': '["Browse", "Search", "Cart", "Orders", "Tracking", "Profile"]',
                'description': 'Restaurant browsing with menu and delivery tracking'
            },
            'e-commerce app': {
                'project_name': 'Shopping Store',
                'summary': 'Modern e-commerce app with shopping features',
                'screen_name': 'Home Screen',
                'banner_title': 'Shop Now',
                'banner_subtitle': 'Discover amazing products',
                'section_title': '🔥 Trending Products',
                'filter_items': '["Electronics", "Fashion", "Home", "Sports"]',
                'description': 'E-commerce home screen with products'
            }
        }
        
        return domain_content.get(app_type, domain_content['tech app'])
    
    def _extract_project_title(self, text: str) -> str:
        """Extract actual project title from document"""
        import re
        import time
        
        lines = [line.strip() for line in text.split('\n')[:20] if line.strip()]
        
        # Add timestamp for uniqueness
        timestamp = str(int(time.time()))[-4:]
        
        # Look for specific PRD patterns first
        prd_patterns = [
            r'Product\s+Name\s*:?\s*([A-Za-z\s]+Agent|[A-Za-z\s]+Tool|[A-Za-z\s]+System)',
            r'Project\s*:?\s*([A-Za-z\s]+Agent|[A-Za-z\s]+Tool|[A-Za-z\s]+System)',
            r'([A-Za-z\s]*Unit\s+Test[A-Za-z\s]*Agent)',
            r'([A-Za-z\s]*Test[A-Za-z\s]*Agent)',
            r'([A-Za-z\s]*Agent[A-Za-z\s]*)',
        ]
        
        for pattern in prd_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return matches[0].strip().title()
        
        # Look for title patterns in lines
        for line in lines:
            # Skip URLs, emails, common headers
            if any(skip in line.lower() for skip in ['http', 'www', '@', 'page', 'document', 'pdf', 'docx']):
                continue
                
            # Check for title-like patterns
            if 5 <= len(line) <= 60:
                # Title case or ALL CAPS
                if re.match(r'^[A-Z][a-zA-Z\s\-_&0-9]+$', line) or line.isupper():
                    return line.title()
                # Numbered titles
                if re.match(r'^\d+\.\s*([A-Z][a-zA-Z\s\-_&]+)$', line):
                    title = re.match(r'^\d+\.\s*([A-Z][a-zA-Z\s\-_&]+)$', line).group(1)
                    return title
        
        # Extract keywords for dynamic naming
        keywords = re.findall(r'\b[A-Z][a-z]{3,12}\b', text)
        if keywords:
            return f"{keywords[0]} {keywords[1] if len(keywords) > 1 else 'Project'}"
        
        # Fallback with timestamp
        # Try to extract from content patterns
        content_titles = re.findall(r'(?:Project|System|Application|Platform|Tool|Agent)\s*:?\s*([A-Z][A-Za-z\s]{5,30})', text, re.IGNORECASE)
        if content_titles:
            return content_titles[0].strip()
        
        return "Dynamic Project"

    def _safe_parse_json(self, raw: str, document_text: str = "") -> Dict[str, Any]:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"```$", "", cleaned)
        cleaned = re.sub(r"^```\s*", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Use content analysis for fallback instead of generic templates
            if document_text:
                content_analysis = self._analyze_document_content(document_text)
                return self._create_fallback_design(content_analysis)
            else:
                # Last resort fallback
                return self._create_minimal_fallback()
    
    def _create_fallback_design(self, content_analysis: Dict) -> Dict[str, Any]:
        """Create design based on content analysis when LLM fails"""
        return {
            "project_name": content_analysis['project_name'],
            "summary": f"Modern {content_analysis['app_type']} with {', '.join(content_analysis['features'][:2])} features",
            "screens": self._generate_multiple_screens(content_analysis),
            "styles": {
                "colors": content_analysis['colors'],
                "typography": {
                    "display": "Poppins 800",
                    "heading": "Poppins 700",
                    "body": "Inter 500"
                },
                "components": ["gradient_banner", "filter_chips", "section_heading", "event_cards", "elevated_container", "rounded_card", "bottom_sheet"]
            }
        }
    
    def _create_minimal_fallback(self) -> Dict[str, Any]:
        """Minimal fallback when no document text available"""
        return {
            "project_name": "Modern Application",
            "summary": "Dynamic application with modern UI components",
            "screens": [
                {
                    "name": "Main Screen",
                    "layout": {
                        "sections": [
                            {
                                "component": "gradient_banner",
                                "gradient": "linear #6366F1 → #8B5CF6",
                                "height": 280,
                                "title": "Welcome",
                                "subtitle": "Modern application interface"
                            },
                            {
                                "component": "section_heading",
                                "title": "Features",
                                "background": "#6366F1",
                                "text_color": "#FFFFFF"
                            }
                        ]
                    },
                    "description": "Main application screen"
                }
            ],
            "styles": {
                "colors": {
                    "primary": "#6366F1",
                    "secondary": "#8B5CF6",
                    "accent": "#06B6D4"
                },
                "typography": {
                    "display": "Poppins 800",
                    "heading": "Poppins 700",
                    "body": "Inter 500"
                }
            }
        }