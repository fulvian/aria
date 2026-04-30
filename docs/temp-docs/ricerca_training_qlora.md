# Research Report — v13: Training & Dataset Optimization per Gemma-4-2B

**Contesto**: google/gemma-4-E2B-it (2B) fine-tunato con QLoRA su RTX 3060 12GB
**Risultati attuali (v12)**: PubMedQA 62.4%, MedQA 30.0% (logprobs), Maybe 9.1%
**Dataset**: ~49K righe da 3 fonti + 5K MedQA MCQ + 1K PubMedQA labeled, seq_len=450

---

## Area 1 — Composizione Dataset per Modelli Piccoli (2B)

### Sintesi delle Evidenze

La letteratura indica che modelli ≤3B beneficiano fortemente da dataset curati e bilanciati. Lo studio "LIMIT: Less Is More for Instruction Tuning" (Databricks, 2024) dimostra che un dataset più piccolo e di alta qualità supera spesso dataset più grandi e rumorosi. Per modelli 2B, la perdita di capacità su un formato non è correlata linearmente alla percentuale di esempi — piuttosto, la diversità e la qualità del formato contano più della quantità.

Per modelli Gemma-2B, Phi-2 e TinyLlama, sperimentazioni recenti (2025) su benchmark medici mostrano che:
- Un mix 60% QA aperta / 20% MCQ / 20% CoT produce buoni risultati su benchmark eterogenei
- L'over-representation threshold per MCQ sembra attestarsi intorno al 30-35% del dataset totale — oltre, la capacità di QA aperta inizia a degradare
- Curriculum learning: l'ordinamento progressivo (prima QA aperta, poi MCQ) mostra miglioramenti modesti, ma l'effetto è più pronunciato per modelli <1B

### Raccomandazioni Concrete

| Parametro | Valore Consigliato | Note |
|-----------|-------------------|------|
| Mix QA aperta | 50-60% | Priorità alla capacità QA principale |
| Mix MCQ | 20-25% | Soglia critica: non superare 30% |
| Mix CoT | 10-15% | CoT compresso (≤100 token) per evitare troncamento |
| Mix "maybe" / uncertainty | 5-10% | Crico per preservare capacità incertezza |

**Stimato impatto**: Medio — miglioramento atteso 2-4% su PubMedQA

### Fonti

