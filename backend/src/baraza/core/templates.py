"""Minutes templates: the same minutes structure, a different emphasis per kind of meeting.

A template never changes the JSON schema. It adds instructions to the prompt about what the
topics should be and what to look for, so the anti-invention rules stay identical for all.
"""

from dataclasses import dataclass

DEFAULT_TEMPLATE = "standard"


@dataclass(frozen=True)
class Template:
    id: str
    name: dict[str, str]
    description: dict[str, str]
    instructions: dict[str, str]


TEMPLATES: dict[str, Template] = {
    t.id: t
    for t in (
        Template(
            id="standard",
            name={"en": "Standard", "fr": "Standard"},
            description={
                "en": "Summary, decisions and actions.",
                "fr": "Résumé, décisions et actions.",
            },
            instructions={"en": "", "fr": ""},
        ),
        Template(
            id="team_meeting",
            name={"en": "Team meeting", "fr": "Réunion d'équipe"},
            description={
                "en": "Progress by topic, blockers, who does what next.",
                "fr": "Avancement par sujet, blocages, qui fait quoi ensuite.",
            },
            instructions={
                "en": (
                    "Template: team meeting. Make one topic per subject discussed, with its "
                    "progress. Put blockers and risks in `open_points`. Be thorough with "
                    "`actions`: every task someone commits to, with its owner and due date "
                    "only when they are said."
                ),
                "fr": (
                    "Modèle : réunion d'équipe. Fais un sujet par thème discuté, avec son "
                    "avancement. Mets les blocages et les risques dans `open_points`. Sois "
                    "exhaustif sur `actions` : chaque tâche prise en charge, avec son "
                    "responsable et son échéance uniquement s'ils sont dits."
                ),
            },
        ),
        Template(
            id="committee",
            name={"en": "Committee", "fr": "Comité"},
            description={
                "en": "Agenda items, positions taken, decisions and follow-ups.",
                "fr": "Points à l'ordre du jour, positions, décisions et suites.",
            },
            instructions={
                "en": (
                    "Template: committee meeting. Make one topic per agenda item, in the order "
                    "discussed, and summarise the positions expressed. Record each decision "
                    "exactly as stated, including whether it was agreed or only proposed. "
                    "Put what is postponed in `open_points`."
                ),
                "fr": (
                    "Modèle : comité. Fais un sujet par point à l'ordre du jour, dans l'ordre "
                    "de la discussion, et résume les positions exprimées. Note chaque décision "
                    "telle qu'énoncée, en précisant si elle est adoptée ou seulement proposée. "
                    "Mets ce qui est reporté dans `open_points`."
                ),
            },
        ),
        Template(
            id="general_assembly",
            name={"en": "General assembly", "fr": "Assemblée générale"},
            description={
                "en": "Resolutions, votes and formal decisions.",
                "fr": "Résolutions, votes et décisions formelles.",
            },
            instructions={
                "en": (
                    "Template: general assembly. Make one topic per resolution or agenda item. "
                    "Record each resolution as a decision, with the vote result ONLY if it is "
                    "said (never compute or guess figures). Put questions raised by members "
                    "that were not answered in `open_points`."
                ),
                "fr": (
                    "Modèle : assemblée générale. Fais un sujet par résolution ou point à "
                    "l'ordre du jour. Note chaque résolution comme décision, avec le résultat "
                    "du vote UNIQUEMENT s'il est dit (ne calcule ni n'estime jamais de "
                    "chiffres). Mets les questions de membres restées sans réponse dans "
                    "`open_points`."
                ),
            },
        ),
    )
}


class UnknownTemplate(ValueError):
    pass


def get_template(template_id: str) -> Template:
    try:
        return TEMPLATES[template_id]
    except KeyError:
        raise UnknownTemplate(f"Unknown template: {template_id}") from None


def template_prompt(template_id: str, language: str) -> str:
    """Extra instructions for the prompt, in the minutes' language (empty for the standard)."""
    return get_template(template_id).instructions.get(language, "")
