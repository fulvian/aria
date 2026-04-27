# ARIA Memory Wiki Module (v3)
#
# Per docs/plans/auto_persistence_echo.md §8.
#
# Wiki.db-backed knowledge store with FTS5 recall.
# Five page kinds: profile, topic, lesson, entity, decision.
#
# Usage:
#   from aria.memory.wiki import WikiStore, Page, PagePatch, WikiUpdatePayload
#   from aria.memory.wiki import WikiRecallEngine
#   from aria.memory.wiki import wiki_update, wiki_recall, wiki_show, wiki_list

from aria.memory.wiki.db import WikiStore
from aria.memory.wiki.recall import RecallResult, WikiRecallEngine
from aria.memory.wiki.schema import (
    Page,
    PageKind,
    PagePatch,
    PageRevision,
    WikiUpdatePayload,
)

__all__ = [
    "Page",
    "PageKind",
    "PagePatch",
    "PageRevision",
    "RecallResult",
    "WikiRecallEngine",
    "WikiStore",
    "WikiUpdatePayload",
]
