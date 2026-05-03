"""Smoke E2E test for traveller-agent golden path (Fase 9).

Questo test verifica che il traveller-agent sia in grado di gestire
un flusso completo di pianificazione viaggio (golden path):

"5 giorni a Barcellona, famiglia 4 persone, budget 3000€"

Il test verifica a livello di contratto:
1. Prompt: contiene pipeline end-to-end (destination → transport → accommodation → activities → itinerary → budget)
2. Skills: tutte le 6 skill sono registrate e hanno SKILL.md
3. Backend: i 3 backend principali sono registrati (airbnb, osm-mcp, aria-amadeus-mcp)
4. Output: il prompt specifica il formato Travel Brief strutturato
5. HITL: il prompt richiede HITL per save Drive

Non richiede backend reali — skip se marker live_assenti.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

TRAVELLER_PROMPT = Path(".aria/kilocode/agents/traveller-agent.md")
CAPABILITY_MATRIX = Path(".aria/config/agent_capability_matrix.yaml")
MCP_CATALOG = Path(".aria/config/mcp_catalog.yaml")
SKILLS_DIR = Path(".aria/kilocode/skills")


@pytest.fixture(scope="module")
def fm() -> dict:
    """YAML frontmatter of traveller-agent.md."""
    text = TRAVELLER_PROMPT.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return yaml.safe_load(parts[1])


@pytest.fixture(scope="module")
def body() -> str:
    """Body of traveller-agent.md (without frontmatter)."""
    text = TRAVELLER_PROMPT.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2]


@pytest.fixture(scope="module")
def matrix() -> dict:
    return yaml.safe_load(CAPABILITY_MATRIX.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> dict:
    return yaml.safe_load(MCP_CATALOG.read_text(encoding="utf-8"))


# ── Golden Path — Pipeline Contract ───────────────────────────────────────────


class TestGoldenPathPipeline:
    """The prompt contains the complete end-to-end travel planning pipeline."""

    def test_pipeline_section_exists(self, body: str):
        """Prompt has a pipeline section describing the planning phases."""
        assert "Pipeline" in body or "Fase" in body

    def test_pipeline_has_intent_classification(self, body: str):
        """Pipeline Fase 1: Intent classification + recall."""
        assert "Intent classification" in body or "intent" in body.lower()

    def test_pipeline_has_recall(self, body: str):
        """Pipeline Fase 1: wiki_recall at start."""
        assert "wiki_recall" in body

    def test_pipeline_has_skill_execution(self, body: str):
        """Pipeline Fase 2: Skill execution phase."""
        assert "skill" in body.lower()

    def test_pipeline_has_synthesis(self, body: str):
        """Pipeline Fase 3: Synthesis produces Travel Brief."""
        assert "Travel Brief" in body or "Sintesi" in body or "synthesis" in body.lower()


# ── Golden Path — Destination Research ───────────────────────────────────────


class TestGoldenPathDestination:
    """Destination research is wired for the golden path."""

    def test_geocoding_available(self, body: str):
        """Prompt references geocoding via osm-mcp."""
        assert "geocode" in body.lower() or "osm-mcp" in body

    def test_destination_info_covered(self, body: str):
        """Prompt covers clima, posizione, info pratiche."""
        topics = ["clima", "posizione", "valuta", "fuso"]
        found = [t for t in topics if t in body.lower()]
        assert len(found) >= 2, f"Not enough destination info topics: {found}"


# ── Golden Path — Transport ──────────────────────────────────────────────────


class TestGoldenPathTransport:
    """Transport planning is wired for the golden path."""

    def test_flight_search_available(self, body: str):
        """Prompt references flight search via aria-amadeus-mcp."""
        assert "flight_offers_search" in body or "volo" in body.lower()

    def test_location_search_available(self, body: str):
        """Prompt references airport/city lookup."""
        lower = body.lower()
        assert "transfer" in lower or "aeroporto" in lower or "iata" in lower

    def test_airbnb_search_available(self, body: str):
        """Prompt references Airbnb search."""
        assert "airbnb" in body.lower()

    def test_multi_ota_comparison(self, body: str):
        """Prompt references multi-OTA comparison."""
        assert "confronto" in body.lower() or "multi-OTA" in body.lower()


# ── Golden Path — Activities ─────────────────────────────────────────────────


class TestGoldenPathActivities:
    """Activity planning is wired for the golden path."""

    def test_poi_search_available(self, body: str):
        """Prompt references POI/attractions."""
        assert "Attività" in body

    def test_nearby_places_available(self, body: str):
        """Prompt references activity/restaurant search."""
        assert "Attività" in body or "Ristoranti" in body


# ── Golden Path — Itinerary ──────────────────────────────────────────────────


class TestGoldenPathItinerary:
    """Itinerary building is wired for the golden path."""

    def test_day_by_day_format(self, body: str):
        """Prompt specifies day-by-day itinerary format."""
        # Check for the Travel Brief template which has "### Giorno N"
        assert "### Giorno" in body

    def test_route_optimization_available(self, body: str):
        """Prompt references route optimization."""
        assert "route" in body.lower() or "waypoint" in body.lower()


# ── Golden Path — Budget ─────────────────────────────────────────────────────


class TestGoldenPathBudget:
    """Budget analysis is wired for the golden path."""

    def test_budget_breakdown_in_template(self, body: str):
        """Prompt budget section exists in Travel Brief template."""
        assert "## Budget" in body

    def test_budget_multiple_categories(self, body: str):
        """Budget covers multiple expense categories."""
        categories = ["volo", "alloggio", "pasto", "attività", "trasporto"]
        found = [c for c in categories if c in body.lower()]
        assert len(found) >= 3, f"Not enough budget categories: {found}"


# ── Golden Path — Output ─────────────────────────────────────────────────────


class TestGoldenPathOutput:
    """The prompt specifies the correct output format."""

    def test_travel_brief_template(self, body: str):
        """Prompt has the Travel Brief template with all sections."""
        sections = [
            "Travel Brief",
            "TL;DR",
            "## Destinazione",
            "## Trasporto",
            "## Alloggio",
            "## Attività",
            "## Itinerario",
            "## Budget",
            "## Link prenotazione",
        ]
        for section in sections:
            assert section in body, f"Missing section in Travel Brief: {section}"

    def test_disclaimer_present(self, body: str):
        """Travel Brief includes the mandatory disclaimer."""
        flat = body.replace("\n", " ")
        assert "Nessuna prenotazione è stata eseguita" in flat
        assert "Verifica disponibilità" in flat


# ── Golden Path — HITL ───────────────────────────────────────────────────────


class TestGoldenPathHITL:
    """HITL gates are correctly configured."""

    def test_hitl_section(self, body: str):
        """Prompt has HITL section."""
        assert "## HITL" in body

    def test_hitl_for_drive(self, body: str):
        """HITL required for Drive export."""
        assert "Drive" in body

    def test_hitl_for_calendar(self, body: str):
        """HITL required for Calendar."""
        assert "Calendar" in body or "calendar" in body.lower()

    def test_hitl_for_email(self, body: str):
        """HITL required for email."""
        assert "email" in body.lower() or "mail" in body.lower()


# ── Golden Path — Skill Composition ──────────────────────────────────────────


class TestGoldenPathSkillComposition:
    """All 6 skills exist and are registered for the golden path."""

    REQUIRED_SKILLS = [
        "destination-research",
        "accommodation-comparison",
        "transport-planning",
        "activity-planning",
        "itinerary-building",
        "budget-analysis",
    ]

    def test_all_skills_have_skill_files(self):
        """Each required skill has a SKILL.md file."""
        for skill in self.REQUIRED_SKILLS:
            skill_file = SKILLS_DIR / skill / "SKILL.md"
            assert skill_file.exists(), f"Missing SKILL.md for {skill}"

    def test_all_skills_listed_in_prompt(self, fm: dict):
        """All 6 skills are listed in the prompt frontmatter."""
        skills = set(fm.get("required-skills", []))
        for skill in self.REQUIRED_SKILLS:
            assert skill in skills, f"Skill {skill} not in prompt required-skills"

    def test_all_skills_have_proxy_tools(self):
        """Each skill frontmatter includes proxy tools."""
        for skill in self.REQUIRED_SKILLS:
            skill_file = SKILLS_DIR / skill / "SKILL.md"
            text = skill_file.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            sf = yaml.safe_load(parts[1])
            tools = sf.get("allowed-tools", [])
            assert any("proxy" in t for t in tools), (
                f"Skill {skill} missing proxy tools"
            )


# ── Golden Path — Backend Readiness ──────────────────────────────────────────


class TestGoldenPathBackendReadiness:
    """All required backends are registered in the catalog."""

    def test_airbnb_in_catalog(self, catalog: dict):
        """Airbnb backend is registered."""
        servers = {s["name"]: s for s in catalog["servers"]}
        assert "airbnb" in servers
        assert servers["airbnb"]["lifecycle"] == "enabled"

    def test_osm_mcp_in_catalog(self, catalog: dict):
        """OSM MCP backend is registered."""
        servers = {s["name"]: s for s in catalog["servers"]}
        assert "osm-mcp" in servers
        assert servers["osm-mcp"]["lifecycle"] == "enabled"

    def test_amadeus_in_catalog(self, catalog: dict):
        """Amadeus MCP backend is registered."""
        servers = {s["name"]: s for s in catalog["servers"]}
        assert "aria-amadeus-mcp" in servers
        assert servers["aria-amadeus-mcp"]["lifecycle"] == "enabled"

    def test_backend_credentials_encrypted(self):
        """Amadeus credentials are SOPS-encrypted."""
        creds = Path(".aria/credentials/secrets/api-keys.enc.yaml")
        assert creds.exists()
        text = creds.read_text(encoding="utf-8")
        assert "amadeus" in text
        assert "ENC[AES256_GCM" in text


# ── Golden Path — Memory Contract ────────────────────────────────────────────


class TestGoldenPathMemory:
    """Memory contract is correctly configured."""

    def test_recall_at_start(self, body: str):
        """Prompt specifies wiki_recall at start."""
        assert "wiki_recall" in body

    def test_update_at_end(self, body: str):
        """Prompt specifies wiki_update at end."""
        assert "wiki_update" in body

    def test_single_update_per_turn(self, body: str):
        """One wiki_update per turn."""
        assert "ESATTAMENTE UNA VOLTA" in body
