"""
Response Validator — Evaluation et amélioration des réponses des agents
"""
import json
import re
from typing import Dict, Tuple, Optional, Any
import asyncio
import litellm


class ResponseValidator:
    """Valide et score les réponses des agents"""

    def __init__(self, model: str = "claude-opus-4-7"):
        self.model = model
        self.validation_cache: Dict[str, float] = {}

    async def validate_response(
        self,
        prompt: str,
        response: str,
        agent_name: str,
        expected_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Valide une réponse et retourne un score de confiance"""
        issues = []
        suggestions = []

        # 1. Format Validation
        format_ok = self._validate_format(response, expected_format, issues, suggestions)

        # 2. Content Validation
        cache_key = f"{prompt}:{response}"
        if cache_key in self.validation_cache:
            content_score = self.validation_cache[cache_key]
        else:
            content_score = await self._validate_content(
                prompt, response, agent_name, issues, suggestions
            )
            self.validation_cache[cache_key] = content_score

        content_ok = content_score >= 0.6

        # 3. Confidence Scoring
        confidence = self._compute_confidence(format_ok, content_ok, content_score)

        return {
            "is_valid": format_ok and content_ok,
            "confidence": confidence,
            "issues": issues,
            "suggestions": suggestions,
            "format_ok": format_ok,
            "content_ok": content_ok,
            "content_score": content_score,
            "should_retry": confidence < 0.5,
        }

    def _validate_format(
        self, response: str, expected_format: Optional[str], issues: list, suggestions: list
    ) -> bool:
        """Valide que la réponse est bien formée"""
        if not response or not isinstance(response, str):
            issues.append("Response is not a string or is empty")
            return False

        if len(response.strip()) < 10:
            issues.append("Response is too short")
            suggestions.append("Provide a more detailed response")
            return False

        if response.strip() in ("", "{}", "null", "[]"):
            issues.append("Response is empty or placeholder")
            return False

        if expected_format == "json":
            try:
                json.loads(response)
            except json.JSONDecodeError:
                issues.append("Response is not valid JSON")
                suggestions.append("Ensure response is properly formatted JSON")
                return False

        return True

    async def _validate_content(
        self,
        prompt: str,
        response: str,
        agent_name: str,
        issues: list,
        suggestions: list,
    ) -> float:
        """Utilise un LLM pour valider si la réponse est pertinente"""
        validation_prompt = f"""You are a quality assurance expert. Evaluate this response on a scale of 0-1.

User Query: "{prompt}"
Agent: {agent_name}
Response: "{response[:500]}"

Evaluate:
1. Does it answer the user's question?
2. Is the information accurate and relevant?
3. Is it helpful and actionable?

Respond with ONLY a number between 0 and 1."""

        try:
            result = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": validation_prompt}],
                max_tokens=10,
                temperature=0.0,
                timeout=5,
            )
            score_str = result.choices[0].message.content.strip()
            score = float(re.search(r"0\.\d+|1\.0?|[0-1]", score_str).group(0))
            return min(1.0, max(0.0, score))
        except Exception as e:
            issues.append(f"Validation check failed: {str(e)}")
            return 0.5

    def _compute_confidence(self, format_ok: bool, content_ok: bool, content_score: float) -> float:
        """Calcule le score de confiance final"""
        if not format_ok:
            return 0.2
        if not content_ok:
            return 0.4 + (content_score * 0.2)
        return 0.8 + (content_score * 0.2)

    async def validate_and_improve(
        self,
        prompt: str,
        initial_response: str,
        agent_name: str,
        max_retries: int = 2,
    ) -> Tuple[str, Dict[str, Any]]:
        """Valide une réponse et la réécrit si nécessaire"""
        current_response = initial_response
        validation_result = await self.validate_response(
            prompt, current_response, agent_name
        )

        retries = 0
        while validation_result["should_retry"] and retries < max_retries:
            improvement_prompt = f"""The initial response to this user query was not satisfactory.

User Query: "{prompt}"
Previous Response: "{current_response[:300]}"
Issues: {', '.join(validation_result['issues'])}
Suggestions: {', '.join(validation_result['suggestions'])}

Please provide an IMPROVED response that addresses these issues."""

            try:
                result = await litellm.acompletion(
                    model=self.model,
                    messages=[{"role": "user", "content": improvement_prompt}],
                    max_tokens=1024,
                    temperature=0.2,
                    timeout=10,
                )
                current_response = result.choices[0].message.content
                validation_result = await self.validate_response(
                    prompt, current_response, agent_name
                )
                retries += 1
            except Exception as e:
                break

        validation_result["retries_used"] = retries
        return current_response, validation_result
