"""Retrieve relevant source passages locally; retain the full source in project storage."""

import re


def page_source(source, title, points, budget=6000):
    if len(source) <= budget:
        return source
    terms = set(re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", title+" "+" ".join(points)))
    # Short CJK bigrams also match a page heading against continuous Chinese prose.
    for term in list(terms):
        if re.search(r"[\u4e00-\u9fff]", term):
            terms.update(term[i:i+2] for i in range(len(term)-1))
    chunks = []
    for paragraph in re.split(r"\n\s*\n", source):
        chunks.extend(paragraph[i:i+900] for i in range(0,len(paragraph),900))
    ranked = sorted(enumerate(chunks), key=lambda pair: (-sum(term.lower() in pair[1].lower() for term in terms),pair[0]))
    selected, used = {}, 0
    for index, chunk in ranked:
        if used+len(chunk) <= budget:
            selected[index] = chunk
            used += len(chunk)
    return "\n\n".join(selected[i] for i in sorted(selected))
