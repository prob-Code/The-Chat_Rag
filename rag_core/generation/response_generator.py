"""
Reflection-Based Response Generator
"""
from typing import Optional, Dict, Any
from langchain_core.prompts import PromptTemplate


class ReflectionResponseGenerator:
    """Generate compassionate, reflection-based responses"""
    
    def __init__(self, llm=None, config=None):
        from ..config import default_config, get_llm
        self.config = config or default_config
        
        if llm is None:
            self.llm = get_llm(self.config)
        else:
            self.llm = llm
        
        self.system_prompt = """
You are a compassionate spiritual guide drawing from the wisdom of sacred traditions.

Your Purpose:
- Provide comfort, clarity, and gentle guidance
- Present wisdom from the retrieved spiritual texts
- Encourage self-reflection, NOT direct advice
- Acknowledge the complexity of human experience
- Honor multiple perspectives without favoring one

Your Approach:
1. EMPATHY FIRST: Acknowledge the questioner's feelings without judgment
2. WISDOM SHARING: Present relevant insights from the retrieved context
3. CONNECTIONS: Highlight universal themes across traditions (if applicable)
4. REFLECTION: Offer questions for contemplation, not commands
5. HOPE: Close with gentle encouragement

Important Guidelines:
- Never prescribe specific actions ("You must...", "You should...")
- Use invitational language ("Consider...", "One might reflect...", "The texts suggest...")
- Avoid religious jargon without explanation
- Be inclusive - the person may be from any faith or none
- For sensitive topics (depression, grief, crisis), always encourage professional support
- Keep responses warm, human, and accessible

Response Structure:
- Opening: Acknowledge their situation (2-3 sentences)
- Body: Share relevant wisdom (2-3 paragraphs)
- Reflection: Questions for contemplation (2-3 questions)
- Closing: Encouragement (1-2 sentences)
"""
        
        self.response_prompt = PromptTemplate(
            input_variables=["system_prompt", "context", "query", "keywords"],
            template="""
{system_prompt}

=== RETRIEVED WISDOM ===
{context}

=== KEYWORDS IDENTIFIED ===
Specific concepts: {keywords}

=== QUESTION ===
{query}

Generate a response following the guidelines above. Be compassionate and thoughtful.
"""
        )
        
        # Simplified prompt for emotional support
        self.support_prompt = PromptTemplate(
            input_variables=["context", "query"],
            template="""
You are a deeply compassionate spiritual friend. Someone is struggling and seeking wisdom.

Your role:
- Start with empathy — acknowledge their pain without judgment
- Use warm, gentle, encouraging language
- Share relevant Gita wisdom in simple, relatable terms
- Remind them difficult times are temporary
- Offer small, actionable reflections they can consider
- End with hope and strength

Wisdom from Sacred Texts:
{context}

Their Question:
{query}

Respond with deep compassion. Speak as a caring friend who truly understands their pain.
Make them feel heard, valued, and capable of overcoming this phase.
Keep the tone warm, supportive, and never preachy.
"""
        )
    
    def generate(self, query: str, context: str, 
                 keywords: Optional[Dict[str, Any]] = None,
                 mode: str = "reflection") -> str:
        """
        Generate a reflection-based response.
        
        Args:
            query: User's question
            context: Structured context from ContextBuilder
            keywords: Extracted keywords (optional)
            mode: "reflection" (default) or "support" (for emotional queries)
            
        Returns:
            Generated response
        """
        if mode == "support":
            return self._generate_support(query, context)
        
        # Format keywords
        if keywords:
            keywords_str = ", ".join(
                keywords.get("low_level_keywords", []) + 
                keywords.get("high_level_keywords", [])
            )
        else:
            keywords_str = "Not extracted"
        
        # Build prompt
        prompt = self.response_prompt.format(
            system_prompt=self.system_prompt,
            context=context,
            query=query,
            keywords=keywords_str
        )
        
        # Generate
        response = self.llm.invoke(prompt)
        return response.content
    
    def _generate_support(self, query: str, context: str) -> str:
        """Generate emotionally supportive response"""
        prompt = self.support_prompt.format(
            context=context,
            query=query
        )
        
        response = self.llm.invoke(prompt)
        return response.content
    
    def detect_emotional_query(self, query: str) -> bool:
        """
        Detect if query suggests emotional distress.
        
        Args:
            query: User's question
            
        Returns:
            True if emotional/support mode should be used
        """
        emotional_indicators = [
            "sad", "depressed", "depression", "anxious", "anxiety",
            "worried", "scared", "afraid", "lost", "hopeless",
            "alone", "lonely", "grief", "grieving", "suffering",
            "pain", "hurt", "struggling", "confused", "overwhelmed",
            "stressed", "stress", "cry", "crying", "help me",
            "don't know what to do", "give up", "desperate"
        ]
        
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in emotional_indicators)
    
    def generate_auto(self, query: str, context: str,
                      keywords: Optional[Dict[str, Any]] = None) -> str:
        """
        Automatically select mode and generate response.
        
        Args:
            query: User's question
            context: Structured context
            keywords: Extracted keywords
            
        Returns:
            Generated response
        """
        if self.detect_emotional_query(query):
            return self.generate(query, context, keywords, mode="support")
        else:
            return self.generate(query, context, keywords, mode="reflection")
