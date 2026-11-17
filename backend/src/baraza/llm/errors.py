"""Erreurs LLM lisibles (issue #81). Le reste du pipeline n'attrape que ces types."""


class LLMError(Exception):
    """Base. `user_message` est affichable à l'utilisateur, jamais de contenu de prompt."""

    code = "llm_error"
    user_message = "Le modèle de langage a rencontré une erreur."

    def __init__(self, detail: str | None = None):
        super().__init__(detail or self.user_message)
        self.detail = detail


class ModelUnreachableError(LLMError):
    code = "model_unreachable"
    user_message = "Le modèle de langage est injoignable."


class LLMTimeoutError(LLMError):
    code = "timeout"
    user_message = "Le modèle de langage a mis trop de temps à répondre."


class LLMServerError(LLMError):
    code = "server_error"
    user_message = "Le fournisseur du modèle a renvoyé une erreur serveur."


class ContextTooLongError(LLMError):
    code = "context_too_long"
    user_message = "La transcription est trop longue pour ce modèle."


class QuotaExceededError(LLMError):
    code = "quota_exceeded"
    user_message = "Le quota ou la limite de débit du fournisseur est dépassé."


class LLMAuthError(LLMError):
    code = "auth_error"
    user_message = "Authentification refusée par le fournisseur du modèle."


class OutputTruncatedError(LLMError):
    code = "output_truncated"
    user_message = "La réponse du modèle a été tronquée (max tokens trop bas)."


class InvalidModelOutputError(LLMError):
    """Sortie non conforme au schéma après réparation (issue #82)."""

    code = "invalid_model_output"
    user_message = "Le modèle n'a pas produit un compte rendu valide."


class ResponseFormatUnsupportedError(LLMError):
    """Le fournisseur refuse le response_format demandé (issue #82)."""

    code = "response_format_unsupported"
    user_message = "Ce modèle ne supporte pas le format de sortie structuré demandé."
