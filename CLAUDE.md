# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **camellia cultivar data enrichment project** — not a traditional software codebase. It transforms simple cultivar name lists into comprehensive botanical reference tables using a Claude AI Skill workflow and web research.

## Files

- **`genes_combined.csv`** — Master list of ~555 camellia cultivars with 3 columns: Cultivar, Epithet, Category
- **`genes_first5_enriched.csv`** / **`genes_first35_enriched.csv`** — Enriched samples with all 7 columns (use as output format reference)
- **`camellia-cultivar-research.skill`** — ZIP archive containing the research workflow (`SKILL.md`) and terminology reference (`references/camellia_terminology.md`)

## Data Schema

**Input (genes_combined.csv):**
```
Cultivar, Epithet, Category
```

**Enriched output (7 columns):**
```
Cultivar, Epithet, Category, Color / Form, Description, Notes, Image URL
```

## Category Codes

| Code | Species |
|------|---------|
| J | *Camellia japonica* |
| S | *Camellia sasanqua* |
| RH | Reticulata Hybrid |
| NRH | Non-Reticulata Hybrid |
| Species | Wild/species types |

## Enrichment Workflow

The `.skill` file defines a pipeline: validate cultivar names → classify species → web-research each cultivar → extract standardized fields → flag unknowns.

**Priority research sources (in order):**
1. International Camellia Register — `camellia.iflora.cn`
2. American Camellia Society — `americancamellias.com`
3. Specialty nurseries (Nuccio's, Camellia Forest, Gene's Camellias)
4. University extension services (NC State, Clemson, UF/IFAS)

## Standardized Terminology

**Flower forms:** Single, Semi-double, Anemone, Peony, Rose-form Double, Formal Double

**Flower sizes:** Miniature (<2"), Small (2-3"), Medium (3-4"), Large (4-5"), Very Large (>5")

**Standard colors:** White, Blush, Pink, Rose, Red, Coral, Variegated

## Key Conventions

- Epithet format: `Camellia japonica 'Cultivar Name'` with registration info when known
- Descriptions prioritize: flower size, originator/location/year, parentage (hybrids), bloom season, growth habit, awards
- When a cultivar cannot be found, mark as "Unknown - possibly unregistered or misspelled"
- Variegated sports should note their parent cultivar relationship
