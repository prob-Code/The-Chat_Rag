"""
Entity and Relation Extraction using LLM
"""
import json
import re
from typing import List, Dict, Any, Optional
from langchain_core.prompts import PromptTemplate


class EntityRelationExtractor:
    """Extract entities and relationships from religious texts using LLM"""
    
    def __init__(self, llm=None, config=None):
        from ..config import default_config, get_llm
        self.config = config or default_config
        
        if llm is None:
            self.llm = get_llm(self.config, temperature=0.3)
        else:
            self.llm = llm
        
        self.extraction_prompt = PromptTemplate(
            input_variables=["chunk", "source_faith", "entity_types", "relationship_types"],
            template="""
You are an expert at extracting structured knowledge from religious and spiritual texts.

Extract entities and relationships from the following text.

Source Text (from {source_faith}):
{chunk}

Entity Types to look for: {entity_types}
Relationship Types to look for: {relationship_types}

Instructions:
1. Identify all significant entities (concepts, people, teachings, virtues, practices, deities)
2. Identify relationships between entities
3. Provide brief descriptions
4. Include the exact source text where entity/relation appears

Output ONLY valid JSON in this exact format:
{{
    "entities": [
        {{
            "name": "entity name",
            "type": "CONCEPT|PERSON|TEACHING|VIRTUE|PRACTICE|DEITY|SCRIPTURE|PLACE",
            "description": "brief description of the entity",
            "source_text": "exact quote from text"
        }}
    ],
    "relationships": [
        {{
            "source": "source entity name",
            "target": "target entity name", 
            "type": "TEACHES|EMBODIES|LEADS_TO|OPPOSES|PART_OF|MENTIONED_IN|GUIDES|EXPLAINS",
            "description": "brief description of relationship",
            "source_text": "exact quote showing this relationship"
        }}
    ]
}}

If no entities or relationships found, return empty arrays.
Output ONLY the JSON, no other text.
"""
        )
    
    def extract(self, chunk: str, source_faith: str = "Bhagavad Gita", chunk_id: str = "") -> Dict[str, Any]:
        """
        Extract entities and relationships from a text chunk.
        
        Args:
            chunk: The text to extract from
            source_faith: Name of the source text/faith tradition
            chunk_id: Identifier for the chunk
            
        Returns:
            Dictionary with entities and relationships
        """
        try:
            # Call LLM
            response = self.llm.invoke(
                self.extraction_prompt.format(
                    chunk=chunk,
                    source_faith=source_faith,
                    entity_types=", ".join(self.config.entity_types),
                    relationship_types=", ".join(self.config.relationship_types)
                )
            )
            
            # Parse JSON response
            content = response.content.strip()
            
            # Clean up response if needed
            content = self._clean_json_response(content)
            
            result = json.loads(content)
            
            # Add metadata
            for entity in result.get("entities", []):
                entity["source_faith"] = source_faith
                entity["chunk_id"] = chunk_id
            
            for relation in result.get("relationships", []):
                relation["source_faith"] = source_faith
                relation["chunk_id"] = chunk_id
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return {"entities": [], "relationships": []}
        except Exception as e:
            print(f"Extraction error: {e}")
            return {"entities": [], "relationships": []}
    
    def _clean_json_response(self, content: str) -> str:
        """Clean LLM response to valid JSON"""
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        
        # Find JSON object
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return match.group()
        
        return content
    
    def extract_batch(self, chunks: List[str], source_faith: str = "Bhagavad Gita") -> List[Dict[str, Any]]:
        """
        Extract from multiple chunks.
        
        Args:
            chunks: List of text chunks
            source_faith: Name of the source text
            
        Returns:
            List of extraction results
        """
        results = []
        for i, chunk in enumerate(chunks):
            print(f"Extracting from chunk {i+1}/{len(chunks)}...")
            result = self.extract(chunk, source_faith, chunk_id=f"{source_faith}_{i}")
            results.append(result)
        return results
    
    def merge_extractions(self, extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple extraction results into one.
        
        Args:
            extractions: List of extraction dictionaries
            
        Returns:
            Merged dictionary with all entities and relationships
        """
        all_entities = []
        all_relationships = []
        
        for extraction in extractions:
            all_entities.extend(extraction.get("entities", []))
            all_relationships.extend(extraction.get("relationships", []))
        
        return {
            "entities": all_entities,
            "relationships": all_relationships
        }
