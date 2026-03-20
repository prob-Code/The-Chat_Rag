"""
Dual-Level Keyword Extraction
"""
import json
import re
from typing import Dict, List, Optional
from langchain_core.prompts import PromptTemplate


class DualKeywordExtractor:
    """Extract low-level and high-level keywords from queries"""
    
    def __init__(self, llm=None, config=None):
        from ..config import default_config, get_llm
        self.config = config or default_config
        
        if llm is None:
            self.llm = get_llm(self.config, temperature=0.3)
        else:
            self.llm = llm
        
        self.extraction_prompt = PromptTemplate(
            input_variables=["query"],
            template="""
Analyze the following question and extract keywords at two levels.

Question: {query}

Extract:
1. LOW-LEVEL KEYWORDS: Specific entities, names, concepts directly mentioned
   - Proper nouns (Krishna, Arjuna, Buddha, Jesus)
   - Specific concepts (karma, dharma, salvation, mindfulness)
   - Concrete terms from the question

2. HIGH-LEVEL KEYWORDS: Abstract themes, philosophical concepts implied
   - Life themes (purpose, suffering, death, love, fear)
   - Philosophical concepts (meaning, ethics, duty, liberation)
   - Emotional states (anxiety, peace, confusion, hope)
   - Universal human experiences

Output ONLY valid JSON:
{{
    "low_level_keywords": ["keyword1", "keyword2"],
    "high_level_keywords": ["theme1", "theme2"]
}}

Provide 2-5 keywords at each level. Output ONLY the JSON.
"""
        )
    
    def extract(self, query: str) -> Dict[str, List[str]]:
        """
        Extract low and high level keywords from a query.
        
        Args:
            query: User's question
            
        Returns:
            Dictionary with low_level_keywords and high_level_keywords
        """
        try:
            response = self.llm.invoke(
                self.extraction_prompt.format(query=query)
            )
            
            content = response.content.strip()
            content = self._clean_json_response(content)
            
            result = json.loads(content)
            
            return {
                "low_level_keywords": result.get("low_level_keywords", []),
                "high_level_keywords": result.get("high_level_keywords", [])
            }
            
        except Exception as e:
            print(f"Keyword extraction error: {e}")
            # Fallback: extract simple keywords from query
            return self._fallback_extraction(query)
    
    def _clean_json_response(self, content: str) -> str:
        """Clean LLM response to valid JSON"""
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return match.group()
        
        return content
    
    def _fallback_extraction(self, query: str) -> Dict[str, List[str]]:
        """Simple keyword extraction as fallback"""
        # Remove common words
        stop_words = {
            "i", "me", "my", "myself", "we", "our", "you", "your", "he", "she",
            "it", "they", "what", "which", "who", "whom", "this", "that", "these",
            "those", "am", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "a", "an", "the",
            "and", "but", "if", "or", "because", "as", "until", "while", "of",
            "at", "by", "for", "with", "about", "against", "between", "into",
            "through", "during", "before", "after", "above", "below", "to",
            "from", "up", "down", "in", "out", "on", "off", "over", "under",
            "again", "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "each", "few", "more", "most", "other", "some",
            "such", "no", "nor", "not", "only", "own", "same", "so", "than",
            "too", "very", "just", "don", "now"
        }
        
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return {
            "low_level_keywords": keywords[:5],
            "high_level_keywords": []
        }
