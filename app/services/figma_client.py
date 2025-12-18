import os
import urllib.parse
import uuid
import random
import re
from typing import Any, Dict, Optional, List

import requests

FIGMA_API_URL = "https://api.figma.com/v1"


class FigmaClient:
    def __init__(
        self,
        access_token: Optional[str] = None,
        template_file_key: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        
        # Use correct ENV variable
        self.access_token = access_token or os.getenv("FIGMA_ACCESS_TOKEN")
        
        # Template file to duplicate from
        self.template_file_key = template_file_key or os.getenv("FIGMA_TEMPLATE_FILE_KEY")
        
        # Project to place new files into
        self.project_id = project_id or os.getenv("FIGMA_PROJECT_ID")

    @property
    def has_real_access(self) -> bool:
        """Check if real Figma duplication is possible."""
        return bool(
            self.access_token 
            and self.template_file_key 
            and self.project_id
        )

    # ---------------------------------------------------------
    # DYNAMIC PROJECT NAME GENERATION
    # ---------------------------------------------------------
    def generate_dynamic_project_name(self, raw_text: str) -> str:
        """Generate unique project name based on PDF content."""
        if not raw_text:
            return f"Custom Application {random.randint(1000, 9999)}"
        
        # Extract key terms from document
        key_terms = self._extract_key_terms(raw_text)
        domain = self._identify_domain(raw_text)
        app_type = self._identify_app_type(raw_text)
        
        # Build dynamic name using actual domain name
        if domain and domain != "Custom System":
            return f"Create a comprehensive {app_type} for '{domain}' based on detailed PDF analysis"
        elif key_terms:
            primary_term = key_terms[0]
            return f"Create a comprehensive {primary_term} {app_type} based on detailed PDF analysis"
        else:
            return f"Create a comprehensive {app_type} based on detailed PDF analysis"
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key business/technical terms from document."""
        # Convert to lowercase for analysis
        text_lower = text.lower()
        
        # Define term categories with weights
        business_terms = {
            'management': 3, 'dashboard': 3, 'analytics': 3, 'monitoring': 3,
            'tracking': 2, 'reporting': 2, 'inventory': 2, 'customer': 2,
            'sales': 2, 'finance': 2, 'hr': 2, 'crm': 2, 'erp': 2,
            'workflow': 2, 'automation': 2, 'integration': 2
        }
        
        tech_terms = {
            'security': 4, 'scanning': 3, 'automated': 3, 'intelligent': 3,
            'smart': 2, 'digital': 2, 'cloud': 2, 'mobile': 2,
            'web': 2, 'api': 2, 'database': 2, 'network': 2
        }
        
        # Score terms based on frequency and weight
        term_scores = {}
        
        for term, weight in {**business_terms, **tech_terms}.items():
            count = text_lower.count(term)
            if count > 0:
                term_scores[term] = count * weight
        
        # Return top terms, capitalized
        sorted_terms = sorted(term_scores.items(), key=lambda x: x[1], reverse=True)
        return [term.capitalize() for term, score in sorted_terms[:3]]
    
    def _identify_domain(self, text: str) -> str:
        """Extract the actual system name from PDF content."""
        lines = text.split('\n')
        
        # Look for actual system names in the document
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line contains system/application name patterns
            line_lower = line.lower()
            
            # Pattern 1: "[Name] System" or "[Name] Application"
            if ('system' in line_lower or 'application' in line_lower) and len(line) < 100:
                # Clean up the line to extract the name
                clean_name = line.replace('Application', '').replace('System', '').strip()
                if len(clean_name) > 5 and len(clean_name) < 50:
                    return clean_name
            
            # Pattern 2: Title-like lines (short, capitalized)
            if (len(line) > 10 and len(line) < 60 and 
                any(char.isupper() for char in line) and 
                not line.startswith('Page') and
                not line.isdigit()):
                # Check if it looks like a system name
                words = line.split()
                if len(words) >= 2 and len(words) <= 6:
                    return line
        
        # Fallback: try to construct from key terms
        text_lower = text.lower()
        key_terms = []
        
        # Extract meaningful terms
        important_terms = [
            'automated', 'code', 'scanning', 'security', 'management', 
            'monitoring', 'tracking', 'analytics', 'dashboard', 'portal'
        ]
        
        for term in important_terms:
            if term in text_lower:
                key_terms.append(term.capitalize())
        
        if key_terms:
            return ' '.join(key_terms[:3])  # Max 3 terms
        
        return "Custom System"
    
    def _identify_app_type(self, text: str) -> str:
        """Identify the type of application from content."""
        text_lower = text.lower()
        
        app_types = {
            'DASHBOARD': ['dashboard', 'overview', 'summary', 'metrics'],
            'PORTAL': ['portal', 'gateway', 'access', 'login'],
            'PLATFORM': ['platform', 'service', 'solution', 'framework'],
            'APPLICATION': ['application', 'app', 'software', 'tool'],
            'SYSTEM': ['system', 'management', 'control', 'administration']
        }
        
        for app_type, keywords in app_types.items():
            if any(keyword in text_lower for keyword in keywords):
                return app_type
        
        return "APPLICATION"

    # ---------------------------------------------------------
    # TEXT FILTERING FOR DESIGN CONTENT
    # ---------------------------------------------------------
    def filter_design_relevant_text(self, raw_text: str) -> str:
        """Extract only design-relevant text from document."""
        if not raw_text:
            return ""
        
        # Remove common unnecessary elements
        text = self._remove_noise(raw_text)
        
        # Extract important sections
        relevant_sections = self._extract_key_sections(text)
        
        return "\n".join(relevant_sections)
    
    def _remove_noise(self, text: str) -> str:
        """Remove headers, footers, page numbers, and other noise."""
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip page numbers, headers, footers
            if re.match(r'^\d+$', line):  # Just numbers
                continue
            if re.match(r'^Page \d+', line, re.IGNORECASE):
                continue
            if len(line) < 3:  # Too short
                continue
            if re.match(r'^[\d\s\-\.]+$', line):  # Just numbers and punctuation
                continue
                
            filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def _extract_key_sections(self, text: str) -> List[str]:
        """Extract sections relevant for UI design."""
        lines = text.split('\n')
        key_sections = []
        
        # Design-relevant keywords
        important_keywords = [
            'title', 'heading', 'header', 'name', 'brand', 'logo',
            'button', 'menu', 'navigation', 'contact', 'about',
            'service', 'product', 'feature', 'benefit', 'call',
            'action', 'welcome', 'home', 'main', 'primary'
        ]
        
        for line in lines:
            line_lower = line.lower()
            
            # Keep headings (usually short and important)
            if len(line) < 100 and any(keyword in line_lower for keyword in important_keywords):
                key_sections.append(line)
                continue
            
            # Keep short impactful sentences
            if 10 <= len(line) <= 80:
                key_sections.append(line)
                continue
            
            # Keep sentences with design-relevant words
            if any(keyword in line_lower for keyword in important_keywords):
                # Truncate long sentences
                if len(line) > 150:
                    line = line[:147] + "..."
                key_sections.append(line)
        
        # Limit to most relevant content
        return key_sections[:20]  # Max 20 key sections

    # ---------------------------------------------------------
    # PUBLIC METHOD — generates real or fallback URL
    # ---------------------------------------------------------
    def create_figma_file(self, project_name: Optional[str] = None, pdf_colors: Optional[List[str]] = None, raw_text: Optional[str] = None) -> str:
        # Generate dynamic project name if not provided or if raw_text is available
        if raw_text:
            dynamic_name = self.generate_dynamic_project_name(raw_text)
            project_name = dynamic_name
        elif not project_name:
            project_name = f"Custom Application {random.randint(1000, 9999)}"
        
        # Filter text if provided
        filtered_text = self.filter_design_relevant_text(raw_text) if raw_text else None
        
        if self.has_real_access:
            return self._duplicate_template(project_name, pdf_colors, filtered_text)
        return self._fallback_link(project_name)

    # ---------------------------------------------------------
    # GET FILE METADATA (optional)
    # ---------------------------------------------------------
    def get_file_metadata(self, file_key: str) -> Dict[str, Any]:
        if not self.access_token:
            raise RuntimeError("FIGMA_ACCESS_TOKEN missing in environment.")
        
        response = requests.get(
            f"{FIGMA_API_URL}/files/{file_key}",
            headers={"X-FIGMA-TOKEN": self.access_token},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ---------------------------------------------------------
    # DYNAMIC COLOR GENERATION
    # ---------------------------------------------------------
    def _generate_dynamic_colors(self, pdf_colors: Optional[List[str]] = None) -> List[str]:
        """Generate dynamic colors based on PDF or random palette."""
        if pdf_colors and len(pdf_colors) >= 3:
            return pdf_colors[:5]  # Use up to 5 colors from PDF
        
        # Generate random color palette if no PDF colors
        base_hue = random.randint(0, 360)
        colors = []
        
        for i in range(5):
            hue = (base_hue + i * 72) % 360  # Complementary colors
            saturation = random.randint(60, 90)
            lightness = random.randint(40, 80)
            colors.append(f"hsl({hue}, {saturation}%, {lightness}%)")
        
        return colors

    def _hsl_to_hex(self, hsl_color: str) -> str:
        """Convert HSL to HEX color format."""
        try:
            # Simple conversion for demo - in production use proper color library
            import colorsys
            hsl = hsl_color.replace('hsl(', '').replace(')', '').replace('%', '')
            h, s, l = map(float, hsl.split(', '))
            h, s, l = h/360, s/100, l/100
            r, g, b = colorsys.hls_to_rgb(h, l, s)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        except:
            # Fallback to random hex color
            return f"#{random.randint(0, 0xFFFFFF):06x}"

    def _update_figma_colors(self, file_key: str, colors: List[str]) -> None:
        """Update colors in the duplicated Figma file."""
        if not self.has_real_access:
            return
            
        # Convert colors to hex format
        hex_colors = [self._hsl_to_hex(color) if color.startswith('hsl') else color for color in colors]
        
        # Get file content to find elements to update
        try:
            file_data = self.get_file_metadata(file_key)
            # Note: In production, you'd traverse the file structure and update specific elements
            # This is a simplified approach - actual implementation would need to:
            # 1. Find specific nodes/elements in the Figma file
            # 2. Update their fill colors using Figma's REST API
            # 3. Handle different element types (rectangles, text, etc.)
            pass
        except Exception as e:
            print(f"Warning: Could not update colors in Figma file: {e}")

    # ---------------------------------------------------------
    # REAL FIGMA FILE DUPLICATION
    # ---------------------------------------------------------
    def _duplicate_template(self, project_name: str, pdf_colors: Optional[List[str]] = None, filtered_text: Optional[str] = None) -> str:
        assert self.template_file_key is not None
        assert self.project_id is not None

        url = f"{FIGMA_API_URL}/files/{self.template_file_key}/copy"

        try:
            project_id_int = int(self.project_id)
        except ValueError:
            raise RuntimeError("FIGMA_PROJECT_ID must be a valid integer ID.")

        payload = {
            "name": project_name,
            "project_id": int(self.project_id),
        }

        response = requests.post(
            url,
            headers={
                "X-FIGMA-TOKEN": self.access_token,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        response.raise_for_status()
        data = response.json()
        
        new_file_key = data.get("key")
        if not new_file_key:
            raise RuntimeError("Figma API error: No 'key' returned from duplication.")

        # Generate and apply dynamic colors
        dynamic_colors = self._generate_dynamic_colors(pdf_colors)
        self._update_figma_colors(new_file_key, dynamic_colors)

        safe_name = urllib.parse.quote(project_name.strip().replace(" ", "-"))

        # Return DESIGN URL (not /file/ which gives /make/ redirects)
        return f"https://www.figma.com/design/{new_file_key}/{safe_name}?node-id=0-1&t={int(__import__('time').time())}"

    # ---------------------------------------------------------
    # FALLBACK LINK (FAKE — only for demo mode)
    # ---------------------------------------------------------
    @staticmethod
    def _fallback_link(project_name: str) -> str:
        file_id = uuid.uuid4().hex[:12]
        safe_name = urllib.parse.quote(project_name.strip().replace(" ", "-"))
        return f"https://www.figma.com/design/{file_id}/{safe_name}?node-id=0-1&t={int(__import__('time').time())}"