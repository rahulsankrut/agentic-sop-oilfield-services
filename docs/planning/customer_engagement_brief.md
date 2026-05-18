# Customer Engagement Brief: Agentic AI on Google Cloud
## Pre-Sales Strategy & Technical Architecture

*A working document for the lead Customer Engineer.*

---

## Executive Summary

The customer has presented four operational pain points that, on the surface, look like distinct problems. They aren't. All four are symptoms of a single underlying condition: the enterprise data and decision-making fabric is fragmented across siloed systems with misaligned semantics, broken feedback loops, and no governed way for AI agents to reason across it. Google Cloud's Next '26 announcements — particularly Knowledge Catalog, Gemini Enterprise Agent Platform, and the Cross-Cloud Lakehouse — were architected almost precisely for this class of problem.

This document covers:

1. The customer's stated problems and what they actually mean
2. The Google Cloud solution landscape (post-Next '26)
3. Technical architecture options per issue
4. Strategic approach choices for the engagement
5. The recommended pre-sales playbook (3-gate funnel)
6. Working materials: POV outline, discovery questions, demo storyboard, ROI framing
7. Risks, assumptions, and what to do this week

The engagement goal is **not** to solve the four issues. It is to use the four issues as the vehicle to land Gemini Enterprise as the customer's AI front end and Gemini Enterprise Agent Platform as the build platform. Every decision should be evaluated against that goal.

---

## Part 1: The Customer Problem

### Industry context

The customer profile — Maximo for equipment status, SAP for materials and workforce, references to drilling activities, basin leaders, Operation Control Centers (OCC), unstructured technical documentation in InTouch, and logistics decisions involving chartering cargo from Australia to West Africa — places this squarely in the oilfield services sector. This is the operational pattern of a tier-one services major.

This matters for the engagement because:

- **CapEx vs. OpEx discipline is unusually strict.** "Unnecessary CapEx to build replacement tools" is a CFO-level conversation in this industry.
- **Asset utilization is a board-level KPI.** Idle fleet capacity has a direct line to quarterly earnings.
- **Data sovereignty and geopolitical sensitivities are real.** Basin-level data has political implications. Knowledge Catalog's access-control-aware retrieval is materially relevant.
- **Procurement cycles are long.** Pre-sales motion needs to accommodate enterprise procurement, not consumer-style velocity.
- **The competitive landscape is mature.** Microsoft and AWS are deeply embedded in this industry. Schlumberger has a known Azure relationship; Halliburton has multi-cloud; Baker Hughes has historical Microsoft alignment. Assume a competitive deal.

### The four issues, restated

**Issue 1 — Buffer time inflation due to volatile customer start dates.** Less than 40% of service shipments hit their originally requested customer start date. Because start dates shift unpredictably (driven by interdependent drilling activities), planners build static buffers into schedules. This ties up active fleet capacity, causing missed opportunities and forcing unnecessary CapEx to build replacement tools.

*What this really is:* a forecasting + dynamic scheduling problem. The buffer logic is a static heuristic compensating for missing probabilistic information about actual start dates. The cost is in fleet underutilization and replacement-tool CapEx.

**Issue 2 — ML forecast output dies at the human review boundary.** A quarterly ML model converts pipeline signals into pre-populated revenue spreadsheets. Geography and basin leaders make manual overrides in static Excel files. The qualitative adjustments and geopolitical insights live offline; they never re-ingest into the data source or train the model.

*What this really is:* a broken human-in-the-loop pattern. The technology to fix this has existed for years; the failure is in workflow design and incentives. Excel is the cultural artifact, not the technical one.

**Issue 3 — No multi-variable visibility during capacity gaps.** When capacity gaps emerge, OCC planners must manually stitch capacity numbers across Maximo (equipment), SAP (materials, workforce), FDP (historical customer configurations), and InTouch (unstructured technical docs). The result: panicked, expensive logistics — chartering a cargo plane from Australia to West Africa when a functionally equivalent sub-variant was sitting in a repair shop 50 km away.

*What this really is:* the canonical multi-system agentic reasoning problem. This is the use case Gemini Enterprise Agent Platform was built for. The cargo-plane story is the single most demoable element in the entire portfolio.

**Issue 4 — Misaligned naming conventions across foundational data layers.** A tool is named one way in the sales pipeline, differently in the well-construction catalog, and categorized under a completely separate taxonomy in procurement. Friction breaks automation. Humans translate fields continuously.

*What this really is:* a master data management / entity resolution problem at the semantic layer. It's the substrate that determines whether Issues 1, 2, and 3 can be solved at all. Without it, every downstream agent is reasoning on quicksand.

### The thread connecting them

All four are coordination costs from broken data and reasoning across silos. Each issue is a different symptom of the same systemic gap:

- Scheduling buffers (Issue 1) compensate for missing probabilistic visibility into upstream signals
- Broken feedback loops (Issue 2) waste human expertise that never becomes model training data
- Invisible capacity (Issue 3) forces expensive decisions based on partial information
- Translation overhead (Issue 4) blocks automation by breaking the semantic continuity agents need

The unifying insight: **the enterprise needs a governed agent fabric across systems that have historically required human glue.** This is the platform pitch, and it generalizes beyond these four issues to whatever else they bring you next.

### What's actually being asked of you (read between the lines)

The customer hasn't asked you to solve four problems. They've asked you to demonstrate that Google Cloud is a credible partner for an agentic transformation. The four issues are the test case. Behind them sits a portfolio of other potential agentic use cases that will flow if this one lands.

The implicit ask: *prove the platform.*

---

## Part 2: The Google Cloud Solution Landscape (post-Next '26)

### What changed at Next '26 (April 22, 2026)

Three announcements materially reshape how to architect this customer's solution:

1. **Knowledge Catalog** (rebrand and evolution of Dataplex Universal Catalog, renamed April 10, 2026)
2. **Gemini Enterprise Agent Platform** (rebrand and evolution of Vertex AI, includes ADK, Agent Studio, Agent Garden, Model Garden, Agent Runtime, Memory Bank, governance stack)
3. **Cross-Cloud Lakehouse** (rebrand and evolution of BigLake, Apache Iceberg-standardized, zero-copy access to AWS S3 and Azure Data Lake)

Together with **Smart Storage + Object Context API** (now GA in Cloud Storage) and the **Deep Research Agent**, **Data Agent Kit**, and **Agent Identity/Registry/Gateway** governance stack, these form an "Agentic Data Cloud" narrative that maps directly onto the customer's four issues.

### Knowledge Catalog (the centerpiece for this customer)

Formerly Dataplex Universal Catalog. The strategic reframe: from passive metadata registry to active, AI-powered context graph.

Capabilities most relevant to this customer:

- **Native connectivity to SAP, ServiceNow, Salesforce Data360, Palantir, and Workday** (Preview). For an oilfield services customer, SAP integration alone removes the need to build custom MCP servers for one of their four problem systems.
- **Gemini-powered continuous enrichment.** Mines schemas, query logs, BI semantic models, and unstructured content (PDFs in Cloud Storage) to build a context graph. This is the productized version of the entity-resolution problem in Issue 4.
- **MCP-compatible context retrieval.** ADK agents can pull governed context directly from Knowledge Catalog via MCP — no custom retrieval layer needed for entity grounding.
- **Hybrid semantic + lexical search with ML-based re-ranking,** with access-control-aware retrieval. Agents only see what their identity is authorized to see.
- **BigQuery measures** and the **LookML Agent** (both Preview) embed business logic directly in the SQL engine so calculations are consistent across the enterprise.

The strategic claim made by Google's Data Cloud leadership: Knowledge Catalog supplies the "missing 50% of accuracy" that clean structured data alone cannot provide. Frame this as the substrate that determines whether the customer's AI investments succeed or fail.

### Gemini Enterprise Agent Platform

Formerly Vertex AI. End-to-end environment for the agent lifecycle.

Components most relevant here:

- **Agent Development Kit (ADK)** — code-first multi-agent framework, model-agnostic. You already know this well.
- **Agent Studio** — low-code visual canvas for building agents without code. Useful for the customer's business analysts later.
- **Agent Runtime** — managed runtime supporting long-running agents that maintain state for days (critical for Issue 1's quarterly planning cycle, for example).
- **Memory Bank + Memory Profiles** — per-user long-term memory with low-latency recall. Each planner or basin leader can have a profile.
- **Agent Identity** — every agent gets a verifiable cryptographic ID with an auditable trail. Critical for Issue 3 where the agent is making recommendations that drive logistics spend.
- **Agent Registry** — central library of approved tools, agents, and skills. Prevents AI sprawl.
- **Agent Gateway** — centralized policy enforcement.
- **Model Armor** — runtime security and prompt-injection protection.
- **Agent Simulation, Evaluation, and Observability** — pre-production testing and full execution traces.
- **Model Garden** — 200+ models including Gemini 3.1 Pro, Gemini 3 Flash, Claude Opus/Sonnet/Haiku, Llama, DeepSeek, etc.

### Smart Storage + Object Context API

Now GA in Cloud Storage. Makes every object self-describing the moment it lands.

Capabilities:

- **Automated annotation** — Google's pipelines auto-attach labels, extracted entities, and compliance signals
- **Custom tags** — customer-defined classifications layered on top
- **Object context** — structured, mutable, IAM-governed metadata on every object
- **Integration with Knowledge Catalog** — unstructured data becomes part of the context graph

For this customer, this is the answer to InTouch. Decades of accumulated technical PDFs and equipment specs become agent-queryable as they sit, semantically linked to canonical asset entities.

### Cross-Cloud Lakehouse

Formerly BigLake. Apache Iceberg standardized. Zero-copy access to AWS S3 and Azure Data Lake via Iceberg REST Catalog federation.

Why this matters for oilfield services specifically:

- **SAP often runs on Azure.** Oilfield majors have SAP RISE deployments.
- **Drilling telemetry often lives in AWS** or in OEM-specific cloud silos.
- **Legacy systems are on-prem.** Maximo deployments are frequently still on-prem or hybrid.

If their data lives across clouds, Cross-Cloud Lakehouse is the unlock that lets you build agents on Google Cloud without forcing a migration — a much easier sell than "rip and replace your data platform." Validate where their data actually lives early; this could be your strongest differentiator vs. Microsoft (whose cross-cloud story is weaker).

### Supporting capabilities worth naming

- **Spanner Omni** (Preview) — Spanner engine running cross-cloud, on-prem, or local. Earlier-stage but worth knowing.
- **Lakehouse federation for AlloyDB** (Preview) — zero-ETL synchronization.
- **Lightning Engine for Apache Spark** — 4.5x faster than open-source Spark.
- **Data Agent Kit** — Gemini-powered data science authoring in IDEs, Notebooks, and CLIs. Useful talking point for their data scientists.
- **Deep Research Agent** (Preview) — multi-step reasoning across BigQuery and external systems, powered by Knowledge Catalog. The "ask anything" surface for executives.
- **Inbox in Gemini Enterprise** — central oversight surface for long-running agents and human-in-the-loop workflows.
- **A2A protocol** — open agent-to-agent interoperability standard.
- **TPU 8th generation (Ironwood) + Axion processors** — infrastructure layer. Probably not in your customer story unless they ask.

### Why Google specifically (the competitive frame)

Microsoft will pitch Copilot Studio + Microsoft Fabric + Azure OpenAI. AWS will pitch Bedrock Agents + Amazon Q + Glue. The customer is likely hearing all three.

Your differentiators, in order of strength for this specific account:

1. **Knowledge Catalog has no direct equivalent.** Microsoft Fabric has OneLake and Purview, but the AI-native context-graph framing is Google-specific. AWS Glue catalog is a different product class entirely.
2. **Gemini's multimodal depth.** InTouch contains technical diagrams, schematics, and image-heavy PDFs. Gemini 3.1's native multimodal handling is materially stronger than Claude or GPT for visual technical documents.
3. **Cross-Cloud Lakehouse with Iceberg.** Lets the customer leave existing data in AWS/Azure. Microsoft will require Fabric migration; AWS will require staying on AWS. You don't.
4. **Integrated, vertically optimized stack.** Storage → catalog → models → agents → governance, all co-developed. The "fully integrated AI stack" framing is the platform-sale anchor.
5. **Open model ecosystem.** Claude, Llama, Gemma all available in Model Garden. You can offer optionality without surrendering the platform.

What Microsoft and AWS will counter with:

- **Microsoft:** "Your Office and Excel users already live in Copilot." This is a real argument for Issue 2 specifically. Counter: the workflow problem is Excel itself; staying in Excel doesn't fix the broken feedback loop.
- **AWS:** "Your drilling telemetry is already in S3." Counter: Cross-Cloud Lakehouse means you don't have to migrate; you can keep S3 and still get Gemini.

Be ready to engage with both directly; don't pretend the competition doesn't exist.

---

## Part 3: The Use Case and Its Natural Architecture

### What the customer actually brought us

The customer presented one use case, not four problems. They walked us through how service capacity is forecasted, planned, deployed, and reconciled across their operations — and they pointed to four places where the workflow currently breaks down. Those breakpoints aren't a shopping list waiting for four point solutions. They are the visible symptoms of one operational value chain that is currently stitched together with manual effort and disconnected systems.

For working purposes, call this use case **end-to-end service capacity orchestration** — from demand signal through fleet deployment through gap resolution, grounded on a coherent operational data layer. The customer will have their own internal term; use theirs in the actual deliverable. Whatever it is called, the four pain points are stations along the same flow:

- **Demand sensing and forecasting** — pipeline signals converted into a revenue and capacity outlook. *This is where the workflow breaks today: the ML forecast loses fidelity at the human review boundary, and qualitative regional knowledge never returns to the model.*
- **Demand-to-fleet planning** — translating the forecast into equipment schedules against customer start dates. *This is where the workflow breaks today: planners over-buffer because start dates are volatile and the system can't reason probabilistically, so active fleet capacity is artificially tied up.*
- **Capacity gap response** — when planning fails and a shipment still has to happen. *This is where the workflow breaks today: planners can't see across Maximo, SAP, FDP, and InTouch fast enough to find equivalent assets, so they make panicked, expensive logistics decisions.*
- **Operational data coherence** — the asset taxonomy that all three above depend on. *This is where the workflow breaks today: the same tool has different names across systems, which breaks automation everywhere and forces continuous human translation.*

Read together, this is one value chain with four breakpoints. Not four projects.

### The natural architecture for this use case

Set aside any vendor's product catalog and sketch the system that would actually deliver end-to-end service capacity orchestration. What does it need?

It needs **a grounded, coherent view of the operational data** — equipment status, materials, workforce, customer configurations, unstructured technical documentation — spanning every system the workflow touches. Without this, every agent above it is guessing.

It needs **agents that span the lifecycle of the use case** — one that lives at the demand stage and learns from human reviewers, one that lives at the planning stage and reasons probabilistically about start dates, one that lives at the gap-response stage and traverses every operational system in seconds. These agents share connectors, ground in the same data, and learn from the same operational telemetry as the work moves through them.

It needs **a runtime that handles both fast and slow agents** — sub-second responses when a planner is in the middle of a capacity gap query, multi-week state when a forecast cycle or planning horizon is running in the background.

It needs **governance that scales with the agent count** — cryptographic identity for every agent, a central registry, runtime policy enforcement, full reasoning traces for procurement audit and regulatory defensibility.

It needs **a unified surface for the humans involved** — planners, basin leaders, executives — so the work flows through one environment instead of being stitched together by each user.

This is the natural shape of the use case. It is not a framework being imposed; it is what the work actually requires.

The Google Cloud products map onto this naturally:

- The grounded data foundation is **Knowledge Catalog** as the context graph, **Smart Storage** with **Object Context API** for unstructured enrichment of InTouch and similar content, **BigQuery** as the warehouse, **BigQuery measures** to make canonical terms like "Permian Q3 forecast" mean one thing everywhere, and where data lives outside GCP, **Cross-Cloud Lakehouse** federating it via Iceberg.
- The agents are built on **Gemini Enterprise Agent Platform** — **ADK** for code-first multi-agent work, **Agent Studio** for low-code, both deploying onto **Agent Runtime** which handles short-lived and long-running agents natively.
- The connectors to source systems are **MCP servers** (Maximo, SAP, FDP, InTouch retrieval), and Knowledge Catalog itself exposes governed context retrieval over MCP — so agents pick up grounding without separate retrieval infrastructure.
- The governance and observability stack is **Agent Identity, Agent Registry, Agent Gateway, Model Armor,** and the **Cloud Observability** suite.
- The unified surface is **Gemini Enterprise app** as the front door, **Agent Inbox** as the human-in-the-loop oversight surface, **Deep Research Agent** as the executive "ask anything" surface, and **Connected Sheets** where the cultural artifact of a spreadsheet review needs to be preserved.

Nothing here is bolted on. It is the architecture you would draw on a whiteboard if you were asked to design the system from scratch, and then realize that Google Cloud already ships every component.

### The four breakpoints, dissolved

When the use case runs end-to-end on this architecture, the four pain points are not "solved" as separate engineering projects. They dissolve as natural consequences of having a coherent system.

The forecast review breakpoint dissolves because the review now happens in the same environment where the forecast was generated, with override rationale captured as structured data and fed back into the model — instead of dying in a detached Excel file.

The over-buffering breakpoint dissolves because the planning agent reasons about start-date probability distributions rather than point estimates, and surfaces risk-calibrated buffers instead of static worst-case padding.

The capacity gap breakpoint dissolves because when a planner asks "where's a Tool X variant near Luanda by Friday?" the agent traverses Maximo, SAP, FDP, and the technical documentation in one query, grounded in the canonical asset taxonomy — and surfaces the sub-variant in the repair shop 50 km away before anyone reaches for the cargo charter.

The naming-convention breakpoint dissolves because Knowledge Catalog continuously resolves entities across source systems, so agents work against canonical entities and never see the underlying taxonomic chaos.

Each breakpoint is a symptom of the disconnected value chain. Reconnect the chain and the symptoms disappear.

### Why this framing matters in the room

The instinct in pre-sales is to enumerate: "you have pain point A, our product addresses it; pain point B, addressed; pain point C, addressed." That framing concedes the customer's working assumption that their pain points are independent items, and turns the conversation into a feature comparison.

The better posture is to give the customer's use case its proper name, sketch the architecture that actually delivers it, and let the four pain points be explained as natural consequences of getting the architecture right. The customer ends up agreeing on the use case shape and the architecture, and the four-pain-points list becomes a sanity check rather than a checklist.

This also reframes the competitive conversation. Microsoft and AWS will both pitch components — a forecasting service, an agent runtime, a data catalog, a workflow tool. The customer will assemble those components themselves. Google Cloud is the only vendor whose stack is already shaped like this use case, end-to-end, co-developed.

### What this means for the engagement

Concretely:

The POV doc opens with the use case as the customer described it, not with the four issues as a parallel list. The four pain points appear in the doc, but as breakpoints in one value chain.

The Gate 2 demo presents the cargo-plane scenario as one moment in an end-to-end flow — not as "the demo for Issue 3." The forecast review surface, the Capacity Planning Agent, and the entity-resolution view show up as adjacent moments in the same flow, each running in the same Gemini Enterprise app, each grounded in the same Knowledge Catalog, each governed by the same Agent Identity and Registry. The customer sees one system that delivers the use case, not four demos stitched together.

The Gate 3 paid POC is the first agent of this use case taken to production-grade — most likely the gap-response agent, because that's where the visible savings land first. But it is sold as Phase 1 of delivering the use case, not as a standalone deliverable. Phase 2 extends the same architecture to the next breakpoint. Phase 3 to the next. The economics of doing this end-to-end on one platform are the supporting argument, not the headline.

### A note on build economics (supporting argument, not the headline)

When the customer's CFO asks how this scales — and they will — the answer is that delivering the use case end-to-end on one architecture is structurally cheaper than the alternative. The data foundation, governance stack, runtime, and user surfaces are built once. Each successive agent (gap-response → forecast review → Capacity Planning Agent → adjacent use cases the customer brings later) reuses most of what came before.

Concretely: the first agent carries most of the platform cost. The second agent costs perhaps a quarter as much. By the fourth or fifth, citizen developers are building agents in Agent Designer with no central engineering involvement. This is not the lead argument with the customer — but it is the closing argument with their CFO.

---

## Part 4: Strategic Approach

### The meta-question

In pre-sales for a platform sale, the deliverable isn't a working agent. It's a customer committed to Gemini Enterprise + Agent Platform as their AI foundation. The four issues are vehicles.

The strategic question for any decision you face: *does this make the platform commitment more likely?*

If yes, do it. If no, don't, no matter how technically interesting.

### Five approach options (full taxonomy)

For completeness, here are all five approaches considered before narrowing:

**Approach 1 — Art-of-the-possible demo (synthetic data).** Thin slice across all 4 issues with fabricated data. 4-6 weeks. Best for vision sale. Risk: customer reads it as consultantware.

**Approach 2 — Single-issue lighthouse (real data, narrow).** One issue, deep, real data. 3-4 months. Best for technical de-risking. Risk: customer wanted the cargo-plane demo, got a forecast reviewer.

**Approach 3 — Data foundation first (Knowledge Catalog as Phase 1).** Knowledge Catalog + Smart Storage deployed before any agents. Best for customers with severe data quality issues. Risk: "data project" framing loses executive interest.

**Approach 4 — Hybrid (mockup horizontal + real vertical).** Mockup across all 4 issues plus deep real build on one. 4-6 months. Best for sophisticated buyers. Resource-intensive.

**Approach 5 — Workshop-led discovery.** 4-8 weeks of structured workshops, deliverable is plan not demo. Best for plan-oriented buyers. Risk: ghosting after workshops.

### Why Approach 4 (Hybrid) wins for this engagement

Given your pre-sales context — lead CE, platform sale, competitive deal, multiple downstream use cases — Approach 4 is the right play, structured as a 3-gate funnel:

- **Gate 1:** Earn the right to discover (POV doc)
- **Gate 2:** Earn the right to demo (working demo of Issue 3 + mockups of the other three)
- **Gate 3:** Convert to paid POC (real data, one issue, time-bounded, customer-funded)

The hybrid logic: the mockup shows platform vision (Gemini Enterprise feels real even where agents aren't), the deep real build on Issue 3 shows credibility, and both feed naturally into a Gate 3 paid engagement.

### Why Issue 3 is the spear tip (not Issue 2)

In delivery: Issue 2 is safer (fewer systems, no write access to ERPs, cleaner data). In pre-sales: Issue 3 every time. Reasons:

1. **The cargo-plane story is unforgettable.** Executives retell it. It survives between meetings.
2. **Showcases Google's differentiators.** Multi-system orchestration (ADK), multimodal reasoning over InTouch (Gemini), entity resolution (Knowledge Catalog). Microsoft and AWS cannot tell this story credibly.
3. **Hits a CFO nerve.** Chartering planes, panicked logistics, missed CapEx optimization. Translates to dollars.
4. **Justifies the platform pitch.** Solving Issue 3 requires governed agents across 4+ systems. That IS the platform.

Issue 2 is your Gate 3 (paid POC) candidate — lower risk to actually ship, more measurable.

---

## Part 5: Pre-Sales Playbook (3-Gate Funnel)

### Gate 1 — Earn the right to discover (2-3 weeks)

**Output:** Point-of-View document, ~5-7 pages. "Here's how Google would solve this." Based on what they've already told you, no new discovery yet. Maps each of the 4 issues to specific Google Cloud components and Knowledge Catalog. Ends with "here's what we'd validate together in a 4-week discovery sprint."

**Your customer ask at this gate:** 2-3 SME interviews + an identified executive sponsor + access to anonymized sample data.

**Why this works:** Low cost to you, high signal from them. The POV doc is currency — it gives the champion something to circulate internally. If they won't give you SME time after reading it, you know the deal isn't real yet.

**Internal Google asks:**
- Specialist hours from the AI/ML team (probably 0.25 FTE for the POV writeup)
- Industry vertical specialist (oilfield services) if available
- Account team alignment on the platform pitch

### Gate 2 — Earn the right to demo (3-4 weeks)

**Output:** Discovery readout + working demo of Issue 3 end-to-end on synthetic-but-realistic data, built inside Gemini Enterprise app using ADK with Knowledge Catalog providing grounding. The other 3 issues appear as mockup tiles in the same Gemini Enterprise app — the customer feels the platform vision.

**Demo principles:**
- Every screen says "Gemini Enterprise"
- Every architecture slide names Agent Platform components by their post-Next '26 names
- The cargo-plane scenario plays out in 4-6 minutes
- The reasoning trace is visible — make the agent's logic legible
- Knowledge Catalog grounding is shown explicitly ("the agent knows Tool-X-Variant-A and Tool-X-V-A are the same because of the canonical entity in Knowledge Catalog")

**Your customer ask at this gate:** Anonymized sample data sufficient to make the demo recognizable + 2-3 days of SME workshop time + introduction to executive sponsor + a follow-up readout meeting scheduled.

**Internal Google asks:**
- Demo engineering: ~0.75 FTE for 4 weeks (could be a Google specialist or a partner)
- A data engineer for synthetic data generation
- Industry specialist to attend the readout
- Possibly Google PSO scoping conversation

### Gate 3 — Convert to paid POC (4-6 weeks of work, then revenue)

**Output:** Proposal for a time-bounded, paid POC on real data — likely Issue 2 (safer) or Issue 3 (more impactful, riskier). Defined success criteria. Dedicated customer technical counterpart. Paid by customer.

**POC scope principles:**
- One issue, narrow scope
- Real data, one or two source systems only
- 12-week duration
- Success criteria are measurable AND tied to platform commitment (e.g., "ready to extend to 2 additional use cases")
- Deployed on Gemini Enterprise Agent Platform with Knowledge Catalog grounding — the platform commitment is structural to the POC

**Your customer ask:** Signed SOW, executive sponsor named in the SOW, technical counterpart assigned, success criteria signed off.

**Internal Google asks:**
- PSO engagement scoped and approved
- Possibly partner involvement (Accenture / Deloitte / Capgemini) for delivery muscle
- Account team alignment on follow-on platform deal

### What to ship this week, this month, this quarter

**This week:**
- Validate the executive sponsor exists. Name them. If unclear, this is your first job, not building anything.
- Sketch the POV doc outline (don't write it yet)
- Decide on the customer asks at each gate and write them down
- Confirm competitive landscape — is Microsoft / AWS in the room?

**This month (next 3-4 weeks):**
- Ship the POV doc (Gate 1 output)
- Get 2-3 SME interviews scheduled
- Confirm executive sponsor relationship
- Pull in Google AI/ML specialist + data engineer for demo build prep
- Validate where customer's data lives (GCP / AWS / Azure / on-prem)

**This quarter:**
- Land Gate 2 (working demo of Issue 3)
- Convert to Gate 3 (signed paid POC)
- By end of quarter: customer has committed budget for an agentic POC built on Gemini Enterprise Agent Platform

---

## Part 6: Working Materials

### POV document outline (Gate 1 deliverable)

**Suggested structure, ~5-7 pages:**

1. **Executive summary** (0.5 page) — the strategic frame: these four issues are symptoms of a coordination cost problem; the cure is a governed agent fabric on a unified context platform.
2. **Issue-by-issue interpretation** (2 pages) — your reading of each issue, what it really means, and the value at stake.
3. **The Google Cloud solution architecture** (1.5 pages) — Knowledge Catalog as substrate, Gemini Enterprise Agent Platform as build layer, Gemini Enterprise app as front door. Reference diagram.
4. **Why Google specifically** (1 page) — Knowledge Catalog differentiation, multimodal depth, Cross-Cloud Lakehouse, integrated stack, open model ecosystem.
5. **Proposed engagement roadmap** (1 page) — the 3-gate funnel framed as "here's how we'd partner to validate this."
6. **What we'd want to validate together** (0.5 page) — the discovery questions. This is your ask.

Keep diagrams simple. Use Google Cloud product names consistently. Don't oversell — pre-sales credibility is earned through restraint.

### Discovery interview guide (Gate 1 → Gate 2)

**Goals of discovery:** Validate the decision logic, confirm data realities, identify champion + sponsor, surface hidden constraints, find the highest-impact narrow slice for the demo.

**For OCC planners (the people who actually live Issue 3):**

- Walk me through the last time you had a capacity gap. What systems did you query? In what order?
- Show me a time when a "functionally equivalent" sub-variant would have saved you a chartered shipment. How did you find out about it (or not)?
- How do you know what counts as "equivalent"? Where does that knowledge live?
- What would you trust an AI recommendation for? What would you not?
- Who do you escalate to when the data systems disagree?

**For basin/geography leaders (Issue 2):**

- When you override the ML forecast, what are you using that the model doesn't see?
- How often is the override quantitative vs. qualitative?
- What format would you trust as much as Excel?
- Have you ever wanted to see why a previous override was made?
- Who else needs to see your overrides?

**For schedulers (Issue 1):**

- How did you arrive at your current buffer logic? Is it the same across regions?
- When start dates slip, what's the cascade impact?
- What's the cost of a late shipment vs. an idle asset?
- How often do you wish you had a probability range instead of a date?

**For data architects (Issue 4):**

- How many systems hold a record of "this tool"? What are they?
- Who currently owns the translation between system X and system Y?
- Has anyone attempted a master data project? What happened?
- What's the political dynamic between sales pipeline taxonomy and procurement taxonomy?

**For the executive sponsor:**

- What does "winning" look like 12 months from now?
- What other use cases are in your portfolio? (This is the platform-sale opening.)
- What's your existing GCP / Azure / AWS footprint?
- Who else is pitching this to you?
- What's your appetite for org change? (Issue 2 specifically.)
- What's your timeline forcing function?

### Demo storyboard for Issue 3 (Gate 2 deliverable)

**Demo length:** 5-7 minutes for the agent demo + 3-5 minutes for the platform tour = 10-12 minutes total. Memorize, don't read.

**Scene 1 (60 seconds): Setup**
- A simulated OCC dashboard showing a capacity gap for Tool X in West Africa
- A planner sits down at the Gemini Enterprise app
- Establishes the stakes: "Without this agent, the next step is a $400K cargo charter"

**Scene 2 (90 seconds): The query**
- Planner types: "I need a Tool X variant on site in Luanda by Friday. What are my options?"
- Agent acknowledges the query and begins decomposition (visible in trace)
- Sub-agents called in parallel: Maximo, SAP, FDP, InTouch retrieval

**Scene 3 (90 seconds): The reasoning**
- Maximo: no Tool X available in region
- SAP: no workforce blocker
- Knowledge Catalog surfaces functionally equivalent sub-variant
- Maximo on sub-variant: one in repair shop 50 km away
- FDP confirms customer configuration compatibility
- InTouch technical doc retrieval (via Smart Storage) confirms the engineering equivalence

**Scene 4 (60 seconds): The recommendation**
- Agent surfaces: "Recommend sourcing Tool X-V7 from Lagos repair shop. Estimated savings: $380K. Full reasoning attached."
- Planner can drill into the reasoning trace
- Approval action triggers the next step (SAP work order, dispatch notification)

**Scene 5 (60 seconds): The platform breadcrumbs**
- Show Agent Inbox: this is one of many agents the planner uses
- Show the (mockup) tiles for Issues 1, 2, 4 — "we'd build these next"
- Show Agent Registry: governance is built in
- Show the Knowledge Catalog view: every term the agent used is grounded in the canonical entity

**Scene 6 (60 seconds): The wrap**
- Single-screen summary: what this agent did, what it required to build, what the next 3 agents would look like
- Transition to architecture discussion

### Value framing / ROI math

Translate each issue into a CFO-legible number. Don't claim precision; claim defensibility.

**Issue 1 — Fleet utilization uplift**
- Current: <40% on-time → significant idle capacity
- Hypothetical uplift: even a 10% improvement in active fleet utilization translates to deferred or avoided CapEx for replacement tools
- Math: (replacement tool unit cost × tools deferred × replacement frequency) / year
- For an oilfield services major, this is realistically $10M-$50M/year of avoided CapEx
- Plus opportunity revenue from improved availability

**Issue 2 — Forecast accuracy improvement**
- Current state: model produces output; humans override significantly with no learning loop
- Improved state: smaller overrides over time, faster review cycle, qualitative context preserved
- Hard number: forecast variance reduction → working capital improvement (inventory, workforce planning)
- Softer number: time saved in review cycles (X regional leaders × Y hours/quarter × loaded rate)
- For a global oilfield services major: $5M-$20M/year in working capital + soft costs

**Issue 3 — Logistics cost avoidance**
- Single avoided cargo charter: $200K-$500K per event
- Frequency: even if this scenario plays out 10-20 times per year, that's $2M-$10M
- Plus reduced excess inventory carrying cost (less need to over-position assets)
- For a global services major: realistically $20M-$100M annualized

**Issue 4 — Foundational, hard to ROI directly**
- Frame as the enabler of the above three
- Indirect math: every downstream automation initiative blocked by data quality
- Or: human translation hours saved × loaded rate × number of systems

**Total order of magnitude:** $40M-$180M/year of identified value across the four issues, depending on customer size and scope. This justifies the platform investment.

Caveat: these are rough envelopes. Refine with the customer's actual numbers in Gate 2 discovery. But have envelopes ready for Gate 1.

### Stakeholder map (typical for oilfield services majors)

You will need to engage these archetypes. Names will vary, roles are consistent:

- **Executive sponsor** — typically Chief Digital Officer, SVP/VP of Digital Transformation, or VP of Supply Chain. The signer.
- **Technical champion** — often a Head of AI/ML, Head of Data Platform, or Chief Architect. Your day-to-day relationship.
- **Domain SMEs** — OCC head, basin leaders, fleet planners. The people whose work changes.
- **Procurement / IT sourcing** — gates the contract. Engage early, not late.
- **Security / compliance** — gates the data access. Engage in Gate 2.
- **Existing vendor relationships** — Microsoft, AWS, SAP. They may be in the room or actively pitching against you.
- **System integrator partners** — Accenture, Deloitte, Capgemini, IBM. May already have a relationship with the customer; could be your delivery partner in Gate 3.

Map the names against these roles in Gate 1. If you can't fill in the executive sponsor and champion boxes, you're not ready to commit to Gate 2.

---

## Part 7: Risks, Assumptions, and Open Questions

### Key assumptions to validate (in priority order)

1. **Executive sponsor exists and is committed.** Name them. If unclear, validate before doing anything else.
2. **This is a competitive deal.** Assume yes until proven otherwise. Adjust narrative accordingly.
3. **The customer has meaningful existing GCP footprint.** Determines whether your story is "expansion" or "displacement."
4. **Data lives across multiple clouds.** Likely for an oilfield services major. Determines whether Cross-Cloud Lakehouse is a Gate 1 talking point.
5. **The customer's procurement timeline is realistic.** Oilfield services often have annual budget cycles; if you're outside the cycle, time-to-commitment is longer.
6. **You have ~0.5 FTE of specialist support available for the demo build.** If less, demo must be simpler.
7. **The customer's portfolio of use cases is real and known to your champion.** If yes, your Gate 3 framing leans hard on portfolio.
8. **The customer's data quality is actually as bad as Issue 4 implies.** If yes, Knowledge Catalog is essential; if not, you have more architectural flexibility.
9. **Microsoft, AWS, or both are also pitching this customer.** Almost certainly true.
10. **The champion has organizational authority to push for change.** Issue 2 specifically requires org change appetite.

### Pre-sales failure modes (and how to avoid them)

**Pilot purgatory** — endless POCs that never commit to platform. *Mitigation:* structure each gate with a customer ask that costs them something; if they won't pay it, the deal isn't real.

**Death by discovery** — months of workshops, no demo. *Mitigation:* lead with the POV doc, not workshops; demo by Gate 2.

**Champion attrition** — your internal champion gets reorged or leaves. *Mitigation:* always have a second champion in the relationship; identify the executive sponsor early.

**POC scope drift** — they want all 4 issues in the POC. *Mitigation:* the POC contract specifies one issue; the other three become Phase 2 conversations.

**Platform commitment delay** — they buy the POC but defer the platform decision. *Mitigation:* structure the POC success criteria to include platform readiness; bring the platform conversation to every readout.

**Competitive entry mid-scope** — Microsoft or AWS enters with a cheaper alternative just as you're closing. *Mitigation:* establish the differentiators (Knowledge Catalog, Cross-Cloud) early so the comparison isn't just "AI agents."

**"Buy the demo, build the rest"** — customer likes the demo but wants to build internally with open-source. *Mitigation:* emphasize the governance stack (Agent Identity, Registry, Gateway) and operational maturity that's hard to replicate.

**Tech-only conversation** — you stay in technical layer and never get to the value layer. *Mitigation:* the ROI envelopes are your bridge; bring them to every readout.

### Competitive considerations

**Microsoft Copilot Studio + Fabric + Azure OpenAI**
- Their strongest point: existing Office/Excel adoption
- Their weakest point: cross-cloud, multimodal depth, governance for agents
- Counter-narrative: agents that live in Excel are still agents that live in Excel

**AWS Bedrock Agents + Q + Glue**
- Their strongest point: existing AWS data footprint
- Their weakest point: integrated stack, multimodal, context graph maturity
- Counter-narrative: Cross-Cloud Lakehouse means you don't have to choose

**Customer's existing SI partner (Accenture / Deloitte / etc.)**
- Likely to be in the room
- Can be ally (delivery partner) or threat (steering toward another platform)
- Engage early; let them know there's revenue for them in a Google Cloud delivery

### Open questions you need to answer

In rough priority order, for the next 1-2 weeks:

1. Who is the executive sponsor?
2. What is the customer's existing GCP footprint?
3. Where does the customer's data actually live?
4. Who else is pitching this account?
5. What is the customer's portfolio of agentic use cases beyond these four?
6. What is the budget cycle reality?
7. What is the org change appetite (specifically for Issue 2)?
8. Who is the technical champion?
9. Are there existing SI relationships?
10. What is the timeline forcing function (next exec readout, RFP date, budget cut-off)?

---

## Part 8: Internal Motion

### Who to pull in from Google

**For Gate 1 (POV doc):**
- You (lead CE) — owns the doc
- Account Executive — owns customer relationship and platform deal close
- Industry vertical specialist (oil & gas) — for credibility and references

**For Gate 2 (demo):**
- All of the above, plus:
- AI/ML specialist (full-time for ~4 weeks)
- Data engineer (synthetic data generation)
- ADK / Agent Platform specialist
- Knowledge Catalog specialist if available

**For Gate 3 (paid POC):**
- All of the above, plus:
- Google PSO (Professional Services) for scoping
- Partner architect if SI is involved
- Customer Success Manager for post-POC platform expansion

### Partner ecosystem

For oilfield services, consider:

- **Accenture** — strong Google Cloud Business Group, strong oil & gas practice
- **Deloitte** — your former employer; strong AI practice; oil & gas vertical
- **Capgemini** — strong engineering services, multi-industry
- **Wipro / Infosys / TCS** — common in oilfield services delivery, cost-effective

Engage partner early in Gate 2 — they can co-pitch and provide implementation muscle for Gate 3. Don't surprise them at Gate 3.

### Customer references to cite (from Next '26 announcements)

Cite carefully — these are public-domain announcements:

- **Bloomberg Media** — uses Knowledge Catalog for Data Access AI Agent
- **Geotab** — uses Agent Platform / ADK for AI Center of Excellence
- **Comcast** — uses Agent Runtime for customer service multi-agent architecture
- **Burns & McDonnell** — uses Agent Platform for organizational knowledge management (engineering-adjacent, useful reference)
- **Spotify** — uses Lakehouse for Iceberg-based modern data architecture
- **American Express** — moving core data warehouse to BigQuery for agentic commerce
- **Virgin Voyages** — 1,000+ agents, mass rebooking reduced from 6 hours to 11 minutes
- **Vodafone** — hundreds of agents saving millions of euros/year
- **Deutsche Telekom** — MINDR multi-agent network operations

Pick 2-3 most relevant to your customer's industry and use case for the POV doc.

---

## Appendix A: Quick reference — Google Cloud products mentioned

**Renamed at Next '26:**
- Vertex AI → **Gemini Enterprise Agent Platform**
- Dataplex Universal Catalog → **Knowledge Catalog**
- BigLake → **Google Cloud Lakehouse**
- Dataproc (managed) → **Managed Service for Apache Spark**

**Core platform components:**
- **Agent Development Kit (ADK)** — code-first framework
- **Agent Studio** — low-code visual canvas
- **Agent Garden** — pre-built agents
- **Model Garden** — 200+ models
- **Agent Runtime** — managed agent hosting
- **Memory Bank + Memory Profiles** — per-user long-term memory
- **Agent Identity** — cryptographic agent identities
- **Agent Registry** — central agent/tool library
- **Agent Gateway** — runtime policy enforcement
- **Model Armor** — runtime security
- **Agent Simulation / Evaluation / Observability** — quality assurance

**Data layer:**
- **Knowledge Catalog** — context graph
- **Smart Storage + Object Context API** — auto-tagged Cloud Storage
- **Cross-Cloud Lakehouse** — Iceberg federation across AWS / Azure
- **BigQuery measures** — embedded business logic
- **LookML Agent** — automated business logic
- **Lakehouse federation for AlloyDB** — zero-ETL
- **Lightning Engine for Spark** — accelerated compute
- **Spanner Omni** — Spanner anywhere

**End-user surfaces:**
- **Gemini Enterprise app** — the front door for employees
- **Agent Designer** — no-code agent building
- **Inbox** — long-running agent oversight
- **Deep Research Agent** — executive research surface
- **Data Agent Kit** — Gemini for data science authoring

---

## Appendix B: Which product solves what (cross-reference)

| Customer pain | Primary Google Cloud answer | Supporting components |
|---|---|---|
| Misaligned naming (Issue 4) | Knowledge Catalog | Smart Storage, Object Context API, BigQuery measures |
| Unstructured technical docs (InTouch, in Issue 3) | Smart Storage + Object Context API | Knowledge Catalog integration, Gemini multimodal |
| Multi-system reasoning (Issue 3) | ADK orchestration on Agent Runtime | Agent Identity, Gateway, Memory Bank, MCP servers per source |
| ERP system data access (Issue 3) | Knowledge Catalog connectors (SAP Preview) + MCP servers | Cross-Cloud Lakehouse if data is in Azure/AWS |
| Probabilistic forecasting (Issue 1) | Vertex AI Forecasting / BigQuery ML | ADK Capacity Planning Agent, Memory Bank |
| Scheduling optimization (Issue 1) | Vertex AI Optimization or CP-SAT in Cloud Run | Agent Runtime for long-running agents |
| Broken human review loop (Issue 2) | Gemini Enterprise app + Connected Sheets | Forecast Review Agent, BigQuery as truth |
| Forecast logic consistency (Issue 2) | BigQuery measures | LookML Agent |
| Executive "ask anything" surface | Deep Research Agent | Knowledge Catalog grounding |
| Agent governance and audit | Agent Identity + Registry + Gateway + Model Armor | Cloud Observability for traces |
| Cross-cloud data access | Cross-Cloud Lakehouse (Iceberg) | Spanner Omni if low-latency operational |
| Data scientist productivity | Data Agent Kit | Notebooks, Lightning Engine for Spark |

---

## Closing: The one thing to remember

When in doubt about any decision in this engagement, return to the strategic question:

**Does this make the platform commitment more likely?**

Not "is this technically correct?" Not "is this thorough?" Not "does this answer the customer's question?"

The four issues are the vehicle. The platform is the destination. Drive accordingly.

---

*End of brief.*
