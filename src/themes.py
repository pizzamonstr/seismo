"""Group logged questions into themes with clustering."""

import json

from sklearn.cluster import KMeans

from src.embed import embed_texts

THEME_MODEL = "gpt-6-luna"
THEME_EFFORT = "none"
MIN_QUESTIONS = 6
MAX_THEMES = 6
QUESTIONS_PER_THEME = 8
EXAMPLES_PER_THEME = 8
MIN_THEME_SIZE = 3
SMALL_THEME_NAME = "Other questions"

NAMING_INSTRUCTIONS = """You name groups of questions that people \
asked a chatbot about a ski brand's marketing and sales metrics.

For each group, write a short theme name of 2 to 5 words, like \
"Retargeting cost spikes" or "Seasonal sales dips". Describe the \
topic in general terms. Never copy personal details, names, \
numbers or exact wording from the questions. If a group is not \
about marketing, sales or the brand, name it "Off-topic questions".

Reply with JSON only, in this shape:
{"themes": [{"group": 1, "name": "Theme name"}]}"""


def pick_theme_count(question_count):
    """Choose how many themes to look for, between 2 and 6."""
    count = question_count // QUESTIONS_PER_THEME
    return max(2, min(MAX_THEMES, count))


def build_naming_message(questions, groups, theme_count):
    """List a few example questions from each group."""
    lines = []
    for group in range(theme_count):
        lines.append(f"Group {group + 1}:")
        shown = 0
        for question, question_group in zip(questions, groups):
            if question_group == group and shown < EXAMPLES_PER_THEME:
                lines.append(f"- {question}")
                shown = shown + 1
        lines.append("")
    return "\n".join(lines)


def name_groups(questions, groups, theme_count, openai_client):
    """Ask the model for a short name for each group."""
    names = {}
    for group in range(theme_count):
        names[group] = f"Theme {group + 1}"

    message = build_naming_message(questions, groups, theme_count)
    response = openai_client.chat.completions.create(
        model=THEME_MODEL,
        reasoning_effort=THEME_EFFORT,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": NAMING_INSTRUCTIONS},
            {"role": "user", "content": message},
        ],
    )
    data = json.loads(response.choices[0].message.content)
    for item in data.get("themes", []):
        group = int(item["group"]) - 1
        if group in names and str(item.get("name", "")) != "":
            names[group] = str(item["name"])
    return names


def find_themes(questions, openai_client):
    """Cluster questions by meaning and name each cluster.

    Returns a dictionary from each question to its theme name.
    """
    unique_questions = []
    for question in questions:
        if question not in unique_questions:
            unique_questions.append(question)
    if len(unique_questions) < MIN_QUESTIONS:
        return {}

    embeddings = embed_texts(openai_client, unique_questions)
    theme_count = pick_theme_count(len(unique_questions))
    model = KMeans(n_clusters=theme_count, n_init=10, random_state=42)
    groups = model.fit_predict(embeddings)

    names = name_groups(
        unique_questions, groups, theme_count, openai_client
    )
    sizes = {}
    for group in groups:
        sizes[int(group)] = sizes.get(int(group), 0) + 1

    themes = {}
    for question, group in zip(unique_questions, groups):
        if sizes[int(group)] < MIN_THEME_SIZE:
            themes[question] = SMALL_THEME_NAME
        else:
            themes[question] = names[int(group)]
    return themes