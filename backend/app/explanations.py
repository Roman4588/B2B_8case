"""Literal token overlap is a separate signal, not attribution for embeddings."""

import re
import unicodedata
from pathlib import Path

# Keep this vocabulary as data: importing sklearn here loads SciPy in the API
# and duplicates the ML runtime inside the 1 GB standalone deployment.
# Source and redistribution notice: seed/english_stop_words.LICENSE.
STOP_WORDS = set(
    (Path(__file__).parent / "seed" / "english_stop_words.txt").read_text(encoding="utf-8").split()
) | set(
    "и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя такой им более всегда конечно всю между это также into using should when then если при после перед нужно необходимо требуется проверить проверка событие регламент инструкция the is are was were have has be been do does did no not".split()
)


# These English stop words carry operational meaning in monitoring alerts.
STOP_WORDS -= {"full", "empty", "down", "system", "fire", "call"}


def terms(text):
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return {
        term
        for term in re.findall(r"[^\W_]+(?:[-+#][^\W_]+)*", normalized, flags=re.UNICODE)
        if len(term) > 1 and not term.isdigit() and term not in STOP_WORDS
    }


def matched_terms(query, condition):
    return sorted(terms(query) & terms(condition))


def explain(query, condition):
    matches = matched_terms(query, condition)
    lexical = (
        "Прямые совпадения слов с условием: " + ", ".join(matches) + "."
        if matches
        else "Прямых совпадений содержательных слов с условием нет."
    )
    return {
        "matched_terms": matches,
        "explanation": lexical
        + " Семантическое сходство — 1 минус cosine distance ближайшего фрагмента регламента. Это сходство текстов, не вероятность правильности. Совпадения слов — отдельный сигнал, они не объясняют решение векторной модели.",
    }