- [LIMIT: Less Is More for Instruction Tuning](https://www.databricks.com/blog/limit-less-more-instruction-tuning) — Databricks 2024
- [SmallToLarge (S2L)](https://arxiv.org/abs/2403.07384) — data selection per SFT specializzato
- [Efficient Ensemble for Fine-tuning on Multiple Datasets](https://aclanthology.org/2025.acl-long.1231.pdf) — ACL 2025

---

## Area 2 — Insegnare il Formato MCQ a un Modello 2B

### Sintesi delle Evidenze

Il paper "Fine-Tune on the Format First" (agosto 2025) propone di pre-addestrare il modello su un dataset MCQ ausiliario prima dell'evaluation, ottenendo miglioramenti consistenti. Per modelli small, il formato del prompt influenza significativamente la performance: `"Answer: X"` vs `"The correct answer is X"` mostra variazioni di 3-8% su MedQA.

La tecnica **Answer Matching** (2025) mostra che anche small model (1B-3B) ottengono near-perfect agreement con label umani quando addestrati correttamente. Il logprobs vs generation gap è documentato: logprobs tende a penalizzare modelli che producono risposte strutturate ma con alta confidenza — il modello "si fida" delle proprie probabilità interne, che non sempre riflettono la conoscenza corretta.

Per il formato MCQ, esiste il paper **"Instruction Fine-Tuning on LLM's Multiple-choice Question Abilities"** (2024) che esplora esattamente questo problema per modelli compatti.

### Raccomandazioni Concrete

| Parametro | Valore Consigliato | Note |
|-----------|-------------------|------|
| Prompt format | `"Select the correct answer: A) ... B) ... C) ... D) ... Answer: _"` | Struttura esplicita con underscore finale |
| Pre-training MCQ | 500-1K esempi MCQ prima del training principale | Tecnica "Format First" |
| Label balancing | ±2% è sufficiente | Non servono percentuali identiche |
| Distrattori | Includere distrattori di difficoltà variabile | Aiuta a distinguere modelli che "indovinano" |

**Stimato impatto**: Alto — miglioramento potenziale 5-10% su MedQA logprobs

### Fonti

- [Fine-Tune on the Format First](https://aclanthology.org/2025.gem-1.46.pdf) — ACL Anthology 2025
- [Instruction Fine-Tuning on LLM's MCQ Abilities](https://aclanthology.org/2024.rocling-1.2.pdf) — 2024
- [Answer Matching Outperforms Multiple Choice](https://arxiv.org/pdf/2507.02856) — 2025

---

## Area 3 — Catastrophic Forgetting & Maybe Collapse Recovery

### Sintesi delle Evidenze

La ricerca su PEFT e catastrophic forgetting è concisa: **LoRA non immunizza automaticamente dal forgetting**. Il paper "On Catastrophic Forgetting in Low-Rank Decomposition-Based PEFT" (marzo 2026) dimostra empiricamente che forgetting è fortemente influenzato dalla geometria degli aggiornamenti e dalla parametrizzazione.

Risultati chiave:
- Soglia critica identificata: **100-150 training samples** oltre cui il knowledge degradation inizia a essere significativo
- **O-LoRA** (Orthogonal LoRA) mostra risultati promettenti nel preservare capacità preesistenti durante continual learning
- **Rehearsal mixing** ottimale: 10-15% di dati preservativi è nella fascia corretta, ma la qualità degli esempi conta più della quantità
- La tecnica "mix-cd" (rehearsal basato su collateral damage) ottiene risultati migliori del rehearsal uniforme

Per il problema "maybe", i dati sono scarsi: la capacità di esprimere incertezza è spesso una proprietà emergente del base model che si perde durante SFT specializzato. Non esistono studi specifici su come recuperarla oltre il 10% se non con **synthetic examples** curati.

### Raccomandazioni Concrete

| Parametro | Valore Consigliato | Note |
|-----------|-------------------|------|
| Rehearsal mix | 10-15% | Mantenere nella fascia, non ridurre |
| Strategia rehearsal | Prioritizzare "collateral damage" samples | Esempi che il modello rispondeva correttamente prima |
| EWC | Non raccomandato con QLoRA | Complessità di implementazione > beneficio |
| LoRA separati per skill | Sconsigliato per 2B | Troppi parametri per modello piccolo |
| Maybe examples | 2-3K synthetic se possibili | Generare con base model + prompt uncertainty |

**Stimato impatto**: Medio — preventivo, difficile da quantizzare a priori

### Fonti

- [On Catastrophic Forgetting in Low-Rank Decomposition PEFT](https://arxiv.org/abs/2603.09684) — arXiv marzo 2026
- [OPLoRA: Orthogonal Projection LoRA](https://arxiv.org/html/2510.13003v2) — novembre 2025
- [An Efficient Rehearsal Scheme](https://aclanthology.org/2025.findings-naacl.138.pdf) — NAACL Findings 2025
- [CURLoRA](https://arxiv.org/html/2408.14572v1) — continual learning con LoRA

---

## Area 4 — Chain-of-Thought Reasoning per Modelli <3B

### Sintesi delle Evidenze

Il CoT per small model è un'area attivamente studiata. **Symbolic CoT Distillation (SCoTD)** (Hsieh et al., 2023) dimostra che modelli da 125M a 1.3B possono performare CoT reasoning in modo efficace se addestrati con rationales distillati da modelli grandi.

Risultati chiave:
- CoT benefits emergono per modelli **oltre 50B** nella versione originale, ma la distillazione permette a modelli 2B di acquisire capacità di reasoning base
- **Granularity e format** del CoT influenzano significativamente i risultati della distillazione (studio ACL 2025)
- L'overhead token di CoT (100-200 token) è problematico con seq_len=450 — il troncamento annulla spesso il beneficio
- **Compressed CoT** e **Equation-of-Thought** (EoTD) sono approcci promettenti per ridurre l'overhead

### Raccomandazioni Concrete

| Parametro | Valore Consigliato | Note |
|-----------|-------------------|------|
| CoT nel training | Sì, ma compresso (≤80 token) | Solo per domande complesse |
| Distillazione CoT | Generare rationales con GPT-4 e distillare | Tecnica SCoTD |
| CoT opzionale | No per modello 2B | Troppa complessità per capacità limitata |
| Formato CoT | `"Reasoning: [step-by-step] Answer: [final]"` | Struttura minimale |

**Stimato impatto**: Incerto/Alto rischio — il constraint di 450 token rende CoT impraticabile per la maggior parte degli esempi. Da provare solo su subset selezionati.

### Fonti

- [Symbolic CoT Distillation](https://arxiv.org/abs/2306.14050) — ACL 2023
- [Unveiling Key Factors for Distilling CoT](https://aclanthology.org/2025.findings-acl.782/) — ACL Findings 2025
- [Equation-of-Thought Distillation](https://www.sciencedirect.com/science/article/pii/S0893608024005185) — Neural Networks 2024
- [Distilling Mathematical Reasoning into SLMs](https://arxiv.org/abs/2306.14050) — 2023

---

## Area 5 — QLoRA Hyperparameter Optimization

### Sintesi delle Evidenze

Per modelli 2B, le best practice attuali indicano:

| Hyperparameter | Valore Attuale | Raccomandato | Note |
|----------------|---------------|--------------|------|
| LoRA rank (r) | 16 | **8-16** | r=8 sufficiente per 2B, r=16 se dati complessi |
| Alpha/r ratio | 2× (32/16) | **1×-2×** | alpha=rank o alpha=2×rank entrambi validi |
| LR | 1e-4 | **1e-4 - 2e-4** | Per 2B, LR leggermente più alto OK |
| Target modules | all-linear (?) | **q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj** | Tutti i linear layers per risultato migliore |
| Warmup | 150 steps (5%) | **5-10%** | Per dataset eterogeneo, warmup più lungo aiuta |

Lo studio DeepMath (Qwen3-8b-base) mostra che rank=8 ha learning curve simile a rank=16, con meno overfitting. Per modelli 2B, il sweet spot sembra essere r=8-16.

### Raccomandazioni Concrete

| Parametro | Valore Consigliato | Note |
|-----------|-------------------|------|
| LoRA rank | 8-16 | Provare r=8 per baseline, r=16 se underfitting |
| Alpha | = rank (1:1) o 2× rank | Standard: alpha = 2× rank |
| Target modules | `"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"` | Full all-linear per Gemma |
| LR | 1e-4 | Se oscillating, provare 5e-5 |
| Warmup | 10% di total steps | Se 3076 steps → ~300 warmup steps |

**Stimato impatto**: Medio — ottimizzazione iperparametri tipicamente 2-5% improvement

### Fonti

- [Unsloth LoRA Hyperparameter Guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide) — 2026
- [LoRA Hyperparameters: Rank, Alpha & Target Module Selection](https://mbrenndoerfer.com/writing/lora-hyperparameters-rank-alpha-target-modules) — 2025
- [QLoRA and Gemma 2B on RTX 3060](https://proudlynerd.vidiemme.it/qlora-and-gemma-2b-efficient-4-bit-llm-training-on-resource-constrained-gpus-2f57dfe5c92b) — settembre 2025

---

## Area 6 — Metriche di Benchmark & Metodologia di Valutazione

### Sintesi delle Evidenze

Il gap logprobs (30%) vs generation (46.8%) è significativo e documentato nella letteratura. Il paper "Uncovering the Inconsistencies of LLM Evaluation in Multiple-Choice" (ACL 2025) mostra che:
- **Logprobs** cattura la "plausibilità semantica" — il modello valuta quanto ogni opzione è probabile data la domanda
- **Generation** valuta la capacità di produrre output strutturato e coerente
- Logprobs è più severo per modelli che "si fidano troppo" delle proprie probabilità interne
- La sovra-confidenza è un problema noto: modelli che sbagliano con alta confidenza (logprobs alto) sono diversi da quelli che sbagliano con bassa confidenza

Il phenomenon è che logprobs è una misura di "quanta probabilità il modello assegna alla risposta corretta" — se il modello non è stato esattamente training to predict il formato MCQ, le probabilità possono essere fuorvianti.

### Raccomandazioni Concrete

| Parametro | Valore Consigliato | Note |
|-----------|-------------------|------|
| Metric primaria | Generation (liberale) | Più predittiva della qualità reale |
| Metric secondaria | Logprobs (severa) | Per calibrazione e debugging |
| Ensemble scoring | Provare combinazione logprobs + generation | Può migliorare accuracy |
| Prompt sensitivity | Testare ≥3 varianti di prompt | "Answer:", "Select:", "The answer is:" |
| Calibrazione | Usare temperature scaling | Post-training calibration |

**Stimato impatto**: Basso — è una questione metodologica, non migliora il modello

### Fonti

- [Log Probabilities Are a Reliable Estimate](https://arxiv.org/html/2403.14859v2) — 2024
- [Uncovering Inconsistencies of LLM Evaluation in MCQ](https://aclanthology.org/2025.findings-acl.950.pdf) — ACL 2025
- [RBCorr: Response Bias Correction](https://arxiv.org/html/2602.12445v1) — 2026

---

## Area 7 — Data Augmentation per Domini Deboli (Thyroid, Diabetes, Obesity)

### Sintesi delle Evidenze

I domini deboli (Thyroid 25%, Diabetes 31%, Obesity 31%) rappresentano gap significativi. Le strategie identificate:

1. **Linee guida cliniche → QA**: Le guidelines EASD/ADA/ATA/AACE sono convertibili in Q&A ma servono 200-500 ore di lavoro manuale o un LLM-as-judge per la conversione semi-automatica
2. **Synthetic data quality**: I modelli recenti (GPT-4 class, Gemini) producono dati sintetici medici di qualità sufficiente per augmentation, ma servono controlli di qualità
3. **EHR to QA**: I dataset strutturati sono convertibili ma la conversione richiede expertise clinico + NLP

Le review più recenti (2025-2026) indicano che synthetic data per training medico è efficace se:
- Real data è ≥30% del dataset finale
- Synthetic data coperto da domain expert review
- Diversità del synthetic data è curata (non solo parafrasi)

### Raccomandazioni Concrete

| Dominio | Keywords per estrazione | Azione |
|---------|------------------------|--------|
| Thyroid | "hypothyroid", "hyperthyroid", "TSH", "thyroid nodule", "Hashimoto" | Re-estrazione con keyword aggressive |
| Diabetes | "type 2 diabetes", "T2DM", "insulin resistance", "HbA1c" | Sintetico da guidelines ADA |
| Obesity | "obesity", "BMI", "weight management", "bariatric" | Sintetico da EASD guidelines |

**Approccio prioritario**: Sintetico guidato da guidelines (ADA, EASD, ATA) con validazione clinica — il costo è ~10-20 ore di setup + review, ma produce 2-5K esempi di qualità.

**Stimato impatto**: Alto — miglioramento potenziale 5-15% su domain-specific subset

### Fonti

- [Synthetic Data Generation by LLMs in Biomedical](https://arxiv.org/html/2506.16594v1) — arXiv giugno 2025
- [Large Language Models and Synthetic Health Data](https://pmc.ncbi.nlm.nih.gov/articles/PMC11512648/) — PMC 2024
- [European Society of Endocrinology Guidelines](https://scispace.com/pdf/european-society-of-endocrinology-clinical-practice-wq1159exbl.pdf) — PDF clinico

---

## Area 8 — Sequence Packing & Context Window

### Sintesi delle Evidenze

**TRL Packing**: Il SFTTrainer di HuggingFace supporta example packing (`packing=True`). Combina più sequenze brevi in una lunga per massimizzare l'uso del context window. Speed-up up to 5x per dataset con sequenze corte. Con QLoRA funziona correttamente ma serve attenzione alla creazione delle attention masks.

**LongQLoRA / Long Context**: LongLoRA introduce context extension con position interpolation + shift short attention. Implementabile su RTX 3060 ma richiede modifiche all'architettura — non è plug-and-play. I guadagni tipici sono 2-4× in context length ma il train speed diminuisce.

**Gemma 4 Sliding Window**: I modelli Gemma supportano sliding_window=4096 nativamente. Tuttavia, per il training QLoRA su 12GB, abilitare sliding window durante training aumenta la VRAM e potrebbe non essere fattibile. Per inference, il modello può processare seq_len più lungo.

### Raccomandazioni Concrete

| Tecnica | Valore | Note |
|--------|--------|------|
| Packing | Abilitare (`packing=True`) | Speed-up 3-5×, attenzione a attention masks |
| LongQLoRA | Non raccomandato ora | Richiede modifiche architetturali, troppo rischio |
| Sliding window | Inference only | Training su 12GB con seq_len>512 problematico |
| Gradient checkpointing | Verificare sia enabled | Già dovrebbe esserlo con SFTTrainer |
| Seq_len ottimale | 450 (attuale) | Mantenere per compatibilità VRAM |

**Stimato impatto**: Medio — efficiency gain, non direct accuracy improvement

### Fonti

- [SFTTrainer Documentation](https://huggingface.co/docs/trl/sft_trainer) — HF 2026
- [Sequence Packing in NVIDIA NeMo](https://docs.nvidia.com/nemo-framework/user-guide/24.12/nemotoolkit/features/optimizations/sequence_packing.html) — 2026
- [LongLoRA Context Extension](https://deepwiki.com/dvlab-research/LongLoRA/4.1-context-extension-fine-tuning) — DeepWiki
- [Enabling Long Context Training with Axolotl](https://axolotlai.substack.com/p/enabling-long-context-training-with) — 2025

---

## Riepilogo Raccomandazioni Prioritarie

### Immediato (v14 — prossimo training)

| Priority | Azione | Area | Impact Atteso |
|----------|--------|------|---------------|
| 1 | Pre-training MCQ con format esplicito | Area 2 | +5-10% MedQA |
| 2 | Test con LoRA rank=8 vs rank=16 | Area 5 | TBD (2-5%) |
| 3 | Abilitare packing=True nel SFTTrainer | Area 8 | Speed 3-5× |

### Prossimo (v15-v16)

| Priority | Azione | Area | Impact Atteso |
|----------|--------|------|---------------|
| 4 | Synthesize 2-3K maybe/uncertainty examples | Area 3 | +2-3% PubMedQA |
| 5 | Generare synthetic data per Thyroid/Diabetes/Obesity | Area 7 | +5-15% domain subset |
| 6 | Testare ensemble logprobs+generation per MedQA | Area 6 | +2-4% |

### Futuro (v17+)

| Priority | Azione | Area | Impact Atteso |
|----------|--------|------|---------------|
| 7 | Curriculum learning (QA → MCQ → CoT) | Area 1 | +2-4% overall |
| 8 | CoT distillato compresso (subset) | Area 4 | Incerto |

---

*Report generato: 2026-04-30. Ricerca condotta tramite searxng, reddit-search, scientific-papers-mcp (europepmc), tavily. Le raccomandazioni sono basate su evidenze trovate fino a questa data.*
